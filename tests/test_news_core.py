import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from news_core import ArticleStore, FEEDS, fetch_category, parse_feed


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

    def test_parser_supports_atom_feeds(self):
        items = parse_feed(ATOM, "Technology", "Atom Publisher")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Atom headline")
        self.assertEqual(items[0]["url"], "https://example.com/atom")
        self.assertEqual(items[0]["summary"], "Atom summary")
        self.assertEqual(items[0]["published"], "2026-10-16T10:00:00Z")

    def test_parser_returns_empty_for_malformed_xml(self):
        self.assertEqual(parse_feed(b"<rss><channel><item>", "World", "Broken"), [])

    def test_store_and_bookmark(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArticleStore(Path(directory) / "test.sqlite3")
            items = parse_feed(RSS, "World", "Test Publisher")
            store.save_articles(items)
            self.assertEqual(len(store.list_articles()), 1)
            article_id = items[0]["id"]
            self.assertTrue(store.toggle_bookmark(article_id))
            self.assertTrue(store.is_bookmarked(article_id))
            self.assertEqual(len(store.list_articles(bookmarks_only=True)), 1)
            self.assertFalse(store.toggle_bookmark(article_id))
            self.assertFalse(store.is_bookmarked(article_id))

    def test_unknown_category_returns_error_without_network(self):
        session = Mock()
        articles, errors = fetch_category("Made Up Category", session=session)
        self.assertEqual(articles, [])
        self.assertTrue(errors)
        session.get.assert_not_called()

    def test_fetch_category_sends_timeout_and_user_agent(self):
        response = Mock()
        response.content = RSS
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        articles, errors = fetch_category("World", session=session)

        self.assertFalse(errors)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["category"], "World")
        session.get.assert_called_once_with(
            FEEDS["World"][0][1],
            timeout=12,
            headers={"User-Agent": "PauzeNews/0.1 (+RSS reader)"},
        )

    def test_one_failed_source_does_not_discard_other_sources(self):
        good = Mock()
        good.content = RSS
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
