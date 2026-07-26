"""Utility helpers."""

import time
from datetime import datetime


def now_ms() -> str:
    """Full timestamp with milliseconds."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{int(time.time_ns() % 1_000_000_000 / 1_000_000):03d}"
