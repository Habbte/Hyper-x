"""
HabteX Adder - Member Scraper

Features:
  - Public and private group support
  - Member activity filtering (all / online+recently / last week)
  - Resume from saved position (status.json)
  - Duplicate / multi-account cluster detection
  - Progress callbacks for UI integration
  - Saves to scraped.txt
"""

import json
import os
import threading
from typing import Callable, List, Optional

from telethon.sync import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError, FloodWaitError
from telethon.tl.types import (
    UserStatusOnline, UserStatusRecently,
    UserStatusLastWeek, UserStatusLastMonth,
)

from src.config import AppConfig
from src.utils.logger import AppLogger
from src.core.session_manager import list_sessions, session_path
from src.core.duplicate_detector import detect_duplicates, members_from_telethon

cfg = AppConfig()
log = AppLogger()

STATUS_FILE = 'status.json'
FILTER_ALL = 0
FILTER_ONLINE = 1
FILTER_LAST_WEEK = 2


# ── helpers ──────────────────────────────────────────────────────────────────

def _is_private_link(link: str) -> bool:
    return 'joinchat' in link or link.count('+') > 0

def _hash_from_link(link: str) -> str:
    return link.split('/')[-1].replace('+', '')

def _username_from_link(link: str) -> str:
    return link.split('/')[-1].lstrip('@')

def _passes_filter(user, filter_mode: int) -> bool:
    if filter_mode == FILTER_ALL:
        return True
    status = getattr(user, 'status', None)
    if filter_mode == FILTER_ONLINE:
        return isinstance(status, (UserStatusOnline, UserStatusRecently))
    if filter_mode == FILTER_LAST_WEEK:
        return isinstance(status, (UserStatusOnline, UserStatusRecently, UserStatusLastWeek))
    return True


def save_resume_status(source_link: str, index: int):
    with open(STATUS_FILE, 'w') as f:
        json.dump({'source': source_link, 'index': index}, f)

def load_resume_status() -> Optional[dict]:
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None

def clear_resume_status():
    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)

def clear_scraped():
    try:
        open(cfg.get('scraped_file', 'scraped.txt'), 'w').close()
        log.info('Scraped list cleared.')
    except Exception as e:
        log.error(f'Could not clear scraped file: {e}')

def load_scraped() -> List[str]:
    path = cfg.get('scraped_file', 'scraped.txt')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


# ── main scrape function ──────────────────────────────────────────────────────

def scrape_members(
    source_link: str,
    filter_mode: int = FILTER_ALL,
    resume: bool = False,
    on_progress: Callable[[str], None] = None,     # status message
    on_count: Callable[[int], None] = None,         # scraped count so far
    on_duplicate_report: Callable[[str], None] = None,  # text summary
    on_done: Callable[[int], None] = None,           # total saved
    on_error: Callable[[str], None] = None,
):
    """
    Run in a background thread.
    Uses the first available session for scraping.
    """
    def _emit(msg): on_progress and on_progress(msg)
    def _cnt(n): on_count and on_count(n)
    def _err(msg):
        log.error(msg)
        on_error and on_error(msg)

    def _run():
        sessions = list_sessions()
        if not sessions:
            _err('No accounts available. Add an account first.')
            return

        api_id = cfg.get('api_id')
        api_hash = cfg.get('api_hash')
        sess_path = session_path(sessions[0]).replace('.session', '')
        client = TelegramClient(sess_path, api_id, api_hash)

        try:
            client.start()
            _emit('Connected. Joining source group...')

            is_private = _is_private_link(source_link)

            try:
                if is_private:
                    h = _hash_from_link(source_link)
                    updates = client(ImportChatInviteRequest(h))
                    group_entity = updates.chats[0]
                else:
                    uname = _username_from_link(source_link)
                    try:
                        client(JoinChannelRequest(uname))
                    except UserAlreadyParticipantError:
                        pass
                    group_entity = client.get_entity(uname)
            except Exception as e:
                _err(f'Could not join source group: {e}')
                return

            _emit(f'Joined "{getattr(group_entity, "title", source_link)}". Scraping members...')

            raw_participants = list(client.iter_participants(group_entity))
            _emit(f'Fetched {len(raw_participants)} total members. Applying filter...')

            # Activity filter
            filtered = [u for u in raw_participants if _passes_filter(u, filter_mode)]
            _emit(f'After filter: {len(filtered)} members.')

            # Duplicate detection
            member_info_list = members_from_telethon(filtered)
            report = detect_duplicates(
                member_info_list,
                threshold=cfg.get('duplicate_threshold', 20),
                min_prefix_len=cfg.get('duplicate_min_prefix_len', 3),
            )
            log.info(f'Duplicate scan: {report.text_summary()}')
            if on_duplicate_report:
                on_duplicate_report(report.text_summary())

            # Save to scraped.txt
            usernames = []
            no_username_count = 0
            for u in filtered:
                if u.username:
                    usernames.append('@' + u.username)
                else:
                    no_username_count += 1

            scraped_file = cfg.get('scraped_file', 'scraped.txt')
            with open(scraped_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(usernames))

            _cnt(len(usernames))
            log.success(
                f'Scraped {len(usernames)} users with usernames '
                f'({no_username_count} had no username, skipped).'
            )
            _emit(
                f'Done! Saved {len(usernames)} users. '
                f'{no_username_count} skipped (no username).'
            )
            save_resume_status(source_link, len(usernames))
            on_done and on_done(len(usernames))

        except FloodWaitError as e:
            _err(f'Flood wait: please wait {e.seconds}s before retrying.')
        except Exception as e:
            _err(f'Scrape error: {e}')
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
