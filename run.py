"""Discord Vanity Sniper — gateway detection + control CLI."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from sniper.config import load_config
from sniper.http2 import SessionPool
from sniper.mfa import MfaManager
from sniper.vanity import VanityOps
from sniper.sniper import SniperEngine
from sniper.multigate import MultiGatewayEngine
from sniper.controller import SniperController
from sniper.cli import SniperCLI
from sniper.logger import log, log_error


async def amain() -> None:
    config_path = Path("config.json")
    if not config_path.exists():
        log_error("config.json not found.")
        sys.exit(1)

    cfg = load_config(config_path)
    log("Config loaded.")

    pool_size = cfg.get("poolSize", 4)
    claim_pool = SessionPool(cfg["token"], pool_size)
    log(f"Claim pool: {pool_size} h2 sessions")

    mfa = MfaManager(claim_pool, cfg.get("password", ""))
    vanity = VanityOps(claim_pool, mfa, cfg["serverId"])

    from discord import Client as DiscordClient
    client = DiscordClient()

    sniper = SniperEngine(
        client, vanity,
        cfg["channelId"], cfg["serverId"],
        cfg["webhookUrl"], cfg["userToDm"],
    )

    multigate = MultiGatewayEngine(cfg["token"], cfg.get("proxyLessGateways", 5))

    def on_drop(event: Any) -> None:
        asyncio.ensure_future(
            sniper.on_drop(event.guild_id, event.code, event.detected_at, source=event.source)
        )

    multigate.on_vanity_drop(on_drop)

    controller = SniperController(client, sniper, multigate, mfa, vanity, cfg)
    controller.register()

    cli = SniperCLI(sniper, multigate, mfa, vanity, client, cfg)

    @client.event
    async def on_ready() -> None:
        tag = str(client.user)
        log(f"Logged in as {tag}")

        for g in client.guilds:
            if g.vanity_url_code and "VANITY_URL" in (g.features or []):
                log(f"  Tier 3: {g.id} | `{g.vanity_url_code}`")

        mfa.start()
        log("MFA refresh started (10s)")

        log(f"Starting {cfg.get('proxyLessGateways', 5)} gateways...")
        asyncio.create_task(multigate.start())

        log("Sniper ready.")

    log("Logging in...")
    await asyncio.gather(
        client.start(cfg["token"]),
        cli.run(),
        return_exceptions=True,
    )


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
