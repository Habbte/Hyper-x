"""
HabteX Adder - Unified Logger
Writes to file + keeps an in-memory buffer for the Logs screen.
Thread-safe. UI callbacks registered per-screen.
"""

import logging
import os
import threading
from datetime import datetime
from collections import deque


class AppLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, log_file='habtex.log', max_memory=500):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._init(log_file, max_memory)
                cls._instance = inst
        return cls._instance

    def _init(self, log_file, max_memory):
        self.log_file = log_file
        self._buffer = deque(maxlen=max_memory)
        self._callbacks = []  # UI listeners
        self._cb_lock = threading.Lock()

        # File handler
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        self._flogger = logging.getLogger('habtex')

    # ── public API ──────────────────────────────────────────────────────

    def info(self, msg):
        self._log('INFO', msg)

    def success(self, msg):
        self._log('SUCCESS', msg)

    def warn(self, msg):
        self._log('WARN', msg)

    def error(self, msg):
        self._log('ERROR', msg)

    def debug(self, msg):
        self._log('DEBUG', msg)

    def register_callback(self, fn):
        """Register a function to be called with (level, msg, timestamp) on each log."""
        with self._cb_lock:
            self._callbacks.append(fn)

    def unregister_callback(self, fn):
        with self._cb_lock:
            if fn in self._callbacks:
                self._callbacks.remove(fn)

    def get_recent(self, n=200):
        return list(self._buffer)[-n:]

    def clear(self):
        self._buffer.clear()
        try:
            open(self.log_file, 'w').close()
        except Exception:
            pass

    def export_path(self):
        return os.path.abspath(self.log_file)

    # ── internals ───────────────────────────────────────────────────────

    def _log(self, level, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        entry = {'level': level, 'msg': msg, 'ts': ts}
        self._buffer.append(entry)

        # Write to file
        getattr(self._flogger, level.lower() if level != 'SUCCESS' else 'info',
                self._flogger.info)(msg)

        # Notify UI listeners (they're responsible for threading back to main thread)
        with self._cb_lock:
            for cb in list(self._callbacks):
                try:
                    cb(level, msg, ts)
                except Exception:
                    pass

    # ── added_members.log ───────────────────────────────────────────────

    def log_added_member(self, username, target_group, added_by, added_log_file='added_members.log'):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'{ts} | {username} | {target_group} | {added_by}\n'
        try:
            with open(added_log_file, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass
