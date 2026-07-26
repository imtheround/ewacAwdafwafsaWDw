"""Terminal REPL for controlling the sniper."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from .http import CurlSession
from .logger import log


class SniperCLI:
    def __init__(
        self,
        sniper: Any,
        multigate: Any,
        mfa: Any,
        vanity: Any,
        http: CurlSession,
        cfg: dict[str, Any],
    ) -> None:
        self._sniper = sniper
        self._multigate = multigate
        self._mfa = mfa
        self._vanity = vanity
        self._http = http
        self._cfg = cfg
        self._running = True
        self._known_guilds: list[dict[str, Any]] = []
        self._known_user: str = ""

    async def run(self) -> None:
        me = await self._http.get_me()
        self._known_user = me.get("username", "?") if isinstance(me, dict) else "?"
        self._known_guilds = await self._http.get_guilds()
        log(f"CLI active ({self._known_user}). Type /help for commands.")
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, self._readline)
                if line is None:
                    break
                await self._handle(line)
            except (EOFError, KeyboardInterrupt):
                log("CLI exiting.")
                self._running = False

    def _readline(self) -> str | None:
        try:
            sys.stdout.write("> ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            return line.strip() if line else None
        except (EOFError, KeyboardInterrupt):
            return None

    async def _handle(self, text: str) -> None:
        if not text or not text.startswith("/"):
            return
        parts = text[1:].split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:]

        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler:
            await handler(args)
        elif cmd:
            log(f"Unknown: /{cmd}. Use /help.")

    def _p(self, msg: str) -> None:
        log(msg)

    def _get_guild_name(self, gid: str) -> str:
        for g in self._known_guilds:
            if g.get("id") == gid:
                return g.get("name", "?")
        return gid

    async def _cmd_help(self, args: list[str]) -> None:
        self._p(
            "Commands:"
            " /status /start /stop /enable /disable"
            " /watch /unwatch /guilds /watched /claim"
            " /exit"
        )

    async def _cmd_status(self, args: list[str]) -> None:
        s = self._sniper
        mg = self._multigate
        target_name = self._get_guild_name(self._cfg["serverId"])
        self._p(
            f"Sniper: {'ON' if s.sniper_enabled else 'OFF'}  "
            f"Claimed: {s.has_successfully_sniped}  "
            f"In flight: {s.request_in_flight}  "
            f"MFA: {'READY' if self._mfa.token else 'WAITING'}"
        )
        self._p(
            f"Gateways: {mg.ws_count}/{mg._count} active  "
            f"Target: {target_name}  "
            f"Monitoring {len(self._cfg.get('monitorGuilds', []))} guilds"
        )

    async def _cmd_start(self, args: list[str]) -> None:
        if self._multigate._enabled:
            self._p("Gateways already running.")
            return
        task = asyncio.create_task(self._multigate.start())
        try:
            await asyncio.wait_for(task, timeout=15)
            self._p(f"Started {self._multigate.ws_count} gateways.")
        except asyncio.TimeoutError:
            self._p("Starting gateways...")

    async def _cmd_stop(self, args: list[str]) -> None:
        self._multigate.destroy()
        self._p("Gateways stopped.")

    async def _cmd_enable(self, args: list[str]) -> None:
        self._sniper.sniper_enabled = True
        self._p("Sniper enabled.")

    async def _cmd_disable(self, args: list[str]) -> None:
        self._sniper.sniper_enabled = False
        self._p("Sniper disabled.")

    async def _cmd_watch(self, args: list[str]) -> None:
        if not args:
            self._p("Usage: /watch <guild_id>")
            return
        gid = args[0]
        watched = self._cfg.setdefault("monitorGuilds", [])
        if gid in watched:
            self._p(f"Already watching {gid}.")
            return
        watched.append(gid)
        self._p(f"Now monitoring {gid}.")

    async def _cmd_unwatch(self, args: list[str]) -> None:
        if not args:
            self._p("Usage: /unwatch <guild_id>")
            return
        gid = args[0]
        watched = self._cfg.get("monitorGuilds", [])
        if gid not in watched:
            self._p(f"{gid} not monitored.")
            return
        watched.remove(gid)
        self._p(f"Stopped monitoring {gid}.")

    async def _cmd_guilds(self, args: list[str]) -> None:
        guilds = self._known_guilds
        if not guilds:
            guilds = await self._http.get_guilds()
            self._known_guilds = guilds
        if not guilds:
            self._p("No guilds.")
            return
        self._p(f"Guilds ({len(guilds)}):")
        for g in guilds:
            gid = g.get("id", "?")
            name = g.get("name", "?")
            vc = g.get("vanity_url_code") or ""
            tag = f" discord.gg/{vc}" if vc else ""
            self._p(f"  {gid} \u2014 {name}{tag}")

    async def _cmd_watched(self, args: list[str]) -> None:
        watched = self._cfg.get("monitorGuilds", [])
        if not watched:
            self._p("No monitored guilds.")
            return
        self._p(f"Monitored ({len(watched)}):")
        for gid in watched:
            self._p(f"  {gid} \u2014 {self._get_guild_name(gid)}")

    async def _cmd_claim(self, args: list[str]) -> None:
        if not args:
            self._p("Usage: /claim <code>")
            return
        code = args[0]
        if not self._mfa.token:
            self._p("MFA not ready.")
            return
        self._p(f"Claiming {code}...")

        import time
        start = time.perf_counter()
        try:
            result = await self._vanity.claim(code)
            elapsed = (time.perf_counter() - start) * 1000
            if result.success:
                self._p(f"CLAIMED {code} in {elapsed:.1f}ms!")
            else:
                self._p(f"Failed: {result.error} ({elapsed:.1f}ms)")
        except Exception as exc:
            self._p(f"Error: {exc}")

    async def _cmd_exit(self, args: list[str]) -> None:
        self._p("Exiting...")
        self._running = False
