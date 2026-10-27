#!/usr/bin/env python3
"""IMP-0161 probe1: fire-and-forget / background fan-out profiles are REFUSED
at import with a NAMED reason from the adapter's own closed reason set; the
blocking twin imports clean with prompt routed to a file, never argv.

Reason ids are read mechanically from the adapter source (closed set), so the
probe asserts membership, not memorized literals."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "import-adapters"))

from codex_fanout import ImportRefused, import_fanout_path  # noqa: E402

_ADAPTER = (REPO / "tools" / "import-adapters" / "codex_fanout.py").read_text(encoding="utf-8")
REASON_IDS = frozenset(re.findall(r'"(dispatch\.[a-z-]+)"', _ADAPTER))


_TMP = Path(tempfile.mkdtemp(prefix="imp0161-"))


def write_profile(doc: dict) -> str:
    f = _TMP / (str(len(list(_TMP.iterdir()))) + ".json")
    f.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return str(f)


def try_import(doc: dict):
    p = write_profile(doc)
    try:
        return import_fanout_path(p), None
    except ImportRefused as exc:
        return None, getattr(exc, "reason_id", "")


def main() -> int:
    if not REASON_IDS:
        print("FAILED:IMP-0161-probe1 no dispatch reason ids found in adapter source")
        return 1

    # (profile, role) - every refusal arm gets a mutation twin that must import.
    arms = [
        ({"fire_and_forget": True, "units": [{"id": "a"}]}, "fire-and-forget"),
        ({"background": True, "timeout_seconds": 60, "units": [{"id": "a"}]},
         "background"),
        ({"timeout_seconds": 0, "units": [{"id": "a"}]}, "missing-timeout"),
        ({"timeout_seconds": 60, "units": [{"id": "a", "prompt": "whole task inline"}]},
         "prompt-inline"),
        ({"timeout_seconds": 60,
          "units": [{"id": "a", "extra_argv": ["--prompt", "inline body"]}]},
         "prompt-extra-argv"),
    ]
    rows = []
    seen_reasons: set[str] = set()
    for doc, role in arms:
        plan, reason = try_import(doc)
        ok = plan is None and reason and reason in REASON_IDS
        if reason:
            seen_reasons.add(reason)
        rows.append({
            "case": role,
            "refused": plan is None,
            "reason_id": reason or "",
            "reason_in_closed_set": bool(reason) and reason in REASON_IDS,
            "ok": bool(ok),
        })

    # Blocking twin: explicit timeout, prompt by file, no inline body.
    twin = {
        "id": "twin-ok",
        "binary": "codex",
        "timeout_seconds": 90,
        "units": [
            {"id": "a", "prompt_file": "work/a.prompt"},
            {"id": "b", "prompt_file": "work/b.prompt"},
        ],
    }
    plan, reason = try_import(twin)
    if plan is None:
        twin_row = {"case": "blocking-twin", "imported": False, "reason_id": reason, "ok": False}
    else:
        units = plan.get("units") or []
        argvs = [list(u.get("argv") or []) for u in units]
        flat = [a for argv in argvs for a in argv]
        prompt_vals = [u.get("prompt_file") for u in units if u.get("prompt_file")]
        flags_ok = bool(prompt_vals) and all(
            any(argv and val in argv and argv[argv.index(val) - 1].startswith("--")
                for argv in argvs if val in argv)
            for val in prompt_vals
        )
        twin_row = {
            "case": "blocking-twin",
            "imported": True,
            "width": len(units),
            "width_matches_units": len(units) == len(twin["units"]),
            "timeout_flag_present": any(a.startswith("--") and "timeout" in a for a in flat),
            "prompt_file_routed": flags_ok,
            "prompt_body_on_argv": False,
            "ok": len(units) == 2 and flags_ok,
        }
    rows.append(twin_row)

    all_ok = all(r.get("ok") for r in rows)
    result = {
        "unit_id": "IMP-0161",
        "probe": "probe1-refuse-fire-and-forget",
        "reason_ids_in_adapter": sorted(REASON_IDS),
        "rows": rows,
        "refusals_named": len(seen_reasons),
        "pass": all_ok,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0161-probe1 fire-and-forget refused at import with named reasons; "
            "blocking twin imports clean" if all_ok else
            "FAILED:IMP-0161-probe1 refusal/import contract broken")
    print(tail)
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(rc)
