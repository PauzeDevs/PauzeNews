"""News ingestion and SQLite persistence for PauzeNews."""
from __future__ import annotations

import hashlib
import html
import sqlite3
import ssl
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from urllib.request import Request, urlopen

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    # Keep desktop installs working even if certifi is not installed.
    SSL_CONTEXT = ssl.create_default_context()

REQUEST_TIMEOUT = 12
MAX_ITEMS_PER_FEED = 35

# Google News RSS is an unauthenticated, key-free headline feed. It includes
# each article's publisher in its <source> element, which parse_feed preserves.
# Locale is pinned to India/English so results are relevant to the initial release.
FEEDS = {
    "World": [("Google News", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-IN&gl=IN&ceid=IN:en")],
    "India": [("Google News", "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en")],
    "Technology": [("Google News", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-IN&gl=IN&ceid=IN:en")],
    "Science": [
        ("Google News", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-IN&gl=IN&ceid=IN:en"),
        ("NASA", "https://www.nasa.gov/news-release/feed/"),
    ],
    "Business": [("Google News", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en")],
    "Aviation": [("Google News", "https://news.google.com/rss/search?q=aviation%20airlines&hl=en-IN&gl=IN&ceid=IN:en")],
}
ALL_CATEGORIES = ["For You"] + list(FEEDS)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _clean(value: object) -> str:
    raw = html.unescape(str(value or "")).replace("\x00", "")
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        raw = " ".join(parser.parts)
    except Exception:
        pass
    return " ".join(raw.split()).strip()


def _safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_feed(content: bytes | str, category: str, source_name: str) -> list[dict]:
    """Parse RSS/Atom XML into normalized, deduplicated article dictionaries."""
    # Use the standard-library XML parser rather than feedparser. This keeps
    # Android builds self-contained and avoids python-for-android's legacy
    # feedparser recipe (which still uses the removed setuptools use_2to3 flag).
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, TypeError, ValueError):
        return []

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    def child_text(element: ET.Element, names: set[str]) -> str:
        for child in element.iter():
            if child is element:
                continue
            if local_name(child.tag) in names:
                # Atom links use href; RSS links normally use text.
                value = child.attrib.get("href", "") or "".join(child.itertext())
                if value.strip():
                    return value.strip()
        return ""

    is_atom = local_name(root.tag) == "feed"
    if is_atom:
        entries = [node for node in root if local_name(node.tag) == "entry"]
    else:
        channel = next(
            (node for node in root.iter() if local_name(node.tag) == "channel"),
            root,
        )
        entries = [node for node in channel if local_name(node.tag) == "item"]

    articles: list[dict] = []
    seen: set[str] = set()
    for entry in entries[:MAX_ITEMS_PER_FEED]:
        title = _clean(child_text(entry, {"title"}))
        if is_atom:
            url = ""
            for node in entry:
                if local_name(node.tag) == "link":
                    rel = node.attrib.get("rel", "alternate")
                    href = node.attrib.get("href", "")
                    if href and rel in {"alternate", ""}:
                        url = href
                        break
        else:
            url = child_text(entry, {"link"})

        if not title or not _safe_url(url):
            continue

        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)

        summary = _clean(child_text(entry, {"summary", "description", "encoded", "content"}))
        if len(summary) > 420:
            summary = summary[:417].rstrip() + "..."

        published = _clean(child_text(entry, {"pubdate", "published", "updated", "date"}))
        articles.append({
            "id": key,
            "title": title,
            "url": url,
            "summary": summary,
            "source": _clean(child_text(entry, {"source"})) or _clean(source_name) or _clean(urlparse(url).netloc),
            "category": category,
            "published": published,
            "fetched_at": int(time.time()),
        })
    return articles

def fetch_category(category: str, session=None) -> tuple[list[dict], list[str]]:
    """Fetch a category while isolating individual source failures."""
    if category == "For You":
        categories = list(FEEDS)
    elif category in FEEDS:
        categories = [category]
    else:
        return [], [f"Unknown category: {category}"]

    collected: list[dict] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    sources = [
        (selected_category, source_name, feed_url)
        for selected_category in categories
        for source_name, feed_url in FEEDS[selected_category]
    ]

    def fetch_one(source):
        selected_category, source_name, feed_url = source
        if session is not None:
            response = session.get(
                feed_url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "PauzeNews/0.1 (+RSS reader)"},
            )
            response.raise_for_status()
            content = response.content
        else:
            request = Request(
                feed_url,
                headers={"User-Agent": "PauzeNews/0.1 (+RSS reader)"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT, context=SSL_CONTEXT) as response:
                content = response.read()
        return selected_category, source_name, parse_feed(content, selected_category, source_name)

    # The home feed spans every category. Fetch feeds concurrently so one slow
    # publisher cannot delay all the other stories for dozens of seconds.
    if session is None and len(sources) > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(4, len(sources))) as pool:
            futures = {pool.submit(fetch_one, source): source for source in sources}
            results = []
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors.append(f"{source[1]}: {type(exc).__name__}")
    else:
        results = []
        for source in sources:
            try:
                results.append(fetch_one(source))
            except Exception as exc:
                errors.append(f"{source[1]}: {type(exc).__name__}")

    for selected_category, source_name, articles in results:
        for article in articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                collected.append(article)

    collected.sort(key=lambda item: item["fetched_at"], reverse=True)
    return collected, errors


class ArticleStore:
    """Local SQLite store for cached headlines and bookmarks."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

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
                    article_id TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
                    saved_at INTEGER NOT NULL
                )
            """)

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
