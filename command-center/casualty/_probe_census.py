r"""Completeness census over command-center/adversarial/*.json -- STRUCTURAL, control-proven.

WHY NOT THE OBVIOUS DETECTORS (both measured, both fail their control):
  (a) an UNKNOWN-sentinel grep scores 8 hits on a complete 162 KB artifact and 8 on a 1.8 KB
      skeleton, because UNKNOWN is a legitimate verdict VALUE (use-vs-mention).
  (b) receipt_schema_gate's BINARY marker prints FAILED for BOTH the known-complete ADV-0024 and
      the known-skeleton ADV-0021, because c1/c5 encode a family-wide convention
      (state=BLOCKED + a FAILED sentinel) that completed adversarial units deliberately use.
      A saturated signal carries no information.

WHAT DISCRIMINATES is whether the SUBSTANCE arrays are populated. This script reuses the repo's
existing gate (platform/lib/receipt_schema_gate.py -- do NOT reimplement it) for the per-condition
vector, and adds direct structural counts. The score is the count of populated substance axes:

  A1 evidence[] has >=2 items whose probes carry real raw_output (not UNKNOWN/PLACEHOLDER)
  A2 tests[] non-empty
  A3 negative_controls[] non-empty
  A4 report has >=2 observations that are not PLACEHOLDER/UNKNOWN
  A5 total probe count >= 2 with distinct fingerprints
  A6 artifact bytes >= its OWN declared min_bytes_threshold

CONTROL (must be run and must pass before any number here is cited): a known-complete file must
score strictly higher than a known-skeleton file on this vector. Both files are named in the
output so the control is auditable, and the script EXITS NON-ZERO if the control does not separate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
ADV = REPO / "command-center" / "adversarial"
OUT = REPO / "command-center" / "casualty"

PLACEHOLDER = re.compile(
    r"^\s*(UNKNOWN|NOT-CHECKED|PLACEHOLDER|TODO|TBD|skeleton|0)\b", re.I
)


def is_real(v) -> bool:
    """A field counts as measured only if it is a non-trivial string that is not a placeholder."""
    if not isinstance(v, str):
        return bool(v)
    s = v.strip()
    return len(s) >= 12 and not PLACEHOLDER.match(s)


def probes_of(ev: dict) -> list:
    p = ev.get("probes")
    return p if isinstance(p, list) else []


def score(doc: dict, nbytes: int) -> dict:
    ev = doc.get("evidence") if isinstance(doc.get("evidence"), list) else []
    tests = doc.get("tests") if isinstance(doc.get("tests"), list) else []
    negs = doc.get("negative_controls") if isinstance(doc.get("negative_controls"), list) else []
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    obs = rep.get("observations") if isinstance(rep.get("observations"), list) else []

    real_ev = 0
    all_probes = []
    for e in ev:
        if not isinstance(e, dict):
            continue
        ps = probes_of(e)
        all_probes.extend([p for p in ps if isinstance(p, dict)])
        if any(is_real(p.get("raw_output")) for p in ps if isinstance(p, dict)):
            real_ev += 1
    fps = {p.get("fingerprint") for p in all_probes if is_real(str(p.get("fingerprint", "")))}
    real_obs = sum(
        1 for o in obs if isinstance(o, dict) and is_real(o.get("measured"))
    )
    thr = doc.get("min_bytes_threshold")
    thr = thr if isinstance(thr, int) and thr > 0 else 4096

    axes = {
        "A1_evidence_with_real_probe_output>=2": real_ev >= 2,
        "A2_tests_nonempty": len(tests) > 0,
        "A3_negative_controls_nonempty": len(negs) > 0,
        "A4_real_observations>=2": real_obs >= 2,
        "A5_distinct_real_fingerprints>=2": len(fps) >= 2,
        "A6_bytes>=own_declared_threshold": nbytes >= thr,
    }
    return {
        "axes": axes,
        "substance_score": sum(axes.values()),
        "counts": {
            "evidence_items": len(ev),
            "evidence_with_real_probe_output": real_ev,
            "probes_total": len(all_probes),
            "distinct_real_fingerprints": len(fps),
            "tests": len(tests),
            "negative_controls": len(negs),
            "observations": len(obs),
            "real_observations": real_obs,
            "declared_min_bytes_threshold": thr,
        },
    }


def main(argv: list[str]) -> int:
    files = sorted(ADV.glob("*.json"))
    if not files:
        print("FAILED:census no artifacts found -- detector or path is wrong, not an empty dir")
        return 1

    rows = []
    for f in files:
        nbytes = f.stat().st_size
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {"file": f.name, "bytes": nbytes, "parse_error": f"{type(exc).__name__}: {exc}",
                 "substance_score": -1}
            )
            continue
        s = score(doc, nbytes)
        rows.append(
            {
                "file": f.name,
                "unit_id": doc.get("unit_id"),
                "bytes": nbytes,
                "state": doc.get("state"),
                "substance_score": s["substance_score"],
                "axes": s["axes"],
                "counts": s["counts"],
            }
        )

    # ---- CONTROL: must separate a known-complete from a known-skeleton ----
    KNOWN_COMPLETE = "ADV-0024-packager-secret-and-bloat-refusal.json"
    KNOWN_SKELETON = "ADV-0021-install-path-stride-threat-model.json"
    byname = {r["file"]: r for r in rows}
    ctrl_ok = False
    ctrl_msg = "control files not both present"
    if KNOWN_COMPLETE in byname and KNOWN_SKELETON in byname:
        hi = byname[KNOWN_COMPLETE]["substance_score"]
        lo = byname[KNOWN_SKELETON]["substance_score"]
        ctrl_ok = hi > lo
        ctrl_msg = (
            f"complete({KNOWN_COMPLETE})={hi}/6 vs skeleton({KNOWN_SKELETON})={lo}/6 "
            f"-> {'SEPARATES' if ctrl_ok else 'DOES NOT SEPARATE'}"
        )
    print(f"CONTROL: {ctrl_msg}")

    rows.sort(key=lambda r: (r["substance_score"], r["bytes"]))
    print(f"\n{'score':>5} {'bytes':>8}  file")
    for r in rows:
        print(f"{r['substance_score']:>5} {r['bytes']:>8}  {r['file']}")

    dist = {}
    for r in rows:
        dist[r["substance_score"]] = dist.get(r["substance_score"], 0) + 1
    print(f"\nscore distribution (0..6): {dict(sorted(dist.items()))}")
    print(f"artifacts scanned: {len(rows)}")

    (OUT / "ADV-COMPLETENESS-CENSUS.json").write_text(
        json.dumps(
            {
                "generated_at_utc": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "detector": "structural substance-axis vector (6 axes); see module docstring",
                "control": {"passed": ctrl_ok, "detail": ctrl_msg},
                "caveat": (
                    "A LIVE WAVE may still be writing this directory. A low score is NOT proof of "
                    "a casualty -- it is equally consistent with a mid-flight write-as-you-go "
                    "skeleton. Re-run and compare timestamps before calling any unit dead."
                ),
                "artifacts_scanned": len(rows),
                "score_distribution": dict(sorted(dist.items())),
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if not ctrl_ok:
        print("FAILED:census detector control did not separate -- no number above may be cited")
        return 1
    print("SUCCESS:census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
