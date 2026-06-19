"""SMS Sync — PC entry point.

Starts the WebSocket server, system tray icon, and notification system.
Receives SMS verification codes from the Android app and displays them
as Windows notifications + copies to clipboard.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import sys
import threading
from pathlib import Path

from .config.settings import get_or_create_token, load_config
from .network.lan_ip import get_lan_ip
from .notification.notifier import Notifier
from .server.relay_client import RelayHostClient
from .server.websocket_server import WebSocketServer
from .ui.pairing_dialog import PairingDialog
from .ui.tray_icon import ConnectionStatus, TrayIcon

# Configure logging
LOG_DIR = Path.home() / "AppData" / "Roaming" / "sms-sync"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "sms-sync.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("sms-sync")


class App:
    """Main application controller.

    Coordinates the WebSocket server, tray icon, QR dialog,
    and notification system.
    """

    def __init__(self, relay_url: str = ""):
        self._config = load_config()
        self._host = get_lan_ip()
        self._port = self._config.get("port", 9876)
        self._token = get_or_create_token()
        self._pc_name = self._host
        self._relay_url = relay_url
        self._use_relay = bool(relay_url)
        self._relay: RelayHostClient | None = None
        self._notifier = Notifier()

        self._server: WebSocketServer | None = None
        if not self._use_relay:
            self._server = WebSocketServer(self._host, self._port, self._token)
            self._server.on_code_received = self._notifier.notify_code
            self._server.on_client_connected = self._on_connected
            self._server.on_client_disconnected = self._on_disconnected
        self._tray = TrayIcon()
        self._dialog: PairingDialog | None = None

        self._loop: asyncio.AbstractEventLoop | None = None
        self._server_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        self._tray.on_show_qr = self._show_dialog
        self._tray.on_quit = self._shutdown

    def _on_room_code(self, code: str) -> None:
        """Callback when relay assigns a room code."""
        logger.info("Room code: %s", code)
        self._tray.set_status(ConnectionStatus.WAITING)

    def _on_relay_message(self, raw: str) -> None:
        """Handle message from relay (from Android)."""
        from .server.message_handler import parse_message
        msg = parse_message(raw)
        if msg and msg.type == "sms_code":
            self._notifier.notify_code(msg.code, msg.sender, msg.body, msg.timestamp)

    def _on_connected(self) -> None:
        logger.info("Android client connected")
        self._tray.set_status(ConnectionStatus.CONNECTED)

    def _on_disconnected(self) -> None:
        logger.info("Android client disconnected")
        self._tray.set_status(ConnectionStatus.WAITING)

    def _add_firewall_rule(self) -> None:
        """Add a Windows Firewall inbound rule for the WebSocket port."""
        rule_name = f"SMS Sync (Port {self._port})"
        try:
            # Just add the rule directly — netsh handles duplicates gracefully
            # Use shell=True to avoid encoding issues with Chinese Windows (GBK)
            cmd = (
                f'netsh advfirewall firewall add rule '
                f'name="{rule_name}" dir=in action=allow '
                f'protocol=TCP localport={self._port}'
            )
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                logger.info("Firewall rule ready: %s", rule_name)
            else:
                # "already exists" is fine, other errors are logged
                stderr = result.stderr.strip() if result.stderr else ""
                stdout = result.stdout.strip() if result.stdout else ""
                logger.info(
                    "Firewall rule result (code=%d): %s %s",
                    result.returncode, stdout, stderr,
                )
        except Exception as e:
            logger.warning("Failed to add firewall rule: %s", e)
            logger.warning(
                "Please manually allow port %d in Windows Firewall:\n"
                "   netsh advfirewall firewall add rule "
                "name=\"SMS Sync\" dir=in action=allow protocol=TCP localport=%d",
                self._port, self._port,
            )

    def _show_dialog(self) -> None:
        """Show the pairing dialog. Handles both LAN and matching-code modes."""
        try:
            if self._dialog is None or not self._dialog.is_showing():
                self._dialog = PairingDialog(
                    lan_host=self._host,
                    lan_port=self._port,
                    lan_token=self._token,
                    pc_name=self._server.pc_name if self._server else self._host,
                    relay_url=self._relay_url,
                )
                # Wire matching code callback
                self._dialog.on_start_relay = self._start_relay_with_code
            self._dialog.show()
        except Exception:
            logger.exception("Failed to show pairing dialog")

    def _start_relay_with_code(self, code: str) -> None:
        """Start relay connection with a pre-generated matching code."""
        if self._relay and self._relay.is_connected:
            return
        if self._server_thread and self._server_thread.is_alive():
            return
        if not self._relay_url:
            logger.error("No relay URL configured")
            if self._dialog:
                self._dialog.update_relay_status("error:未配置中继服务器地址")
            return

        self._relay = RelayHostClient(self._relay_url)
        self._relay.on_message = self._on_relay_message
        self._relay.on_connected = self._on_connected
        self._relay.on_disconnected = self._on_disconnected

        self._loop = asyncio.new_event_loop()

        def relay_loop():
            asyncio.set_event_loop(self._loop)
            try:
                # Connect with pre-generated code
                self._loop.run_until_complete(self._relay.start(code))
                # Update dialog: waiting for client
                if self._dialog:
                    self._dialog.update_relay_status("waiting")
                # Wait for client to join
                self._loop.run_until_complete(self._relay.wait_for_client())
                if self._dialog:
                    self._dialog.update_relay_status("connected")
                # Listen for messages
                self._loop.create_task(self._relay.listen())
                self._loop.run_forever()
            except Exception as e:
                logger.exception("Relay error")
                if self._dialog:
                    self._dialog.update_relay_status(f"error:连接失败 — {e}")
            finally:
                pending = asyncio.all_tasks(self._loop)
                for t in pending:
                    t.cancel()
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()

        self._server_thread = threading.Thread(target=relay_loop, daemon=True)
        self._server_thread.start()

        # Show connecting status
        if self._dialog:
            self._dialog.update_relay_status("connecting")

    def _shutdown(self) -> None:
        """Graceful shutdown sequence."""
        logger.info("Shutting down...")
        self._shutdown_event.set()

        # Stop the server
        if self._loop is not None:
            if self._use_relay and self._relay:
                future = asyncio.run_coroutine_threadsafe(self._relay.stop(), self._loop)
            elif self._server:
                future = asyncio.run_coroutine_threadsafe(self._server.stop(), self._loop)
            try:
                future.result(timeout=5)
            except Exception:
                pass

        # Close pairing dialog if open
        if self._dialog is not None:
            self._dialog.close()

        # Stop tray icon
        self._tray.stop()

        logger.info("Shutdown complete")

    def run(self) -> None:
        logger.info("Starting SMS Sync...")

        if self._use_relay:
            logger.info("Mode: RELAY — %s", self._relay_url)
            self._run_relay()
        else:
            logger.info("Mode: LOCAL — %s:%d", self._host, self._port)
            self._run_local()

    def _run_relay(self) -> None:
        """Relay mode: show pairing dialog with matching code option.

        The dialog generates a 6-digit matching code. When the user
        confirms, _start_relay_with_code() connects to the relay server
        and registers with that code.
        """
        logger.info("Mode: RELAY — %s", self._relay_url)
        self._tray.set_status(ConnectionStatus.WAITING)
        self._show_dialog()

        try:
            self._tray.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _run_local(self) -> None:
        """Local mode: start WebSocket server, show QR code."""
        logger.info("LAN IP: %s, Port: %d", self._host, self._port)
        logger.info("PC Name: %s", self._server.pc_name)

        self._add_firewall_rule()

        from .network.lan_ip import get_all_local_ips
        all_ips = get_all_local_ips()
        if len(all_ips) > 1:
            logger.info("All detected IPs: %s", ", ".join(all_ips))

        if self._host == "127.0.0.1":
            logger.warning("Could not detect LAN IP. Ensure you are on a network.")

        self._loop = asyncio.new_event_loop()

        def run_server_loop():
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._server.start())
                self._loop.run_forever()
            except Exception:
                logger.exception("Server loop error")
            finally:
                pending = asyncio.all_tasks(self._loop)
                for t in pending:
                    t.cancel()
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()

        self._server_thread = threading.Thread(target=run_server_loop, daemon=True)
        self._server_thread.start()

        self._tray.set_status(ConnectionStatus.WAITING)
        self._show_dialog()

        try:
            self._tray.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()


def main() -> None:
    relay_url = ""
    if "--relay" in sys.argv:
        idx = sys.argv.index("--relay")
        if idx + 1 < len(sys.argv):
            relay_url = sys.argv[idx + 1]
    app = App(relay_url=relay_url)
    app.run()


if __name__ == "__main__":
    main()
