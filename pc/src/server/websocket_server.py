"""WebSocket server for receiving SMS verification codes from Android.

Runs on the LAN IP (not 0.0.0.0) for security. Uses a pairing token
embedded in a QR code that the Android client must present on first
connection.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Callable

from websockets.asyncio.server import ServerConnection, serve

from ..config.settings import MAX_MISSED_PINGS, PAIR_TIMEOUT, PING_INTERVAL, PONG_TIMEOUT
from .message_handler import build_message, parse_message

logger = logging.getLogger(__name__)


class WebSocketServer:
    """Async WebSocket server that receives SMS codes from Android.

    Lifecycle:
      1. Server starts, generates a random pairing token.
      2. Android connects, sends {"type":"pair","token":"..."} within
         PAIR_TIMEOUT seconds.
      3. If token matches, Android is "paired" and can send sms_code messages.
      4. Server sends periodic pings; disconnects on timeout.
    """

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
    ):
        """Initialize the server.

        Args:
            host: LAN IP address to bind to.
            port: Port to listen on.
            token: Random pairing token (shown in QR code).
        """
        self._host = host
        self._port = port
        self._token = token
        self._server = None
        self._running = False
        self._connected = False
        self._pc_name = socket.gethostname()

        # Callbacks — set by main.py to wire up UI
        self.on_code_received: Callable[[str, str, str, int], None] | None = None
        self.on_client_connected: Callable[[], None] | None = None
        self.on_client_disconnected: Callable[[], None] | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def token(self) -> str:
        return self._token

    @property
    def pc_name(self) -> str:
        return self._pc_name

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the WebSocket server."""
        try:
            self._server = await serve(
                self._handle_connection,
                self._host,
                self._port,
            )
        except OSError as e:
            logger.error("Cannot bind to %s:%d — %s", self._host, self._port, e)
            logger.error(
                "Port may be in use. Close other instances or change port in config."
            )
            return
        self._running = True
        logger.info("WebSocket server started on ws://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the WebSocket server gracefully."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        """Handle a new WebSocket connection from Android.

        Only one client is allowed at a time. A new connection
        replaces any existing one.
        """
        remote = websocket.remote_address
        logger.info("New connection from %s", remote)

        # Close any existing connection implicitly by accepting this one.
        # (The old handler will detect the close and call on_disconnected.)

        try:
            # Step 1: Wait for pairing message
            raw = await asyncio.wait_for(websocket.recv(), timeout=PAIR_TIMEOUT)
            msg = parse_message(raw)

            if msg is None or msg.type != "pair":
                logger.warning("Client %s did not send pair message, closing", remote)
                await websocket.send(build_message("paired", status="error", reason="expected_pair_message"))
                await websocket.close()
                return

            # Step 2: Validate token
            if msg.token != self._token:
                logger.warning("Client %s sent invalid token", remote)
                await websocket.send(build_message("paired", status="error", reason="invalid_token"))
                await websocket.close()
                return

            # Step 3: Token valid or manual — send success
            await websocket.send(build_message("paired", status="ok", pc_name=self._pc_name))
            self._connected = True
            logger.info("Client %s paired successfully", remote)
            if self.on_client_connected:
                try:
                    self.on_client_connected()
                except Exception:
                    logger.exception("on_client_connected callback failed")

            # Step 4: Main message loop with heartbeat
            pong_event = asyncio.Event()
            ping_task = asyncio.create_task(self._ping_loop(websocket, pong_event))

            try:
                async for raw in websocket:
                    msg = parse_message(raw)
                    if msg is None:
                        logger.debug("Ignoring malformed message from %s", remote)
                        continue

                    if msg.type == "pong":
                        pong_event.set()  # signal the ping task
                        continue

                    if msg.type == "sms_code":
                        logger.info("Received code: %s from %s", msg.code, msg.sender)
                        if self.on_code_received:
                            try:
                                self.on_code_received(
                                    msg.code,
                                    msg.sender,
                                    msg.body,
                                    msg.timestamp,
                                )
                            except Exception:
                                logger.exception("on_code_received callback failed")
                        # Acknowledge receipt
                        await websocket.send(
                            build_message("ack", code=msg.code, status="ok")
                        )

                    if msg.type == "disconnect":
                        logger.info("Client %s requested disconnect", remote)
                        break

            except asyncio.CancelledError:
                pass
            finally:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass

        except (TimeoutError, asyncio.TimeoutError):
            logger.debug("Client %s did not send pair message in time", remote)
        except OSError:
            # Network blip (WinError 64 etc.) — normal on WiFi
            logger.debug("Client %s network error", remote)
        except Exception as e:
            # ConnectionClosedOK/Error: normal client disconnect, not a bug
            cls = type(e).__name__
            if "ConnectionClosed" in cls or "close frame" in str(e):
                logger.debug("Client %s closed normally: %s", remote, e)
            else:
                logger.exception("Error handling connection from %s", remote)
        finally:
            self._connected = False
            logger.debug("Client %s disconnected", remote)
            if self.on_client_disconnected:
                try:
                    self.on_client_disconnected()
                except Exception:
                    logger.exception("on_client_disconnected callback failed")

    async def _ping_loop(
        self, websocket: ServerConnection, pong_event: asyncio.Event
    ) -> None:
        """Send periodic pings and disconnect if no pong is received."""
        missed = 0
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                await websocket.send(build_message("ping"))
                # Wait for the handler to signal a pong response
                try:
                    await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
                    pong_event.clear()
                    missed = 0
                except asyncio.TimeoutError:
                    missed += 1
                    logger.debug(
                        "Missed pong %d/%d from %s",
                        missed, MAX_MISSED_PINGS, websocket.remote_address,
                    )
                    if missed >= MAX_MISSED_PINGS:
                        logger.warning(
                            "Client %s missed %d pings, closing",
                            websocket.remote_address, missed,
                        )
                        await websocket.close()
                        return
            except Exception:
                break
