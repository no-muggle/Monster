"""SMS Sync Relay Server — deploy on a public VPS.

Pairs PC (host) with Android (client) via a 4-digit room code.
Forwards all WebSocket messages between paired connections.
"""

import asyncio
import logging
import random
import secrets
import sys
from collections.abc import Callable

from websockets.asyncio.server import ServerConnection, serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("relay")
ALIVE_TIMEOUT = 120  # kill room after 2 min idle
PORT = 8765


class Room:
    def __init__(self, code: str):
        self.code = code
        self.host: ServerConnection | None = None
        self.client: ServerConnection | None = None
        self.host_token = secrets.token_hex(8)

    @property
    def ready(self) -> bool:
        return self.host is not None and self.client is not None

    async def forward(self):
        """Bidirectional forward between host and client."""
        if not self.host or not self.client:
            return
        try:
            while True:
                msg = await asyncio.wait_for(self.client.recv(), timeout=ALIVE_TIMEOUT)
                await self.host.send(msg)
        except (TimeoutError, asyncio.CancelledError):
            pass
        except Exception:
            logger.info("Room %s: client disconnected", self.code)
        finally:
            await self.cleanup()

    async def cleanup(self):
        try:
            if self.host: await self.host.close()
        except Exception: pass
        try:
            if self.client: await self.client.close()
        except Exception: pass
        self.host = None
        self.client = None


class RelayServer:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.host_to_room: dict[ServerConnection, Room] = {}
        self.client_to_room: dict[ServerConnection, Room] = {}

    async def handle(self, ws: ServerConnection) -> None:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
        except TimeoutError:
            await ws.close()
            return

        # First message: {"type":"host"} or {"type":"client","room":"1234"}
        import json
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await ws.close()
            return

        role = data.get("type", "")
        if role == "host":
            await self._handle_host(ws)
        elif role == "client":
            await self._handle_client(ws, data.get("room", ""))

    async def _handle_host(self, ws: ServerConnection):
        # Generate unique room code
        while True:
            code = f"{random.randint(0, 9999):04d}"
            if code not in self.rooms or self.rooms[code].host is None:
                break

        room = Room(code)
        room.host = ws
        self.rooms[code] = room
        self.host_to_room[ws] = room

        # Send room code to PC
        import json
        await ws.send(json.dumps({"type": "room_code", "code": code}))
        logger.info("Room %s: host connected", code)

        # Wait for client to join
        try:
            while not room.client:
                await asyncio.sleep(1)
                if not room.host:  # host disconnected
                    logger.info("Room %s: host left before client joined", code)
                    return
            # Client joined — send confirmation
            await ws.send(json.dumps({"type": "client_joined"}))
            # Forward client → host
            await room.forward()
        except Exception:
            logger.info("Room %s: host disconnected", code)
        finally:
            await room.cleanup()

    async def _handle_client(self, ws: ServerConnection, room_code: str):
        room = self.rooms.get(room_code)
        if not room or not room.host:
            import json
            await ws.send(json.dumps({"type": "error", "reason": "room_not_found"}))
            await ws.close()
            return

        room.client = ws
        self.client_to_room[ws] = room
        logger.info("Room %s: client joined", room_code)

        # Forward host → client
        try:
            while True:
                msg = await asyncio.wait_for(room.host.recv(), timeout=ALIVE_TIMEOUT)
                await ws.send(msg)
        except (TimeoutError, asyncio.CancelledError):
            pass
        except Exception:
            logger.info("Room %s: connection closed", room_code)
        finally:
            await room.cleanup()


async def main():
    server = RelayServer()
    logger.info("Relay server starting on port %d", PORT)
    async with serve(server.handle, "0.0.0.0", PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
