"""Fixture adapter used as a resolvable file:line target for IMP-0214."""


def run(goal: str) -> str:
    return f"adopt:{goal}"


ENTRYPOINT = "run"
