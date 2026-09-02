"""Entry point for commit-after: core + util + extra payload module."""

from tool_startup import core, extra, util

def main() -> str:
    return f"{core.ENTRY_NAME}:{util.banner()}:{extra.PAYLOAD_NAME}"
