"""Tiny ANSI helpers — no dependency, honors NO_COLOR and non-TTY output."""

import os
import sys


def _enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(text: str, code: str) -> str:
    if not _enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(t: str) -> str:
    return paint(t, "1")


def dim(t: str) -> str:
    return paint(t, "2")


def cyan(t: str) -> str:
    return paint(t, "36")


def yellow(t: str) -> str:
    return paint(t, "33")


def green(t: str) -> str:
    return paint(t, "32")


def red(t: str) -> str:
    return paint(t, "31")


def magenta(t: str) -> str:
    return paint(t, "35")


def rule(char: str = "─", width: int = 72) -> str:
    return dim(char * width)
