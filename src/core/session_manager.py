"""
HabteX Adder - Session Manager

Handles .session files cleanly:
  - add_account()    : OTP login with 2FA support
  - list_sessions()  : returns list of session filenames
  - remove_session() : delete by filename or range
  - filter_banned()  : check each session and remove dead/banned ones
"""

import os
import re
import threading
from typing import List, Callable, Optional

from telethon.sync import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberBannedError,
    FloodWaitError,
)

from src.config import AppConfig
from src.utils.logger import AppLogger

cfg = AppConfig()
log = AppLogger()


# ── helpers ──────────────────────────────────────────────────────────────────

def _sanitize(phone: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '_', phone.strip())

def _sessions_dir() -> str:
    d = cfg.get('sessions_folder', 'sessions')
    os.makedirs(d, exist_ok=True)
    return d

def _is_valid_session(fname: str) -> bool:
    return (
        fname.endswith('.session')
        and not fname.endswith('-journal')
        and not fname.startswith('.')
    )

def _clean_journals():
    """Remove leftover SQLite journal files."""
    d = _sessions_dir()
    for f in os.listdir(d):
        if f.endswith('-journal'):
            try:
                os.remove(os.path.join(d, f))
            except Exception:
                pass


# ── public API ───────────────────────────────────────────────────────────────

def list_sessions() -> List[str]:
    _clean_journals()
    d = _sessions_dir()
    return sorted(f for f in os.listdir(d) if _is_valid_session(f))


def remove_session(filename: str):
    d = _sessions_dir()
    path = os.path.join(d, filename)
    for ext in ['', '-journal']:
        p = path + ext if ext else path
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    log.info(f'Session deleted: {filename}')


def remove_sessions_by_range(start: int, end: int):
    """1-indexed, inclusive range."""
    sessions = list_sessions()
    if start < 1 or end > len(sessions) or start > end:
        raise ValueError(f'Invalid range {start}/{end} for {len(sessions)} sessions')
    for fname in sessions[start - 1:end]:
        remove_session(fname)
    log.info(f'Deleted sessions {start}–{end}')


def remove_all_sessions():
    for fname in list_sessions():
        remove_session(fname)
    log.info('All sessions deleted')


def session_path(filename: str) -> str:
    return os.path.join(_sessions_dir(), filename)


def _make_client(phone_or_path: str) -> TelegramClient:
    api_id = cfg.get('api_id')
    api_hash = cfg.get('api_hash')
    return TelegramClient(phone_or_path, api_id, api_hash)


# ── add account ──────────────────────────────────────────────────────────────

class AddAccountSession:
    """
    Step-by-step account login for UI integration.
    Usage:
        s = AddAccountSession(phone)
        s.request_code()          → raises on error
        s.submit_code(code)       → raises SessionPasswordNeededError if 2FA
        s.submit_password(pw)     → finishes 2FA login
        s.result                  → dict with phone/id/name on success
    """

    def __init__(self, phone: str):
        self.phone = phone.strip()
        self._name = _sanitize(self.phone)
        self._path = os.path.join(_sessions_dir(), self._name)
        self._client: Optional[TelegramClient] = None
        self.result: Optional[dict] = None

    def request_code(self):
        if os.path.exists(self._path + '.session'):
            raise FileExistsError(f'Session already exists for {self.phone}')
        api_id = cfg.get('api_id')
        api_hash = cfg.get('api_hash')
        self._client = TelegramClient(self._path, api_id, api_hash)
        self._client.connect()
        if not self._client.is_user_authorized():
            self._client.send_code_request(self.phone)
            log.info(f'Code sent to {self.phone}')
        else:
            self._finalize()

    def submit_code(self, code: str):
        """May raise SessionPasswordNeededError → caller must call submit_password."""
        self._client.sign_in(self.phone, code.strip())
        self._finalize()

    def submit_password(self, password: str):
        self._client.sign_in(password=password.strip())
        self._finalize()

    def _finalize(self):
        if self._client.is_user_authorized():
            me = self._client.get_me()
            self.result = {
                'phone': me.phone,
                'user_id': me.id,
                'name': f'{me.first_name or ""} {me.last_name or ""}'.strip(),
                'username': me.username,
            }
            log.success(f'Account added: {self.result["phone"]} ({self.result["name"]})')
        else:
            self.cleanup()
            raise RuntimeError('Authorization failed')
        self._client.disconnect()

    def cleanup(self):
        try:
            if self._client:
                self._client.disconnect()
        except Exception:
            pass
        for ext in ['.session', '.session-journal']:
            p = self._path + ext
            if os.path.exists(p):
                os.remove(p)


# ── filter banned (runs in background thread) ─────────────────────────────────

def filter_banned_sessions(
    on_progress: Callable[[str, str], None],   # (session_filename, status_text)
    on_done: Callable[[int, int], None],       # (removed_count, remaining_count)
):
    """
    Checks every session; removes dead/banned ones.
    Calls on_progress for each and on_done when complete.
    Designed to be run in a background thread.
    """
    def _run():
        sessions = list_sessions()
        removed = 0
        for fname in sessions:
            path = session_path(fname)
            try:
                client = _make_client(path.replace('.session', ''))
                client.connect()
                if not client.is_user_authorized():
                    client.disconnect()
                    remove_session(fname)
                    removed += 1
                    on_progress(fname, '🔴 Expired – removed')
                    log.warn(f'Expired session removed: {fname}')
                else:
                    me = client.get_me()
                    on_progress(fname, f'✅ OK – {me.phone}')
                    log.info(f'Session OK: {fname}')
                    client.disconnect()
            except PhoneNumberBannedError:
                remove_session(fname)
                removed += 1
                on_progress(fname, '🚫 Banned – removed')
                log.warn(f'Banned account removed: {fname}')
            except Exception as e:
                remove_session(fname)
                removed += 1
                on_progress(fname, f'❌ Error – removed ({str(e)[:40]})')
                log.error(f'Session error {fname}: {e}')

        remaining = len(list_sessions())
        on_done(removed, remaining)

    threading.Thread(target=_run, daemon=True).start()


def get_session_info(fname: str) -> Optional[dict]:
    """Quick info fetch for a single session (blocking)."""
    path = session_path(fname).replace('.session', '')
    try:
        client = _make_client(path)
        client.connect()
        if client.is_user_authorized():
            me = client.get_me()
            info = {
                'phone': me.phone,
                'name': f'{me.first_name or ""} {me.last_name or ""}'.strip(),
                'username': me.username,
                'user_id': me.id,
            }
            client.disconnect()
            return info
        client.disconnect()
        return None
    except Exception:
        return None
