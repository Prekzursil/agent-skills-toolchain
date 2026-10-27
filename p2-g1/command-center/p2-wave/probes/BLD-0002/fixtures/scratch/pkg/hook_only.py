"""Reachable ONLY through the hook manifest registration."""


def on_pre_tool() -> str:
    return "hook-ok"
