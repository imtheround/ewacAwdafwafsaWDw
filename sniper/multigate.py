"""Proxyless multi-gateway detection via raw WebSocket connections.

Opens N concurrent raw WebSocket connections to Discord's gateway.
Each connection independently receives GUILD_CREATE / GUILD_UPDATE events.
The first one to detect a change fires the callback.

No discord.py dependency — pure `websockets` library.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from .logger import log, log_error

GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"


@dataclass
class DropEvent:
    guild_id: str
    code: str
    detected_at: float
    source: str


DropCallback = Callable[[DropEvent], None]


class MultiGatewayEngine:
    def __init__(self, token: str, count: int = 5) -> None:
        self._token = token
        self._count = max(2, min(10, count))
        self._enabled = False
        self._active_count = 0
        self._on_drop: DropCallback | None = None
        self._guild_vanities: dict[str, str | None] = {}

    @property
    def ws_count(self) -> int:
        return self._active_count

    def on_vanity_drop(self, cb: DropCallback) -> None:
        self._on_drop = cb

    async def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        log(f"RawWS multi-gateway: starting {self._count} connections...")

        tasks = []
        for i in range(self._count):
            tasks.append(asyncio.create_task(self._start_one(i + 1)))

        await asyncio.gather(*tasks, return_exceptions=True)
        log(f"RawWS multi-gateway: {self._active_count}/{self._count} active.")

    def destroy(self) -> None:
        self._enabled = False
        self._guild_vanities.clear()
        self._active_count = 0

    async def _heartbeat(self, ws: Any, interval_s: float) -> None:
        while self._enabled:
            await asyncio.sleep(interval_s)
            try:
                await ws.send(json.dumps({"op": 1, "d": None}))
            except Exception:
                break

    async def _start_one(self, idx: int) -> None:
        import websockets
        try:
            async with websockets.connect(GATEWAY_URL) as ws:
                hello = json.loads(await ws.recv())
                if hello.get("op") != 10:
                    return
                hb_interval = hello["d"]["heartbeat_interval"] / 1000.0

                hb_task = asyncio.create_task(self._heartbeat(ws, hb_interval))

                await ws.send(json.dumps({
                    "op": 2,
                    "d": {
                        "token": self._token,
                        "intents": 0,
                        "properties": {
                            "os": "Windows",
                            "browser": "Discord Client",
                            "device": "discord.js-selfbot-v13",
                        },
                    },
                }))

                ready = json.loads(await ws.recv())
                if ready.get("op") != 0:
                    hb_task.cancel()
                    return

                self._active_count += 1
                log(f"[raw-gw-{idx}] Connected")

                try:
                    async for raw in ws:
                        if not self._enabled:
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if msg.get("op") != 0:
                            continue
                        t = msg.get("t")
                        d = msg.get("d", {})
                        if t == "GUILD_CREATE":
                            self._on_guild_create(idx, d)
                        elif t == "GUILD_UPDATE":
                            self._on_guild_update(idx, d)
                        elif t == "GUILD_DELETE":
                            self._on_guild_delete(idx, d)
                finally:
                    hb_task.cancel()

        except Exception as exc:
            log_error(f"[raw-gw-{idx}] Connection error: {exc}")

    def _on_guild_create(self, idx: int, data: dict[str, Any]) -> None:
        guild_id = data.get("id", "0")
        code = data.get("vanity_url_code")
        self._guild_vanities[guild_id] = code
        if code:
            log(f"[raw-gw-{idx}] Guild {guild_id} vanity: `{code}`")

    def _on_guild_update(self, idx: int, data: dict[str, Any]) -> None:
        guild_id = data.get("id", "0")
        new_code = data.get("vanity_url_code")
        old_code = self._guild_vanities.get(guild_id)

        if old_code is not None and old_code != new_code:
            source = f"raw-gw-{idx}"
            log(f"{source}: `{old_code}` \u2192 `{new_code or 'none'}` (guild: {guild_id})")
            if self._on_drop:
                self._on_drop(DropEvent(
                    guild_id=guild_id,
                    code=old_code,
                    detected_at=time.perf_counter(),
                    source=source,
                ))

        self._guild_vanities[guild_id] = new_code

    def _on_guild_delete(self, idx: int, data: dict[str, Any]) -> None:
        guild_id = data.get("id", "0")
        old_code = self._guild_vanities.pop(guild_id, None)
        if old_code:
            source = f"raw-gw-{idx}"
            log(f"{source}: guild deleted \u2014 `{old_code}` released (guild: {guild_id})")
            if self._on_drop:
                self._on_drop(DropEvent(
                    guild_id=guild_id,
                    code=old_code,
                    detected_at=time.perf_counter(),
                    source=source,
                ))
