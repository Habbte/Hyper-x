"""
Hyper X - Dashboard Screen
Shows: session count, scraped count, internet status, quick tips.
"""

import os
import threading
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.gridlayout import MDGridLayout

from src.utils.internet_check import check_internet
from src.core.session_manager import list_sessions
from src.core.scraper import load_scraped


class StatCard(MDCard):
    def __init__(self, icon, value, label, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(16)
        self.spacing = dp(4)
        self.radius = [dp(12)]
        self.elevation = 2
        self.size_hint = (1, None)
        self.height = dp(90)

        from kivymd.uix.label import MDIcon
        self.val_label = MDLabel(
            text=str(value),
            font_style='H4',
            halign='center',
            bold=True,
        )
        lbl = MDLabel(
            text=f'  {icon}  {label}',
            font_style='Caption',
            halign='center',
            theme_text_color='Secondary',
        )
        self.add_widget(self.val_label)
        self.add_widget(lbl)

    def update(self, value):
        self.val_label.text = str(value)


class DashboardScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))

        # ── Title ──────────────────────────────────────────────────────────
        root.add_widget(MDLabel(
            text='📡  Hyper X',
            font_style='H5',
            halign='left',
            bold=True,
            size_hint_y=None,
            height=dp(48),
        ))

        # ── Status row ─────────────────────────────────────────────────────
        self._inet_label = MDLabel(
            text='⏳ Checking internet...',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(24),
        )
        root.add_widget(self._inet_label)

        # ── Stat cards grid ────────────────────────────────────────────────
        grid = MDGridLayout(
            cols=2,
            spacing=dp(10),
            size_hint_y=None,
            height=dp(200),
        )
        self._session_card  = StatCard('👤', '–', 'Sessions')
        self._scraped_card  = StatCard('🔍', '–', 'Scraped Users')
        self._added_card    = StatCard('✅', '–', 'Added (log)')
        self._warning_card  = StatCard('⚠', '–', 'Duplicates Found')

        grid.add_widget(self._session_card)
        grid.add_widget(self._scraped_card)
        grid.add_widget(self._added_card)
        grid.add_widget(self._warning_card)
        root.add_widget(grid)

        # ── Info card ──────────────────────────────────────────────────────
        info = MDCard(
            orientation='vertical',
            padding=dp(14),
            radius=[dp(10)],
            elevation=1,
            size_hint_y=None,
            height=dp(120),
        )
        info.add_widget(MDLabel(
            text='ℹ️  Quick Guide',
            font_style='Subtitle1',
            bold=True,
        ))
        info.add_widget(MDLabel(
            text=(
                '1. Add accounts  →  Accounts tab\n'
                '2. Scrape a group  →  Scrape tab\n'
                '3. Add to target  →  Add tab'
            ),
            font_style='Caption',
            theme_text_color='Secondary',
        ))
        root.add_widget(info)

        # ── Refresh button ─────────────────────────────────────────────────
        root.add_widget(MDFlatButton(
            text='Refresh Stats',
            on_release=lambda x: self._refresh(),
        ))

        self.add_widget(root)

    def on_enter(self, *args):
        self._refresh()

    def _refresh(self):
        self._inet_label.text = '⏳ Checking internet...'

        def _do():
            inet = check_internet()
            sessions = list_sessions()
            scraped = load_scraped()

            # Count added from log
            added = 0
            log_path = 'added_members.log'
            if os.path.exists(log_path):
                with open(log_path) as f:
                    added = sum(1 for _ in f)

            # Count duplicate warnings from habtex.log
            dups = 0
            log_file = 'habtex.log'
            if os.path.exists(log_file):
                with open(log_file) as f:
                    for line in f:
                        if 'cluster' in line.lower() and 'detected' in line.lower():
                            dups += 1

            Clock.schedule_once(lambda dt: self._apply(inet, sessions, scraped, added, dups), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _apply(self, inet, sessions, scraped, added, dups):
        self._inet_label.text = (
            '🟢 Internet: Connected' if inet else '🔴 Internet: Disconnected'
        )
        self._session_card.update(len(sessions))
        self._scraped_card.update(len(scraped))
        self._added_card.update(added)
        self._warning_card.update(dups)
