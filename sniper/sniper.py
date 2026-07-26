"""Sniper engine — holds claim state, fires on drop events."""

from __future__ import annotations

import time
from typing import Any

from .http import CurlSession
from .vanity import VanityOps
from .webhook import send_webhook, send_detection_webhook
from .logger import log, log_error


class SniperEngine:
    sniper_enabled: bool = True
    has_successfully_sniped: bool = False
    request_in_flight: bool = False

    def __init__(
        self,
        vanity_ops: VanityOps,
        channel_id: str,
        webhook_url: str,
        http: CurlSession | None = None,
    ) -> None:
        self._ops = vanity_ops
        self._channel_id = channel_id
        self._webhook_url = webhook_url
        self._http = http

    async def on_drop(
        self,
        guild_id: str,
        code: str,
        detected_at: float,
        scout_label: str | None = None,
        source: str | None = None,
    ) -> None:
        if not self.sniper_enabled or self.request_in_flight:
            return
        if self.has_successfully_sniped:
            log(f"Drop detected for `{code}` — but already sniped.")
            return

        await self._fire_claim(guild_id, code, detected_at, scout_label=scout_label, source=source)

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
                        {"name": "Total (detect \u2192 claim)", "value": f"`{total_ms}ms ({total_ms / 1000:.3f}s)`", "inline": False},
                    ],
                })
                if self._http:
                    msg = (
                        f"**Vanity Snipe Successful!**\n"
                        f"\u25b8 **Vanity:** `{code}`\n"
                        f"\u25b8 **Detection:** `{detection_ms}ms`\n"
                        f"\u25b8 **Claim:** `{speed_str}s`\n"
                        f"\u25b8 **Total:** `{total_ms}ms ({total_ms / 1000:.3f}s)`"
                    )
                    await self._http.send_message(int(self._channel_id), msg)
            else:
                log_error(f'FAILED to claim "{code}": {result.error}')
        except Exception as exc:
            log_error(f"Claim attempt threw: {exc}")
        finally:
            self.request_in_flight = False
