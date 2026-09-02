"""Tests import the CLI and the AST-live helper. They must not import plugin_only."""

from aud0032_fx.entry import main
from aud0032_fx.live_mod import greet


def test_main() -> None:
    assert "hello" in main()
    assert greet("t").startswith("hello")
