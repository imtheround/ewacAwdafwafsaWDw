"""HTTP pool using discord.py's native HTTPClient.

Importantly: we use HTTPClient's built-in methods (get_vanity_code,
change_vanity_code) which bypass Cloudflare.
"""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any

from discord.http import HTTPClient

from .logger import log_error


class SessionPool:
    """Thin pool of discord.py HTTP clients.

    Each pool session is an HTTPClient. They share discord.py's
    internal connector and auth state, which avoids Cloudflare blocks.
    """

    def __init__(self, token: str, size: int = 4) -> None:
        self._token = token
        self._size = size
        self._index = 0
        self._lock = asyncio.Lock()
        self._http: HTTPClient | None = None

    @property
    def count(self) -> int:
        return self._size

    def _ensure(self) -> HTTPClient:
        if self._http is None:
            self._http = HTTPClient(connector=None, loop=asyncio.get_event_loop())
        return self._http

    @property
    def http(self) -> HTTPClient:
        return self._ensure()

    async def ensure_authed(self) -> None:
        http = self._ensure()
        if not http.token:
            await http.static_login(self._token)

    # ── vanity operations ───────────────────────────────────────

    async def probe_vanity(self, guild_id: int) -> str | None:
        """Get a guild's current vanity code. Returns None if none set."""
        await self.ensure_authed()
        try:
            data = await self.http.get_vanity_code(guild_id)
            code: str | None = data.get("code") if isinstance(data, dict) else None
            # None or empty string means no vanity
            return code if code else None
        except Exception as exc:
            log_error(f"probe {guild_id}: {exc}")
            return None

    async def claim_vanity(self, guild_id: int, code: str, mfa_token: str) -> dict[str, Any]:
        """Claim a vanity URL. Returns the response dict."""
        await self.ensure_authed()
        from discord.http import Route
        try:
            return await self.http.request(
                Route("PATCH", "/guilds/{guild_id}/vanity-url", guild_id=guild_id),
                json={"code": code},
                headers={"X-Discord-MFA-Authorization": mfa_token},
            )
        except Exception as exc:
            log_error(f"claim {code}: {exc}")
            raise

    async def delete_vanity(self, guild_id: int, mfa_token: str) -> dict[str, Any]:
        """Delete/clear a guild's vanity URL."""
        await self.ensure_authed()
        from discord.http import Route
        try:
            return await self.http.request(
                Route("PATCH", "/guilds/{guild_id}/vanity-url", guild_id=guild_id),
                json={"code": ""},
                headers={"X-Discord-MFA-Authorization": mfa_token},
            )
        except Exception as exc:
            log_error(f"delete: {exc}")
            raise

    # ── MFA operations ───────────────────────────────────────────

    async def mfa_probe(self) -> dict[str, Any]:
        """PATCH /guilds/0/vanity-url — check MFA status, returns ticket if needed."""
        await self.ensure_authed()
        try:
            return await self.http.change_vanity_code(0, "probe")
        except Exception as exc:
            # discord.py's HTTPException stores the full JSON in .json
            # (including the mfa.ticket field on 60003)
            json_data = getattr(exc, "json", None)
            if isinstance(json_data, dict):
                return json_data
            return {"code": 0, "error": str(exc)}

    async def mfa_finish(self, ticket: str, password: str) -> dict[str, Any]:
        """POST /mfa/finish with ticket + password."""
        await self.ensure_authed()
        from discord.http import Route
        r = Route("POST", "/mfa/finish")
        try:
            return await self.http.request(r, json={
                "ticket": ticket, "mfa_type": "password", "data": password,
            })
        except Exception as exc:
            log_error(f"mfa_finish: {exc}")
            raise

    # ── generic request (for non-vanity endpoints) ───────────────

    async def request(self, _method: str, _path: str, **__: Any) -> str:
        """Generic request — rarely needed. Use specific methods above."""
        await self.ensure_authed()
        # For anything else, use raw http.request with a Route
        from discord.http import Route
        import re
        path = re.sub(r'^/api/v\d+/', '/', _path)
        kwargs: dict[str, Any] = {}
        parts = path.strip("/").split("/")
        if "guilds" in parts and parts.index("guilds") + 1 < len(parts):
            gid = int(parts[parts.index("guilds") + 1])
            kwargs["guild_id"] = gid
            path = path.replace(str(gid), "{guild_id}")
        r = Route(_method, path, **kwargs)
        result = await self.http.request(r)
        if isinstance(result, dict):
            return _json.dumps(result)
        return str(result)

    async def race_first(self, *args: Any, **kwargs: Any) -> str:
        """Single-threaded — just call request."""
        return await self.request(*args, **kwargs)

    def destroy(self) -> None:
        if self._http:
            try:
                asyncio.get_event_loop().create_task(self._http.close())
            except Exception:
                pass
            self._http = None
