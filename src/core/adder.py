"""
HabteX Adder - Member Adder

Features:
  - Multi-account rotation (60 adds per account)
  - Configurable delay + account cooldown
  - PeerFlood detection (stops account after N errors)
  - Public + private target group support
  - Per-member status display (Online / Recently / Last Week / Last Month)
  - Skips already-participants automatically
  - Resumable (reads from scraped.txt at saved index)
  - Full error categorization
  - Thread-safe progress callbacks for UI
  - Graceful stop() support
"""

import os
import threading
import time
from typing import Callable, List, Optional

from telethon.sync import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, AddChatUserRequest
from telethon.tl.types import (
    InputPeerChannel,
    UserStatusOnline, UserStatusRecently,
    UserStatusLastWeek, UserStatusLastMonth,
)
from telethon.errors import (
    PeerFloodError, UserPrivacyRestrictedError,
    UserAlreadyParticipantError, ChatAdminRequiredError,
    ChatWriteForbiddenError, UserBannedInChannelError,
    FloodWaitError, SessionPasswordNeededError,
)

from src.config import AppConfig
from src.utils.logger import AppLogger
from src.core.session_manager import list_sessions, session_path
from src.core.scraper import load_scraped

cfg = AppConfig()
log = AppLogger()


def _is_private_link(link: str) -> bool:
    return 'joinchat' in link or '+' in link

def _hash_from_link(link: str) -> str:
    return link.split('/')[-1].replace('+', '')

def _username_from_link(link: str) -> str:
    return link.split('/')[-1].lstrip('@')

def _status_emoji(user) -> str:
    status = getattr(user, 'status', None)
    if isinstance(status, UserStatusOnline):
        return '🟢 Online'
    elif isinstance(status, UserStatusRecently):
        return '🟡 Recently'
    elif isinstance(status, UserStatusLastWeek):
        return '🟠 Last Week'
    elif isinstance(status, UserStatusLastMonth):
        return '🔴 Last Month'
    return '⚪ Unknown'


# ── AdderSession – one long-running task ────────────────────────────────────

class AdderSession:
    """
    Create one AdderSession per "Start Adding" run.
    Call start() to launch in background.
    Call stop() to request graceful stop.
    """

    def __init__(
        self,
        target_link: str,
        account_start: int,           # 1-indexed
        account_end: int,             # 1-indexed, inclusive
        delay: Optional[int] = None,
        start_index: int = 0,         # where in scraped.txt to begin
        on_progress: Callable[[str], None] = None,
        on_stats: Callable[[dict], None] = None,  # {'added', 'privacy', 'flood', 'other', 'index'}
        on_done: Callable[[dict], None] = None,
        on_error: Callable[[str], None] = None,
    ):
        self.target_link = target_link
        self.account_start = account_start
        self.account_end = account_end
        self.delay = delay if delay is not None else cfg.get('default_delay', 5)
        self.start_index = start_index

        self._on_progress = on_progress
        self._on_stats = on_stats
        self._on_done = on_done
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # stats
        self.added = 0
        self.privacy_errors = 0
        self.flood_errors = 0
        self.other_errors = 0
        self.current_index = start_index

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        log.info('Stop requested by user.')

    def _emit(self, msg: str):
        log.info(msg)
        self._on_progress and self._on_progress(msg)

    def _emit_stats(self):
        stats = {
            'added': self.added,
            'privacy': self.privacy_errors,
            'flood': self.flood_errors,
            'other': self.other_errors,
            'index': self.current_index,
        }
        self._on_stats and self._on_stats(stats)

    def _run(self):
        users = load_scraped()
        if not users:
            msg = 'Scraped list is empty. Run scraper first.'
            log.error(msg)
            self._on_error and self._on_error(msg)
            return

        sessions = list_sessions()
        if not sessions:
            msg = 'No accounts found. Add accounts first.'
            log.error(msg)
            self._on_error and self._on_error(msg)
            return

        # validate range
        s, e = self.account_start - 1, self.account_end
        if s < 0 or e > len(sessions) or s >= e:
            msg = f'Invalid account range {self.account_start}/{self.account_end} (have {len(sessions)} sessions)'
            log.error(msg)
            self._on_error and self._on_error(msg)
            return

        selected_sessions = sessions[s:e]
        max_adds = cfg.get('max_adds_per_account', 60)
        cooldown = cfg.get('account_cooldown', 40)
        flood_limit = cfg.get('peer_flood_limit', 10)
        api_id = cfg.get('api_id')
        api_hash = cfg.get('api_hash')
        target_is_private = _is_private_link(self.target_link)

        index = self.current_index
        total_accs = len(selected_sessions)

        for acc_num, fname in enumerate(selected_sessions, 1):
            if self._stop_event.is_set():
                self._emit('⛔ Stopped by user.')
                break
            if index >= len(users):
                self._emit('✅ All users processed.')
                break

            self._emit(f'[{acc_num}/{total_accs}] Starting session: {fname}')
            path = session_path(fname).replace('.session', '')
            client = TelegramClient(path, api_id, api_hash)

            try:
                client.start()
            except SessionPasswordNeededError:
                # 2FA accounts in session files should already be authenticated;
                # if not, skip rather than hang.
                self._emit(f'⚠ 2FA required for {fname} – skipping.')
                continue
            except Exception as exc:
                self._emit(f'❌ Could not start {fname}: {exc}')
                continue

            acc_name = 'Unknown'
            try:
                me = client.get_me()
                acc_name = me.first_name or me.phone or fname
            except Exception:
                pass

            # Join target group
            target_entity = None
            try:
                if target_is_private:
                    h = _hash_from_link(self.target_link)
                    updates = client(ImportChatInviteRequest(h))
                    target_entity = updates.chats[0]
                else:
                    uname = _username_from_link(self.target_link)
                    try:
                        client(JoinChannelRequest(uname))
                    except UserAlreadyParticipantError:
                        pass
                    target_entity = client.get_entity(uname)
            except Exception as exc:
                self._emit(f'❌ {acc_name} could not join target: {exc}')
                client.disconnect()
                continue

            # Determine whether target is a channel or legacy group
            is_channel = hasattr(target_entity, 'access_hash')
            if is_channel:
                target_peer = InputPeerChannel(target_entity.id, target_entity.access_hash)

            peer_flood_count = 0
            stop_slot = min(index + max_adds, len(users))
            self._emit(f'{acc_name}: adding users {index + 1}–{stop_slot}')

            for i in range(index, stop_slot):
                if self._stop_event.is_set():
                    break

                raw = users[i].lstrip('@')
                self.current_index = i

                try:
                    if is_channel:
                        client(InviteToChannelRequest(target_peer, [raw]))
                    else:
                        client(AddChatUserRequest(target_entity.id, raw, 42))

                    # fetch user object for status
                    try:
                        u = client.get_entity(raw)
                        status_txt = _status_emoji(u)
                        member_name = getattr(u, 'first_name', raw) or raw
                    except Exception:
                        status_txt = '⚪'
                        member_name = raw

                    self._emit(f'✅ {acc_name} → {member_name} [{status_txt}]')
                    log.log_added_member(
                        username=raw,
                        target_group=getattr(target_entity, 'title', self.target_link),
                        added_by=acc_name,
                        added_log_file=cfg.get('added_log_file', 'added_members.log'),
                    )
                    self.added += 1
                    index = i + 1

                    self._emit_stats()
                    time.sleep(self.delay)

                except UserAlreadyParticipantError:
                    index = i + 1
                    continue

                except UserPrivacyRestrictedError:
                    self._emit(f'⛔ Privacy restricted: {raw}')
                    self.privacy_errors += 1
                    index = i + 1

                except PeerFloodError:
                    self._emit(f'⚠ PeerFlood on {acc_name} ({peer_flood_count + 1}/{flood_limit})')
                    self.flood_errors += 1
                    peer_flood_count += 1
                    if peer_flood_count >= flood_limit:
                        self._emit(f'🔴 {acc_name} hit flood limit – rotating account.')
                        break

                except (ChatWriteForbiddenError, ChatAdminRequiredError) as exc:
                    self._emit(f'❌ Cannot add to target: {exc}')
                    client.disconnect()
                    self._on_done and self._on_done(self._summary())
                    return

                except UserBannedInChannelError:
                    self._emit(f'🚫 {acc_name} is banned from target group – rotating.')
                    break

                except FloodWaitError as exc:
                    self._emit(f'⏳ FloodWait: waiting {exc.seconds}s')
                    time.sleep(exc.seconds)

                except Exception as exc:
                    self._emit(f'⚠ Error adding {raw}: {exc}')
                    self.other_errors += 1
                    index = i + 1

            try:
                client.disconnect()
            except Exception:
                pass

            self._emit(f'Session {acc_name} complete.')

            # Cooldown between accounts (skip after last)
            if acc_num < total_accs and not self._stop_event.is_set() and index < len(users):
                self._emit(f'⏳ Cooldown: {cooldown}s before next account...')
                for _ in range(cooldown):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

        self.current_index = index
        self._emit_stats()
        self._on_done and self._on_done(self._summary())
        log.success(
            f'Adding complete. Added: {self.added} | '
            f'Privacy: {self.privacy_errors} | '
            f'Flood: {self.flood_errors} | '
            f'Other: {self.other_errors}'
        )

    def _summary(self) -> dict:
        return {
            'added': self.added,
            'privacy': self.privacy_errors,
            'flood': self.flood_errors,
            'other': self.other_errors,
            'index': self.current_index,
        }
