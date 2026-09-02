"""Declared CLI entry for the AUD-0032 planted control package.

A textual mention of aud0032_fx.mention_only must not count as a use.
"""

from aud0032_fx.live_mod import greet

PLUGIN_REGISTRY = {
    "orphan-plugin": "aud0032_fx.plugin_only",
}


def main() -> str:
    return greet("entry")


if __name__ == "__main__":
    print(main())
