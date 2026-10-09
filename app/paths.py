"""Application data paths (per-OS, user-local, never bundled with the app)."""

import os
import sys


def app_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, "SecureVaultPM")
    os.makedirs(path, exist_ok=True)
    return path


def db_path() -> str:
    return os.path.join(app_data_dir(), "vault.db")
