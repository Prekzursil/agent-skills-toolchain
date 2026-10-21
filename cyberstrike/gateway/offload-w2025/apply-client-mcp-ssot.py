#!/usr/bin/env python3
"""Emit ~/.config/cyberstrike/cyberstrike.json from mcp-ssot.json.

Exactly ONE runtime-facing MCP registration: the gateway. Backends never
appear as per-session entries - they are manifest rows inside the gateway
(harness_capabilities), reachable only via harness_invoke.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SSOT = os.path.join(HERE, "mcp-ssot.json")
CLIENT = os.path.expanduser(r"~\.config\cyberstrike\cyberstrike.json")


def main() -> int:
    with open(SSOT, encoding="utf-8") as f:
        ssot = json.load(f)
    with open(CLIENT, encoding="utf-8") as f:
        client = json.load(f)

    gw = ssot["gateway"]
    client["mcp"] = {
        gw["name"]: {
            "type": "remote",
            "url": f"http://127.0.0.1:{gw['port']}{gw['path']}",
            "enabled": True,
        }
    }

    os.makedirs(os.path.dirname(CLIENT), exist_ok=True)
    with open(CLIENT, "w", encoding="utf-8") as f:
        json.dump(client, f, indent=2)
        f.write("\n")
    print(f"emitted {CLIENT}: single MCP registration '{gw['name']}' "
          f"-> http://127.0.0.1:{gw['port']}{gw['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
