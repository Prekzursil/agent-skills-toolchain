"""Generate Codex ``hooks.json`` for the CI parity runner.

Routes every Codex lifecycle event to the vendored, pure-stdlib harness dispatcher
(``ci/harness/dispatcher.py --provider codex --event <E>``). Reads two env vars set
by the workflow: ``GITHUB_WORKSPACE`` (repo checkout root) and ``CODEX_HOME``.
"""

from __future__ import annotations

import json
import os

EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "SubagentStart",
    "SubagentStop",
    "Stop",
)


def main() -> None:
    dispatcher = os.path.join(
        os.environ["GITHUB_WORKSPACE"], "runner", "ci", "harness", "dispatcher.py"
    )
    codex_home = os.environ["CODEX_HOME"]
    config = {
        "hooks": {
            event: [
                {
                    "matcher": ".*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'python "{dispatcher}" --provider codex --event {event}',
                            "timeout": 5,
                        }
                    ],
                }
            ]
            for event in EVENTS
        }
    }
    target = os.path.join(codex_home, "hooks.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    print(f"hooks.json written for {len(EVENTS)} events -> {target}")


if __name__ == "__main__":
    main()
