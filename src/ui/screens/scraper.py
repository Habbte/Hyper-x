"""
HabteX Adder - Scraper Screen
"""

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar

from src.core.scraper import (
    scrape_members, clear_scraped, load_scraped,
    load_resume_status, clear_resume_status,
    FILTER_ALL, FILTER_ONLINE, FILTER_LAST_WEEK,
)


class ScraperScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._filter_mode = FILTER_ALL
        self._build_ui()

    def _build_ui(self):
        sv = ScrollView()
        root = MDBoxLayout(
            orientation='vertical', padding=dp(16), spacing=dp(10),
            size_hint_y=None,
        )
        root.bind(minimum_height=root.setter('height'))

        root.add_widget(MDLabel(text='🔍  Scrape Members', font_style='H6', bold=True,
                                size_hint_y=None, height=dp(40)))

        # ── Group link ───────────────────────────────────────────────────────
        self._link_field = MDTextField(
            hint_text='Source group link (public or private invite)',
            mode='rectangle',
            size_hint_y=None,
            height=dp(56),
        )
        root.add_widget(self._link_field)

        # ── Filter options ───────────────────────────────────────────────────
        root.add_widget(MDLabel(text='Activity Filter:', font_style='Subtitle2',
                                size_hint_y=None, height=dp(28)))
        for label, mode in [
            ('All members', FILTER_ALL),
            ('Online / Recently online only', FILTER_ONLINE),
            ('Active last week', FILTER_LAST_WEEK),
        ]:
            row = MDBoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
            cb = MDCheckbox(
                group='filter', size_hint=(None, None), size=(dp(36), dp(36)),
                active=(mode == FILTER_ALL),
            )
            cb.bind(active=lambda w, v, m=mode: self._set_filter(m, v))
            row.add_widget(cb)
            row.add_widget(MDLabel(text=label, font_style='Body2'))
            root.add_widget(row)

        # ── Resume row ───────────────────────────────────────────────────────
        self._resume_card = MDCard(
            orientation='vertical', padding=dp(10), radius=[dp(8)],
            size_hint_y=None, height=dp(60), elevation=1,
        )
        self._resume_label = MDLabel(text='No previous scrape to resume.', font_style='Caption')
        self._resume_card.add_widget(self._resume_label)
        root.add_widget(self._resume_card)
        self._refresh_resume_status()

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self._start_btn = MDRaisedButton(
            text='Start Scrape',
            on_release=lambda x: self._start(),
        )
        btn_row.add_widget(self._start_btn)
        btn_row.add_widget(MDFlatButton(
            text='Clear Scraped',
            on_release=lambda x: self._clear(),
        ))
        root.add_widget(btn_row)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress = MDProgressBar(value=0, size_hint_y=None, height=dp(4))
        root.add_widget(self._progress)

        # ── Status label ─────────────────────────────────────────────────────
        self._status = MDLabel(
            text='Ready.',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20),
        )
        root.add_widget(self._status)

        # ── Count label ──────────────────────────────────────────────────────
        self._count_label = MDLabel(
            text='',
            font_style='Subtitle1',
            bold=True,
            size_hint_y=None,
            height=dp(28),
        )
        root.add_widget(self._count_label)

        # ── Duplicate report card ─────────────────────────────────────────────
        self._dup_card = MDCard(
            orientation='vertical', padding=dp(12), radius=[dp(8)],
            size_hint_y=None, elevation=1,
        )
        self._dup_label = MDLabel(
            text='Duplicate detection will run automatically after scraping.',
            font_style='Caption',
            theme_text_color='Secondary',
        )
        self._dup_card.add_widget(MDLabel(
            text='⚠️  Multi-Account Detection', font_style='Subtitle2', bold=True,
            size_hint_y=None, height=dp(24),
        ))
        self._dup_card.add_widget(self._dup_label)
        self._dup_card.bind(minimum_height=self._dup_card.setter('height'))
        root.add_widget(self._dup_card)

        sv.add_widget(root)
        self.add_widget(sv)

    def on_enter(self, *args):
        self._refresh_resume_status()
        scraped = load_scraped()
        if scraped:
            self._count_label.text = f'Currently saved: {len(scraped)} users'

    def _set_filter(self, mode, active):
        if active:
            self._filter_mode = mode

    def _refresh_resume_status(self):
        status = load_resume_status()
        if status:
            self._resume_label.text = (
                f"Resume available: {status.get('source', '?')} "
                f"(index {status.get('index', 0)})"
            )
        else:
            self._resume_label.text = 'No previous scrape to resume.'

    def _start(self):
        link = self._link_field.text.strip()
        if not link:
            Snackbar(text='Please enter a group link.', snackbar_x='8dp',
                     snackbar_y='72dp', size_hint_x=0.95).open()
            return

        self._start_btn.disabled = True
        self._progress.value = 10
        self._status.text = 'Starting...'
        self._dup_label.text = 'Running...'

        scrape_members(
            source_link=link,
            filter_mode=self._filter_mode,
            on_progress=lambda msg: Clock.schedule_once(
                lambda dt: setattr(self._status, 'text', msg), 0),
            on_count=lambda n: Clock.schedule_once(
                lambda dt: self._update_count(n), 0),
            on_duplicate_report=lambda rpt: Clock.schedule_once(
                lambda dt: self._show_dup_report(rpt), 0),
            on_done=lambda n: Clock.schedule_once(
                lambda dt: self._on_done(n), 0),
            on_error=lambda err: Clock.schedule_once(
                lambda dt: self._on_error(err), 0),
        )

    def _update_count(self, n):
        self._count_label.text = f'Scraped: {n} users'
        self._progress.value = min(90, self._progress.value + 10)

    def _show_dup_report(self, report_text):
        self._dup_label.text = report_text

    def _on_done(self, n):
        self._progress.value = 100
        self._count_label.text = f'✅ Saved {n} users to scraped.txt'
        self._start_btn.disabled = False
        self._refresh_resume_status()

    def _on_error(self, err):
        self._status.text = f'❌ {err}'
        self._progress.value = 0
        self._start_btn.disabled = False

    def _clear(self):
        clear_scraped()
        clear_resume_status()
        self._count_label.text = ''
        self._status.text = 'Scraped list cleared.'
        self._refresh_resume_status()
