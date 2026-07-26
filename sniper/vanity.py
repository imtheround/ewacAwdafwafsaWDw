"""Core vanity operations — probe, claim, delete.

All HTTP goes through CurlSession (curl_cffi with TLS fingerprint).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .http import CurlSession


@dataclass
class ClaimResult:
    success: bool
    code: str | None
    speed: float
    raw_speed: int
    error: str | None = None


class VanityOps:
    def __init__(self, http: CurlSession, mfa_token_getter: object, server_id: str) -> None:
        self._http = http
        self._mfa_getter = mfa_token_getter
        self._server_id = int(server_id)

    async def probe(self, guild_id: str) -> str | None:
        return await self._http.probe_vanity(int(guild_id))

    async def claim(self, vanity_code: str) -> ClaimResult:
        mfa_token: str | None = getattr(self._mfa_getter, "token", None)
        if not mfa_token:
            return ClaimResult(False, None, 0, 0, "No MFA token — password required to claim")

        start = time.perf_counter()
        try:
            data = await self._http.claim_vanity(self._server_id, vanity_code, mfa_token)
            elapsed = time.perf_counter() - start
            elapsed_ms = round(elapsed * 1000)

            code = data.get("code") if isinstance(data, dict) else vanity_code
            success = code == vanity_code

            return ClaimResult(
                success=success, code=code, speed=elapsed,
                raw_speed=elapsed_ms,
                error=None if success else "Server rejected claim",
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return ClaimResult(False, None, elapsed, round(elapsed * 1000), str(exc))

    async def delete(self) -> ClaimResult:
        mfa_token: str | None = getattr(self._mfa_getter, "token", None)
        if not mfa_token:
            return ClaimResult(False, None, 0, 0, "No MFA token available")

        start = time.perf_counter()
        try:
            await self._http.delete_vanity(self._server_id, mfa_token)
            elapsed = time.perf_counter() - start
            return ClaimResult(True, None, elapsed, round(elapsed * 1000))
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return ClaimResult(False, None, elapsed, round(elapsed * 1000), str(exc))
