"""
HabteX Adder - Settings Screen
All config values editable live; saved to habtex_config.json.
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.snackbar import Snackbar

from src.config import AppConfig

cfg = AppConfig()

PALETTES = ['DeepPurple', 'Teal', 'Blue', 'Green', 'Red', 'Orange', 'Pink', 'Indigo']


class SettingsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._fields = {}
        self._build_ui()

    def _build_ui(self):
        sv = ScrollView()
        root = MDBoxLayout(
            orientation='vertical', padding=dp(16), spacing=dp(10),
            size_hint_y=None,
        )
        root.bind(minimum_height=root.setter('height'))

        root.add_widget(MDLabel(text='⚙️  Settings', font_style='H6', bold=True,
                                size_hint_y=None, height=dp(40)))

        # ── API Section ───────────────────────────────────────────────────────
        root.add_widget(self._section('Telegram API'))
        self._add_field(root, 'api_id', 'API ID', input_filter='int')
        self._add_field(root, 'api_hash', 'API Hash')

        # ── Behavior ──────────────────────────────────────────────────────────
        root.add_widget(self._section('Adding Behavior'))
        self._add_field(root, 'max_adds_per_account', 'Max adds per account', input_filter='int')
        self._add_field(root, 'default_delay', 'Delay between adds (sec)', input_filter='int')
        self._add_field(root, 'account_cooldown', 'Cooldown between accounts (sec)', input_filter='int')
        self._add_field(root, 'peer_flood_limit', 'PeerFlood stop limit', input_filter='int')

        # ── Duplicate Detection ───────────────────────────────────────────────
        root.add_widget(self._section('Multi-Account Detection'))
        self._add_field(root, 'duplicate_threshold',
                        'Flag cluster if prefix repeats ≥ N times', input_filter='int')
        self._add_field(root, 'duplicate_min_prefix_len',
                        'Minimum prefix length to check', input_filter='int')

        # ── Theme ─────────────────────────────────────────────────────────────
        root.add_widget(self._section('Appearance'))

        theme_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
        theme_row.add_widget(MDLabel(text='Dark Theme', font_style='Body2'))
        self._dark_switch = MDSwitch(
            active=(cfg.get('theme', 'Dark') == 'Dark'),
        )
        self._dark_switch.bind(active=lambda w, v: self._toggle_theme(v))
        theme_row.add_widget(self._dark_switch)
        root.add_widget(theme_row)

        root.add_widget(MDLabel(
            text='Color Palette:', font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None, height=dp(20),
        ))
        palette_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        for p in PALETTES:
            btn = MDFlatButton(
                text=p,
                on_release=lambda x, pal=p: self._set_palette(pal),
            )
            palette_row.add_widget(btn)
        sv2 = ScrollView(size_hint_y=None, height=dp(44))
        sv2.add_widget(palette_row)
        root.add_widget(sv2)

        # ── Save button ───────────────────────────────────────────────────────
        root.add_widget(MDRaisedButton(
            text='💾  Save Settings',
            size_hint_y=None,
            height=dp(48),
            on_release=lambda x: self._save(),
        ))

        root.add_widget(MDLabel(
            text='⚠ API ID/Hash changes require app restart.',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20),
        ))

        sv.add_widget(root)
        self.add_widget(sv)

    def _section(self, title):
        lbl = MDLabel(
            text=title,
            font_style='Subtitle1',
            bold=True,
            theme_text_color='Primary',
            size_hint_y=None,
            height=dp(36),
        )
        return lbl

    def _add_field(self, parent, key, hint, input_filter=None):
        field = MDTextField(
            hint_text=hint,
            text=str(cfg.get(key, '')),
            mode='rectangle',
            size_hint_y=None,
            height=dp(56),
        )
        if input_filter:
            field.input_filter = input_filter
        self._fields[key] = field
        parent.add_widget(field)

    def _save(self):
        for key, field in self._fields.items():
            val = field.text.strip()
            if val:
                # Cast int fields
                try:
                    if field.input_filter == 'int':
                        val = int(val)
                except Exception:
                    pass
                cfg.set(key, val)
        Snackbar(text='✅ Settings saved!', snackbar_x='8dp',
                 snackbar_y='72dp', size_hint_x=0.95).open()

    def _toggle_theme(self, dark: bool):
        try:
            App.get_running_app().toggle_theme()
        except Exception:
            pass

    def _set_palette(self, palette: str):
        try:
            App.get_running_app().set_palette(palette)
            Snackbar(text=f'Palette: {palette}', snackbar_x='8dp',
                     snackbar_y='72dp', size_hint_x=0.95).open()
        except Exception:
            pass
