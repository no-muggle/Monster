"""Message parsing and validation for the WebSocket protocol.

All messages are UTF-8 JSON with a "type" field that determines
how the rest of the message is processed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Known message types from Android
KNOWN_TYPES = {"pair", "sms_code", "pong", "disconnect"}

# Required fields for each message type
REQUIRED_FIELDS: dict[str, set[str]] = {
    "pair": {"token"},
    "sms_code": {"code", "sender", "body", "timestamp"},
    "pong": set(),
    "disconnect": set(),
}


@dataclass
class ParsedMessage:
    """A validated and parsed message from the Android client."""
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    @property
    def code(self) -> str:
        return self.data.get("code", "")

    @property
    def sender(self) -> str:
        return self.data.get("sender", "")

    @property
    def body(self) -> str:
        return self.data.get("body", "")

    @property
    def timestamp(self) -> int:
        return self.data.get("timestamp", 0)

    @property
    def token(self) -> str:
        return self.data.get("token", "")


def parse_message(raw: str) -> ParsedMessage | None:
    """Parse a raw JSON string into a validated ParsedMessage.

    Args:
        raw: The raw JSON string received from the WebSocket.

    Returns:
        A ParsedMessage if valid, or None if the message is malformed.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(obj, dict):
        return None

    msg_type = obj.get("type", "")
    if msg_type not in KNOWN_TYPES:
        return None

    # Check required fields
    required = REQUIRED_FIELDS.get(msg_type, set())
    missing = required - set(obj.keys())
    if missing:
        return None

    return ParsedMessage(type=msg_type, data=obj, raw=raw)


def build_message(msg_type: str, **kwargs: Any) -> str:
    """Build a JSON message string for sending to Android.

    Args:
        msg_type: The message type (must be a known PC→Android type).
        **kwargs: Additional fields to include in the message.

    Returns:
        A JSON string with the "type" field set.
    """
    payload = {"type": msg_type, **kwargs}
    return json.dumps(payload, ensure_ascii=False)
