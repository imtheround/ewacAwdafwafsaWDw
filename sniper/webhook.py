"""Webhook embed sender."""

from __future__ import annotations

import aiohttp
from .logger import log_error


async def send_webhook(webhook_url: str, embed: dict[str, object]) -> None:
    """Send an embed + @everyone ping to the configured webhook."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json={"content": "@everyone", "embeds": [embed]},
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log_error(f"Webhook returned {resp.status}: {body[:200]}")
    except Exception as exc:
        log_error(f"Webhook delivery failed: {exc}")


async def send_detection_webhook(
    webhook_url: str,
    *,
    code: str,
    guild_id: str,
    source: str,
    scout_label: str | None = None,
    detection_ms: float | None = None,
) -> None:
    """Send a detection embed — fired the moment a drop is noticed."""
    source_str = source.upper()
    if scout_label:
        source_str += f" ({scout_label})"

    fields: list[dict[str, str]] = [
        {"name": "Vanity", "value": f"`{code}`", "inline": True},
        {"name": "Guild", "value": f"`{guild_id}`", "inline": True},
        {"name": "Source", "value": f"`{source_str}`", "inline": True},
    ]

    if detection_ms is not None:
        fields.append({
            "name": "Detection Speed",
            "value": f"`{detection_ms:.1f}ms`",
            "inline": True,
        })

    embed: dict[str, object] = {
        "title": "Vanity Dropped — Detected",
        "description": f"```diff\n+ discord.gg/{code} is now available\n```",
        "color": 0xFFA500,
        "fields": fields,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json={"content": "", "embeds": [embed]},
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log_error(f"Detection webhook returned {resp.status}: {body[:200]}")
    except Exception as exc:
        log_error(f"Detection webhook failed: {exc}")
