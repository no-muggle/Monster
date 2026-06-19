"""SMS Sync Relay Server — deploy on a public VPS.

Pairs PC (host) with Android (client) via a 6-digit room code.
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
WAIT_TIMEOUT = 300   # host waits 5 min for client to join
IDLE_TIMEOUT = 3600  # connected room idle timeout (1 hour, no practical limit)
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
                msg = await asyncio.wait_for(self.client.recv(), timeout=IDLE_TIMEOUT)
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
            await self._handle_host(ws, data)
        elif role == "client":
            await self._handle_client(ws, data.get("room", ""))

    async def _handle_host(self, ws: ServerConnection, data: dict):
        # Accept optional code from host, otherwise generate 6-digit code
        host_code = data.get("code", "")
        if host_code and len(host_code) == 6 and host_code.isdigit():
            code = host_code
            if code in self.rooms and self.rooms[code].host is not None:
                import json
                await ws.send(json.dumps({"type": "error", "reason": "code_taken"}))
                await ws.close()
                return
        else:
            while True:
                code = f"{random.randint(100000, 999999):06d}"
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

        # Wait for client to join (with timeout)
        try:
            waited = 0
            while not room.client:
                await asyncio.sleep(1)
                waited += 1
                if not room.host:  # host disconnected
                    logger.info("Room %s: host left before client joined", code)
                    return
                if waited >= WAIT_TIMEOUT:
                    logger.info("Room %s: no client joined within %ds, closing", code, WAIT_TIMEOUT)
                    await ws.send(json.dumps({"type": "error", "reason": "timeout"}))
                    return
            # Client joined — send confirmation
            await ws.send(json.dumps({"type": "client_joined"}))
            # Forward client → host (no idle timeout for connected rooms)
            await room.forward()
        except Exception:
            logger.info("Room %s: host disconnected", code)
        finally:
            await room.cleanup()

    async def _handle_client(self, ws: ServerConnection, room_code: str):
        import json
        room = self.rooms.get(room_code)
        if not room or not room.host:
            await ws.send(json.dumps({"type": "error", "reason": "room_not_found"}))
            await ws.close()
            return

        room.client = ws
        self.client_to_room[ws] = room
        logger.info("Room %s: client joined", room_code)

        # Send confirmation so Android knows it's connected
        await ws.send(json.dumps({"type": "joined", "code": room_code}))

        # Forward host → client
        try:
            while True:
                msg = await asyncio.wait_for(room.host.recv(), timeout=IDLE_TIMEOUT)
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
