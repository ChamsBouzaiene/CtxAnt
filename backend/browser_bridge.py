import asyncio
import json
import logging
import uuid
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

import pairing
from config import WS_PORT

logger = logging.getLogger(__name__)

# The single connected extension WebSocket (only one extension at a time)
_connection: Optional[WebSocketServerProtocol] = None
_pending: dict[str, asyncio.Future] = {}
_last_status: dict[str, str | bool | None] = {
    "connected": False,
    "message": "No browser session connected.",
}


def status_snapshot() -> dict[str, str | bool | None]:
    return dict(_last_status)


async def _handler(ws: WebSocketServerProtocol):
    global _connection

    # First message must be auth
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msg = json.loads(raw)
    except Exception:
        await ws.close(1008, "auth timeout")
        return

    expected = pairing.get_or_create_secret()
    if msg.get("type") != "auth" or msg.get("token") != expected:
        await ws.close(1008, "unauthorized")
        logger.warning("Extension connection rejected: bad auth token")
        return

    if _connection is not None and _connection is not ws and not _connection.closed:
        reason = "Another Chrome profile is already paired with CtxAnt."
        _last_status.update({"connected": True, "message": reason})
        logger.warning("Rejected secondary extension connection while another browser session is active")
        await ws.close(1013, reason)
        return

    _connection = ws
    _last_status.update({"connected": True, "message": "Browser extension connected."})
    logger.info("Browser extension connected")

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            cmd_id = msg.get("id")
            if cmd_id and cmd_id in _pending:
                fut = _pending.pop(cmd_id)
                if not fut.done():
                    fut.set_result(msg)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if _connection is ws:
            _connection = None
            for fut in list(_pending.values()):
                if not fut.done():
                    fut.set_result({"error": "Browser extension disconnected"})
            _pending.clear()
            _last_status.update({"connected": False, "message": "Browser extension disconnected."})
        logger.info("Browser extension disconnected")


async def send_command(cmd_type: str, **kwargs) -> dict:
    if _connection is None:
        return {"error": "Browser extension not connected. Load it in Chrome and make sure it shows Connected."}

    cmd_id = str(uuid.uuid4())
    payload = {"id": cmd_id, "type": cmd_type, **kwargs}

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[cmd_id] = fut

    try:
        await _connection.send(json.dumps(payload))
        result = await asyncio.wait_for(fut, timeout=30)
        return result
    except asyncio.TimeoutError:
        _pending.pop(cmd_id, None)
        return {"error": "Extension did not respond within 30s"}
    except Exception as e:
        _pending.pop(cmd_id, None)
        return {"error": str(e)}


async def start_server():
    logger.info(f"WebSocket server listening on ws://localhost:{WS_PORT}")
    return await websockets.serve(_handler, "localhost", WS_PORT)
