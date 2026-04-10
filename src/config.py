"""
HabteX Adder - App Configuration
All settings are user-editable from the Settings screen.
Defaults stored in config.json (gitignored).
"""

import json
import os

CONFIG_FILE = 'habtex_config.json'

DEFAULTS = {
    # Telegram API
    'api_id': 26908211,
    'api_hash': '6233bafd1d0ec5801b8c0e7ad0bf1aaa',

    # Folders & Files
    'sessions_folder': 'sessions',
    'scraped_file': 'scraped.txt',
    'log_file': 'habtex.log',
    'added_log_file': 'added_members.log',
    'status_file': 'status.json',

    # Adding behavior
    'max_adds_per_account': 60,
    'default_delay': 5,
    'account_cooldown': 40,
    'peer_flood_limit': 10,

    # Duplicate detection
    'duplicate_threshold': 20,      # flag if prefix repeats >= this many times
    'duplicate_min_prefix_len': 3,  # ignore prefixes shorter than this

    # UI
    'theme': 'Dark',
    'primary_palette': 'DeepPurple',
    'accent_palette': 'Teal',
}


class AppConfig:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def get(self, key, fallback=None):
        return self._data.get(key, DEFAULTS.get(key, fallback))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def get_all(self):
        return dict(self._data)
