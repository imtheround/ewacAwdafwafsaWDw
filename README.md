# discord-vanity-sniper

High-performance Discord vanity URL sniper — monitors your servers for vanity URL drops and races to claim them using HTTP/2 directly against Discord's API.

## Features

- **Low-latency HTTP/2 client** — bypasses TCP+TLS handshake per request by maintaining a persistent h2 session to `canary.discord.com`
- **MFA auto-refresh** — keeps a fresh MFA token so write endpoints are always ready
- **Guild monitoring** — reacts to `guildUpdate` events; when a vanity drops, races to claim it
- **Webhook notifications** — success/failure webhooks with speed measurements
- **DM on success** — pings a configurable user when a snipe lands
- **Command interface** — `.claim`, `.delete`, `.sniper`, `.autokick`, `.pause` and more from your log channel
- **TypeScript** — fully typed, modular architecture

## Quick start

```bash
cp config.example.json config.json
# → fill in your token, channelId, serverId, password, webhookUrl, userToDm

npm install
npm run dev
```

## Commands

| Command | Description |
|---------|-------------|
| `.help` | Show command list |
| `.mfa <on\|off>` | Start/stop MFA ticket refresh |
| `.sniper <on\|off>` | Enable/disable auto-sniping |
| `.claim <vanity>` | Manually claim a vanity URL |
| `.delete` | Delete your server's current vanity |
| `.reset` | Reset sniper state (allow another claim) |
| `.vanity` | List vanity URLs visible to this client |
| `.leave <vanity\|guildId>` | Leave a server |
| `.autokick` | Toggle auto-kick on member join |
| `.pause` | Disable invites for 24 hours |
| `.restart` | Exit the process |

## Configuration

`config.json`:

| Field | Description |
|-------|-------------|
| `token` | Your Discord user token (self-bot) |
| `channelId` | Channel ID where commands are read |
| `serverId` | Target server to set the vanity on |
| `userToDm` | User to DM on snipe success |
| `password` | Your Discord password (for MFA) |
| `webhookUrl` | Discord webhook for notifications |

## Architecture

```
src/
├── index.ts      — Entry point, wires everything together
├── config.ts     — Config loader with validation
├── http2.ts      — RexClient: persistent HTTP/2 session to Discord
├── mfa.ts        — MfaManager: auto-refreshes MFA tickets
├── vanity.ts     — VanityOps: claim / delete wrappers
├── sniper.ts     — SniperEngine: guild event → race logic
├── commands.ts   — .command handler (in-chat control)
├── webhook.ts    — Discord webhook embed sender
├── logger.ts     — Colorful timestamped logging
└── util.ts       — Time formatting, sleep helper
```

## How it works

1. **Login** as a self-bot with `discord.js-selfbot-v13`
2. **MFA loop**: Every 10 seconds, probes `PATCH /api/v9/guilds/0/vanity-url` — if Discord returns `code: 60003`, we finish MFA with the password to get a fresh token
3. **Monitor**: `guildUpdate` fires when any guild you're in changes its vanity URL
4. **Race**: If the old URL is non-null (someone dropped it) and our target server has no vanity, fire `PATCH /api/v10/guilds/<serverId>/vanity-url` with the MFA token via HTTP/2
5. **Notify**: Webhook + DM on success, webhook on failure

## Disclaimer

Self-botting violates Discord's Terms of Service. Use at your own risk.
