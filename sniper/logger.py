"""Colorful timestamped logging."""

import sys
import random
from datetime import datetime

from colorama import init, Fore, Style

init(autoreset=True)

COLORS = [
    Fore.GREEN,
    Fore.YELLOW,
    Fore.BLUE,
    Fore.MAGENTA,
    Fore.CYAN,
    Fore.WHITE,
]


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _color(text: str) -> str:
    return random.choice(COLORS) + text + Style.RESET_ALL


def log(*args: object) -> None:
    msg = " ".join(str(a) for a in args)
    print(_color(f"[{_ts()}] {msg}"))


def log_error(*args: object) -> None:
    msg = " ".join(str(a) for a in args)
    print(_color(f"[{_ts()}] {msg}"), file=sys.stderr)
