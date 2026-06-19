"""Desktop notification and clipboard integration.

Shows Windows native toast with sender as title, code as body,
and a Copy button.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

import pyperclip
from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastButton,
    ToastDuration,
    ToastActivatedEventArgs,
)

logger = logging.getLogger(__name__)


class Notifier:

    def __init__(self, app_name: str = "SMS Sync"):
        self._app_name = app_name
        self._toaster = InteractableWindowsToaster(app_name)
        self._toaster.on_activated = self._on_activated
        self._lock = threading.Lock()
        self._last_code: str = ""
        self._last_code_time: datetime | None = None

    @property
    def last_code(self) -> str:
        return self._last_code

    @property
    def last_code_time(self) -> datetime | None:
        return self._last_code_time

    def notify_code(self, code: str, sender: str, body: str = "", timestamp: int = 0) -> None:
        with self._lock:
            self._last_code = code
            self._last_code_time = datetime.now()

        try:
            pyperclip.copy(code)
            logger.info("Code '%s' copied", code)
        except Exception:
            logger.exception("Clipboard failed")

        try:
            toast = Toast()
            toast.attribution_text = sender
            toast.text_fields = [code]
            toast.duration = ToastDuration.Short
            toast.AddAction(ToastButton("复制", arguments=code))
            self._toaster.show_toast(toast)
        except Exception:
            logger.exception("Toast failed")

    def _on_activated(self, args: ToastActivatedEventArgs) -> None:
        try:
            if args.arguments:
                pyperclip.copy(str(args.arguments))
        except Exception:
            pass
