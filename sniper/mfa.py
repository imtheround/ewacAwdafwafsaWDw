"""MFA ticket manager.

Uses SessionPool.mfa_probe() and .mfa_finish() for direct MFA operations.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .http2 import SessionPool
from .logger import log, log_error


class MfaManager:
    def __init__(self, pool: SessionPool, password: str) -> None:
        self._pool = pool
        self._password = password
        self._mfa_token: str | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def token(self) -> str | None:
        return self._mfa_token

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def refresh(self) -> None:
        try:
            data = await self._pool.mfa_probe()
            code = data.get("code", 0)

            if code == 200:
                return  # token still valid

            if code == 60003:
                mfa_info = data.get("mfa", {})
                ticket = mfa_info.get("ticket") if isinstance(mfa_info, dict) else None
                if ticket:
                    await self._finish_mfa(ticket)
        except Exception as exc:
            log_error(f"MFA refresh: {exc}")

    async def _finish_mfa(self, ticket: str) -> None:
        # Password is required to convert a ticket to an MFA token.
        # Without it, we can't claim — but detection still works.
        if not self._password:
            log("MFA ticket received but no password set — cannot finish MFA")
            return
        data = await self._pool.mfa_finish(ticket, self._password)
        if isinstance(data, dict) and data.get("token"):
            self._mfa_token = data["token"]
            log("MFA token refreshed")

    async def _loop(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(10)
