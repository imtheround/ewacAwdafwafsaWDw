"""Config loader with validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict


class ScoutAccount(TypedDict):
    token: str
    label: str


class Config(TypedDict, total=False):
    token: str
    channelId: str
    serverId: str
    userToDm: str
    password: str
    webhookUrl: str
    monitorGuilds: list[str]
    poolSize: int
    proxyLessGateways: int
    controlChannelId: str
    controllerPassword: str


_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")


def load_config(path: Path) -> Config:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    required = ["token", "channelId", "serverId", "userToDm"]
    for field in required:
        if not raw.get(field):
            raise ValueError(f'Missing required config field: "{field}"')

    if "." not in raw["token"]:
        raise ValueError("Token looks invalid — should be a JWT-style token.")
    if not _SNOWFLAKE_RE.match(raw["channelId"]):
        raise ValueError("channelId should be a 17-20 digit snowflake.")
    if not _SNOWFLAKE_RE.match(raw["serverId"]):
        raise ValueError("serverId should be a 17-20 digit snowflake.")

    for gid in raw.get("monitorGuilds", []):
        if not _SNOWFLAKE_RE.match(gid):
            raise ValueError(f'Invalid guild ID in monitorGuilds: "{gid}"')

    for s in raw.get("scouts", []):
        if not s.get("token") or "." not in s["token"]:
            raise ValueError(f'Scout "{s.get("label", "?")}" has an invalid token.')
        if not s.get("label"):
            raise ValueError("Each scout must have a label.")

    return raw  # type: ignore[return-value]
