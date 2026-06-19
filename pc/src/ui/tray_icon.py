"""System tray icon for the SMS Sync application.

Provides a tray icon with context menu for controlling the app:
- Show QR code for pairing
- View connection status
- Quit the application
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection state for the tray icon color."""
    STOPPED = "stopped"      # red — server not running
    WAITING = "waiting"      # yellow — server running, no client
    CONNECTED = "connected"  # green — Android paired


def _make_icon_image(color: str, size: int = 64) -> Image.Image:
    """Generate a simple colored circle icon.

    Args:
        color: The fill color ('green', 'yellow', 'red', or hex).
        size: Image dimensions (square).

    Returns:
        A PIL Image of a colored circle.
    """
    color_map = {
        "stopped": "#F44336",   # red
        "waiting": "#FF9800",   # yellow
        "connected": "#4CAF50", # green
    }
    fill = color_map.get(color, color)

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    padding = 8
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=fill,
        outline="#333333",
        width=2,
    )
    return image


class TrayIcon:
    """System tray icon with status indication and menu."""

    _APP_NAME = "SMS Sync"
    _ICON_SIZE = 64

    def __init__(self):
        self._status = ConnectionStatus.STOPPED
        self._icon: Icon | None = None
        self._stop_event = threading.Event()

        # Callbacks set by main.py
        self.on_show_qr: Callable[[], None] | None = None
        self.on_quit: Callable[[], None] | None = None

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    def set_status(self, status: ConnectionStatus) -> None:
        """Update the tray icon color to reflect connection status.

        Args:
            status: The new connection status.
        """
        self._status = status
        if self._icon is not None:
            try:
                self._icon.icon = _make_icon_image(status.value, self._ICON_SIZE)
            except Exception:
                pass

    def _build_menu(self) -> Menu:
        """Build the tray context menu."""
        status_texts = {
            ConnectionStatus.STOPPED: "状态: 未启动",
            ConnectionStatus.WAITING: "状态: 等待连接...",
            ConnectionStatus.CONNECTED: "状态: 已连接 ✓",
        }
        status_text = status_texts.get(self._status, "状态: 未知")

        return Menu(
            MenuItem(
                status_text,
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "显示配对窗口",
                lambda: self.on_show_qr() if self.on_show_qr else None,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "退出",
                lambda: self.on_quit() if self.on_quit else None,
            ),
        )

    def run(self) -> None:
        """Run the tray icon (blocking — use in a thread)."""
        image = _make_icon_image(self._status.value, self._ICON_SIZE)
        self._icon = Icon(
            self._APP_NAME,
            image,
            self._APP_NAME,
            menu=self._build_menu(),
        )
        logger.info("Tray icon started")
        self._icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        self._stop_event.set()
        logger.info("Tray icon stopped")
