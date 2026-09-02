r"""H2 — is a hooks/<dir> genuinely unwired, or is it wired somewhere I did not look?

H1 flagged 30 repo hooks/<dir> as absent from BOTH the _dispatch manifest and
settings.json. That is one detector. Before calling any of them inert this
script checks four MORE surfaces that could wire a hook:

  1. ~/.agents/harness/*.py            (the SECOND dispatcher, 16 settings events)
  2. ~/.agents/harness/installed.json  (its install record)
  3. hooks/hooks.json                  (the Codex-side hook config)
  4. repo hooks/_dispatch/manifest.json `script` fields at ANY depth (not just dir[0])

DETECTOR CONTROL: a known-WIRED dir (`wire-check`) must come back wired on
surface 4, and a known-absent sentinel must come back unwired everywhere. If the
control fails the run aborts rather than reporting a clean 30.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
HARNESS = Path("C:/Users/Prekzursil/.agents/harness")
OUT = REPO / "command-center" / "hook-audit"

CANDIDATES = [
    "anti-degen",
    "beads",
    "calibrated-silence",
    "capability-catalog",
    "checkpoint",
    "compchem-preflight",
    "compute-confidence-gate",
    "contraindication",
    "event-ledger",
    "figma-mirror",
    "fresh-verify",
    "goal-reinject",
    "harness-bench",
    "iatrogenics",
    "inquisitiveness",
    "mcp-canonical-sync",
    "mcp-defaults",
    "mcp-userscope-sync",
    "memory-guard",
    "mvt-patch-leaving",
    "notify-idle",
    "orphan-commit",
    "persist-nudge",
    "recall-gate",
    "recall-inject",
    "skill-router",
    "strong-tool-nudge",
    "subagent-lifecycle",
    "tool-preflight",
    "truth-verify",
]
CONTROL_WIRED = "wire-check"  # must be found wired
CONTROL_ABSENT = "zzz-not-a-hook-xyz"  # must be found nowhere


def harness_text() -> str:
    buf = []
    for p in sorted(HARNESS.glob("*.py")):
        try:
            buf.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    for extra in ("installed.json",):
        q = HARNESS / extra
        if q.is_file():
            buf.append(q.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(buf)


def manifest_scripts() -> set[str]:
    man = json.loads(
        (REPO / "hooks/_dispatch/manifest.json").read_text(encoding="utf-8")
    )
    out = set()
    for blob in (man.get("events") or {}).values():
        for c in (blob or {}).get("checks") or []:
            if c.get("script"):
                out.add(c["script"].replace("\\", "/"))
    return out


def hooksjson_text() -> str:
    p = REPO / "hooks" / "hooks.json"
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def probe(name: str, ht: str, ms: set[str], hj: str) -> dict:
    tok = re.escape(name)
    return {
        "in_harness_py_or_installed": bool(re.search(tok, ht)),
        "in_dispatch_manifest_script": any(name + "/" in s for s in ms),
        "in_hooks_json": bool(re.search(tok, hj)),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ht, ms, hj = harness_text(), manifest_scripts(), hooksjson_text()

    cw = probe(CONTROL_WIRED, ht, ms, hj)
    ca = probe(CONTROL_ABSENT, ht, ms, hj)
    if not cw["in_dispatch_manifest_script"]:
        print(
            f"FAILED:h2-unwired control {CONTROL_WIRED} not found wired -> detector broken"
        )
        return 1
    if any(ca.values()):
        print(
            f"FAILED:h2-unwired absent-control {CONTROL_ABSENT} matched -> detector broken"
        )
        return 1
    print(f"  control OK: {CONTROL_WIRED}={cw}  {CONTROL_ABSENT}=all-false")

    rows = {n: probe(n, ht, ms, hj) for n in CANDIDATES}
    truly_dark = sorted(n for n, r in rows.items() if not any(r.values()))
    harness_only = sorted(
        n
        for n, r in rows.items()
        if r["in_harness_py_or_installed"] and not r["in_dispatch_manifest_script"]
    )
    hooksjson_only = sorted(
        n
        for n, r in rows.items()
        if r["in_hooks_json"]
        and not r["in_dispatch_manifest_script"]
        and not r["in_harness_py_or_installed"]
    )

    (OUT / "H2-UNWIRED.json").write_text(
        json.dumps(
            {
                "controls": {"wired": cw, "absent": ca},
                "rows": rows,
                "truly_dark": truly_dark,
                "named_in_harness_only": harness_only,
                "named_in_hooksjson_only": hooksjson_only,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nTRULY DARK ({len(truly_dark)}): {truly_dark}")
    print(f"named in harness only ({len(harness_only)}): {harness_only}")
    print(f"named in hooks.json only ({len(hooksjson_only)}): {hooksjson_only}")
    print("SUCCESS:h2-unwired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
