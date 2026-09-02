"""Live invocation of a surface name: file must exist, then disposition resolves."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dispositions import ALIASES, DEPRECATED, classify, target_of  # noqa: E402
from enumerate import enumerate_live  # noqa: E402

LIVE = HERE / "fixtures" / "live"


def invoke(name: str, live_root: Path | None = None) -> dict[str, Any]:
    root = live_root or LIVE
    rows = enumerate_live(root)
    names = {r["name"]: r for r in rows}
    if name not in names:
        return {
            "ok": False,
            "name": name,
            "disposition": None,
            "target": None,
            "warning": False,
            "reason": "NOT-FOUND",
        }
    kind = classify(name)
    if kind is None:
        return {
            "ok": False,
            "name": name,
            "disposition": None,
            "target": None,
            "warning": False,
            "reason": "NO-DISPOSITION",
            "path": names[name]["path"],
        }
    if kind == "removed":
        return {
            "ok": False,
            "name": name,
            "disposition": kind,
            "target": None,
            "warning": False,
            "reason": "REMOVED",
            "successor": target_of(name),
            "path": names[name]["path"],
        }
    target = target_of(name)
    return {
        "ok": True,
        "name": name,
        "disposition": kind,
        "target": target,
        "warning": kind == "deprecated",
        "reason": None,
        "path": names[name]["path"],
        "kind": names[name]["kind"],
        "alias_hit": name in ALIASES,
        "deprecated_hit": name in DEPRECATED,
    }


def roundtrip_aliases(live_root: Path | None = None) -> dict[str, Any]:
    root = live_root or LIVE
    failed: list[dict[str, Any]] = []
    checked = 0
    for old, want in sorted(ALIASES.items()):
        checked += 1
        got = invoke(old, root)
        if not got.get("ok") or got.get("target") != want or got.get("disposition") != "aliased":
            failed.append({"old": old, "want": want, "got": got})
    unknown = invoke("/no-such-command", root)
    removed_ok = True
    from dispositions import REMOVED_SUCCESSORS  # local to avoid cycle noise

    for name in REMOVED_SUCCESSORS:
        got = invoke(name, root)
        if got.get("ok") or got.get("reason") != "REMOVED":
            removed_ok = False
            failed.append({"old": name, "want": "REMOVED", "got": got})
    return {
        "pass": not failed and unknown.get("reason") == "NOT-FOUND",
        "aliases_checked": checked,
        "failed": failed,
        "negative_control_unknown_name": unknown.get("reason") == "NOT-FOUND",
        "removed_do_not_resolve": removed_ok,
        "unknown": unknown,
    }


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("usage: invoke.py <name>")
        return 2
    rec = invoke(name)
    print(json.dumps(rec, sort_keys=True))
    return 0 if rec.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
