"""
HabteX Adder - Accounts Screen
Add accounts (OTP + 2FA), view/delete sessions, filter banned.
"""

import threading
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, TwoLineIconListItem, IconLeftWidget
from kivy.uix.scrollview import ScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar

from src.core.session_manager import (
    list_sessions, remove_session, remove_all_sessions,
    filter_banned_sessions, AddAccountSession,
)


class AccountsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._add_session: AddAccountSession = None
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        # ── Header ──────────────────────────────────────────────────────────
        hdr = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        hdr.add_widget(MDLabel(text='👤  Accounts', font_style='H6', bold=True))
        hdr.add_widget(MDFlatButton(
            text='Filter Banned',
            on_release=lambda x: self._filter_banned(),
        ))
        hdr.add_widget(MDFlatButton(
            text='Delete All',
            theme_text_color='Error',
            on_release=lambda x: self._confirm_delete_all(),
        ))
        root.add_widget(hdr)

        # ── Count label ──────────────────────────────────────────────────────
        self._count_label = MDLabel(
            text='Sessions: 0',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20),
        )
        root.add_widget(self._count_label)

        # ── Session list ─────────────────────────────────────────────────────
        sv = ScrollView()
        self._list = MDList()
        sv.add_widget(self._list)
        root.add_widget(sv)

        # ── Add Account button ───────────────────────────────────────────────
        root.add_widget(MDRaisedButton(
            text='+ Add Account',
            size_hint_y=None,
            height=dp(48),
            on_release=lambda x: self._open_add_dialog_phone(),
        ))

        # ── Progress label ───────────────────────────────────────────────────
        self._status_label = MDLabel(
            text='',
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20),
        )
        root.add_widget(self._status_label)

        self.add_widget(root)

    def on_enter(self, *args):
        self._reload()

    def _reload(self):
        sessions = list_sessions()
        self._list.clear_widgets()
        self._count_label.text = f'Sessions: {len(sessions)}'
        for fname in sessions:
            item = TwoLineIconListItem(
                text=fname.replace('.session', ''),
                secondary_text='Tap to delete',
                on_release=lambda x, f=fname: self._confirm_delete(f),
            )
            item.add_widget(IconLeftWidget(icon='account-circle'))
            self._list.add_widget(item)

    # ── Add Account flow ──────────────────────────────────────────────────────

    def _open_add_dialog_phone(self):
        self._phone_field = MDTextField(
            hint_text='Phone number (+251...)',
            mode='rectangle',
        )
        self._add_dialog = MDDialog(
            title='Add Account',
            type='custom',
            content_cls=self._phone_field,
            buttons=[
                MDFlatButton(text='Cancel', on_release=lambda x: self._add_dialog.dismiss()),
                MDRaisedButton(text='Send Code', on_release=lambda x: self._send_code()),
            ],
        )
        self._add_dialog.open()

    def _send_code(self):
        phone = self._phone_field.text.strip()
        if not phone:
            return
        self._add_dialog.dismiss()
        self._status_label.text = f'Sending code to {phone}...'

        def _do():
            try:
                self._add_session = AddAccountSession(phone)
                self._add_session.request_code()
                Clock.schedule_once(lambda dt: self._open_code_dialog(), 0)
            except FileExistsError:
                Clock.schedule_once(lambda dt: self._snack(f'Session already exists for {phone}'), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._snack(f'Error: {e}'), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _open_code_dialog(self):
        self._status_label.text = 'Code sent! Enter it below.'
        self._code_field = MDTextField(hint_text='Verification code', mode='rectangle')
        self._code_dialog = MDDialog(
            title='Enter Code',
            type='custom',
            content_cls=self._code_field,
            buttons=[
                MDFlatButton(text='Cancel', on_release=lambda x: self._code_dialog.dismiss()),
                MDRaisedButton(text='Verify', on_release=lambda x: self._submit_code()),
            ],
        )
        self._code_dialog.open()

    def _submit_code(self):
        code = self._code_field.text.strip()
        if not code:
            return
        self._code_dialog.dismiss()
        self._status_label.text = 'Verifying...'

        def _do():
            from telethon.errors import SessionPasswordNeededError
            try:
                self._add_session.submit_code(code)
                Clock.schedule_once(lambda dt: self._on_account_added(), 0)
            except SessionPasswordNeededError:
                Clock.schedule_once(lambda dt: self._open_2fa_dialog(), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._snack(f'Code error: {e}'), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _open_2fa_dialog(self):
        self._status_label.text = '2FA required.'
        self._pw_field = MDTextField(hint_text='2FA Password', password=True, mode='rectangle')
        self._pw_dialog = MDDialog(
            title='Two-Factor Auth',
            type='custom',
            content_cls=self._pw_field,
            buttons=[
                MDFlatButton(text='Cancel', on_release=lambda x: self._pw_dialog.dismiss()),
                MDRaisedButton(text='Login', on_release=lambda x: self._submit_2fa()),
            ],
        )
        self._pw_dialog.open()

    def _submit_2fa(self):
        pw = self._pw_field.text.strip()
        self._pw_dialog.dismiss()

        def _do():
            try:
                self._add_session.submit_password(pw)
                Clock.schedule_once(lambda dt: self._on_account_added(), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._snack(f'2FA error: {e}'), 0)

        threading.Thread(target=_do, daemon=True).start()

    def _on_account_added(self):
        info = self._add_session.result
        self._status_label.text = f"✅ Added: {info['phone']} ({info['name']})"
        self._reload()

    # ── Delete ────────────────────────────────────────────────────────────────

    def _confirm_delete(self, fname):
        d = MDDialog(
            title='Delete Session',
            text=f'Delete {fname}?',
            buttons=[
                MDFlatButton(text='Cancel', on_release=lambda x: d.dismiss()),
                MDRaisedButton(
                    text='Delete',
                    on_release=lambda x: self._do_delete(fname, d),
                ),
            ],
        )
        d.open()

    def _do_delete(self, fname, dialog):
        dialog.dismiss()
        remove_session(fname)
        self._reload()
        self._snack(f'Deleted {fname}')

    def _confirm_delete_all(self):
        d = MDDialog(
            title='Delete ALL Sessions',
            text='This will remove every session file. Are you sure?',
            buttons=[
                MDFlatButton(text='Cancel', on_release=lambda x: d.dismiss()),
                MDRaisedButton(text='Delete All', on_release=lambda x: self._do_delete_all(d)),
            ],
        )
        d.open()

    def _do_delete_all(self, dialog):
        dialog.dismiss()
        remove_all_sessions()
        self._reload()
        self._snack('All sessions deleted')

    # ── Filter Banned ──────────────────────────────────────────────────────────

    def _filter_banned(self):
        self._status_label.text = 'Checking sessions...'
        self._list.clear_widgets()

        def _progress(fname, status):
            Clock.schedule_once(
                lambda dt: self._add_check_result(fname, status), 0
            )

        def _done(removed, remaining):
            Clock.schedule_once(
                lambda dt: self._on_filter_done(removed, remaining), 0
            )

        filter_banned_sessions(on_progress=_progress, on_done=_done)

    def _add_check_result(self, fname, status):
        item = TwoLineIconListItem(
            text=fname.replace('.session', ''),
            secondary_text=status,
        )
        icon = 'check-circle' if '✅' in status else 'close-circle'
        item.add_widget(IconLeftWidget(icon=icon))
        self._list.add_widget(item)

    def _on_filter_done(self, removed, remaining):
        self._status_label.text = f'Done. Removed: {removed} | Remaining: {remaining}'
        self._count_label.text = f'Sessions: {remaining}'

    # ── Snackbar ──────────────────────────────────────────────────────────────

    def _snack(self, text):
        Snackbar(text=text, snackbar_x='8dp', snackbar_y='72dp', size_hint_x=0.95).open()
