"""Discord Vanity Sniper — raw WebSocket detection + CLI control."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from sniper.config import load_config
from sniper.http import CurlSession
from sniper.mfa import MfaManager
from sniper.vanity import VanityOps
from sniper.sniper import SniperEngine
from sniper.multigate import MultiGatewayEngine
from sniper.cli import SniperCLI
from sniper.logger import log, log_error


async def amain() -> None:
    config_path = Path("config.json")
    if not config_path.exists():
        log_error("config.json not found.")
        sys.exit(1)

    cfg = load_config(config_path)
    log("Config loaded.")

    http = CurlSession(cfg["token"], cfg.get("poolSize", 4))
    log(f"HTTP pool: {http.count} curl_cffi sessions")

    mfa = MfaManager(http, cfg.get("password", ""))
    vanity = VanityOps(http, mfa, cfg["serverId"])

    sniper = SniperEngine(
        vanity, cfg["channelId"], cfg["webhookUrl"], http,
    )

    multigate = MultiGatewayEngine(cfg["token"], cfg.get("proxyLessGateways", 5))

    def on_drop(event: Any) -> None:
        asyncio.ensure_future(
            sniper.on_drop(event.guild_id, event.code, event.detected_at, source=event.source)
        )

    multigate.on_vanity_drop(on_drop)

    cli = SniperCLI(sniper, multigate, mfa, vanity, http, cfg)

    mfa.start()
    log("MFA refresh started (10s)")

    log(f"Starting {cfg.get('proxyLessGateways', 5)} gateways...")
    asyncio.create_task(multigate.start())

    log("Sniper ready. CLI active.")
    await cli.run()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
