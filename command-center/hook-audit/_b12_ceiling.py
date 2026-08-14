"""B12b. What is the ENFORCED event ceiling -- the manifest's mirror, or settings.json?

`manifest.json` carries `settings_timeout` per event, but that field is a MIRROR. The value the
vendor actually enforces is the `timeout` registered on the hook COMMAND in settings.json. Round 4
found the two disagree on PostToolUse (15 vs 25) and PreToolUse (15 vs 20), so the manifest mirror
cannot be trusted as the ceiling without checking.

SECURITY: `~/.claude/settings.json` holds live credentials. This reads it, walks ONLY the `hooks`
subtree, and prints ONLY event names and integer timeouts. No value from any other key is read,
printed or written. (AGENTS.md 9.)

Re-runnable:  python command-center/hook-audit/_b12_ceiling.py
Evidence:     command-center/hook-audit/B12-CEILING.json
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPO_MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"
LIVE_SETTINGS = Path.home() / ".claude" / "settings.json"
OUT = Path(__file__).resolve().parent / "B12-CEILING.json"

# The dispatcher registers itself as one command per event; that command's `command` string
# names dispatch.py. Only those entries define OUR ceiling.
DISPATCH_MARK = "_dispatch"


def settings_ceilings() -> tuple[dict, dict]:
    """Return ({event: [timeouts of dispatcher commands]}, {event: [all timeouts]})."""
    if not LIVE_SETTINGS.is_file():
        return {}, {}
    doc = json.loads(LIVE_SETTINGS.read_text(encoding="utf-8"))
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return {}, {}
    ours: dict[str, list] = {}
    every: dict[str, list] = {}
    for event, matchers in hooks.items():
        if not isinstance(matchers, list):
            continue
        for m in matchers:
            for h in (m or {}).get("hooks") or []:
                if not isinstance(h, dict):
                    continue
                t = h.get("timeout")
                if not isinstance(t, (int, float)):
                    continue
                every.setdefault(event, []).append(t)
                if DISPATCH_MARK in str(h.get("command") or ""):
                    ours.setdefault(event, []).append(t)
    return ours, every


def main() -> int:
    doc = json.loads(REPO_MANIFEST.read_text(encoding="utf-8"))
    events = doc.get("events") or {}
    ours, every = settings_ceilings()

    rows = []
    for event, node in events.items():
        mirror = node.get("settings_timeout")
        enforced = min(ours[event]) if ours.get(event) else None
        checks = node.get("checks") or []
        worst = max(
            (
                c.get("timeout")
                for c in checks
                if isinstance(c.get("timeout"), (int, float))
            ),
            default=None,
        )
        rows.append(
            {
                "event": event,
                "manifest_mirror_s": mirror,
                "settings_enforced_s": enforced,
                "mirror_matches_enforced": mirror == enforced,
                "n_checks": len(checks),
                "max_declared_check_timeout_s": worst,
                "worst_check_fits_enforced": (
                    None if enforced is None or worst is None else worst < enforced
                ),
            }
        )

    # Controls.
    c1 = LIVE_SETTINGS.is_file()
    c2 = len(rows) >= 4  # fail closed if the manifest shape moved
    c3 = any(r["settings_enforced_s"] is not None for r in rows)
    # C4: the reader must be able to see a DISAGREEMENT, not just report parity. Round 4
    # recorded two known mismatches; if the reader now reports every event matching, that is
    # either a real fix or a blind reader, and those must not look the same.
    c4_disagreements = [r["event"] for r in rows if not r["mirror_matches_enforced"]]

    blob = {
        "probe": "_b12_ceiling.py",
        "live_settings_present": c1,
        "rows": rows,
        "events_where_mirror_disagrees_with_enforced": c4_disagreements,
        "controls": {
            "C1_live_settings_readable": c1,
            "C2_manifest_shape_plausible": c2,
            "C3_found_dispatcher_commands": c3,
        },
    }
    OUT.write_text(json.dumps(blob, indent=1) + "\n", encoding="utf-8")

    if not (c1 and c2 and c3):
        print(
            "FAILED:b12-ceiling controls failed -- refusing to report a ceiling I cannot read"
        )
        return 2
    for r in rows:
        print(
            f"{r['event']:<14} mirror={r['manifest_mirror_s']} enforced={r['settings_enforced_s']} "
            f"match={r['mirror_matches_enforced']} maxcheck={r['max_declared_check_timeout_s']} "
            f"fits={r['worst_check_fits_enforced']}"
        )
    print(f"SUCCESS:b12-ceiling disagreements={c4_disagreements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
