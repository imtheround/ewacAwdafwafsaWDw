"""Selfbot control panel — / commands with password auth + whitelist."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .logger import log, log_error


class SniperController:
    def __init__(
        self,
        client: Any,
        sniper: Any,
        multigate: Any,
        mfa: Any,
        vanity: Any,
        cfg: dict[str, Any],
    ) -> None:
        self._client = client
        self._sniper = sniper
        self._multigate = multigate
        self._mfa = mfa
        self._vanity = vanity
        self._cfg = cfg
        self._control_id = cfg.get("controlChannelId")
        self._admin_pwd = cfg.get("controllerPassword", "")
        self._whitelist: set[int] = set()

    def register(self) -> None:
        @self._client.event
        async def on_message(msg: Any) -> None:
            await self._handle(msg)

    async def _handle(self, msg: Any) -> None:
        if not self._is_control(msg):
            return
        text = msg.content.strip()
        if not text.startswith("/"):
            return

        parts = text[1:].split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:]

        if cmd == "login":
            await self._cmd_login(msg, args)
            return

        if cmd and cmd != "login" and msg.author.id not in self._whitelist:
            await self._reply(msg, "Not authorized. Use `/login <password>` first.")
            return

        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler:
            await handler(msg, args)
        elif cmd:
            await self._reply(msg, f"Unknown command `/{cmd}`. Use `/help`.")

    def _is_control(self, msg: Any) -> bool:
        if msg.author.id == self._client.user.id:
            return False
        if isinstance(msg.channel, type(self._client).DMChannel):
            return True
        cid = getattr(msg.channel, "id", None)
        return bool(cid and self._control_id and str(cid) == self._control_id)

    async def _reply(self, msg: Any, text: str) -> None:
        try:
            await msg.channel.send(text)
        except Exception as exc:
            log_error(f"Controller reply failed: {exc}")

    async def _cmd_login(self, msg: Any, args: list[str]) -> None:
        if not self._admin_pwd:
            await self._reply(msg, "No controller password configured. Set `controllerPassword` in config.")
            return
        if not args:
            await self._reply(msg, "Usage: `/login <password>`")
            return
        if args[0] == self._admin_pwd:
            self._whitelist.add(msg.author.id)
            await self._reply(msg, "Authenticated. You can now use `/` commands.")
            log(f"Auth: {msg.author} ({msg.author.id}) logged in.")
        else:
            await self._reply(msg, "Wrong password.")

    async def _cmd_help(self, msg: Any, args: list[str]) -> None:
        await self._reply(msg, (
            "**Commands**"
            "\n`/login <pwd>` — authenticate"
            "\n`/status` — sniper state"
            "\n`/start` — start gateways"
            "\n`/stop` — stop gateways"
            "\n`/enable` — allow claiming"
            "\n`/disable` — detect only"
            "\n`/watch <id>` — monitor a guild"
            "\n`/unwatch <id>` — stop monitoring"
            "\n`/guilds` — list your guilds"
            "\n`/watched` — monitored guilds"
            "\n`/claim <code>` — manual claim"
        ))

    async def _cmd_status(self, msg: Any, args: list[str]) -> None:
        s = self._sniper
        mg = self._multigate
        target = self._client.get_guild(int(self._cfg["serverId"]))
        target_name = target.name if target else self._cfg["serverId"]

        await self._reply(msg, (
            f"**Sniper** {'🟢 ON' if s.sniper_enabled else '🔴 OFF'}"
            f"\nClaimed: `{s.has_successfully_sniped}`"
            f"\nIn flight: `{s.request_in_flight}`"
            f"\nMFA: `{'✅ READY' if self._mfa.token else '⏳ WAITING'}`"
            f"\nGateways: `{mg.ws_count}/{mg._count}` active"
            f"\nTarget: `{target_name}`"
            f"\nMonitoring `{len(self._cfg.get('monitorGuilds', []))}` guilds"
        ))

    async def _cmd_start(self, msg: Any, args: list[str]) -> None:
        if self._multigate._enabled:
            await self._reply(msg, "Gateways already running.")
            return
        task = asyncio.create_task(self._multigate.start())
        try:
            await asyncio.wait_for(task, timeout=15)
            await self._reply(msg, f"Started {self._multigate.ws_count} gateway connections.")
        except asyncio.TimeoutError:
            await self._reply(msg, "Starting gateways (may lag behind).")

    async def _cmd_stop(self, msg: Any, args: list[str]) -> None:
        self._multigate.destroy()
        await self._reply(msg, "Gateways stopped.")

    async def _cmd_enable(self, msg: Any, args: list[str]) -> None:
        self._sniper.sniper_enabled = True
        await self._reply(msg, "Sniper enabled — will claim on next drop.")

    async def _cmd_disable(self, msg: Any, args: list[str]) -> None:
        self._sniper.sniper_enabled = False
        await self._reply(msg, "Sniper disabled — detecting only.")

    async def _cmd_watch(self, msg: Any, args: list[str]) -> None:
        if not args:
            await self._reply(msg, "Usage: `/watch <guild_id>`")
            return
        gid = args[0]
        watched = self._cfg.setdefault("monitorGuilds", [])
        if gid in watched:
            await self._reply(msg, f"Already watching `{gid}`.")
            return
        watched.append(gid)
        await self._reply(msg, f"Now monitoring `{gid}`.")

    async def _cmd_unwatch(self, msg: Any, args: list[str]) -> None:
        if not args:
            await self._reply(msg, "Usage: `/unwatch <guild_id>`")
            return
        gid = args[0]
        watched = self._cfg.get("monitorGuilds", [])
        if gid not in watched:
            await self._reply(msg, f"`{gid}` is not being monitored.")
            return
        watched.remove(gid)
        await self._reply(msg, f"Stopped monitoring `{gid}`.")

    async def _cmd_guilds(self, msg: Any, args: list[str]) -> None:
        guilds = self._client.guilds or []
        lines = [f"**Guilds ({len(guilds)})**"]
        for g in guilds:
            vc = getattr(g, "vanity_url_code", None) or ""
            tag = f" `discord.gg/{vc}`" if vc else ""
            lines.append(f"`{g.id}` — {g.name}{tag}")
        await self._reply(msg, "\n".join(lines[:50]))

    async def _cmd_watched(self, msg: Any, args: list[str]) -> None:
        watched = self._cfg.get("monitorGuilds", [])
        if not watched:
            await self._reply(msg, "No guilds are being monitored.")
            return
        lines = [f"**Monitored ({len(watched)})**"]
        for gid in watched:
            g = self._client.get_guild(int(gid))
            lines.append(f"`{gid}` — {g.name if g else '?'}")
        await self._reply(msg, "\n".join(lines))

    async def _cmd_claim(self, msg: Any, args: list[str]) -> None:
        if not args:
            await self._reply(msg, "Usage: `/claim <code>`")
            return
        code = args[0]
        if not self._mfa.token:
            await self._reply(msg, "MFA not ready — can't claim.")
            return
        await self._reply(msg, f"Claiming `{code}`...")
        start = time.perf_counter()
        try:
            result = await self._vanity.claim(code)
            elapsed = (time.perf_counter() - start) * 1000
            if result.success:
                await self._reply(msg, f"Claimed `{code}` in `{elapsed:.1f}ms`!")
            else:
                await self._reply(msg, f"Failed: `{result.error}` ({elapsed:.1f}ms)")
        except Exception as exc:
            await self._reply(msg, f"Error: `{exc}`")
