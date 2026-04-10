"""
Hyper X - Main App Entry Point
Built with Kivy + KivyMD
"""

import os
import sys
import threading

# ── Android setup ─────────────────────────────────────────────────────────────
try:
    from android.permissions import request_permissions, Permission
    from android.storage import app_storage_path
    IS_ANDROID = True
    # Store data in app's private storage
    os.chdir(app_storage_path())
except ImportError:
    IS_ANDROID = False

# ── Kivy config BEFORE imports ────────────────────────────────────────────────
from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'systemanddock')
Config.set('graphics', 'resizable', '0')

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, NoTransition

from kivymd.app import MDApp
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem

from src.config import AppConfig
from src.utils.logger import AppLogger
from src.utils.internet_check import check_internet


class HabteXApp(MDApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = AppConfig()
        self.log = AppLogger(log_file=self.cfg.get('log_file', 'habtex.log'))
        self.title = 'Hyper X'

    # ── build ─────────────────────────────────────────────────────────────────

    def build(self):
        # Theme
        self.theme_cls.primary_palette = self.cfg.get('primary_palette', 'DeepPurple')
        self.theme_cls.accent_palette = self.cfg.get('accent_palette', 'Teal')
        self.theme_cls.theme_style = self.cfg.get('theme', 'Dark')

        # Android permissions
        if IS_ANDROID:
            self._request_android_permissions()

        # Root layout
        root = BoxLayout(orientation='vertical')

        # Screen manager (no animation for speed)
        self.sm = ScreenManager(transition=NoTransition())

        # Lazy-import screens to avoid circular imports
        from src.ui.screens.dashboard import DashboardScreen
        from src.ui.screens.accounts import AccountsScreen
        from src.ui.screens.scraper import ScraperScreen
        from src.ui.screens.adder import AdderScreen
        from src.ui.screens.logs import LogsScreen
        from src.ui.screens.settings import SettingsScreen

        self.sm.add_widget(DashboardScreen(name='dashboard'))
        self.sm.add_widget(AccountsScreen(name='accounts'))
        self.sm.add_widget(ScraperScreen(name='scraper'))
        self.sm.add_widget(AdderScreen(name='adder'))
        self.sm.add_widget(LogsScreen(name='logs'))
        self.sm.add_widget(SettingsScreen(name='settings'))

        # Bottom nav
        nav = MDBottomNavigation(panel_color=self.theme_cls.primary_dark)
        items = [
            ('dashboard', 'Home',     'view-dashboard-outline'),
            ('accounts',  'Accounts', 'account-multiple-outline'),
            ('scraper',   'Scrape',   'magnify'),
            ('adder',     'Add',      'account-plus-outline'),
            ('logs',      'Logs',     'text-box-outline'),
        ]
        for name, text, icon in items:
            item = MDBottomNavigationItem(name=name, text=text, icon=icon)
            item.bind(on_tab_press=lambda x, n=name: self._goto(n))
            nav.add_widget(item)

        root.add_widget(self.sm)
        root.add_widget(nav)

        # Internet check on startup
        Clock.schedule_once(lambda dt: self._check_internet(), 1.5)

        self.log.info('Hyper X started.')
        return root

    # ── navigation ────────────────────────────────────────────────────────────

    def _goto(self, screen_name: str):
        if self.sm.current != screen_name:
            self.sm.current = screen_name

    # ── Android ───────────────────────────────────────────────────────────────

    def _request_android_permissions(self):
        request_permissions([
            Permission.INTERNET,
            Permission.RECEIVE_BOOT_COMPLETED,
            Permission.FOREGROUND_SERVICE,
            Permission.WAKE_LOCK,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])

    # ── startup internet check ────────────────────────────────────────────────

    def _check_internet(self):
        def _do():
            ok = check_internet()
            Clock.schedule_once(lambda dt: self._on_internet_result(ok), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _on_internet_result(self, ok: bool):
        if not ok:
            self._snack('⚠  No internet connection!')

    def _snack(self, text: str):
        from kivymd.uix.snackbar import Snackbar
        Snackbar(
            text=text,
            snackbar_x='8dp',
            snackbar_y='72dp',       # above bottom nav
            size_hint_x=0.95,
        ).open()

    # ── theme toggle (called from Settings screen) ────────────────────────────

    def toggle_theme(self):
        current = self.theme_cls.theme_style
        new = 'Light' if current == 'Dark' else 'Dark'
        self.theme_cls.theme_style = new
        self.cfg.set('theme', new)

    def set_palette(self, palette: str):
        self.theme_cls.primary_palette = palette
        self.cfg.set('primary_palette', palette)

    # ── background service (Android foreground service) ───────────────────────

    def start_foreground_service(self):
        """Keep the app alive while adding in background."""
        if IS_ANDROID:
            try:
                from android import AndroidService
                service = AndroidService('Hyper X', 'Running in background...')
                service.start('service_started')
                self.android_service = service
                self.log.info('Android foreground service started.')
            except Exception as e:
                self.log.warn(f'Could not start foreground service: {e}')

    def stop_foreground_service(self):
        if IS_ANDROID:
            try:
                self.android_service.stop()
            except Exception:
                pass


if __name__ == '__main__':
    HabteXApp().run()
