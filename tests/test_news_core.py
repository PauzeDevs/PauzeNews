import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from news_core import ArticleStore, FEEDS, article_sort_key, fetch_category, parse_feed, published_timestamp


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Headline One</title><link>https://example.com/one</link>
<description><![CDATA[<p>A <b>short</b> summary &amp; update.</p>]]></description>
<pubDate>Fri, 16 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Headline One duplicate</title><link>https://example.com/one</link></item>
<item><title>Unsafe link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <entry>
    <title>Atom headline</title>
    <link href="https://example.com/atom" rel="alternate" />
    <summary>Atom summary</summary>
    <updated>2026-10-16T10:00:00Z</updated>
  </entry>
</feed>"""


class FeedParsingTests(unittest.TestCase):
    def test_parser_normalizes_and_filters_entries(self):
        items = parse_feed(RSS, "World", "Test Publisher")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Headline One")
        self.assertEqual(items[0]["source"], "Test Publisher")
        self.assertEqual(items[0]["url"], "https://example.com/one")
        self.assertEqual(items[0]["summary"], "A short summary & update.")
        self.assertGreater(items[0]["published_at"], 0)

    def test_publication_timestamp_supports_rss_and_iso_dates(self):
        self.assertEqual(
            published_timestamp("Fri, 16 Oct 2026 10:00:00 GMT"),
            published_timestamp("2026-10-16T10:00:00Z"),
        )
        self.assertEqual(published_timestamp("not a date"), 0)

    def test_articles_sort_by_publication_time_not_fetch_order(self):
        older = {"published": "2026-10-15T10:00:00Z", "published_at": 0, "fetched_at": 999}
        newer = {"published": "2026-10-16T10:00:00Z", "published_at": 0, "fetched_at": 1}
        self.assertGreater(article_sort_key(newer), article_sort_key(older))

    def test_parser_supports_atom_feeds(self):
        items = parse_feed(ATOM, "Technology", "Atom Publisher")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Atom headline")
        self.assertEqual(items[0]["url"], "https://example.com/atom")
        self.assertEqual(items[0]["summary"], "Atom summary")
        self.assertEqual(items[0]["published"], "2026-10-16T10:00:00Z")
        self.assertGreater(items[0]["published_at"], 0)

    def test_parser_uses_publisher_from_news_rss_source_element(self):
        content = b"""<rss version="2.0"><channel><item>
        <title>Headline from publisher</title>
        <link>https://example.com/publisher-story</link>
        <source url="https://example.com">Example Publisher</source>
        <description>Test summary</description>
        </item></channel></rss>"""
        items = parse_feed(content, "World", "Google News")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "Example Publisher")

    def test_parser_rejects_oversized_and_dtd_xml(self):
        self.assertEqual(parse_feed(b"x" * (2 * 1024 * 1024 + 1), "World", "Test"), [])
        dtd = b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel/></rss>'
        self.assertEqual(parse_feed(dtd, "World", "Test"), [])

    def test_parser_rejects_dtd_and_entity_declarations(self):
        dtd = b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel/></rss>'
        spaced = b'<! DOCTYPE rss><rss><channel/></rss>'
        self.assertEqual(parse_feed(dtd, "World", "Test"), [])
        self.assertEqual(parse_feed(spaced, "World", "Test"), [])

    def test_parser_rejects_oversized_input(self):
        self.assertEqual(parse_feed(b"x" * (2 * 1024 * 1024 + 1), "World", "Test"), [])

    def test_parser_returns_empty_for_malformed_xml(self):
        self.assertEqual(parse_feed(b"<rss><channel><item>", "World", "Broken"), [])

    def test_store_migrates_legacy_schema_and_backfills_publication_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("""
                    CREATE TABLE articles (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
                        summary TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
                        category TEXT NOT NULL DEFAULT '', published TEXT NOT NULL DEFAULT '',
                        fetched_at INTEGER NOT NULL DEFAULT 0
                    )
                """)
                db.execute("""
                    INSERT INTO articles
                    (id, title, url, summary, source, category, published, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ("legacy", "Old headline", "https://example.com/legacy", "", "Test",
                      "World", "Fri, 16 Oct 2026 10:00:00 GMT", 1))
            store = ArticleStore(path)
            row = store.list_articles()[0]
            self.assertGreater(row["published_at"], 0)
            self.assertEqual(row["id"], "legacy")
            self.assertEqual(len(store.list_articles(category="World")), 1)

    def test_store_and_bookmark(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "test.sqlite3")
            items = parse_feed(RSS, "World", "Test Publisher")
            store.save_articles(items)
            self.assertEqual(len(store.list_articles()), 1)
            self.assertIn("published_at", store.list_articles()[0])
            article_id = items[0]["id"]
            self.assertTrue(store.toggle_bookmark(article_id))
            self.assertTrue(store.is_bookmarked(article_id))
            self.assertEqual(len(store.list_articles(bookmarks_only=True)), 1)
            self.assertFalse(store.toggle_bookmark(article_id))
            self.assertFalse(store.is_bookmarked(article_id))

    def test_saved_articles_are_ordered_by_bookmark_time(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "saved.sqlite3")
            first = parse_feed(RSS, "World", "Test Publisher")[0]
            second = dict(first)
            second.update(id="second-article", url="https://example.com/second", title="Second headline")
            store.save_articles([first, second])
            store.toggle_bookmark(first["id"])
            store.toggle_bookmark(second["id"])
            with sqlite3.connect(store.db_path) as db:
                db.execute("UPDATE bookmarks SET saved_at = 100 WHERE article_id = ?", (first["id"],))
                db.execute("UPDATE bookmarks SET saved_at = 200 WHERE article_id = ?", (second["id"],))
            saved = store.list_articles(bookmarks_only=True)
            self.assertEqual([row["id"] for row in saved], ["second-article", first["id"]])

    def test_article_can_belong_to_multiple_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "categories.sqlite3")
            article = parse_feed(RSS, "World", "Test Publisher")[0]
            article["categories"] = ["World", "Technology"]
            store.save_articles([article])
            self.assertEqual(len(store.list_articles(category="World")), 1)
            self.assertEqual(len(store.list_articles(category="Technology")), 1)

    def test_oversized_feed_is_rejected(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [b"x" * (2 * 1024 * 1024), b"x"]
        session = Mock()
        session.get.return_value = response
        articles, errors = fetch_category("World", session=session)
        self.assertEqual(articles, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("ValueError", errors[0])
        response.close.assert_called_once()

    def test_search_treats_like_wildcards_as_literal_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "search.sqlite3")
            percent = parse_feed(RSS, "World", "Test Publisher")[0]
            percent.update(id="percent", url="https://example.com/percent", title="100% accurate")
            underscore = dict(percent, id="underscore", url="https://example.com/underscore", title="one_two")
            ordinary = dict(percent, id="ordinary", url="https://example.com/ordinary", title="100 percent accurate")
            store.save_articles([percent, underscore, ordinary])
            self.assertEqual([x["id"] for x in store.list_articles(query="%")], ["percent"])
            self.assertEqual([x["id"] for x in store.list_articles(query="_")], ["underscore"])

    def test_cache_retention_preserves_bookmarks(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "retention.sqlite3")
            saved = parse_feed(RSS, "World", "Test Publisher")[0]
            old = dict(saved, id="old", url="https://example.com/old", title="Old story")
            store.save_articles([saved, old])
            store.toggle_bookmark(old["id"])
            cutoff = int(__import__("time").time()) - 31 * 24 * 60 * 60
            with sqlite3.connect(store.db_path) as db:
                db.execute("UPDATE articles SET fetched_at = ? WHERE id = ?", (cutoff, saved["id"]))
                db.execute("UPDATE articles SET fetched_at = ? WHERE id = ?", (cutoff, old["id"]))
            store.save_articles([])
            ids = {x["id"] for x in store.list_articles()}
            self.assertNotIn(saved["id"], ids)
            self.assertIn(old["id"], ids)
            self.assertEqual(len(store.list_articles(bookmarks_only=True)), 1)

    def test_unknown_category_returns_error_without_network(self):
        session = Mock()
        articles, errors = fetch_category("Made Up Category", session=session)
        self.assertEqual(articles, [])
        self.assertTrue(errors)
        session.get.assert_not_called()

    def test_fetch_category_sends_timeout_and_user_agent(self):
        response = Mock()
        response.iter_content.return_value = [RSS]
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        articles, errors = fetch_category("World", session=session)

        self.assertFalse(errors)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["category"], "World")
        response.close.assert_called_once()
        session.get.assert_called_once_with(
            FEEDS["World"][0][1],
            timeout=12,
            headers={"User-Agent": "PauzeNews/0.1 (+RSS reader)"},
            stream=True,
        )

    def test_one_failed_source_does_not_discard_other_sources(self):
        good = Mock()
        good.iter_content.return_value = [RSS]
        good.raise_for_status.return_value = None
        bad = Mock()
        bad.raise_for_status.side_effect = RuntimeError("feed unavailable")
        session = Mock()
        session.get.side_effect = [bad, good]

        articles, errors = fetch_category("Science", session=session)

        self.assertEqual(len(FEEDS["Science"]), 2)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], FEEDS["Science"][1][0])
        self.assertEqual(len(errors), 1)
        self.assertIn("RuntimeError", errors[0])


if __name__ == "__main__":
    unittest.main()
