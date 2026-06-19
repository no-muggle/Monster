"""Application configuration and constants."""

import json
import os
import secrets
from pathlib import Path

# Default server port
DEFAULT_PORT = 9876

# Pairing token length in bytes (x2 for hex chars)
TOKEN_BYTES = 16  # -> 32 hex characters

# Heartbeat interval and timeout (seconds)
PING_INTERVAL = 30
PONG_TIMEOUT = 10  # must receive pong within this time
MAX_MISSED_PINGS = 3  # disconnect after this many missed pongs

# Pairing window: Android must send pair message within this time (seconds)
PAIR_TIMEOUT = 10

# Config file location
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "sms-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default settings
DEFAULT_CONFIG: dict = {
    "port": DEFAULT_PORT,
    "notification_duration": 7,  # seconds
    "auto_start": False,
    "store_sms_body": False,  # keep full SMS body in history?
}


def ensure_config_dir() -> None:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from disk, merging with defaults.

    Returns:
        Configuration dictionary with all keys filled.
    """
    ensure_config_dir()
    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict) -> None:
    """Save configuration to disk.

    Args:
        config: Configuration dictionary to save.
    """
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def generate_token() -> str:
    """Generate a random pairing token.

    Returns:
        32-character hex string.
    """
    return secrets.token_hex(TOKEN_BYTES)


def get_or_create_token() -> str:
    """Get the saved pairing token, or create + save a new one.

    Token persists across restarts so Android doesn't need to re-scan QR.
    """
    ensure_config_dir()
    token_file = CONFIG_DIR / "pairing_token.txt"
    if token_file.exists():
        token = token_file.read_text().strip()
        if len(token) == TOKEN_BYTES * 2:
            return token
    token = generate_token()
    token_file.write_text(token)
    return token
