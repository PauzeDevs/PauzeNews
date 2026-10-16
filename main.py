"""PauzeNews Android-first RSS reader built with Python and Kivy."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from news_core import ALL_CATEGORIES, ArticleStore, fetch_category

# Premium gold editorial palette inspired by Apple's typography and spacing.
BG = (0.035, 0.035, 0.039, 1)
PANEL = (0.085, 0.083, 0.078, 1)
PANEL_RAISED = (0.12, 0.115, 0.105, 1)
ACCENT = (0.88, 0.68, 0.30, 1)
ACCENT_DARK = (0.32, 0.23, 0.09, 1)
TEXT = (0.96, 0.95, 0.92, 1)
MUTED = (0.66, 0.65, 0.61, 1)


class NewsCard(BoxLayout):
    def __init__(self, article, app, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(14), size_hint_y=None, **kwargs)
        self.article = article
        self.app = app
        self.height = dp(202 if article.get("summary") else 160)
        self.canvas.before.clear()
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            Color(*PANEL)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        published = article.get("published", "")
        meta_parts = [article.get("category", "News"), article.get("source", "Source")]
        if published:
            meta_parts.append(published)
        meta = "  ·  ".join(meta_parts)
        self.add_widget(Label(text=meta, color=ACCENT, font_size="10sp", bold=True,
                              halign="left", valign="middle", size_hint_y=None, height=dp(20),
                              text_size=(Window.width - dp(60), None)))
        title = Button(text=article.get("title", "Untitled"), color=TEXT, font_size="17sp",
                       bold=True, halign="left", valign="middle", text_size=(Window.width - dp(64), None),
                       background_normal="", background_color=(0, 0, 0, 0),
                       size_hint_y=None, height=dp(58))
        title.bind(on_release=lambda *_: self.app.open_article(article))
        self.add_widget(title)
        summary = article.get("summary", "")
        if summary:
            self.add_widget(Label(text=summary, color=MUTED, font_size="12sp", halign="left",
                                  valign="top", size_hint_y=None, height=dp(42),
                                  text_size=(Window.width - dp(64), dp(42))))
        footer = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        read = Button(text="Read story  →", font_size="12sp", bold=True, color=BG,
                      background_normal="", background_color=ACCENT)
        read.bind(on_release=lambda *_: self.app.open_article(article))
        saved = self.app.store.is_bookmarked(article["id"])
        bookmark = Button(text="★ Saved" if saved else "☆ Save", font_size="12sp",
                          color=ACCENT, background_normal="", background_color=ACCENT_DARK)
        bookmark.bind(on_release=lambda *_: self.app.toggle_bookmark(article))
        footer.add_widget(read)
        footer.add_widget(bookmark)
        self.add_widget(footer)

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class PauzeNewsApp(App):
    title = "PauzeNews"

    def build(self):
        Window.clearcolor = BG
        self.category = "For You"
        self.show_saved = False
        self.loading = False
        self.articles = []
        # Render a small first page to avoid creating hundreds of Kivy widgets
        # at once on low-memory Android devices.
        self.visible_limit = 24
        self.store = ArticleStore(str(Path(self.user_data_dir) / "pauzenews.sqlite3"))

        # API 34 is used with the current SDL2 bootstrap so system-bar insets
        # are handled by Android instead of allowing the UI under the status bar.
        root = BoxLayout(orientation="vertical", padding=[dp(16), dp(18), dp(16), dp(12)], spacing=dp(12))
        header = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(8))
        brand = BoxLayout(orientation="vertical")
        brand.add_widget(Label(text="[b]PauzeNews[/b]", markup=True, color=TEXT, font_size="25sp",
                               halign="left", valign="middle"))
        brand.add_widget(Label(text="THE WORLD, IN CONTEXT.", color=ACCENT, font_size="10sp",
                               bold=True, halign="left", valign="middle"))
        header.add_widget(brand)
        refresh = Button(text="Refresh", size_hint_x=None, width=dp(82), font_size="12sp",
                         bold=True, color=BG, background_normal="", background_color=ACCENT)
        refresh.bind(on_release=lambda *_: self.refresh_news())
        header.add_widget(refresh)
        root.add_widget(header)

        self.search = TextInput(hint_text="Search headlines or publishers", multiline=False,
                                size_hint_y=None, height=dp(48), padding=[dp(14), dp(12)],
                                background_normal="", background_active="",
                                background_color=PANEL_RAISED, foreground_color=TEXT,
                                hint_text_color=MUTED, cursor_color=ACCENT,
                                selection_color=ACCENT_DARK, font_size="14sp")
        self.search.bind(text=lambda *_: self._search_changed())
        root.add_widget(self.search)

        category_scroll = ScrollView(size_hint_y=None, height=dp(42), do_scroll_y=False, do_scroll_x=True, bar_width=0)
        category_row = BoxLayout(size_hint_x=None, size_hint_y=None, height=dp(38), spacing=dp(7))
        category_row.bind(minimum_width=category_row.setter("width"))
        self.category_buttons = {}
        for category in ALL_CATEGORIES + ["Saved"]:
            button = Button(text=category, size_hint_x=None, width=dp(max(82, len(category) * 8 + 28)),
                            background_normal="", background_color=ACCENT if category == self.category else PANEL,
                            color=BG if category == self.category else MUTED,
                            bold=category == self.category, font_size="12sp")
            button.bind(on_release=lambda instance, c=category: self.select_category(c))
            self.category_buttons[category] = button
            category_row.add_widget(button)
        category_scroll.add_widget(category_row)
        root.add_widget(category_scroll)

        self.status = Label(text="Loading real headlines…", color=MUTED, size_hint_y=None,
                            height=dp(30), font_size="12sp", halign="left", valign="middle")
        root.add_widget(self.status)
        self.scroll = ScrollView(do_scroll_x=False)
        self.card_list = BoxLayout(orientation="vertical", spacing=dp(10), padding=[0, dp(2), 0, dp(10)],
                                   size_hint_y=None)
        self.card_list.bind(minimum_height=self.card_list.setter("height"))
        self.scroll.add_widget(self.card_list)
        root.add_widget(self.scroll)
        self.refresh_news()
        return root

    def _search_changed(self):
        self.visible_limit = 24
        self.render_articles()

    def _load_more(self, *_):
        self.visible_limit = min(self.visible_limit + 24, 500)
        self.render_articles()

    def select_category(self, category):
        self.category = category
        self.visible_limit = 24
        self.show_saved = category == "Saved"
        for name, button in self.category_buttons.items():
            button.background_color = ACCENT if name == category else PANEL
            button.color = BG if name == category else MUTED
            button.bold = name == category
        self.render_articles()
        if not self.show_saved:
            self.refresh_news()

    def refresh_news(self):
        if self.loading:
            return
        self.loading = True
        self.status.text = "Loading real headlines from Google News…"
        self.render_articles()
        category = self.category if self.category != "Saved" else "For You"

        def worker():
            try:
                articles, errors = fetch_category(category)
            except Exception as exc:
                Logger.exception("PauzeNews: unexpected news-fetch failure")
                articles, errors = [], [type(exc).__name__]

            def finish(_dt):
                try:
                    if articles:
                        self.store.save_articles(articles)
                    self.loading = False
                    self.render_articles()
                    if articles and errors:
                        self.status.text = (
                            f"{len(articles)} headlines updated · "
                            f"{len(errors)} source(s) unavailable"
                        )
                    elif articles:
                        self.status.text = f"{len(articles)} headlines updated"
                    elif errors:
                        self.status.text = "Could not reach the news feeds. Check internet and tap Refresh."
                    else:
                        self.status.text = "No stories returned. Check internet and tap Refresh."
                except Exception:
                    Logger.exception("PauzeNews: failed to save or display news")
                    self.loading = False
                    self.status.text = "Couldn't display headlines. Tap Refresh to retry."

            Clock.schedule_once(finish, 0)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            Logger.exception("PauzeNews: could not start news worker")
            self.loading = False
            self.status.text = "Couldn't start news loading. Tap Refresh to retry."
            self.render_articles()

    def render_articles(self):
        if not hasattr(self, "card_list"):
            return
        self.card_list.clear_widgets()
        try:
            found = self.store.list_articles(
                category=self.category if self.category != "Saved" else "For You",
                query=self.search.text if hasattr(self, "search") else "",
                bookmarks_only=self.show_saved,
                limit=min(self.visible_limit + 1, 500),
            )
        except Exception:
            Logger.exception("PauzeNews: failed to read cached headlines")
            found = []
            self.status.text = "Couldn't read saved headlines. Try restarting the app."

        has_more = len(found) > self.visible_limit
        articles = found[:self.visible_limit]
        if not articles:
            if self.loading:
                message = "Fetching live headlines. Stories will appear here shortly."
            elif self.show_saved:
                message = "No saved stories yet."
            else:
                message = "No cached headlines yet. Tap Try again to load real news."
            self.card_list.add_widget(Label(
                text=message, color=MUTED, size_hint_y=None, height=dp(84),
                halign="center", valign="middle",
                text_size=(max(dp(220), Window.width - dp(48)), dp(84)),
            ))
            if not self.loading and not self.show_saved:
                retry = Button(
                    text="Try again", size_hint_y=None, height=dp(44),
                    background_normal="", background_color=ACCENT, color=BG, bold=True,
                )
                retry.bind(on_release=lambda *_: self.refresh_news())
                self.card_list.add_widget(retry)
            return
        for article in articles:
            card = NewsCard(article, self, size_hint_y=None)
            self.card_list.add_widget(card)

        if has_more:
            more = Button(
                text="Load more headlines",
                size_hint_y=None,
                height=dp(46),
                background_normal="",
                background_color=ACCENT_DARK,
                color=TEXT,
                bold=True,
            )
            more.bind(on_release=self._load_more)
            self.card_list.add_widget(more)

    def toggle_bookmark(self, article):
        saved = self.store.toggle_bookmark(article["id"])
        self.status.text = "Story saved" if saved else "Bookmark removed"
        self.render_articles()

    def open_article(self, article):
        url = article.get("url", "")
        if url.startswith(("https://", "http://")):
            webbrowser.open(url)

    def on_pause(self):
        return True


if __name__ == "__main__":
    PauzeNewsApp().run()
