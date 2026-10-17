"""PauzeNews: a compact, Android-first news reader with a glass-inspired UI."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from kivy.utils import platform
from kivy.uix.widget import Widget

try:
    from android.runnable import run_on_ui_thread
except ImportError:
    # Keep the module importable for desktop linting and unit-test collection.
    def run_on_ui_thread(function):
        return function

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from news_core import ALL_CATEGORIES, ArticleStore, fetch_category

# Matte graphite with cool, restrained highlights.
BG = (0.025, 0.029, 0.036, 1)
PANEL = (0.075, 0.085, 0.103, 0.96)
PANEL_RAISED = (0.095, 0.106, 0.127, 0.96)
ACCENT = (0.36, 0.64, 1.0, 1)
ACCENT_DARK = (0.10, 0.19, 0.31, 1)
TEXT = (0.95, 0.96, 0.98, 1)
MUTED = (0.62, 0.66, 0.72, 1)
EDGE = (0.40, 0.47, 0.58, 0.34)


def _shorten(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


class GlassSurface(BoxLayout):
    """Rounded matte panel with subtle glass-edge highlights."""

    def __init__(self, surface_color=PANEL, radius=dp(18), **kwargs):
        self.surface_color = surface_color
        self.corner_radius = radius
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*self.surface_color)
            self._surface = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self.corner_radius]
            )
            Color(*EDGE)
            self._lower_edge = Line(
                points=[self.x, self.y, self.x + self.width, self.y], width=0.8
            )
            Color(0.78, 0.84, 0.94, 0.20)
            self._shine = Line(
                points=[
                    self.x + dp(20), self.y + self.height - dp(1),
                    self.x + self.width - dp(20), self.y + self.height - dp(1),
                ],
                width=1.0,
            )
        self.bind(pos=self._sync_surface, size=self._sync_surface)

    def _sync_surface(self, *_):
        self._surface.pos = self.pos
        self._surface.size = self.size
        self._surface.radius = [self.corner_radius]
        self._lower_edge.points = [
            self.x + dp(18), self.y + dp(1),
            self.x + self.width - dp(18), self.y + dp(1),
        ]
        self._shine.points = [
            self.x + dp(20), self.y + self.height - dp(1),
            self.x + self.width - dp(20), self.y + self.height - dp(1),
        ]


def _text_label(text, *, color=TEXT, font_size="12sp", bold=False, height=None,
                text_size=None, halign="left", valign="middle"):
    label = Label(
        text=text,
        color=color,
        font_size=font_size,
        bold=bold,
        halign=halign,
        valign=valign,
        size_hint_y=None,
    )
    if height is not None:
        label.height = height
    if text_size is not None:
        label.text_size = text_size
    return label


def _action_button(text, *, background, color=TEXT, font_size="11sp", bold=True, height=None):
    button = Button(
        text=text,
        color=color,
        font_size=font_size,
        bold=bold,
        background_normal="",
        background_down="",
        background_color=background,
        size_hint_y=None,
    )
    if height is not None:
        button.height = height
    return button


class NewsCard(GlassSurface):
    """Compact editorial story card with a readable hierarchy and simple actions."""

    def __init__(self, article, app, **kwargs):
        summary = article.get("summary", "")
        super().__init__(
            orientation="vertical",
            spacing=dp(4),
            padding=[dp(12), dp(9), dp(12), dp(9)],
            surface_color=PANEL,
            radius=dp(16),
            size_hint_y=None,
            height=dp(152 if summary else 124),
            **kwargs,
        )
        self.article = article
        self.app = app

        published = _shorten(article.get("published", ""), 22)
        category = article.get("category", "News")
        source = _shorten(article.get("source", "Source"), 25)
        meta = "  ·  ".join(part for part in (category, source, published) if part)
        self.add_widget(_text_label(
            _shorten(meta, 72),
            color=ACCENT,
            font_size="10sp",
            bold=True,
            height=dp(16),
            text_size=(max(dp(180), Window.width - dp(56)), dp(16)),
        ))

        self.add_widget(_text_label(
            _shorten(article.get("title", "Untitled"), 108),
            color=TEXT,
            font_size="15sp",
            bold=True,
            height=dp(42),
            text_size=(max(dp(180), Window.width - dp(56)), dp(42)),
            valign="top",
        ))

        if summary:
            self.add_widget(_text_label(
                _shorten(summary, 142),
                color=MUTED,
                font_size="11sp",
                height=dp(32),
                text_size=(max(dp(180), Window.width - dp(56)), dp(32)),
                valign="top",
            ))

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(30),
            spacing=dp(7),
        )
        actions.add_widget(Widget())

        read = _action_button(
            "READ",
            background=ACCENT,
            color=BG,
            font_size="10sp",
            height=dp(30),
        )
        read.size_hint_x = None
        read.width = dp(82)
        read.bind(on_release=lambda *_: self.app.open_article(article))

        saved = self.app.store.is_bookmarked(article["id"])
        bookmark = _action_button(
            "SAVED" if saved else "SAVE",
            background=ACCENT_DARK if saved else PANEL_RAISED,
            color=ACCENT if saved else MUTED,
            font_size="10sp",
            height=dp(30),
        )
        bookmark.size_hint_x = None
        bookmark.width = dp(72)
        bookmark.bind(on_release=lambda *_: self.app.toggle_bookmark(article))

        actions.add_widget(read)
        actions.add_widget(bookmark)
        self.add_widget(actions)


class PauzeNewsApp(App):
    title = "PauzeNews"

    def build(self):
        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._handle_keyboard)
        self._article_overlay = None
        self._article_content = None
        self._article_webview = None
        self._article_back_listener = None
        self.category = "For You"
        self.show_saved = False
        self.loading = False
        self.articles = []
        # Small first paint limits widget churn and memory use on phones.
        self.visible_limit = 8
        self.store = ArticleStore(str(Path(self.user_data_dir) / "pauzenews.sqlite3"))

        # Extra top and bottom clearance keeps content away from Android's
        # status/navigation areas on devices where SDL2 reports edge overlap.
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(14), dp(12), dp(14), dp(10)],
            spacing=dp(10),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
        )
        brand = BoxLayout(orientation="vertical", spacing=0)
        brand.add_widget(_text_label(
            "PauzeNews",
            color=TEXT,
            font_size="27sp",
            bold=True,
            height=dp(38),
            text_size=(max(dp(170), Window.width - dp(150)), dp(38)),
        ))
        brand.add_widget(_text_label(
            "THE WORLD, IN CONTEXT.",
            color=MUTED,
            font_size="9sp",
            bold=True,
            height=dp(19),
            text_size=(max(dp(170), Window.width - dp(150)), dp(19)),
        ))
        header.add_widget(brand)

        refresh = _action_button(
            "Refresh",
            background=ACCENT,
            color=BG,
            font_size="12sp",
            height=dp(44),
        )
        refresh.size_hint_x = None
        refresh.width = dp(88)
        refresh.bind(on_release=lambda *_: self.refresh_news())
        header.add_widget(refresh)
        root.add_widget(header)

        search_shell = GlassSurface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(13), dp(3), dp(13), dp(3)],
            surface_color=PANEL_RAISED,
            radius=dp(16),
        )
        self.search = TextInput(
            hint_text="Search headlines or publishers",
            multiline=False,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT,
            hint_text_color=MUTED,
            cursor_color=ACCENT,
            selection_color=ACCENT_DARK,
            font_size="14sp",
            padding=[dp(2), dp(10), dp(2), dp(8)],
        )
        self.search.bind(text=lambda *_: self._search_changed())
        search_shell.add_widget(self.search)
        root.add_widget(search_shell)

        category_scroll = ScrollView(
            size_hint_y=None,
            height=dp(44),
            do_scroll_y=False,
            do_scroll_x=True,
            bar_width=0,
            scroll_type=["content"],
        )
        category_row = BoxLayout(
            size_hint_x=None,
            size_hint_y=None,
            height=dp(40),
            spacing=dp(7),
        )
        category_row.bind(minimum_width=category_row.setter("width"))
        self.category_buttons = {}
        for category in ALL_CATEGORIES + ["Saved"]:
            selected = category == self.category
            button = Button(
                text=category,
                size_hint_x=None,
                width=dp(max(80, len(category) * 7.1 + 28)),
                background_normal="",
                background_down="",
                background_color=ACCENT_DARK if selected else PANEL,
                color=ACCENT if selected else MUTED,
                bold=selected,
                font_size="11sp",
            )
            button.bind(on_release=lambda instance, c=category: self.select_category(c))
            self.category_buttons[category] = button
            category_row.add_widget(button)
        category_scroll.add_widget(category_row)
        root.add_widget(category_scroll)

        self.status = _text_label(
            "Preparing your briefing…",
            color=MUTED,
            font_size="11sp",
            height=dp(24),
            text_size=(max(dp(220), Window.width - dp(40)), dp(24)),
        )
        root.add_widget(self.status)

        self.scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(3),
            scroll_type=["bars", "content"],
        )
        self.card_list = BoxLayout(
            orientation="vertical",
            spacing=dp(11),
            padding=[0, dp(2), 0, dp(12)],
            size_hint_y=None,
        )
        self.card_list.bind(minimum_height=self.card_list.setter("height"))
        self.scroll.add_widget(self.card_list)
        root.add_widget(self.scroll)

        # Let the first frame and safe-area spacing settle before networking.
        Clock.schedule_once(lambda _dt: self.refresh_news(), 0.25)
        return root

    def _search_changed(self):
        self.visible_limit = 8
        self.render_articles()

    def _load_more(self, *_):
        self.visible_limit = min(self.visible_limit + 8, 160)
        self.render_articles()

    def select_category(self, category):
        self.category = category
        self.visible_limit = 8
        self.show_saved = category == "Saved"
        for name, button in self.category_buttons.items():
            selected = name == category
            button.background_color = ACCENT_DARK if selected else PANEL
            button.color = ACCENT if selected else MUTED
            button.bold = selected
        self.render_articles()
        if not self.show_saved:
            self.refresh_news()

    def refresh_news(self):
        if self.loading:
            return
        self.loading = True
        self.status.text = "Loading headlines…"
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
                        self.status.text = (
                            "Could not reach the news feeds. Check your connection and retry."
                        )
                    else:
                        self.status.text = "No stories returned. Pull down by tapping Refresh."
                except Exception:
                    Logger.exception("PauzeNews: failed to save or display news")
                    self.loading = False
                    self.status.text = "Couldn't display headlines. Tap Refresh to retry."

            try:
                Clock.schedule_once(finish, 0)
            except Exception:
                Logger.exception("PauzeNews: could not schedule news results")

        try:
            threading.Thread(
                target=worker,
                name="pauzenews-news-refresh",
                daemon=True,
            ).start()
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
                limit=min(self.visible_limit + 1, 160),
            )
        except Exception:
            Logger.exception("PauzeNews: failed to read cached headlines")
            found = []
            self.status.text = "Couldn't read saved headlines. Try restarting the app."

        has_more = len(found) > self.visible_limit
        articles = found[:self.visible_limit]
        if not articles:
            if self.loading:
                message = "Fetching live headlines. They will appear here shortly."
            elif self.show_saved:
                message = "No saved stories yet. Save one from any topic."
            elif self.search.text.strip():
                message = "No matching stories. Try a shorter search."
            else:
                message = "No cached headlines yet. Tap Refresh to retry."
            self.card_list.add_widget(_text_label(
                message,
                color=MUTED,
                font_size="12sp",
                height=dp(84),
                text_size=(max(dp(220), Window.width - dp(48)), dp(84)),
                halign="center",
            ))
            if not self.loading and not self.show_saved:
                retry = _action_button(
                    "Try again",
                    background=ACCENT_DARK,
                    color=ACCENT,
                    height=dp(44),
                )
                retry.bind(on_release=lambda *_: self.refresh_news())
                self.card_list.add_widget(retry)
            return

        for article in articles:
            self.card_list.add_widget(NewsCard(article, self))

        if has_more:
            more = _action_button(
                "Load more headlines",
                background=ACCENT_DARK,
                color=ACCENT,
                height=dp(46),
            )
            more.bind(on_release=self._load_more)
            self.card_list.add_widget(more)

    def toggle_bookmark(self, article):
        saved = self.store.toggle_bookmark(article["id"])
        self.status.text = "Story saved" if saved else "Bookmark removed"
        self.render_articles()

    def open_article(self, article):
        url = article.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            self.status.text = "This story has an invalid article link."
            return

        title = article.get("title", "Article")
        if platform != "android":
            # Desktop fallback; Android always uses the embedded reader below.
            try:
                opened = webbrowser.open(url)
                if opened is False:
                    self.status.text = "Could not open the link on this device."
            except Exception:
                Logger.exception("PauzeNews: could not open article")
                self.status.text = "Could not open this article."
            return

        self.status.text = "Opening article in PauzeNews…"
        self._open_article_reader(url, title)

    def _handle_keyboard(self, _window, key, *_args):
        # Android Back/Escape returns from the article view instead of exiting.
        if key in (27, 1001) and self._article_overlay is not None:
            self._reader_back()
            return True
        return False

    @run_on_ui_thread
    def _reader_back(self):
        """Navigate back within the publisher page before closing the reader."""
        webview = self._article_webview
        try:
            if webview is not None and webview.canGoBack():
                webview.goBack()
                return
        except Exception:
            Logger.exception("PauzeNews: could not navigate back in the article")
        self.close_article()

    @run_on_ui_thread
    def _open_article_reader(self, url, title):
        """Display publisher pages inside a native Android WebView overlay."""
        try:
            from jnius import PythonJavaClass, autoclass, java_method

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            content = activity.findViewById(16908290)  # android.R.id.content
            if content is None:
                raise RuntimeError("Android activity content view is unavailable")

            # Remove any previously opened reader before creating another one.
            if self._article_overlay is not None and self._article_content is not None:
                self._article_content.removeView(self._article_overlay)

            Color = autoclass("android.graphics.Color")
            Gravity = autoclass("android.view.Gravity")
            FrameLayout = autoclass("android.widget.FrameLayout")
            LinearLayout = autoclass("android.widget.LinearLayout")
            TextView = autoclass("android.widget.TextView")
            WebView = autoclass("android.webkit.WebView")
            WebViewClient = autoclass("android.webkit.WebViewClient")
            WebChromeClient = autoclass("android.webkit.WebChromeClient")

            density = float(activity.getResources().getDisplayMetrics().density)

            def px(value):
                return int(value * density)

            reader = LinearLayout(activity)
            reader.setOrientation(LinearLayout.VERTICAL)
            reader.setBackgroundColor(Color.parseColor("#080A0E"))

            toolbar = LinearLayout(activity)
            toolbar.setOrientation(LinearLayout.HORIZONTAL)
            toolbar.setGravity(Gravity.CENTER_VERTICAL)
            toolbar.setPadding(px(12), 0, px(12), 0)
            toolbar.setBackgroundColor(Color.parseColor("#10151D"))

            back = TextView(activity)
            back.setText("BACK")
            back.setTextColor(Color.parseColor("#70B0FF"))
            back.setTextSize(12)
            back.setGravity(Gravity.CENTER)
            back.setClickable(True)
            back.setFocusable(True)
            toolbar.addView(back, LinearLayout.LayoutParams(px(64), px(56)))

            heading = LinearLayout(activity)
            heading.setOrientation(LinearLayout.VERTICAL)
            heading.setGravity(Gravity.CENTER_VERTICAL)
            brand = TextView(activity)
            brand.setText("PAUZENEWS")
            brand.setTextColor(Color.parseColor("#F2F5FA"))
            brand.setTextSize(16)
            brand.setTypeface(None, 1)
            subtitle = TextView(activity)
            subtitle.setText(_shorten(title, 52))
            subtitle.setTextColor(Color.parseColor("#9AA6B7"))
            subtitle.setTextSize(11)
            subtitle.setSingleLine(True)
            heading.addView(brand, LinearLayout.LayoutParams(-1, px(25)))
            heading.addView(subtitle, LinearLayout.LayoutParams(-1, px(20)))
            toolbar.addView(heading, LinearLayout.LayoutParams(0, px(56), 1.0))
            reader.addView(toolbar, LinearLayout.LayoutParams(-1, px(60)))

            webview = WebView(activity)
            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setLoadsImagesAutomatically(True)
            settings.setSupportMultipleWindows(False)
            settings.setJavaScriptCanOpenWindowsAutomatically(False)
            settings.setAllowFileAccess(False)
            settings.setAllowContentAccess(False)
            webview.setWebViewClient(WebViewClient())
            webview.setWebChromeClient(WebChromeClient())
            webview.setBackgroundColor(Color.WHITE)
            reader.addView(webview, LinearLayout.LayoutParams(-1, 0, 1.0))

            class BackClickListener(PythonJavaClass):
                __javainterfaces__ = ["android/view/View$OnClickListener"]
                __javacontext__ = "app"

                def __init__(self, app):
                    super().__init__()
                    self.app = app

                @java_method("(Landroid/view/View;)V")
                def onClick(self, _view):
                    self.app._reader_back()

            self._article_back_listener = BackClickListener(self)
            back.setOnClickListener(self._article_back_listener)

            params = FrameLayout.LayoutParams(-1, -1)
            content.addView(reader, params)
            self._article_overlay = reader
            self._article_content = content
            self._article_webview = webview
            webview.loadUrl(url)
        except Exception:
            Logger.exception("PauzeNews: failed to open the in-app article reader")
            self._article_overlay = None
            self._article_content = None
            self._article_webview = None
            Clock.schedule_once(
                lambda _dt: setattr(self.status, "text", "Couldn't open the in-app reader. Please try again."),
                0,
            )

    @run_on_ui_thread
    def close_article(self):
        """Close the embedded reader and return to the headline list."""
        overlay = self._article_overlay
        content = self._article_content
        webview = self._article_webview
        self._article_overlay = None
        self._article_content = None
        self._article_webview = None
        self._article_back_listener = None

        try:
            if content is not None and overlay is not None:
                content.removeView(overlay)
            if webview is not None:
                webview.stopLoading()
                webview.destroy()
            if hasattr(self, "status"):
                Clock.schedule_once(
                    lambda _dt: setattr(self.status, "text", "Back to headlines"),
                    0,
                )
        except Exception:
            Logger.exception("PauzeNews: could not close the article reader")

    def on_pause(self):
        return True


if __name__ == "__main__":
    PauzeNewsApp().run()
