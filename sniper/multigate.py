"""Proxyless multi-gateway detection.

Opens N concurrent WebSocket connections to Discord's gateway on a single
token. Each connection receives `guildUpdate` events independently.
The first one to fire wins.

Zero HTTP traffic during monitoring — pure WebSocket push.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable

from discord import Client as DiscordClient

from .logger import log, log_error


@dataclass
class DropEvent:
    guild_id: str
    code: str
    detected_at: float  # time.perf_counter()
    source: str  # e.g. "gw-3"


DropCallback = Callable[[DropEvent], None]


class MultiGatewayEngine:
    def __init__(self, token: str, count: int = 5) -> None:
        self._token = token
        self._count = max(2, min(10, count))
        self._clients: list[DiscordClient] = []
        self._enabled = False
        self._active_count = 0
        self._on_drop: DropCallback | None = None

    @property
    def ws_count(self) -> int:
        return self._active_count

    def on_vanity_drop(self, cb: DropCallback) -> None:
        self._on_drop = cb

    async def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        log(f"Multi-gateway: starting {self._count} WebSocket connections...")

        tasks = []
        for i in range(self._count):
            tasks.append(asyncio.create_task(self._start_one(i + 1)))

        await asyncio.gather(*tasks, return_exceptions=True)
        log(f"Multi-gateway: {self._active_count}/{self._count} connections active.")

    def destroy(self) -> None:
        self._enabled = False
        for client in self._clients:
            try:
                asyncio.create_task(client.close())
            except Exception:
                pass
        self._clients.clear()
        self._active_count = 0

    async def _start_one(self, idx: int) -> None:
        client = DiscordClient()

        @client.event
        async def on_guild_update(before: Any, after: Any) -> None:
            if not self._enabled:
                return
            old_code = getattr(before, "vanity_url_code", None)
            new_code = getattr(after, "vanity_url_code", None)
            if old_code == new_code or not old_code:
                return

            source = f"gw-{idx}"
            log(f"{source}: `{old_code}` → `{new_code or 'none'}` (guild: {after.id})")
            if self._on_drop:
                self._on_drop(DropEvent(
                    guild_id=str(after.id),
                    code=old_code,
                    detected_at=time.perf_counter(),
                    source=source,
                ))

        @client.event
        async def on_guild_delete(guild: Any) -> None:
            if not self._enabled:
                return
            code = getattr(guild, "vanity_url_code", None)
            if not code:
                return
            source = f"gw-{idx}"
            log(f"{source}: guild deleted — `{code}` released (guild: {guild.id})")
            if self._on_drop:
                self._on_drop(DropEvent(
                    guild_id=str(guild.id),
                    code=code,
                    detected_at=time.perf_counter(),
                    source=source,
                ))

        self._clients.append(client)
        try:
            await client.start(self._token)  # no 'bot=False' — this isn't discord.py
            self._active_count += 1
            log(f"[gateway-{idx}] Connected as {client.user}")
        except Exception as exc:
            log_error(f"[gateway-{idx}] Login failed: {exc}")
