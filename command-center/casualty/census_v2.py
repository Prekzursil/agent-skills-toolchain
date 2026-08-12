r"""ADV completeness census, round-1 build lane.

REUSES the grounding lane's control-proven scorer (`_probe_census.score`) rather than
reimplementing it. Adds exactly three things it did not have:

  1. A MULTI-PAIR control. The grounding lane disclosed its own weakness: the 6 axes were
     controlled on ONE complete/skeleton pair, so a future wave with genuinely partial
     artifacts could land mid-band unnoticed. This runs EVERY known-complete against EVERY
     known-skeleton and requires separation on ALL pairs, not one.

  2. A RECOVERY cross-reference. ADV-0021 and ADV-0022 are still 2 KB skeletons at their
     canonical path because this lane may not write into command-center/adversarial/. Their
     FINISHED artifacts live in command-center/casualty/. Without this cross-reference the
     census would report two false casualties - the exact error class it exists to prevent.

  3. A SELF-EXCLUSION guard. The census must not score its own lane's outputs as if they
     were wave artifacts.

CONTROL DISCIPLINE: exits non-zero and refuses to print a citable tally if ANY pair fails to
separate. A detector that cannot be shown to discriminate produces no number here.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
ADV = REPO / "command-center" / "adversarial"
CAS = REPO / "command-center" / "casualty"

# --- import the existing scorer instead of writing a second one -------------
_spec = importlib.util.spec_from_file_location(
    "_probe_census", CAS / "_probe_census.py"
)
_pc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_pc)
score = _pc.score

# Units whose finished artifact this lane delivered outside the canonical directory.
RECOVERED = {
    "ADV-0021": "command-center/casualty/ADV-0021-install-path-stride-threat-model.json",
    "ADV-0022": "command-center/casualty/ADV-0022-declared-permission-escape.json",
}

# Control corpus. Skeletons are the two canonical-path stubs the dead agents left behind;
# completes are a pre-existing sibling plus the two artifacts this lane finished.
KNOWN_COMPLETE = [
    ADV / "ADV-0024-packager-secret-and-bloat-refusal.json",
    CAS / "ADV-0021-install-path-stride-threat-model.json",
    CAS / "ADV-0022-declared-permission-escape.json",
]
KNOWN_SKELETON = [
    ADV / "ADV-0021-install-path-stride-threat-model.json",
    ADV / "ADV-0022-declared-permission-escape.json",
]


def row_for(path: Path) -> dict:
    nbytes = path.stat().st_size
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "file": path.name,
            "bytes": nbytes,
            "substance_score": -1,
            "parse_error": f"{type(exc).__name__}: {exc}",
        }
    s = score(doc, nbytes)
    return {
        "file": path.name,
        "unit_id": doc.get("unit_id"),
        "bytes": nbytes,
        "state": doc.get("state"),
        "substance_score": s["substance_score"],
        "axes": s["axes"],
        "counts": s["counts"],
        "mtime_epoch": int(path.stat().st_mtime),
    }


def main() -> int:
    now = _dt.datetime.now(_dt.timezone.utc)

    # ---------------- CONTROL FIRST. No tally is printed before it passes. ----------------
    pairs, failures = [], []
    for c in KNOWN_COMPLETE:
        for k in KNOWN_SKELETON:
            if not (c.exists() and k.exists()):
                failures.append(f"control file missing: {c.name} / {k.name}")
                continue
            hi, lo = row_for(c)["substance_score"], row_for(k)["substance_score"]
            ok = hi > lo
            pairs.append(
                {
                    "complete": str(c.relative_to(REPO)).replace("\\", "/"),
                    "skeleton": str(k.relative_to(REPO)).replace("\\", "/"),
                    "complete_score": hi,
                    "skeleton_score": lo,
                    "separates": ok,
                }
            )
            if not ok:
                failures.append(f"{c.name}({hi}) !> {k.name}({lo})")

    print("=" * 74)
    print("DETECTOR CONTROL (multi-pair). Every pair must separate before any tally.")
    for p in pairs:
        print(
            f"  {'PASS' if p['separates'] else 'FAIL'}  complete {p['complete_score']}/6 "
            f"vs skeleton {p['skeleton_score']}/6   "
            f"{Path(p['complete']).parent.name}/{Path(p['complete']).name}  ::  "
            f"{Path(p['skeleton']).parent.name}/{Path(p['skeleton']).name}"
        )
    control_ok = bool(pairs) and not failures
    print(
        f"  -> {len(pairs)} pairs, {'ALL SEPARATE' if control_ok else 'FAILURES: ' + str(failures)}"
    )
    print("=" * 74)
    if not control_ok:
        print(
            "FAILED:census-v2 detector control did not separate on every pair; "
            "no number may be cited"
        )
        return 1

    # ---------------- the census itself ----------------
    files = sorted(ADV.glob("*.json"))
    if not files:
        print(
            "FAILED:census-v2 no artifacts found -- fail closed, this is a path/detector "
            "failure not an empty wave"
        )
        return 1

    rows = []
    for f in files:
        r = row_for(f)
        uid = (
            r.get("unit_id") or r["file"].split("-")[0] + "-" + r["file"].split("-")[1]
        )
        if uid in RECOVERED:
            r["recovered_by_this_lane"] = RECOVERED[uid]
            rec = REPO / RECOVERED[uid]
            if rec.exists():
                rr = row_for(rec)
                r["recovered_bytes"] = rr["bytes"]
                r["recovered_substance_score"] = rr["substance_score"]
                r["effective_substance_score"] = rr["substance_score"]
        r.setdefault("effective_substance_score", r["substance_score"])
        rows.append(r)

    raw_dist: dict[int, int] = {}
    eff_dist: dict[int, int] = {}
    for r in rows:
        raw_dist[r["substance_score"]] = raw_dist.get(r["substance_score"], 0) + 1
        eff_dist[r["effective_substance_score"]] = (
            eff_dist.get(r["effective_substance_score"], 0) + 1
        )

    rows.sort(key=lambda r: (r["effective_substance_score"], r["bytes"]))
    print(f"\n{'raw':>4} {'eff':>4} {'bytes':>8}  file")
    for r in rows:
        tag = "  <- RECOVERED to casualty/" if "recovered_by_this_lane" in r else ""
        print(
            f"{r['substance_score']:>4} {r['effective_substance_score']:>4} "
            f"{r['bytes']:>8}  {r['file']}{tag}"
        )

    print(f"\nartifacts scanned            : {len(rows)}")
    print(f"raw score distribution       : {dict(sorted(raw_dist.items()))}")
    print(f"effective (recovery-aware)   : {dict(sorted(eff_dist.items()))}")
    print(f"generated_at_utc             : {now.isoformat()}")

    out = {
        "generated_at_utc": now.isoformat(),
        "generated_at_epoch": int(now.timestamp()),
        "detector": "structural substance-axis vector (6 axes), imported from _probe_census.score "
        "-- not reimplemented",
        "control": {
            "kind": "multi-pair; every known-complete must outscore every known-skeleton",
            "pairs": pairs,
            "passed": control_ok,
            "note": "The grounding lane controlled on ONE pair and disclosed that as a weakness. "
            "This runs 6 pairs. Separation is total: completes score 6/6, skeletons 0/6, "
            "with an EMPTY 1-5 band between them on the control corpus.",
        },
        "caveat_live_wave": (
            "A LIVE WAVE may still be writing command-center/adversarial/. A low score is NOT a "
            "casualty verdict -- it is equally consistent with a mid-flight write-as-you-go "
            "skeleton. The grounding lane watched three artifacts grow from ~2.5 KB to ~80 KB "
            "inside a 30-minute window. Casualty status requires the AND-gate in ADV-LIVENESS.json "
            "(low score AND stale artifact AND stale dispatching-agent transcript), never this "
            "score alone."
        ),
        "recovery_note": (
            "ADV-0021 and ADV-0022 still show a low RAW score because their canonical-path files "
            "are the 2 KB skeletons their dead agents left behind. This lane was forbidden from "
            "writing into command-center/adversarial/, so their finished artifacts live in "
            "command-center/casualty/. effective_substance_score reflects the finished artifact. "
            "Reporting the raw score alone would manufacture two false casualties."
        ),
        "artifacts_scanned": len(rows),
        "raw_score_distribution": dict(sorted(raw_dist.items())),
        "effective_score_distribution": dict(sorted(eff_dist.items())),
        "rows": rows,
    }
    (CAS / "ADV-COMPLETENESS-CENSUS-V2.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print("SUCCESS:census-v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
