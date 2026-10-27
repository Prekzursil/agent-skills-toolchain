"""P13 Q-core: measure the catalogued-vs-executed gap over all 2,007 work units.

The catalog carries NO execution-state field, so execution is measured by an
independent route: every work unit declares `output_path`; the unit produced
something iff that path exists on disk and is non-empty.

DETECTOR CONTROLS (both-states, mandatory before any "N never executed" claim):
  positive - a path that IS known to exist must be reported PRESENT
  negative - a path that is known ABSENT must be reported MISSING
  Both must hold or the script refuses to emit a verdict.

Read-only. Writes one JSON report.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
OUT = CC / "P13-EXECUTION-GAP.json"


def present(rel: str) -> tuple[bool, int]:
    """Return (exists_and_nonempty, size). rel is repo-relative POSIX-ish."""
    if not rel or not isinstance(rel, str):
        return False, -1
    p = REPO / rel.replace("\\", "/")
    try:
        if p.is_file():
            n = p.stat().st_size
            return (n > 0), n
        if p.is_dir():
            # a directory output counts as produced iff it holds >=1 non-empty file
            for q in p.rglob("*"):
                if q.is_file() and q.stat().st_size > 0:
                    return True, -2
            return False, -2
    except OSError:
        return False, -3
    return False, 0


def run_controls() -> dict:
    """Prove the detector finds a known-present file and fires on a known-absent one."""
    known_present = "command-center/WORK-UNIT-CATALOG.json"
    known_absent = "command-center/__p13_control_definitely_absent__.json"
    kp_ok, kp_size = present(known_present)
    ka_ok, _ = present(known_absent)
    # a second known-present of a DIFFERENT shape (directory)
    known_present_dir = "command-center/catalog-slices"
    kpd_ok, _ = present(known_present_dir)
    # a known-present-but-EMPTY file control: must report MISSING (non-empty rule)
    empty = CC / "__p13_control_empty__.tmp"
    empty.write_text("", encoding="utf-8")
    try:
        emp_ok, emp_size = present("command-center/__p13_control_empty__.tmp")
    finally:
        empty.unlink(missing_ok=True)
    return {
        "positive_file": {
            "path": known_present,
            "reported_present": kp_ok,
            "bytes": kp_size,
        },
        "positive_dir": {"path": known_present_dir, "reported_present": kpd_ok},
        "negative_absent": {"path": known_absent, "reported_present": ka_ok},
        "negative_empty": {
            "path": "command-center/__p13_control_empty__.tmp",
            "reported_present": emp_ok,
            "bytes": emp_size,
        },
        "all_pass": bool(kp_ok and kpd_ok and (not ka_ok) and (not emp_ok)),
    }


def main() -> int:
    controls = run_controls()
    if not controls["all_pass"]:
        print("FAILED:p13-execution-gap detector controls did not pass")
        print(json.dumps(controls, indent=2))
        return 1
    print("detector controls: PASS")
    print(json.dumps(controls, indent=2))

    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wus = cat["work_units"]

    produced: list[dict] = []
    missing: list[dict] = []
    for w in wus:
        ok, size = present(w.get("output_path", ""))
        rec = {
            "id": w.get("id"),
            "phase": str(w.get("phase")),
            "slice": w.get("_source_slice_file"),
            "output_path": w.get("output_path"),
            "bytes": size,
        }
        (produced if ok else missing).append(rec)

    by_phase_total: collections.Counter = collections.Counter(
        str(w.get("phase")) for w in wus
    )
    by_phase_done: collections.Counter = collections.Counter(
        r["phase"] for r in produced
    )
    by_slice_total: collections.Counter = collections.Counter(
        w.get("_source_slice_file") for w in wus
    )
    by_slice_done: collections.Counter = collections.Counter(
        r["slice"] for r in produced
    )

    # Distinct output DIRECTORIES the catalog expects, and whether each exists at all.
    dirs: dict[str, dict] = {}
    for w in wus:
        op = (w.get("output_path") or "").replace("\\", "/")
        d = op.rsplit("/", 1)[0] if "/" in op else ""
        rec = dirs.setdefault(
            d, {"expected": 0, "exists": (REPO / d).is_dir() if d else False}
        )
        rec["expected"] += 1

    report = {
        "artifact": "P13-EXECUTION-GAP",
        "unit": "depth/p13-blindspot",
        "status": "MEASURED",
        "probe": (
            "existence+non-emptiness of each work_unit.output_path on disk; the catalog "
            "carries no execution-state field so this is the only mechanically "
            "independent execution signal available"
        ),
        "detector_controls": controls,
        "totals": {
            "work_units_catalogued": len(wus),
            "output_present": len(produced),
            "output_missing": len(missing),
            "fraction_present": round(len(produced) / len(wus), 4),
        },
        "by_phase": {
            ph: {
                "catalogued": by_phase_total[ph],
                "produced": by_phase_done.get(ph, 0),
                "missing": by_phase_total[ph] - by_phase_done.get(ph, 0),
            }
            for ph in sorted(by_phase_total, key=lambda x: (len(x), x))
        },
        "by_slice": {
            sl: {
                "catalogued": by_slice_total[sl],
                "produced": by_slice_done.get(sl, 0),
                "missing": by_slice_total[sl] - by_slice_done.get(sl, 0),
            }
            for sl in sorted(by_slice_total)
        },
        "expected_output_dirs": {
            d: {"expected_units": v["expected"], "dir_exists": v["exists"]}
            for d, v in sorted(dirs.items(), key=lambda kv: -kv[1]["expected"])
        },
        "produced_sample": produced[:60],
        "produced_all_ids": [r["id"] for r in produced],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"catalogued={len(wus)} produced={len(produced)} missing={len(missing)}")
    print()
    print("=== by phase (catalogued / produced / missing) ===")
    for ph, v in report["by_phase"].items():
        print(
            f"  phase {ph:>3}  {v['catalogued']:5d} / {v['produced']:4d} / {v['missing']:5d}"
        )
    print()
    print("=== by slice ===")
    for sl, v in report["by_slice"].items():
        print(
            f"  {str(sl):16s} {v['catalogued']:5d} / {v['produced']:4d} / {v['missing']:5d}"
        )
    print()
    print("=== expected output dirs that DO NOT EXIST (top 25 by expected units) ===")
    n = 0
    for d, v in report["expected_output_dirs"].items():
        if not v["dir_exists"]:
            print(f"  {v['expected_units']:5d} units -> MISSING DIR {d}")
            n += 1
            if n >= 25:
                break
    print()
    print(f"SUCCESS:p13-execution-gap wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
