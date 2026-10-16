import tempfile
import unittest
from pathlib import Path

from news_core import ArticleStore, parse_feed


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Headline One</title><link>https://example.com/one</link>
<description><![CDATA[<p>A <b>short</b> summary &amp; update.</p>]]></description>
<pubDate>Fri, 16 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Headline One duplicate</title><link>https://example.com/one</link></item>
<item><title>Unsafe link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""


class FeedParsingTests(unittest.TestCase):
    def test_parser_normalizes_and_filters_entries(self):
        items = parse_feed(RSS, "World", "Test Publisher")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Headline One")
        self.assertEqual(items[0]["source"], "Test Publisher")
        self.assertEqual(items[0]["url"], "https://example.com/one")
        self.assertEqual(items[0]["summary"], "A short summary & update.")

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
        from news_core import fetch_category
        articles, errors = fetch_category("Made Up Category")
        self.assertEqual(articles, [])
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
