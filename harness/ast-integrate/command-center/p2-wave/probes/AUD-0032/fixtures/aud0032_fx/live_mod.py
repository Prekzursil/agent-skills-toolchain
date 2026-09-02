"""AST-imported helper. Probe 1 and probe 2 must both mark this LIVE."""


def greet(who: str) -> str:
    return f"hello {who}"


def unused_helper() -> str:
    """Defined but never called — function-level dead inside a live module."""
    return "never-called"
