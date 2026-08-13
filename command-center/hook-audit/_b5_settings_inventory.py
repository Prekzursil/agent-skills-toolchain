r"""B5 - enumerate every LIVE settings.json hook entry, classify its wiring PLANE, and
record its declared budget. Reads ONLY the `hooks` key of settings.json (that file also
holds live credentials; nothing else is touched or printed).

Plane classification, by what the command actually invokes:
  P1  hooks/_dispatch/dispatch.py        -> the in-repo dispatcher (expands to N checks)
  P2  hooks/<dir>/<script>.py            -> a hook script wired DIRECTLY, bypassing P1
  P3  ~/.agents/harness/dispatcher.py    -> the agent-self dispatcher (a second fan-out)
  P4  anything else                      -> recorded verbatim, never silently dropped

Vendor default budgets (code.claude.com/docs/en/hooks): 600 s, except UserPromptSubmit
at 30 s. An entry with no `timeout` inherits those, so "no budget" is never reported.

Writes B5-SETTINGS-INVENTORY.json. Fails closed at zero entries.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SETTINGS = Path("C:/Users/Prekzursil/.claude/settings.json")
OUT = Path(__file__).resolve().parent
DEFAULT_BUDGET = {"UserPromptSubmit": 30.0}
VENDOR_DEFAULT = 600.0

_P1 = re.compile(r"_dispatch[/\\]dispatch\.py", re.IGNORECASE)
_P3 = re.compile(r"\.agents[/\\]harness[/\\]dispatcher\.py", re.IGNORECASE)
_P2 = re.compile(
    r"\.claude[/\\]hooks[/\\]([A-Za-z0-9_.-]+)[/\\]([A-Za-z0-9_.-]+\.py)", re.IGNORECASE
)


def classify(cmd: str) -> tuple[str, str | None, str | None]:
    if _P1.search(cmd):
        m = re.search(r"dispatch\.py\s+(\w+)", cmd)
        return "P1-dispatcher", "_dispatch", (m.group(1) if m else None)
    if _P3.search(cmd):
        m = re.search(r"dispatcher\.py\s+([\w-]+)", cmd)
        return "P3-agent-self", "~/.agents/harness", (m.group(1) if m else None)
    m2 = _P2.search(cmd)
    if m2:
        return "P2-direct", m2.group(1), m2.group(2)
    return "P4-other", None, None


def main() -> int:
    raw = json.loads(SETTINGS.read_text(encoding="utf-8")).get("hooks") or {}
    rows: list[dict] = []
    for event, groups in raw.items():
        for grp in groups or []:
            matcher = grp.get("matcher")
            for e in grp.get("hooks") or []:
                cmd = str(e.get("command") or "")
                plane, hookdir, target = classify(cmd)
                declared = e.get("timeout")
                rows.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "plane": plane,
                        "hook_dir": hookdir,
                        "target": target,
                        "declared_timeout_s": declared,
                        "effective_budget_s": float(declared)
                        if declared
                        else DEFAULT_BUDGET.get(event, VENDOR_DEFAULT),
                        "budget_source": "declared" if declared else "vendor-default",
                        "type": e.get("type"),
                        "uses_if_field": "if" in e,
                        "uses_exec_form": "args" in e,
                        "command": cmd,
                    }
                )

    by_plane: dict[str, int] = {}
    for r in rows:
        by_plane[r["plane"]] = by_plane.get(r["plane"], 0) + 1
    res = {
        "settings_path": str(SETTINGS),
        "total_entries": len(rows),
        "events": sorted({r["event"] for r in rows}),
        "event_count": len({r["event"] for r in rows}),
        "by_plane": by_plane,
        "declared_budget_count": sum(
            1 for r in rows if r["budget_source"] == "declared"
        ),
        "vendor_default_count": sum(
            1 for r in rows if r["budget_source"] == "vendor-default"
        ),
        "uses_if_field_count": sum(1 for r in rows if r["uses_if_field"]),
        "uses_exec_form_count": sum(1 for r in rows if r["uses_exec_form"]),
        "entries": rows,
    }
    (OUT / "B5-SETTINGS-INVENTORY.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )
    print(f"total entries      : {res['total_entries']}")
    print(f"distinct events    : {res['event_count']}")
    print(f"by plane           : {res['by_plane']}")
    print(f"declared budgets   : {res['declared_budget_count']}")
    print(f"vendor-default     : {res['vendor_default_count']}")
    print(f"entries using `if` : {res['uses_if_field_count']}")
    print(f"entries exec form  : {res['uses_exec_form_count']}")
    print()
    for r in sorted(rows, key=lambda x: (x["event"], x["plane"])):
        print(
            f"  {r['event']:20s} {r['plane']:14s} {str(r['hook_dir'])[:24]:24s} "
            f"{str(r['target'])[:26]:26s} budget={r['effective_budget_s']:>6.0f}s "
            f"({r['budget_source']}) m={str(r['matcher'])[:22]}"
        )
    if not rows:
        print("FAILED:b5-settings-inventory zero entries -- parser or path is wrong")
        return 1
    print("\nSUCCESS:b5-settings-inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
