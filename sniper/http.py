"""HTTP pool using curl_cffi with TLS fingerprint impersonation.

Bypasses Cloudflare by mimicking Chrome 110's TLS fingerprint.
All HTTP requests go through curl_cffi's AsyncSession.
"""

from __future__ import annotations

from typing import Any

from curl_cffi.requests import AsyncSession

from .logger import log_error

API_BASE = "https://discord.com/api/v10"


class CurlSession:
    """Curl-cffi HTTP pool with Cloudflare bypass."""

    def __init__(self, token: str, size: int = 4) -> None:
        self._token = token
        self._size = size
        self._index = 0
        self._sessions: list[AsyncSession] = []

    @property
    def count(self) -> int:
        return self._size

    async def _get_session(self) -> AsyncSession:
        if not self._sessions:
            for _ in range(self._size):
                s = AsyncSession(impersonate="chrome110")
                s.headers.update({
                    "Authorization": self._token,
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.1130 Chrome/128.0.6613.186 Safari/537.36",
                    "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJyZWxlYXNlX2NoYW5uZWwiOiJwdGIiLCJjbGllbnRfdmVyc2lvbiI6IjEuMC4xMTMwIiwib3NfdmVyc2lvbiI6IjEwLjAuMTkwNDUiLCJvc19hcmNoIjoieDY0IiwiYXBwX2FyY2giOiJ4NjQiLCJzeXN0ZW1fbG9jYWxlIjoidHIiLCJoYXNfY2xpZW50X21vZHMiOmZhbHNlLCJicm93c2VyX3VzZXJfYWdlbnQiOiJNb3ppbGxhLzUuMCAoV2luZG93cyBOVCAxMC4wOyBXaW42NDsgeDY0KSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBkaXNjb3JkLzEuMC4xMTMwIENocm9tZS8xMjguMC42NjEzLjE4NiBFbGVjdHJvbi8zMi4yLjcgU2FmYXJpLzUzNy4zNiIsImJyb3dzZXJfdmVyc2lvbiI6IjMyLjIuNyIsIm9zX3Nka192ZXJzaW9uIjoiMTkwNDUiLCJjbGllbnRfYnVpbGRfbnVtYmVyIjozNjY5NTUsIm5hdGl2ZV9idWlsZF9udW1iZXIiOjU4NDYzLCJjbGllbnRfZXZlbnRfc291cmNlIjpudWxsfQ==",
                })
                self._sessions.append(s)
        idx = self._index % self._size
        self._index += 1
        return self._sessions[idx]

    async def _do(self, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
        url = f"{API_BASE}{path}"
        s = await self._get_session()
        r = await s.request(method, url, **kwargs)
        try:
            data = r.json()
        except Exception:
            data = {"code": r.status_code, "message": r.text[:500]}
        return r.status_code, data

    async def probe_vanity(self, guild_id: int) -> str | None:
        try:
            status, data = await self._do("GET", f"/guilds/{guild_id}/vanity-url")
            code: str | None = data.get("code") if isinstance(data, dict) else None
            return code if code else None
        except Exception as exc:
            log_error(f"probe {guild_id}: {exc}")
            return None

    async def claim_vanity(self, guild_id: int, code: str, mfa_token: str) -> dict[str, Any]:
        try:
            status, data = await self._do("PATCH", f"/guilds/{guild_id}/vanity-url",
                json={"code": code},
                headers={"X-Discord-MFA-Authorization": mfa_token},
            )
            if status >= 400:
                raise RuntimeError(f"HTTP {status}: {data}")
            return data
        except Exception as exc:
            log_error(f"claim {code}: {exc}")
            raise

    async def delete_vanity(self, guild_id: int, mfa_token: str) -> dict[str, Any]:
        try:
            status, data = await self._do("PATCH", f"/guilds/{guild_id}/vanity-url",
                json={"code": ""},
                headers={"X-Discord-MFA-Authorization": mfa_token},
            )
            if status >= 400:
                raise RuntimeError(f"HTTP {status}: {data}")
            return data
        except Exception as exc:
            log_error(f"delete: {exc}")
            raise

    async def mfa_probe(self) -> dict[str, Any]:
        try:
            status, data = await self._do("PATCH", "/guilds/0/vanity-url", json={"code": "probe"})
            return data
        except Exception as exc:
            return {"code": 0, "error": str(exc)}

    async def mfa_finish(self, ticket: str, password: str) -> dict[str, Any]:
        try:
            status, data = await self._do("POST", "/mfa/finish", json={
                "ticket": ticket, "mfa_type": "password", "data": password,
            })
            if status >= 400:
                raise RuntimeError(f"HTTP {status}: {data}")
            return data
        except Exception as exc:
            log_error(f"mfa_finish: {exc}")
            raise

    async def send_message(self, channel_id: int, content: str) -> dict[str, Any]:
        try:
            status, data = await self._do("POST", f"/channels/{channel_id}/messages", json={"content": content})
            return data
        except Exception as exc:
            log_error(f"send_message: {exc}")
            return {"error": str(exc)}

    async def get_guilds(self) -> list[dict[str, Any]]:
        try:
            status, data = await self._do("GET", "/users/@me/guilds")
            return data if isinstance(data, list) else []
        except Exception as exc:
            log_error(f"get_guilds: {exc}")
            return []

    async def get_me(self) -> dict[str, Any]:
        try:
            status, data = await self._do("GET", "/users/@me")
            return data
        except Exception as exc:
            return {"error": str(exc)}

    def destroy(self) -> None:
        for s in self._sessions:
            try:
                coro = s.close()
                import asyncio
                try:
                    asyncio.get_event_loop().create_task(coro)
                except Exception:
                    pass
            except Exception:
                pass
        self._sessions.clear()
