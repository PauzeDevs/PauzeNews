"""News ingestion and SQLite persistence for PauzeNews.

Only feed metadata and excerpts are stored. The original article remains with
its publisher and is opened through its source URL.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import feedparser
import requests

APP_NAME = "PauzeNews"
REQUEST_TIMEOUT = 12
MAX_ITEMS_PER_FEED = 35

FEEDS = {
    "World": [
        ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ],
    "India": [
        ("BBC News", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
    ],
    "Technology": [
        ("BBC News", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ],
    "Science": [
        ("BBC News", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("NASA", "https://www.nasa.gov/news-release/feed/"),
    ],
    "Business": [
        ("BBC News", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ],
    "Aviation": [
        ("Simple Flying", "https://simpleflying.com/feed/"),
    ],
}

ALL_CATEGORIES = ["For You"] + list(FEEDS)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", "").split()).strip()


def _safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_feed(content: bytes | str, category: str, source_name: str) -> list[dict]:
    """Parse RSS/Atom XML into normalized, deduplicated article dictionaries."""
    parsed = feedparser.parse(content)
    articles: list[dict] = []
    seen: set[str] = set()

    for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
        title = _clean(entry.get("title"))
        url = _clean(entry.get("link"))
        if not title or not _safe_url(url):
            continue

        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)

        summary = _clean(entry.get("summary") or entry.get("description"))
        # Keep feed-provided excerpts short; do not present them as full articles.
        if len(summary) > 420:
            summary = summary[:417].rstrip() + "..."

        published = _clean(entry.get("published") or entry.get("updated"))
        articles.append({
            "id": key,
            "title": title,
            "url": url,
            "summary": summary,
            "source": _clean(source_name) or _clean(urlparse(url).netloc),
            "category": category,
            "published": published,
            "fetched_at": int(time.time()),
        })

    return articles


def fetch_category(category: str, session=None) -> tuple[list[dict], list[str]]:
    """Fetch one category without letting a failed source break the whole feed."""
    if category == "For You":
        categories = list(FEEDS)
    elif category in FEEDS:
        categories = [category]
    else:
        return [], [f"Unknown category: {category}"]

    http = session or requests.Session()
    collected: list[dict] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    for selected_category in categories:
        for source_name, feed_url in FEEDS[selected_category]:
            try:
                response = http.get(
                    feed_url,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "PauzeNews/0.1 (+RSS reader)"},
                )
                response.raise_for_status()
                entries = parse_feed(response.content, selected_category, source_name)
                for article in entries:
                    if article["url"] not in seen_urls:
                        seen_urls.add(article["url"])
                        collected.append(article)
            except Exception as exc:
                # Keep diagnostics useful without exposing response bodies/secrets.
                errors.append(f"{source_name}: {type(exc).__name__}")

    collected.sort(key=lambda item: item["fetched_at"], reverse=True)
    return collected, errors


class ArticleStore:
    """Small local SQLite store for cached headlines and bookmarks."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    published TEXT NOT NULL DEFAULT '',
                    fetched_at INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    article_id TEXT PRIMARY KEY,
                    saved_at INTEGER NOT NULL,
                    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            """)
            db.execute("PRAGMA foreign_keys = ON")

    def save_articles(self, articles: Iterable[dict]) -> None:
        with self._connect() as db:
            db.executemany("""
                INSERT INTO articles
                    (id, title, url, summary, source, category, published, fetched_at)
                VALUES
                    (:id, :title, :url, :summary, :source, :category, :published, :fetched_at)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    source=excluded.source,
                    category=excluded.category,
                    published=excluded.published,
                    fetched_at=excluded.fetched_at
            """, list(articles))

    def list_articles(self, category: str = "For You", query: str = "", bookmarks_only: bool = False, limit: int = 150) -> list[dict]:
        sql = "SELECT a.* FROM articles a"
        params: list[object] = []
        if bookmarks_only:
            sql += " JOIN bookmarks b ON b.article_id = a.id"
        clauses = []
        if category not in {"For You", "Saved"}:
            clauses.append("a.category = ?")
            params.append(category)
        if query.strip():
            clauses.append("(a.title LIKE ? OR a.summary LIKE ? OR a.source LIKE ?)")
            term = f"%{query.strip()}%"
            params.extend([term, term, term])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY a.fetched_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def toggle_bookmark(self, article_id: str) -> bool:
        with self._connect() as db:
            exists = db.execute("SELECT 1 FROM bookmarks WHERE article_id = ?", (article_id,)).fetchone()
            if exists:
                db.execute("DELETE FROM bookmarks WHERE article_id = ?", (article_id,))
                return False
            article = db.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,)).fetchone()
            if not article:
                return False
            db.execute("INSERT INTO bookmarks(article_id, saved_at) VALUES (?, ?)", (article_id, int(time.time())))
            return True

    def is_bookmarked(self, article_id: str) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM bookmarks WHERE article_id = ?", (article_id,)).fetchone() is not None
