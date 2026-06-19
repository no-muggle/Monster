"""Relay mode: connects to a public relay server (VPS) as host.

Shows a 6-digit room code that the Android user enters to pair.
"""

from __future__ import annotations

import asyncio
import json
import logging

from websockets.asyncio.client import connect

logger = logging.getLogger(__name__)


class RelayHostClient:
    """Connects to relay server as host, receives a room code,
    and relays messages between the relay and the local handler."""

    def __init__(self, relay_url: str):
        self._relay_url = relay_url
        self._room_code: str | None = None
        self._ws = None
        self._running = False
        self.on_code_received = None  # (code) callback
        self.on_message = None        # (msg) callback
        self.on_connected = None
        self.on_disconnected = None

    @property
    def room_code(self) -> str | None:
        return self._room_code

    @property
    def is_connected(self) -> bool:
        return self._running and self._ws is not None

    async def start(self, code: str):
        """Connect to relay and register with a pre-generated room code.

        Args:
            code: 6-digit room code generated locally.
        """
        self._room_code = code
        self._ws = await connect(self._relay_url)
        # Register as host with pre-generated code
        await self._ws.send(json.dumps({"type": "host", "code": code}))
        # Wait for confirmation
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
        data = json.loads(raw)
        if data.get("type") == "error":
            raise Exception(f"Relay rejected code: {data.get('reason')}")
        if data.get("type") != "room_code":
            raise Exception(f"Expected room_code, got {data}")
        self._running = True
        logger.info("Relay host connected, room: %s", self._room_code)
        if self.on_code_received:
            self.on_code_received(self._room_code)
        return self._room_code

    async def wait_for_client(self):
        """Wait for Android client to join.

        Returns:
            True once the client joins.

        Raises:
            Exception: If the relay sends an error (e.g. timeout) or an
                       unexpected message type.
        """
        raw = await self._ws.recv()
        data = json.loads(raw)
        msg_type = data.get("type", "")

        if msg_type == "error":
            reason = data.get("reason", "unknown")
            raise Exception(f"Relay error: {reason}")

        if msg_type == "client_joined":
            logger.info("Client joined room %s", self._room_code)
            if self.on_connected:
                self.on_connected()
            return True

        raise Exception(f"Unexpected message while waiting for client: {msg_type}")

    async def listen(self):
        """Listen for messages from relay (from Android) and forward."""
        try:
            async for raw in self._ws:
                if self.on_message:
                    self.on_message(raw)
        finally:
            self._running = False
            if self.on_disconnected:
                self.on_disconnected()

    async def send(self, msg: str):
        """Send a message to the relay (to Android)."""
        if self._ws:
            await self._ws.send(msg)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
