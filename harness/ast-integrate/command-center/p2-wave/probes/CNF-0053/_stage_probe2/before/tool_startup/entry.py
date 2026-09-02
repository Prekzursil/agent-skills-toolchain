"""Entry point for commit-before: core + util only."""

from tool_startup import core, util

def main() -> str:
    return f"{core.ENTRY_NAME}:{util.banner()}"
