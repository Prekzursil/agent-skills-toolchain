"""Reached ONLY via a string in PLUGIN_REGISTRY / registry.json.

Probe 1 (AST imports/calls) must report DEAD.
Probe 2 (string-named plugin registry + CI/docs seeds) must report LIVE.
If both agree, the pair is not independent.
"""


def plugin_main() -> str:
    return "registry-only"
