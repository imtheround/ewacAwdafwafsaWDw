"""Sniper engine — holds claim state, fires on drop events."""

from __future__ import annotations

import time
import asyncio
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .vanity import VanityOps

from .webhook import send_webhook, send_detection_webhook
from .util import now_ms
from .logger import log, log_error


class SniperEngine:
    sniper_enabled: bool = True
    has_successfully_sniped: bool = False
    request_in_flight: bool = False
    autokick_enabled: bool = False

    def __init__(
        self,
        client: Any,  # discord.Client
        vanity_ops: VanityOps,
        channel_id: str,
        server_id: str,
        webhook_url: str,
        user_to_dm: str,
    ) -> None:
        self._client = client
        self._ops = vanity_ops
        self._channel_id = channel_id
        self._server_id = server_id
        self._webhook_url = webhook_url
        self._user_to_dm = user_to_dm

    def attach(self) -> None:
        """Bind WebSocket backup handlers."""
        @self._client.event
        async def on_guild_update(before: Any, after: Any) -> None:
            await self._on_guild_update(before, after)

        @self._client.event
        async def on_guild_delete(guild: Any) -> None:
            await self._on_guild_delete(guild)

    async def on_drop(
        self,
        guild_id: str,
        code: str,
        detected_at: float,
        scout_label: str | None = None,
        source: str | None = None,
    ) -> None:
        """Called by detection sources when a vanity drops."""
        if not self.sniper_enabled or self.request_in_flight:
            return
        if self.has_successfully_sniped:
            log(f"Drop detected for `{code}` — but already sniped.")
            return

        await self._fire_claim(guild_id, code, detected_at, scout_label=scout_label, source=source)

    # ── internals ──────────────────────────────────────────────────

    async def _on_guild_update(self, old: Any, new: Any) -> None:
        old_code = getattr(old, "vanity_url_code", None)
        new_code = getattr(new, "vanity_url_code", None)
        if old_code == new_code or not old_code:
            return

        log(f"WS: Vanity changed — `{old_code}` dropped (now: `{new_code or 'none'}`)")
        await self.on_drop(str(new.id), old_code, time.perf_counter(), source="ws")

    async def _on_guild_delete(self, guild: Any) -> None:
        code = getattr(guild, "vanity_url_code", None)
        self._send_channel(f"*Vanity URL `{code}` was deleted at {now_ms()}*")
        if code:
            await self.on_drop(str(guild.id), code, time.perf_counter(), source="ws")

    async def _fire_claim(
        self,
        guild_id: str,
        code: str,
        detected_at: float,
        scout_label: str | None = None,
        source: str | None = None,
    ) -> None:
        self.request_in_flight = True
        try:
            now = time.perf_counter()
            detection_ms = round((now - detected_at) * 1000, 1)

            log(f"RACE: claiming `{code}`... (detection: {detection_ms}ms)")

            await send_detection_webhook(
                self._webhook_url,
                code=code,
                guild_id=guild_id,
                source=source or "unknown",
                scout_label=scout_label,
                detection_ms=detection_ms,
            )

            start = time.perf_counter()
            result = await self._ops.claim(code)
            end = time.perf_counter()
            claim_ms = round((end - start) * 1000)
            total_ms = round((end - detected_at) * 1000)
            speed_str = f"{result.speed:.3f}"

            if result.success:
                self.has_successfully_sniped = True
                scout = f" (scout: {scout_label})" if scout_label else ""
                log(f'CLAIMED "{code}" — claim: {speed_str}s, detection: {detection_ms}ms, total: {total_ms}ms{scout}')

                await send_webhook(self._webhook_url, {
                    "title": "Vanity Captured",
                    "description": f"```Successfully captured discord.gg/{code}```",
                    "color": 0x00FF00,
                    "fields": [
                        {"name": "Detection Speed", "value": f"`{detection_ms}ms`", "inline": True},
                        {"name": "Claim Time", "value": f"`{speed_str}s ({claim_ms}ms)`", "inline": True},
                        {"name": "Total (detect → claim)", "value": f"`{total_ms}ms ({total_ms / 1000:.3f}s)`", "inline": False},
                    ],
                })
                await self._dm_owner(code, speed_str, detection_ms, total_ms)
            else:
                log_error(f'FAILED to claim "{code}": {result.error}')
        except Exception as exc:
            log_error(f"Claim attempt threw: {exc}")
        finally:
            self.request_in_flight = False

    def _send_channel(self, msg: str) -> None:
        try:
            ch = self._client.get_channel(int(self._channel_id))
            if ch and hasattr(ch, "send"):
                asyncio.create_task(ch.send(msg))
        except Exception:
            pass

    async def _dm_owner(self, vanity: str, speed: str, detection_ms: float, total_ms: int) -> None:
        try:
            user = await self._client.fetch_user(int(self._user_to_dm))
            if user:
                await user.send(
                    f"🎯 **Vanity Snipe Successful!**\n\n"
                    f"▸ **Vanity:** `{vanity}`\n"
                    f"▸ **Detection:** `{detection_ms}ms`\n"
                    f"▸ **Claim:** `{speed}s`\n"
                    f"▸ **Total:** `{total_ms}ms ({total_ms / 1000:.3f}s)`\n"
                    f"✅ Successfully claimed for your server!"
                )
        except Exception as exc:
            log_error(f"Failed to DM owner: {exc}")
