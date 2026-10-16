"""PauzeNews Android-first RSS reader built with Python and Kivy."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from news_core import ALL_CATEGORIES, ArticleStore, fetch_category

BG = (0.035, 0.047, 0.075, 1)
PANEL = (0.075, 0.09, 0.135, 1)
ACCENT = (0.36, 0.40, 0.98, 1)
TEXT = (0.93, 0.95, 1, 1)
MUTED = (0.62, 0.67, 0.77, 1)


class NewsCard(BoxLayout):
    def __init__(self, article, app, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(14), size_hint_y=None, **kwargs)
        self.article = article
        self.app = app
        self.height = dp(190 if article.get("summary") else 145)
        self.canvas.before.clear()
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            Color(*PANEL)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        published = article.get("published", "")
        meta_parts = [article.get("category", "News"), article.get("source", "Source")]
        if published:
            meta_parts.append(published)
        meta = "  ·  ".join(meta_parts)
        self.add_widget(Label(text=meta, color=ACCENT, font_size="11sp", bold=True,
                              halign="left", valign="middle", size_hint_y=None, height=dp(18), text_size=(Window.width - dp(60), None)))
        title = Button(text=article.get("title", "Untitled"), color=TEXT, font_size="16sp",
                       bold=True, halign="left", valign="middle", text_size=(Window.width - dp(64), None),
                       background_normal="", background_color=(0, 0, 0, 0),
                       size_hint_y=None, height=dp(52))
        title.bind(on_release=lambda *_: self.app.open_article(article))
        self.add_widget(title)
        summary = article.get("summary", "")
        if summary:
            self.add_widget(Label(text=summary, color=MUTED, font_size="12sp", halign="left",
                                  valign="top", size_hint_y=None, height=dp(42),
                                  text_size=(Window.width - dp(64), dp(42))))
        footer = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        read = Button(text="Read source", font_size="12sp", background_normal="", background_color=ACCENT)
        read.bind(on_release=lambda *_: self.app.open_article(article))
        saved = self.app.store.is_bookmarked(article["id"])
        bookmark = Button(text="★ Saved" if saved else "☆ Save", font_size="12sp",
                          background_normal="", background_color=(0.16, 0.18, 0.25, 1))
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
        self.store = ArticleStore(str(Path(self.user_data_dir) / "pauzenews.sqlite3"))

        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(12), dp(14), dp(8)], spacing=dp(10))
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        brand = BoxLayout(orientation="vertical")
        brand.add_widget(Label(text="[b]PauzeNews[/b]", markup=True, color=TEXT, font_size="23sp",
                               halign="left", valign="middle"))
        brand.add_widget(Label(text="Your world. In context.", color=MUTED, font_size="11sp",
                               halign="left", valign="middle"))
        header.add_widget(brand)
        refresh = Button(text="↻", size_hint_x=None, width=dp(48), font_size="24sp",
                         background_normal="", background_color=ACCENT)
        refresh.bind(on_release=lambda *_: self.refresh_news())
        header.add_widget(refresh)
        root.add_widget(header)

        self.search = TextInput(hint_text="Search headlines or publishers", multiline=False,
                                size_hint_y=None, height=dp(44), padding=[dp(12), dp(10)],
                                background_color=PANEL, foreground_color=TEXT, hint_text_color=MUTED,
                                cursor_color=ACCENT)
        self.search.bind(text=lambda *_: self.render_articles())
        root.add_widget(self.search)

        category_scroll = ScrollView(size_hint_y=None, height=dp(42), do_scroll_y=False, do_scroll_x=True)
        category_row = BoxLayout(size_hint_x=None, size_hint_y=None, height=dp(38), spacing=dp(7))
        category_row.bind(minimum_width=category_row.setter("width"))
        self.category_buttons = {}
        for category in ALL_CATEGORIES + ["Saved"]:
            button = Button(text=category, size_hint_x=None, width=dp(max(78, len(category) * 8 + 24)),
                            background_normal="", background_color=ACCENT if category == self.category else PANEL,
                            color=TEXT, font_size="12sp")
            button.bind(on_release=lambda instance, c=category: self.select_category(c))
            self.category_buttons[category] = button
            category_row.add_widget(button)
        category_scroll.add_widget(category_row)
        root.add_widget(category_scroll)

        self.status = Label(text="Loading real headlines…", color=MUTED, size_hint_y=None,
                            height=dp(24), font_size="12sp", halign="left", valign="middle")
        root.add_widget(self.status)
        self.scroll = ScrollView(do_scroll_x=False)
        self.card_list = BoxLayout(orientation="vertical", spacing=dp(10), padding=[0, dp(2), 0, dp(10)],
                                   size_hint_y=None)
        self.card_list.bind(minimum_height=self.card_list.setter("height"))
        self.scroll.add_widget(self.card_list)
        root.add_widget(self.scroll)
        self.refresh_news()
        return root

    def select_category(self, category):
        self.category = category
        self.show_saved = category == "Saved"
        for name, button in self.category_buttons.items():
            button.background_color = ACCENT if name == category else PANEL
        self.render_articles()
        if not self.show_saved:
            self.refresh_news()

    def refresh_news(self):
        if self.loading:
            return
        self.loading = True
        self.status.text = "Fetching headlines from configured RSS sources…"
        category = self.category if self.category != "Saved" else "For You"

        def worker():
            articles, errors = fetch_category(category)

            def finish(_dt):
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
                    self.status.text = "Refresh failed. Showing cached headlines if available."
                else:
                    self.status.text = "No stories available yet. Tap ↻ to try again."

            Clock.schedule_once(finish, 0)

        threading.Thread(target=worker, daemon=True).start()

    def render_articles(self):
        if not hasattr(self, "card_list"):
            return
        self.card_list.clear_widgets()
        articles = self.store.list_articles(
            category=self.category if self.category != "Saved" else "For You",
            query=self.search.text if hasattr(self, "search") else "",
            bookmarks_only=self.show_saved,
        )
        if not articles:
            message = "No saved stories yet." if self.show_saved else "No cached headlines yet. Tap ↻ to refresh."
            self.card_list.add_widget(Label(text=message, color=MUTED, size_hint_y=None, height=dp(70)))
            return
        for article in articles:
            card = NewsCard(article, self, size_hint_y=None)
            self.card_list.add_widget(card)

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
