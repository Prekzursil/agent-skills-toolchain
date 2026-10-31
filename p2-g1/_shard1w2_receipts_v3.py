#!/usr/bin/env python3
"""Shard1 wave-2 receipt writer for the 9 from-scratch probe units.

Reuses the schema-validated build() from _shard1w2_receipts_v2.py, extending
UNITS with the 9 units whose probe dirs were emitted this session.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location(
    "shard1w2_receipts_v2", REPO / "_shard1w2_receipts_v2.py"
)
v2 = importlib.util.module_from_spec(spec)
sys.modules["shard1w2_receipts_v2"] = v2
spec.loader.exec_module(v2)

MORE = {
    "ADV-0040": {
        "out": "command-center/adversarial/ADV-0040-corpus-pii-recall-calibrated-sweep.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0040",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (19308 bytes), parses, "
            "sentinel present, one verdict per enumerated target, 8 text + 3 negative controls recorded; probe1 "
            "delivery predicate and probe2 re-derivation (planted-PII recall 8/8=1.0 recomputed from text 6/6 + "
            "png-ztxt 2/2; T2 hits==corpus email count) both exited 0 live. state stays BLOCKED/reviewer-absent "
            "per receipt_core; prior SUCCESS receipt carried NO reviewer block and was rewritten to this posture."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: prior receipt claimed state=SUCCESS with no reviewer "
            "block (contract-invalid; rewritten). Probes built from scratch this session. No owner gate."
        ),
    },
    "ADV-0090": {
        "out": "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0090",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (32138 bytes), parses, "
            "sentinel present; probe1 predicate and probe2 re-derivation (synthetic-6-of-10 flaky fixture fires "
            "flaky on bad state and stays silent on deterministic good state; verdict stays PARTIAL, not "
            "laundered green; probe1_answer == report.answer) both exited 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0091": {
        "out": "command-center/adversarial/ADV-0091-instant-unanimity-trigger.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0091",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (11935 bytes), parses, "
            "sentinel present, 4 verdicts; probe2 re-derives the trigger asymmetry (primed round-1 zero-brief "
            "unanimity FIRES with hold-for-revaluation live; late legitimate unanimity does NOT) and that zero "
            "listed interventions executed. Both probes exit 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0100": {
        "out": "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0100",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (83430 bytes), parses, "
            "sentinel present, 3 targets CONFIRMED; probe2 re-derives the COI detector both-states control "
            "(known-present self-author FIREd and excluded) and live re-verifies a production-census byte count "
            "on this worktree. Both probes exit 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0109": {
        "out": "command-center/adversarial/ADV-0109-dissent-omission-differential.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0109",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (39544 bytes), parses, "
            "sentinel present, 5 verdicts; probe2 recomputes the forward ratio (1+1+3 == denominator 5, drop_rate "
            "0.6) and the planted-silent-drop control (got==want==silently-dropped). Both probes exit 0 live. "
            "BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0110": {
        "out": "command-center/adversarial/ADV-0110-root-cause-hierarchy-falsifiability.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0110",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (78472 bytes), parses, "
            "sentinel present, 124 falsifiability verdicts one per target (targets==enumerated_targets map "
            "equality re-derived); declared output_schema file verified present live; audit_sha256 well-formed. "
            "Both probes exit 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0117": {
        "out": "command-center/adversarial/ADV-0117-windows-hostile-path-matrix.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0117",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (248441 bytes), parses, "
            "sentinel present; probe2 recomputes count_summary total (28+2+16+3=49) from the raw component_matrix "
            "rows and the ordinary-class correct==7 histogram from per_class. Both probes exit 0 live. "
            "BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0119": {
        "out": "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0119",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (17762 bytes), parses, "
            "sentinel present, 5 targets CONFIRMED; probe2 re-derives the three-point inventory invariants "
            "(byte-identical user data, commands restored, zero N-only residue lists empty) and golden-journey "
            "rc=0 rows. Both probes exit 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
    "ADV-0123": {
        "out": "command-center/adversarial/ADV-0123-concurrent-session-index-and-lease-race.json",
        "probe_dir": "command-center/p2-wave/probes/ADV-0123",
        "reason": (
            "Independent reviewer closure unavailable in builder shard. Artifact exists (17534 bytes), parses, "
            "sentinel present, 4 targets one verdict each aligned 1:1 with evidence; probe2 re-derives the "
            "broad-stage sibling-contamination oracle output (non-empty sibling_in_cached), 3/3 PASS controls, "
            "and F1/F2 findings at P0+P1. Both probes exit 0 live. BLOCKED/reviewer-absent."
        ),
        "note": (
            "Shard1 wave-2 builder (resume) 2026-10-25: probe dir built from scratch this session. No owner gate."
        ),
    },
}


def main() -> int:
    import json
    import subprocess

    v2.UNITS.update(MORE)
    ids = sys.argv[1:] or list(MORE)
    rc = 0
    for uid in ids:
        cfg = v2.UNITS[uid]
        r = subprocess.run(
            [sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=3600,
        )
        tail = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode != 0:
            print(f"SKIP receipt {uid}: measure not green: {tail[-200:]}")
            rc = 1
            continue
        receipt = v2.build(uid, cfg, tail)
        outp = REPO / "command-center" / "receipts" / f"{uid}.json"
        outp.write_text(
            json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8", newline=chr(10)
        )
        print("wrote", outp)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
