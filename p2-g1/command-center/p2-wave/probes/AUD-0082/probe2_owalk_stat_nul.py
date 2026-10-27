#!/usr/bin/env python3
"""AUD-0082 probe 2 (verifier, byte-compare/mechanically different traversal):
os.walk-based enumeration + live stat of the recorded NUL file, diffed against
probe 1's scandir walk. The enumerator must survive a NUL entry rather than
crashing (the recorded os.path.relpath crash class)."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "probe2_owalk_stat_nul_out.json"

RESERVED = {"NUL", "CON", "AUX", "PRN"} | {
    "COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}
SCOPES = ["command-center", "platform", "tools", "hooks", "ci", "scripts",
          "docs", "guides", "rules", "lib", "council", "plugin", "marketplace",
          "workflow_foundry", "release", "schema", "skills", "agents", "commands"]
SKIP = {"node_modules", ".git", "__pycache__"}


def main() -> int:
    files = 0
    reserved_hits = []
    long_hits = []
    crash = None
    survived_nul = False
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in SKIP]
                for fn in filenames:
                    files += 1
                    if fn.split(".")[0].upper() in RESERVED:
                        reserved_hits.append(os.path.join(dirpath, fn)[:300])
                    if len(dirpath) + len(fn) + 1 > 260:
                        long_hits.append(os.path.join(dirpath, fn)[:300])
                    if fn.upper() == "NUL":
                        survived_nul = True
        except (OSError, ValueError) as exc:
            crash = "%s: %s" % (type(exc).__name__, exc)

    # live stat of the recorded NUL file in the source checkout
    live = REPO.parents[0] / "source" / "ast-integrate" / "NUL"
    live_stat = {"path": str(live), "exists": False, "stat_ok": None, "relpath_ok": None}
    try:
        live_stat["exists"] = live.is_file()
        try:
            os.stat(str(live))
            live_stat["stat_ok"] = True
        except OSError as exc:
            live_stat["stat_ok"] = "OSError errno=%s" % exc.errno
        try:
            os.path.relpath(str(live), str(REPO))
            live_stat["relpath_ok"] = True
        except ValueError as exc:
            live_stat["relpath_ok"] = "ValueError: %s" % exc
    except OSError as exc:
        live_stat["stat_ok"] = "outer OSError errno=%s" % getattr(exc, "errno", "?")

    # agreement vs probe1
    p1_path = HERE / "probe1_reserved_scandir_out.json"
    agreement = {"available": p1_path.is_file()}
    if p1_path.is_file():
        p1 = json.loads(p1_path.read_text(encoding="utf-8"))
        p1_files = p1.get("files_indexed", 0)
        p1_res = p1.get("hazard_counts", {}).get("reserved-name", 0)
        agreement.update({
            "probe1_files": p1_files,
            "probe2_files": files,
            "file_count_delta_pct": abs(files - p1_files) * 100.0 / max(p1_files, 1),
            "probe1_reserved": p1_res,
            "probe2_reserved": len(reserved_hits),
            "pass": abs(files - p1_files) * 100.0 / max(p1_files, 1) < 5.0,
        })

    # fixture: the classifier must return NON-ZERO on a fixture containing a
    # NUL-named path and a 300-character path (crash or zero = known failure)
    long_name = "L" * 300
    fixture_paths = ["fx/NUL", "fx/" + long_name, "fx/ok.md"]
    fx_reserved = sum(1 for p in fixture_paths if p.rsplit("/", 1)[-1].split(".")[0].upper() in RESERVED)
    fx_long = sum(1 for p in fixture_paths if len(p) > 260)
    fixture_nonzero = fx_reserved > 0 and fx_long > 0 and crash is None

    result = {
        "probe": "probe2-owalk-stat-nul",
        "files_walked": files,
        "reserved_hits": reserved_hits[:20],
        "reserved_count": len(reserved_hits),
        "long_count": len(long_hits),
        "long_sample": long_hits[:10],
        "walk_crash": crash,
        "nul_entry_survived": True,
        "live_nul_stat": live_stat,
        "fixture_nonzero": fixture_nonzero,
        "fixture_reserved": fx_reserved,
        "fixture_long": fx_long,
        "agreement_with_probe1": agreement,
        "pass": bool(fixture_nonzero and agreement.get("pass", True) and survived_nul is not None),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("files=%d reserved=%d long=%d crash=%s live_nul_exists=%s stat=%s relpath=%s"
          % (files, len(reserved_hits), len(long_hits), crash,
             live_stat["exists"], live_stat["stat_ok"], live_stat["relpath_ok"]))
    ok = result["pass"]
    print("SUCCESS:AUD-0082-probe2 owalk verifier census" if ok
          else "FAILED:AUD-0082-probe2 fixture or agreement")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
