"""PauzeNews: a compact, Android-first news reader with a glass-inspired UI."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime
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

# PauzeNews premium charcoal-and-gold palette: restrained, high-contrast, editorial.
BG = (0.027, 0.027, 0.029, 1)          # near-black canvas
PANEL = (0.075, 0.075, 0.079, 1)       # raised charcoal surface
PANEL_RAISED = (0.105, 0.105, 0.110, 1)
ACCENT = (0.86, 0.68, 0.34, 1)         # warm metallic gold
ACCENT_DARK = (0.19, 0.145, 0.065, 1)  # subdued gold wash
TEXT = (0.96, 0.96, 0.97, 1)
MUTED = (0.63, 0.63, 0.66, 1)
EDGE = (0.52, 0.39, 0.18, 0.34)       # subtle warm border


def _shorten(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _published_label(value: str) -> str:
    """Make feed timestamps compact and consistent across publishers."""
    if not value:
        return "LATEST"
    try:
        published = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            published = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            return _shorten(value.upper(), 16)
    try:
        if published.tzinfo is not None:
            published = published.astimezone()
        return published.strftime("%d %b · %H:%M").upper()
    except (ValueError, OverflowError):
        return _shorten(value.upper(), 16)


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
            Color(0.95, 0.77, 0.40, 0.16)
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
                width=None, size_hint_x=1, text_size=None, halign="left", valign="middle"):
    label = Label(
        text=text,
        color=color,
        font_size=font_size,
        bold=bold,
        halign=halign,
        valign=valign,
        size_hint_x=size_hint_x,
        size_hint_y=None,
    )
    if height is not None:
        label.height = height
    if width is not None:
        label.width = width
    if text_size is not None:
        label.text_size = text_size
    return label


class RoundedActionButton(Button):
    """Minimal rounded button with a custom surface and pressed state."""

    def __init__(self, *, fill_color, radius=dp(10), **kwargs):
        self.fill_color = tuple(fill_color)
        self.corner_radius = radius
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        super().__init__(**kwargs)
        with self.canvas.before:
            self._fill_instruction = Color(*self.fill_color)
            self._shape = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self.corner_radius]
            )
        self.bind(pos=self._sync_shape, size=self._sync_shape)
        self.bind(on_press=self._show_pressed, on_release=self._show_released)

    def _sync_shape(self, *_):
        self._shape.pos = self.pos
        self._shape.size = self.size
        self._shape.radius = [self.corner_radius]

    def _show_pressed(self, *_):
        self._fill_instruction.rgba = tuple(
            max(0.0, channel * 0.82) for channel in self.fill_color[:3]
        ) + (self.fill_color[3],)

    def _show_released(self, *_):
        self._fill_instruction.rgba = self.fill_color


def _action_button(text, *, background, color=TEXT, font_size="11sp", bold=True, height=None):
    button = RoundedActionButton(
        fill_color=background,
        text=text,
        color=color,
        font_size=font_size,
        bold=bold,
        size_hint_y=None,
    )
    if height is not None:
        button.height = height
    return button


class TopicButton(Button):
    """Rounded, restrained topic pill with a clear gold-selected state."""

    def __init__(self, *, selected=False, **kwargs):
        self.selected = bool(selected)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", BG if self.selected else MUTED)
        kwargs.setdefault("font_size", "11sp")
        kwargs.setdefault("bold", self.selected)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._pill_color = Color(*self._fill_color())
            self._pill = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(12)]
            )
        self.bind(pos=self._sync_pill, size=self._sync_pill)

    def _fill_color(self):
        return ACCENT if self.selected else PANEL

    def _sync_pill(self, *_):
        self._pill.pos = self.pos
        self._pill.size = self.size
        self._pill_color.rgba = self._fill_color()

    def set_selected(self, selected):
        self.selected = bool(selected)
        self.color = BG if self.selected else MUTED
        self.bold = self.selected
        self._sync_pill()


class NewsCard(GlassSurface):
    """Full-width editorial story card designed for a vertical mobile feed."""

    def __init__(self, article, app, featured=False, **kwargs):
        self.article = article
        self.app = app
        self.featured = featured
        summary = article.get("summary", "").strip()
        card_height = (
            dp(224) if featured and summary else
            dp(184) if featured else
            dp(196) if summary else dp(158)
        )
        super().__init__(
            orientation="vertical",
            spacing=dp(7),
            padding=[dp(16), dp(13), dp(16), dp(13)],
            surface_color=PANEL_RAISED if featured else PANEL,
            radius=dp(18 if featured else 16),
            size_hint=(1, None),
            height=card_height,
            **kwargs,
        )
        self._body_labels = []
        self._meta_source = None
        self._meta_time = None
        self._lead_rail = None

        if featured:
            with self.canvas.before:
                Color(ACCENT[0], ACCENT[1], ACCENT[2], 0.96)
                self._lead_rail = RoundedRectangle(
                    pos=(self.x + dp(2), self.y + dp(13)),
                    size=(dp(3), max(dp(1), self.height - dp(26))),
                    radius=[dp(2)],
                )
            self.bind(pos=self._sync_lead_rail, size=self._sync_lead_rail)

            kicker = _text_label(
                "LEAD STORY  /  EDITOR'S PICK",
                color=ACCENT,
                font_size="9sp",
                bold=True,
                height=dp(14),
                text_size=(max(dp(160), self.width - dp(34)), dp(14)),
            )
            self._body_labels.append(kicker)
            self.add_widget(kicker)

        meta = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(17),
            spacing=dp(7),
        )
        category = _shorten(article.get("category", "News").upper(), 16)
        source = _shorten(article.get("source", "Source"), 24)
        self._meta_source = _text_label(
            f"{category}  ·  {source}",
            color=ACCENT,
            font_size="9sp",
            bold=True,
            height=dp(17),
            text_size=(max(dp(100), self.width - dp(134)), dp(17)),
        )
        meta.add_widget(self._meta_source)
        self._meta_time = _text_label(
            _published_label(article.get("published", "")),
            color=MUTED,
            font_size="8sp",
            bold=True,
            height=dp(17),
            width=dp(88),
            size_hint_x=None,
            text_size=(dp(88), dp(17)),
            halign="right",
        )
        meta.add_widget(self._meta_time)
        self.add_widget(meta)

        headline = _text_label(
            _shorten(article.get("title", "Untitled"), 150),
            color=TEXT,
            font_size="17sp" if featured else "15sp",
            bold=True,
            height=dp(48 if featured else 44),
            text_size=(max(dp(160), self.width - dp(34)), dp(48 if featured else 44)),
            valign="top",
        )
        self._body_labels.append(headline)
        self.add_widget(headline)

        if summary:
            summary_label = _text_label(
                _shorten(summary, 180),
                color=MUTED,
                font_size="11sp",
                height=dp(40),
                text_size=(max(dp(160), self.width - dp(34)), dp(40)),
                valign="top",
            )
            self._body_labels.append(summary_label)
            self.add_widget(summary_label)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )
        actions.add_widget(Widget())

        read = _action_button(
            "READ STORY  ↗",
            background=ACCENT,
            color=BG,
            font_size="9sp",
            height=dp(34),
        )
        read.size_hint_x = None
        read.width = dp(116)
        read.bind(on_release=lambda *_: self.app.open_article(article))

        saved = self.app.store.is_bookmarked(article["id"])
        bookmark = _action_button(
            "SAVED" if saved else "SAVE",
            background=ACCENT_DARK if saved else PANEL,
            color=ACCENT if saved else MUTED,
            font_size="9sp",
            height=dp(34),
        )
        bookmark.size_hint_x = None
        bookmark.width = dp(76)
        bookmark.bind(on_release=lambda *_: self.app.toggle_bookmark(article))

        actions.add_widget(read)
        actions.add_widget(bookmark)
        self.add_widget(actions)
        self.bind(width=self._sync_text_sizes)
        self._sync_text_sizes()
        self._sync_lead_rail()

    def _sync_text_sizes(self, *_):
        inner_width = max(dp(160), self.width - dp(34))
        for label in self._body_labels:
            label.text_size = (inner_width, label.height)
        if self._meta_source is not None:
            self._meta_source.text_size = (
                max(dp(100), self.width - dp(134)),
                dp(17),
            )
        if self._meta_time is not None:
            self._meta_time.text_size = (dp(88), dp(17))

    def _sync_lead_rail(self, *_):
        if self._lead_rail is not None:
            self._lead_rail.pos = (self.x + dp(2), self.y + dp(13))
            self._lead_rail.size = (dp(3), max(dp(1), self.height - dp(26)))


class PauzeNewsApp(App):
    title = "PauzeNews"

    def build(self):
        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._handle_keyboard)
        self._article_overlay = None
        self._article_content = None
        self._article_dialog = None
        self._article_webview = None
        self._article_back_listener = None
        self._article_key_listener = None
        self._article_dialog_key_listener = None
        self._article_external_listener = None
        self.category = "For You"
        self.show_saved = False
        self.loading = False
        self.articles = []
        self.visible_limit = 8
        self.store = ArticleStore(str(Path(self.user_data_dir) / "pauzenews.sqlite3"))

        # Compact, top-aligned app chrome; the stories receive the remaining
        # height and scroll vertically like a conventional news reader.
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(12), dp(18), dp(10)],
            spacing=dp(11),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(60),
            spacing=dp(10),
        )
        brand = BoxLayout(
            orientation="vertical",
            size_hint_x=1,
            spacing=dp(0),
        )
        brand.add_widget(_text_label(
            "PauzeNews",
            color=TEXT,
            font_size="26sp",
            bold=True,
            height=dp(34),
            text_size=(max(dp(170), Window.width - dp(150)), dp(34)),
        ))
        brand.add_widget(_text_label(
            "THE WORLD, IN CONTEXT.",
            color=ACCENT,
            font_size="9sp",
            bold=True,
            height=dp(17),
            text_size=(max(dp(170), Window.width - dp(150)), dp(17)),
        ))
        header.add_widget(brand)

        refresh = _action_button(
            "↻  REFRESH",
            background=ACCENT,
            color=BG,
            font_size="9sp",
            height=dp(40),
        )
        refresh.size_hint_x = None
        refresh.width = dp(104)
        refresh.bind(on_release=lambda *_: self.refresh_news())
        header.add_widget(refresh)
        root.add_widget(header)

        search_shell = GlassSurface(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            spacing=dp(8),
            padding=[dp(13), dp(3), dp(13), dp(3)],
            surface_color=PANEL_RAISED,
            radius=dp(16),
        )
        search_icon = _text_label(
            "⌕",
            color=ACCENT,
            font_size="24sp",
            height=dp(42),
            width=dp(24),
            size_hint_x=None,
            halign="center",
        )
        search_shell.add_widget(search_icon)
        self.search = TextInput(
            hint_text="Search stories or publishers",
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
            height=dp(40),
            do_scroll_y=False,
            do_scroll_x=True,
            bar_width=0,
            scroll_type=["content"],
        )
        category_row = BoxLayout(
            size_hint_x=None,
            size_hint_y=None,
            height=dp(36),
            spacing=dp(8),
        )
        category_row.bind(minimum_width=category_row.setter("width"))
        self.category_buttons = {}
        for category in ALL_CATEGORIES + ["Saved"]:
            button = TopicButton(
                text=category,
                selected=(category == self.category),
                size_hint_x=None,
                size_hint_y=None,
                height=dp(34),
                width=dp(max(78, len(category) * 7.0 + 32)),
            )
            button.bind(on_release=lambda instance, c=category: self.select_category(c))
            self.category_buttons[category] = button
            category_row.add_widget(button)
        category_scroll.add_widget(category_row)
        root.add_widget(category_scroll)

        feed_heading = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
        )
        feed_copy = BoxLayout(
            orientation="vertical",
            size_hint_x=1,
            spacing=dp(0),
        )
        feed_copy.add_widget(_text_label(
            "LATEST STORIES",
            color=TEXT,
            font_size="12sp",
            bold=True,
            height=dp(18),
            text_size=(max(dp(170), Window.width - dp(60)), dp(18)),
        ))
        self.status = _text_label(
            "Preparing your briefing…",
            color=MUTED,
            font_size="10sp",
            height=dp(18),
            text_size=(max(dp(170), Window.width - dp(60)), dp(18)),
        )
        feed_copy.add_widget(self.status)
        feed_heading.add_widget(feed_copy)
        feed_heading.add_widget(_text_label(
            "PAUZENEWS  /  DAILY",
            color=ACCENT,
            font_size="8sp",
            bold=True,
            height=dp(18),
            width=dp(112),
            size_hint_x=None,
            text_size=(dp(112), dp(18)),
            halign="right",
        ))
        root.add_widget(feed_heading)

        # Vertical scrolling removes the empty upper half and exposes a
        # predictable, full-width reading column on tall and compact phones.
        self.scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(2),
            scroll_type=["bars", "content"],
            effect_cls="ScrollEffect",
        )
        self.card_list = BoxLayout(
            orientation="vertical",
            spacing=dp(11),
            padding=[dp(1), dp(2), dp(1), dp(20)],
            size_hint_x=1,
            size_hint_y=None,
        )
        self.card_list.bind(minimum_height=self.card_list.setter("height"))
        self.scroll.add_widget(self.card_list)
        root.add_widget(self.scroll)

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
            button.set_selected(name == category)
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

            empty = GlassSurface(
                orientation="vertical",
                spacing=dp(9),
                padding=[dp(18), dp(18), dp(18), dp(18)],
                surface_color=PANEL,
                radius=dp(18),
                size_hint=(1, None),
                height=dp(154),
            )
            empty.add_widget(_text_label(
                "YOUR BRIEFING IS CLEAR",
                color=ACCENT,
                font_size="10sp",
                bold=True,
                height=dp(18),
                text_size=(max(dp(180), Window.width - dp(90)), dp(18)),
                halign="center",
            ))
            empty.add_widget(_text_label(
                message,
                color=MUTED,
                font_size="12sp",
                height=dp(58),
                text_size=(max(dp(180), Window.width - dp(90)), dp(58)),
                halign="center",
            ))
            if not self.loading and not self.show_saved:
                retry = _action_button(
                    "TRY AGAIN",
                    background=ACCENT_DARK,
                    color=ACCENT,
                    height=dp(36),
                )
                retry.size_hint_x = 1
                retry.bind(on_release=lambda *_: self.refresh_news())
                empty.add_widget(retry)
            self.card_list.add_widget(empty)
            return

        for index, article in enumerate(articles):
            self.card_list.add_widget(NewsCard(article, self, featured=(index == 0)))

        if has_more:
            more = _action_button(
                "LOAD MORE STORIES  ↓",
                background=ACCENT_DARK,
                color=ACCENT,
                height=dp(44),
            )
            more.size_hint_x = 1
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
        content = None
        reader = None
        webview = None
        dialog = None
        activity = None
        try:
            from jnius import PythonJavaClass, autoclass, java_method

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            # A Dialog owns a window above Kivy's rendering surface. Adding
            # a WebView directly to android.R.id.content can fail on some
            # Kivy/Android combinations because that view tree is not a normal
            # activity layout.
            if self._article_dialog is not None:
                try:
                    self._article_dialog.dismiss()
                except Exception:
                    Logger.exception("PauzeNews: could not dismiss previous reader")

            Color = autoclass("android.graphics.Color")
            Gravity = autoclass("android.view.Gravity")
            Dialog = autoclass("android.app.Dialog")
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
            back.setTextColor(Color.parseColor("#DDB66B"))
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
            brand.setTextColor(Color.parseColor("#F5F5F7"))
            brand.setTextSize(16)
            brand.setTypeface(None, 1)
            subtitle = TextView(activity)
            subtitle.setText(_shorten(title, 52))
            subtitle.setTextColor(Color.parseColor("#AAA6A0"))
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

            class ReaderKeyListener(PythonJavaClass):
                __javainterfaces__ = ["android/view/View$OnKeyListener"]
                __javacontext__ = "app"

                def __init__(self, app):
                    super().__init__()
                    self.app = app

                @java_method("(Landroid/view/View;ILandroid/view/KeyEvent;)Z")
                def onKey(self, _view, key_code, event):
                    # Android KEYCODE_BACK = 4, ACTION_DOWN = 0.
                    if key_code == 4 and event.getAction() == 0:
                        self.app._reader_back()
                        return True
                    return False

            class DialogKeyListener(PythonJavaClass):
                __javainterfaces__ = ["android/content/DialogInterface$OnKeyListener"]
                __javacontext__ = "app"

                def __init__(self, app):
                    super().__init__()
                    self.app = app

                @java_method("(Landroid/content/DialogInterface;ILandroid/view/KeyEvent;)Z")
                def onKey(self, _dialog, key_code, event):
                    # Keep Android Back behavior consistent inside the native reader window.
                    if key_code == 4 and event.getAction() == 0:
                        self.app._reader_back()
                        return True
                    return False

            self._article_back_listener = BackClickListener(self)
            self._article_key_listener = ReaderKeyListener(self)
            back.setOnClickListener(self._article_back_listener)

            open_external = TextView(activity)
            open_external.setText("OPEN ↗")
            open_external.setTextColor(Color.parseColor("#DDB66B"))
            open_external.setTextSize(11)
            open_external.setGravity(Gravity.CENTER)
            open_external.setClickable(True)
            open_external.setFocusable(True)
            toolbar.addView(open_external, LinearLayout.LayoutParams(px(70), px(56)))

            class ExternalClickListener(PythonJavaClass):
                __javainterfaces__ = ["android/view/View$OnClickListener"]
                __javacontext__ = "app"

                def __init__(self, target_activity, target_url):
                    super().__init__()
                    self.target_activity = target_activity
                    self.target_url = target_url

                @java_method("(Landroid/view/View;)V")
                def onClick(self, _view):
                    try:
                        Intent = autoclass("android.content.Intent")
                        Uri = autoclass("android.net.Uri")
                        intent = Intent(Intent.ACTION_VIEW, Uri.parse(self.target_url))
                        self.target_activity.startActivity(intent)
                    except Exception:
                        Logger.exception("PauzeNews: unable to open article externally")

            self._article_external_listener = ExternalClickListener(activity, url)
            open_external.setOnClickListener(self._article_external_listener)
            webview.setFocusableInTouchMode(True)
            webview.setOnKeyListener(self._article_key_listener)

            dialog = Dialog(activity)
            dialog.setCancelable(True)
            dialog.setCanceledOnTouchOutside(False)
            self._article_dialog_key_listener = DialogKeyListener(self)
            dialog.setOnKeyListener(self._article_dialog_key_listener)
            dialog.setContentView(reader)
            dialog.show()
            window = dialog.getWindow()
            if window is not None:
                window.setLayout(-1, -1)

            self._article_overlay = reader
            self._article_content = None
            self._article_dialog = dialog
            self._article_webview = webview
            webview.requestFocus()
            webview.loadUrl(url)
            self.status.text = "Reader opened · Use Back to return to headlines"
        except Exception as exc:
            Logger.exception("PauzeNews: failed to open the in-app article reader")
            try:
                if dialog is not None:
                    dialog.dismiss()
                elif content is not None and reader is not None:
                    content.removeView(reader)
                if webview is not None:
                    webview.stopLoading()
                    webview.destroy()
            except Exception:
                Logger.exception("PauzeNews: reader cleanup failed after an open error")
            self._article_overlay = None
            self._article_content = None
            self._article_dialog = None
            self._article_webview = None
            self._article_back_listener = None
            self._article_key_listener = None
            self._article_dialog_key_listener = None
            self._article_external_listener = None

            # If native WebView setup is unavailable on this device, do not
            # strand the user at a dead READ button: attempt the system browser.
            opened_external = False
            if activity is not None:
                try:
                    Intent = autoclass("android.content.Intent")
                    Uri = autoclass("android.net.Uri")
                    intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    activity.startActivity(intent)
                    opened_external = True
                except Exception:
                    Logger.exception("PauzeNews: browser fallback also failed")
            if opened_external:
                message = f"Embedded reader unavailable ({type(exc).__name__}); opened your browser."
            else:
                message = f"Could not open reader ({type(exc).__name__}). Check the link and retry."
            Clock.schedule_once(
                lambda _dt, msg=message: setattr(self.status, "text", msg),
                0,
            )

    @run_on_ui_thread
    def close_article(self):
        """Close the embedded reader and return to the headline list."""
        overlay = self._article_overlay
        content = self._article_content
        dialog = self._article_dialog
        webview = self._article_webview
        self._article_overlay = None
        self._article_content = None
        self._article_dialog = None
        self._article_webview = None
        self._article_back_listener = None
        self._article_key_listener = None
        self._article_dialog_key_listener = None
        self._article_external_listener = None

        try:
            if dialog is not None:
                dialog.dismiss()
            elif content is not None and overlay is not None:
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
