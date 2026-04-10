"""
HabteX Adder - Adder Screen
"""

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar

from src.core.adder import AdderSession
from src.core.session_manager import list_sessions
from src.core.scraper import load_scraped
from src.config import AppConfig

cfg = AppConfig()


class AdderScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._adder: AdderSession = None
        self._build_ui()

    def _build_ui(self):
        sv = ScrollView()
        root = MDBoxLayout(
            orientation='vertical', padding=dp(16), spacing=dp(10),
            size_hint_y=None,
        )
        root.bind(minimum_height=root.setter('height'))

        root.add_widget(MDLabel(text='➕  Add Members', font_style='H6', bold=True,
                                size_hint_y=None, height=dp(40)))

        # ── Inputs ───────────────────────────────────────────────────────────
        self._target_field = MDTextField(
            hint_text='Target group link (public or private)',
            mode='rectangle', size_hint_y=None, height=dp(56),
        )
        root.add_widget(self._target_field)

        row1 = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self._acc_start = MDTextField(
            hint_text='Account start (e.g. 1)',
            input_filter='int', mode='rectangle',
        )
        self._acc_end = MDTextField(
            hint_text='Account end (e.g. 10)',
            input_filter='int', mode='rectangle',
        )
        row1.add_widget(self._acc_start)
        row1.add_widget(self._acc_end)
        root.add_widget(row1)

        self._delay_field = MDTextField(
            hint_text=f'Delay per add (sec, default {cfg.get("default_delay", 5)})',
            input_filter='int', mode='rectangle',
            size_hint_y=None, height=dp(56),
        )
        root.add_widget(self._delay_field)

        # ── Info ─────────────────────────────────────────────────────────────
        self._info_label = MDLabel(
            text='', font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(20),
        )
        root.add_widget(self._info_label)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self._start_btn = MDRaisedButton(
            text='▶  Start Adding',
            on_release=lambda x: self._start(),
        )
        self._stop_btn = MDFlatButton(
            text='⏹  Stop',
            disabled=True,
            on_release=lambda x: self._stop(),
        )
        btn_row.add_widget(self._start_btn)
        btn_row.add_widget(self._stop_btn)
        root.add_widget(btn_row)

        # ── Progress ─────────────────────────────────────────────────────────
        self._progress = MDProgressBar(value=0, size_hint_y=None, height=dp(4))
        root.add_widget(self._progress)

        # ── Live stats card ───────────────────────────────────────────────────
        stats_card = MDCard(
            orientation='vertical', padding=dp(12), radius=[dp(8)],
            size_hint_y=None, elevation=1,
        )
        stats_card.add_widget(MDLabel(text='Live Stats', font_style='Subtitle2', bold=True,
                                      size_hint_y=None, height=dp(24)))
        self._stat_added  = MDLabel(text='✅ Added:    0', font_style='Body2',
                                    size_hint_y=None, height=dp(22))
        self._stat_priv   = MDLabel(text='⛔ Privacy:  0', font_style='Body2',
                                    size_hint_y=None, height=dp(22))
        self._stat_flood  = MDLabel(text='⚠ Flood:    0', font_style='Body2',
                                    size_hint_y=None, height=dp(22))
        self._stat_other  = MDLabel(text='❌ Other:    0', font_style='Body2',
                                    size_hint_y=None, height=dp(22))
        self._stat_index  = MDLabel(text='📍 Position: 0', font_style='Body2',
                                    size_hint_y=None, height=dp(22))
        for lbl in [self._stat_added, self._stat_priv, self._stat_flood,
                    self._stat_other, self._stat_index]:
            stats_card.add_widget(lbl)
        stats_card.bind(minimum_height=stats_card.setter('height'))
        root.add_widget(stats_card)

        # ── Last action log ───────────────────────────────────────────────────
        root.add_widget(MDLabel(text='Last action:', font_style='Caption',
                                size_hint_y=None, height=dp(20)))
        self._last_action = MDLabel(
            text='–', font_style='Body2',
            theme_text_color='Secondary',
            size_hint_y=None, height=dp(36),
        )
        root.add_widget(self._last_action)

        sv.add_widget(root)
        self.add_widget(sv)

    def on_enter(self, *args):
        sessions = list_sessions()
        scraped = load_scraped()
        self._info_label.text = (
            f'{len(sessions)} session(s) available | '
            f'{len(scraped)} users in scraped list'
        )
        # Prefill end with total sessions
        if not self._acc_end.text:
            self._acc_end.text = str(len(sessions))
        if not self._acc_start.text:
            self._acc_start.text = '1'

    def _start(self):
        target = self._target_field.text.strip()
        if not target:
            Snackbar(text='Enter a target group link.', snackbar_x='8dp',
                     snackbar_y='72dp', size_hint_x=0.95).open()
            return

        try:
            s = int(self._acc_start.text or '1')
            e = int(self._acc_end.text or '1')
        except ValueError:
            Snackbar(text='Invalid account range.', snackbar_x='8dp',
                     snackbar_y='72dp', size_hint_x=0.95).open()
            return

        delay = int(self._delay_field.text or str(cfg.get('default_delay', 5)))

        # Start Android foreground service if available
        try:
            from kivy.app import App
            App.get_running_app().start_foreground_service()
        except Exception:
            pass

        self._reset_stats()
        self._start_btn.disabled = True
        self._stop_btn.disabled = False
        self._progress.value = 5

        self._adder = AdderSession(
            target_link=target,
            account_start=s,
            account_end=e,
            delay=delay,
            on_progress=lambda msg: Clock.schedule_once(
                lambda dt: self._on_progress(msg), 0),
            on_stats=lambda stats: Clock.schedule_once(
                lambda dt: self._update_stats(stats), 0),
            on_done=lambda stats: Clock.schedule_once(
                lambda dt: self._on_done(stats), 0),
            on_error=lambda err: Clock.schedule_once(
                lambda dt: self._on_error(err), 0),
        )
        self._adder.start()

    def _stop(self):
        if self._adder:
            self._adder.stop()
        self._stop_btn.disabled = True

    def _on_progress(self, msg):
        self._last_action.text = msg
        v = self._progress.value
        if v < 95:
            self._progress.value = v + 2

    def _update_stats(self, stats):
        self._stat_added.text  = f'✅ Added:    {stats["added"]}'
        self._stat_priv.text   = f'⛔ Privacy:  {stats["privacy"]}'
        self._stat_flood.text  = f'⚠ Flood:    {stats["flood"]}'
        self._stat_other.text  = f'❌ Other:    {stats["other"]}'
        self._stat_index.text  = f'📍 Position: {stats["index"]}'

    def _on_done(self, stats):
        self._progress.value = 100
        self._start_btn.disabled = False
        self._stop_btn.disabled = True
        self._update_stats(stats)
        self._last_action.text = (
            f'✅ Complete! Added {stats["added"]} members.'
        )
        try:
            from kivy.app import App
            App.get_running_app().stop_foreground_service()
        except Exception:
            pass

    def _on_error(self, err):
        self._last_action.text = f'❌ {err}'
        self._progress.value = 0
        self._start_btn.disabled = False
        self._stop_btn.disabled = True

    def _reset_stats(self):
        for lbl, txt in [
            (self._stat_added,  '✅ Added:    0'),
            (self._stat_priv,   '⛔ Privacy:  0'),
            (self._stat_flood,  '⚠ Flood:    0'),
            (self._stat_other,  '❌ Other:    0'),
            (self._stat_index,  '📍 Position: 0'),
        ]:
            lbl.text = txt
        self._last_action.text = '–'
        self._progress.value = 0
