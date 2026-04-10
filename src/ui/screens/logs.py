"""
HabteX Adder - Logs Screen
"""

import os
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import Snackbar

from src.utils.logger import AppLogger

log = AppLogger()

LEVEL_COLORS = {
    'SUCCESS': '#4CAF50',
    'INFO':    '#90CAF9',
    'WARN':    '#FFB74D',
    'ERROR':   '#EF9A9A',
    'DEBUG':   '#B0BEC5',
}


class LogsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
        log.register_callback(self._on_new_log)

    def _build_ui(self):
        root = MDBoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        # Header
        hdr = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        hdr.add_widget(MDLabel(text='📋  Logs', font_style='H6', bold=True))
        hdr.add_widget(MDFlatButton(text='Clear', on_release=lambda x: self._clear()))
        hdr.add_widget(MDFlatButton(text='Export Path', on_release=lambda x: self._show_path()))
        root.add_widget(hdr)

        # Log view
        sv = ScrollView()
        self._log_box = MDBoxLayout(
            orientation='vertical', spacing=dp(2), size_hint_y=None, padding=dp(4),
        )
        self._log_box.bind(minimum_height=self._log_box.setter('height'))
        sv.add_widget(self._log_box)
        root.add_widget(sv)

        self.add_widget(root)
        self._sv = sv

    def on_enter(self, *args):
        self._log_box.clear_widgets()
        for entry in log.get_recent(200):
            self._append(entry['level'], entry['msg'], entry['ts'])

    def _on_new_log(self, level, msg, ts):
        Clock.schedule_once(lambda dt: self._append(level, msg, ts), 0)

    def _append(self, level, msg, ts):
        color = LEVEL_COLORS.get(level, '#FFFFFF')
        lbl = MDLabel(
            text=f'[color={color}][{ts}] [{level}][/color] {msg}',
            markup=True,
            font_style='Caption',
            size_hint_y=None,
        )
        lbl.bind(texture_size=lbl.setter('size'))
        self._log_box.add_widget(lbl)
        # Auto-scroll
        Clock.schedule_once(lambda dt: setattr(self._sv, 'scroll_y', 0), 0.05)

    def _clear(self):
        log.clear()
        self._log_box.clear_widgets()
        Snackbar(text='Logs cleared.', snackbar_x='8dp',
                 snackbar_y='72dp', size_hint_x=0.95).open()

    def _show_path(self):
        path = log.export_path()
        Snackbar(text=f'Log: {path}', snackbar_x='8dp',
                 snackbar_y='72dp', size_hint_x=0.95).open()
