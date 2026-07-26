# discord-vanity-sniper

Python vanity URL sniper — monitors guilds for vanity drops via raw WebSocket and claims them via HTTP API.

## Architecture

```
run.py                       — entry point, wires everything together
sniper/
├── __init__.py
├── config.py                — config loader with validation
├── http2.py                 — SessionPool: discord.py HTTPClient wrapper
├── mfa.py                   — MfaManager: auto-refreshes MFA tickets (10s)
├── vanity.py                — VanityOps: claim / delete / probe
├── sniper.py                — SniperEngine: drop detection → claim pipeline
├── multigate.py             — MultiGatewayEngine: N× raw WS connections
├── controller.py            — Discord selfbot control (/commands in DMs)
├── cli.py                   — terminal REPL (same commands)
├── webhook.py               — Discord webhook embed sender
├── logger.py                — colorful timestamped logging
└── util.py                  — helpers
```

## Quick start

```bash
cp config.example.json config.json
# fill in your values
pip install -r requirements.txt
python run.py
```

Then either:
- **Discord**: DM the selfbot `/login <password>` then `/start`
- **Terminal**: Type `/start` in the running CLI

## Detection flow

```
       ┌─────────────────────┐
       │  Discord Gateway ←──│── raw WebSocket (no discord.py)
       │  GUILD_UPDATE       │
       │  GUILD_CREATE       │
       └──────┬──────────────┘
              │ vanity_url_code changed
              ▼
      MultiGatewayEngine
        detects drop
              │
              ▼
       SniperEngine
    ┌─── fires detection webhook
    │─── MfaManager.get_token()
    │─── SessionPool.claim_vanity()
    │─── fires success/fail webhook
    └─── DMs the configured user
```

## Detection

- Raw WebSocket to `wss://gateway.discord.gg/?v=9&encoding=json`
- No HTTP polling — Discord pushes `GUILD_UPDATE` events
- Multiple concurrent WS connections (configurable, default 3) — first to fire wins
- Latency: ~40ms WebSocket RTT + ~450ms HTTP claim = ~490ms total

**Limitation:** Discord does NOT send `GUILD_UPDATE` to the user who made the change. You need a **scout account** (different token) in the target guild to receive events about changes made by your main account.

## Claiming

- Uses discord.py's `HTTPClient` (avoids Cloudflare)
- `PATCH /guilds/{id}/vanity-url` with `X-Discord-MFA-Authorization` header
- MFA token auto-refreshed every 10s (probe → ticket → password → token)
- Claim latency: ~450ms

## Commands

| Command | Description |
|---------|-------------|
| `/login <password>` | Authenticate (whitelist-based) |
| `/status` | Sniper state, MFA status, gateways |
| `/start` | Start gateway connections |
| `/stop` | Stop gateways |
| `/enable` | Allow claiming |
| `/disable` | Detect only, no claims |
| `/watch <id>` | Add guild to monitor list |
| `/unwatch <id>` | Remove guild from monitor |
| `/guilds` | List guilds the token is in |
| `/watched` | List monitored guilds |
| `/claim <code>` | Manually claim a vanity |
| `/exit` | Shutdown |

Commands work in DMs to the selfbot, in the configured `controlChannelId`, or in the terminal CLI.

## Config

| Field | Description |
|-------|-------------|
| `token` | Discord user token (selfbot) |
| `channelId` | Channel for log messages |
| `serverId` | Target server to claim vanities on |
| `userToDm` | User to DM on snipe success |
| `password` | Discord account password (for MFA) |
| `webhookUrl` | Webhook for notifications |
| `monitorGuilds` | List of guild IDs to watch for drops |
| `poolSize` | HTTP client pool size (default 4) |
| `proxyLessGateways` | Number of WS connections (default 3) |
| `controlChannelId` | Channel where /commands work (optional) |
| `controllerPassword` | Password for `/login` auth |

## Disclaimer

Self-botting violates Discord's Terms of Service. Use at your own risk.
