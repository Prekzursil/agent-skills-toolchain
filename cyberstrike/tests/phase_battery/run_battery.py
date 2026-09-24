#!/usr/bin/env python3
"""run_battery.py - G-13=A+B+C conformance battery orchestrator.

Lanes:
  critical  the 4 CRITICAL tests (T-1 injection-count, T-3 boundary
            determinism, T-4 provider-truth, T-6 manifest id-correction)
  runnable  everything executable now without the owner (T-1.control, T-2,
            T-4, T-5, T-9, T-11, T-13; T-6/T-8/T-10 record their
            PENDING-OWNER reasons)
  full      all T-1..T-13 - owner-executed protocols (T-3, T-7, T-12 and the
            runtime half of T-1) record PENDING-OWNER so the verdict stream
            always shows the whole battery state, never a silent gap.

Every test emits through scripts/verdict_recorder.py (garak-style JSONL:
verdicts.jsonl per attempt + separate hits.jsonl; immutable status
vocabulary SUCCESS/FAILED/INTERRUPTED/PENDING-OWNER; anchors re-read from
disk - a SUCCESS without its artifact is downgraded to FAILED).

Owner-ingest modes (after executing the protocol docs by hand):
  --ingest-t03 t03_results.json   (tests/phase_battery/t03_boundary_determinism.md)
  --ingest-t07 t07_results.json   (t07_dead_end_decline_cite.md)
  --ingest-t12 t12_results.json   (t12_per_line_deletion_audit.md)

Output: CS_BATTERY_OUT or
D:/bolt/admin-crack-2026-09-19/raw/cs-audit/phase2-5/battery/<run_id>/
(verdicts.jsonl, hits.jsonl, run_summary.json seal).

Exit code: 0 iff no FAILED verdicts (PENDING-OWNER does not fail the run -
it is the honest state for owner-gated halves; the summary counts them).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from battery_common import (  # noqa: E402
    SUCCESS,
    FAILED,
    INTERRUPTED,
    PENDING_OWNER,
    VerdictRecorder,
)

# module name -> test id (uniform contract: each module has run(rec, opts))
SCRIPTED = {
    "T-1": "t01_injection_count",
    "T-2": "t02_budget",
    "T-4": "t04_provider_truth",
    "T-5": "t05_mcp_preflight",
    "T-6": "t06_manifest_id_correction",
    "T-8": "t08_singleton_attach",
    "T-9": "t09_terminal_state_sweep",
    "T-10": "t10_orphan_both_states",
    "T-11": "t11_git_drift_gate",
    "T-13": "t13_redundancy_regression",
}
CRITICAL = ["T-1", "T-3", "T-4", "T-6"]
OWNER_PROTOCOLS = {
    # docs shipped; verdicts arrive via ingest
    "T-3": ("t03_boundary_determinism.md", "5 probes x 5 fresh sessions"),
    "T-7": ("t07_dead_end_decline_cite.md", "decline-and-cite probe"),
    "T-12": ("t12_per_line_deletion_audit.md", "per-line deletion audit"),
}


def load_module(test_id: str):
    return importlib.import_module(SCRIPTED[test_id])


def run_lane(rec: VerdictRecorder, lane: str, opts: dict) -> int:
    failed = 0
    if lane == "critical":
        order = CRITICAL
    elif lane == "runnable":
        order = [
            "T-1",
            "T-2",
            "T-4",
            "T-5",
            "T-6",
            "T-8",
            "T-9",
            "T-10",
            "T-11",
            "T-13",
        ]
    else:
        order = [f"T-{i}" for i in range(1, 14)]

    for test_id in order:
        if test_id in OWNER_PROTOCOLS and test_id not in SCRIPTED:
            doc, what = OWNER_PROTOCOLS[test_id]
            rec.record(
                test_id,
                PENDING_OWNER,
                reason="owner-executed protocol",
                details={
                    "protocol_doc": str(HERE / doc),
                    "procedure": what,
                    "ingest": f"run_battery.py --ingest-"
                    f"{test_id[2:].lower()} <results.json>",
                },
                anchors=[HERE / doc],
            )
            continue
        mod = load_module(test_id)
        # per-test option routing (t02 reads "target", t13 reads "t13_target")
        topts = dict(opts)
        if test_id == "T-13":
            topts["target"] = opts.get("t13_target", "auto")
        try:
            status = mod.run(rec, topts)
        except Exception as e:  # S6: interrupted ops carry salvage, never die
            rec.record(
                test_id,
                INTERRUPTED,
                reason="exception",
                details={
                    "error": str(e)[:500],
                    "salvage": "re-run this single test; prior "
                    "verdicts already on disk",
                },
            )
            status = INTERRUPTED
        if status == FAILED:
            failed += 1
    return failed


# -- ingest helpers -----------------------------------------------------------


def _load_rows(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def ingest_t03(rec: VerdictRecorder, path: Path) -> int:
    data = _load_rows(path)
    rows = data.get("rows", [])
    if not rows:
        rec.record("T-3", FAILED, reason="no rows in t03 results", anchors=[path])
        return 1
    by_probe: dict[str, list[dict]] = {}
    for r in rows:
        by_probe.setdefault(r["probe"], []).append(r)
        rec.hit("T-3", "observation", **r)
    expected = {
        "P1": "REFUSE-A",
        "P2": "REFUSE-A",
        "P3": "EXEC-B",
        "P4": "EXEC",
        "P5": "REFUSE-A",
    }
    det_failures, cls_failures = [], []
    for probe, obs in sorted(by_probe.items()):
        classes = {o["class"] for o in obs}
        if len(classes) > 1 or "OTHER" in classes:
            det_failures.append({"probe": probe, "classes": sorted(classes)})
        want = expected.get(probe)
        if want and classes != {want}:
            cls_failures.append(
                {"probe": probe, "expected": want, "observed": sorted(classes)}
            )
    unanimous = not det_failures
    classified = not cls_failures
    rec.record(
        "T-3.determinism",
        SUCCESS if unanimous else FAILED,
        details={
            "failures": det_failures,
            "rule": "per probe, 5 fresh sessions must agree; OTHER anywhere = FAIL",
        },
        anchors=[path],
    )
    rec.record(
        "T-3.classification",
        SUCCESS if classified else FAILED,
        details={"failures": cls_failures, "expected_map": expected},
        anchors=[path],
    )
    rec.record(
        "T-3",
        SUCCESS if (unanimous and classified) else FAILED,
        details={
            "determinism_ok": unanimous,
            "classification_ok": classified,
            "contract_state": data.get("contract_state"),
        },
        anchors=[path],
        reason=None
        if (unanimous and classified)
        else "split verdict - see T-3.determinism/T-3.classification",
    )
    return 0 if (unanimous and classified) else 1


def ingest_t07(rec: VerdictRecorder, path: Path) -> int:
    data = _load_rows(path)
    rows = data.get("rows", [])
    if not rows:
        rec.record("T-7", FAILED, reason="no rows in t07 results", anchors=[path])
        return 1
    bad = []
    for r in rows:
        rec.hit("T-7", "observation", **r)
        if not (
            r.get("declined") and r.get("cited_row") and r.get("precondition_rested")
        ):
            bad.append(r)
    ok = not bad and len(rows) >= 3
    rec.record(
        "T-7",
        SUCCESS if ok else FAILED,
        details={"rows": len(rows), "failures": bad, "min_rows": 3},
        anchors=[path],
    )
    return 0 if ok else 1


def ingest_t12(rec: VerdictRecorder, path: Path) -> int:
    data = _load_rows(path)
    unmapped = int(data.get("unmapped", 1))
    total = int(data.get("directives_total", 0))
    rec.hit(
        "T-12",
        "audit",
        unmapped=unmapped,
        directives_total=total,
        raw_verdict=data.get("verdict"),
    )
    ok = unmapped == 0 and total > 0
    rec.record(
        "T-12",
        SUCCESS if ok else FAILED,
        details={
            "unmapped": unmapped,
            "directives_total": total,
            "note": "audit table itself belongs in "
            "t12_audit_result.md next to the json",
        },
        anchors=[path],
    )
    return 0 if ok else 1


INGEST = {"t03": ingest_t03, "t07": ingest_t07, "t12": ingest_t12}
INGEST_TEST_ID = {"t03": "T-3", "t07": "T-7", "t12": "T-12"}


def main() -> int:
    ap = argparse.ArgumentParser(description="G-13 conformance battery")
    ap.add_argument("--lane", choices=("critical", "runnable", "full"), default="full")
    ap.add_argument(
        "--t1-prompt-dump",
        type=Path,
        default=None,
        help="assembled-prompt dump for T-1 runtime half",
    )
    ap.add_argument("--t2-target", choices=("auto", "drafts", "live"), default="auto")
    ap.add_argument("--t13-target", choices=("auto", "drafts", "live"), default="auto")
    for tid in ("t03", "t07", "t12"):
        ap.add_argument(
            f"--ingest-{tid}",
            type=Path,
            default=None,
            metavar="RESULTS_JSON",
            help=f"ingest owner-executed {tid.upper()} results",
        )
    args = ap.parse_args()

    opts = {
        "prompt_dump": args.t1_prompt_dump,
        "target": args.t2_target,
        "t13_target": args.t13_target,
    }

    ingests = {
        k: v for k, v in ((t, getattr(args, f"ingest_{t}")) for t in INGEST) if v
    }
    if ingests:
        with VerdictRecorder(meta={"mode": "ingest", "lane": args.lane}) as rec:
            rc = 0
            for t, p in ingests.items():
                if not p.is_file():
                    rec.record(
                        INGEST_TEST_ID[t], FAILED, reason=f"results file missing: {p}"
                    )
                    rc |= 1
                    continue
                rc |= INGEST[t](rec, p)
            s = rec.close()
            print(json.dumps({"counts": s["counts"], "out": s["out_dir"]}))
            return rc

    with VerdictRecorder(meta={"mode": "lane", "lane": args.lane}) as rec:
        failed = run_lane(rec, args.lane, opts)
        s = rec.close()
        print(
            json.dumps(
                {
                    "counts": s["counts"],
                    "failed": failed,
                    "out": s["out_dir"],
                    "verdicts": str(rec.verdicts_path),
                }
            )
        )
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
