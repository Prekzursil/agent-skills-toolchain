#!/usr/bin/env python3
"""Shard1 wave-2 driver: manifest + SUBAGENT-RETURN + measure for the 9 units.

Per unit: run probe1 (must exit 0) -> write UNIT-ARTIFACT-MANIFEST.json
(LF-normalized sha of the live artifact) -> run probe2 (must exit 0; it
byte-compares the manifest) -> write SUBAGENT-RETURN.json -> run
command-center/p2-wave/_measure_one_delivered.py (must print SUCCESS).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
UNITS = {
    "ADV-0040": "command-center/adversarial/ADV-0040-corpus-pii-recall-calibrated-sweep.json",
    "ADV-0090": "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json",
    "ADV-0091": "command-center/adversarial/ADV-0091-instant-unanimity-trigger.json",
    "ADV-0100": "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json",
    "ADV-0109": "command-center/adversarial/ADV-0109-dissent-omission-differential.json",
    "ADV-0110": "command-center/adversarial/ADV-0110-root-cause-hierarchy-falsifiability.json",
    "ADV-0117": "command-center/adversarial/ADV-0117-windows-hostile-path-matrix.json",
    "ADV-0119": "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json",
    "ADV-0123": "command-center/adversarial/ADV-0123-concurrent-session-index-and-lease-race.json",
}
NOTES = {
    "ADV-0040": "Resume 2026-10-25: prior builder artifact verified; probe1 predicate + probe2 recall re-derivation (text 6/6 + png-ztxt 2/2 == 8/8) + manifest byte-compare + mutation both-states control. No owner gate (owner_approval_required=false).",
    "ADV-0090": "Resume 2026-10-25: prior builder artifact verified; probe2 re-derives the synthetic-6-of-10 flaky-fixture both-states control and the PARTIAL (not laundered-green) verdict consistency. No owner gate.",
    "ADV-0091": "Resume 2026-10-25: prior builder artifact verified; probe2 re-derives primed-fires/late-silent trigger asymmetry and that zero listed interventions executed. No owner gate.",
    "ADV-0100": "Resume 2026-10-25: prior builder artifact verified; probe2 re-derives the COI detector both-states control and live re-verifies a production-census byte count on this worktree. No owner gate.",
    "ADV-0109": "Resume 2026-10-25: prior builder artifact verified; probe2 recomputes the forward ratio (1+1+3=5, drop_rate 0.6) and the planted-drop control. No owner gate.",
    "ADV-0110": "Resume 2026-10-25: prior builder artifact verified; probe2 checks targets==enumerated_targets map equality and live schema-file presence; 124 falsifiability verdicts, one each. No owner gate.",
    "ADV-0117": "Resume 2026-10-25: prior builder artifact verified; probe2 recomputes count_summary total (49) from raw component_matrix rows and the ordinary-class correct==7 histogram. No owner gate.",
    "ADV-0119": "Resume 2026-10-25: prior builder artifact verified; probe2 re-derives the three-point inventory invariants (zero missing/altered/leftover) and golden-journey rc=0 rows. No owner gate.",
    "ADV-0123": "Resume 2026-10-25: prior builder artifact verified; probe2 re-derives target/evidence alignment, the broad-stage sibling-contamination oracle output, and F1/F2 P0+P1 findings. No owner gate.",
}


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), timeout=3600)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    ids = sys.argv[1:] or list(UNITS)
    bad = []
    for uid in ids:
        out_rel = UNITS[uid]
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        p1, p2 = pdir / "probe1_delivery_predicate.py", pdir / "probe2_independent_recheck.py"

        rc1, out1 = run([sys.executable, "-B", str(p1.relative_to(REPO))])
        if rc1 != 0:
            print(f"{uid} probe1 rc={rc1}: {out1[-300:]}")
            bad.append(uid)
            continue

        raw = (REPO / out_rel).read_bytes()
        norm = raw.replace(b"\r\n", b"\n")
        sha = hashlib.sha256(norm).hexdigest()
        rows = [
            {
                "unit_id": uid,
                "path": out_rel,
                "bytes": len(norm),
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": "primary",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
            {
                "unit_id": uid,
                "path": f"command-center/p2-wave/probes/{uid}/probe1_delivery_predicate.py",
                "bytes": p1.stat().st_size,
                "sha256": hashlib.sha256(p1.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "exists": True,
                "eol": "LF",
                "role": "supporting",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
            {
                "unit_id": uid,
                "path": f"command-center/p2-wave/probes/{uid}/probe2_independent_recheck.py",
                "bytes": p2.stat().st_size,
                "sha256": hashlib.sha256(p2.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "exists": True,
                "eol": "LF",
                "role": "supporting",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
        ]
        (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "contract": "completion-predicate-condition-11-unit-artifact-registration",
                    "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
                    "unit_id": uid,
                    "artifacts": rows,
                    "present": len(rows),
                    "expected": len(rows),
                    "verified_on_disk": True,
                },
                indent=1,
            ),
            encoding="utf-8",
            newline="\n",
        )

        rc2, out2 = run([sys.executable, "-B", str(p2.relative_to(REPO))])
        if rc2 != 0:
            print(f"{uid} probe2 rc={rc2}: {out2[-400:]}")
            bad.append(uid)
            continue

        cmds = [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p1.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p2.relative_to(REPO).as_posix()}",
        ]
        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "BLOCKED",
            "sentinel": f"FAILED:{uid} builder-side delivery COMPLETE (artifact + live probes + manifest sha verified); SUCCESS withheld: reviewer-absent",
            "output_path": out_rel,
            "named_probes": [
                {"id": "probe1", "command": cmds[0], "exit_code": rc1, "role": "delivery-predicate", "raw_output": out1[:8000]},
                {"id": "probe2", "command": cmds[1], "exit_code": rc2, "role": "independent-recheck", "raw_output": out2[:8000]},
            ],
            "artifacts": [{"path": out_rel, "bytes": len(norm), "sha256": sha, "exists": True, "role": "primary"}],
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "failure": {
                "classification": ["reviewer-absent"],
                "reason": "Independent reviewer closure unavailable in builder shard; artifact + named probes + manifest sha all verify live this session.",
            },
            "notes": NOTES[uid],
            "extensions": {
                "builder": "shard1 wave-2 (resume) 2026-10-25",
                "prior_builder": "died mid-flight; artifacts verified against the live contract, not rebuilt",
            },
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (pdir / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n"
        )

        mrc, mout = run([sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid])
        tail = mout.strip().splitlines()[-1] if mout.strip() else ""
        print(f"{uid}: measure rc={mrc} {tail}")
        if mrc != 0:
            bad.append(uid)
    if bad:
        print("NOT-GREEN:", ",".join(bad))
        return 1
    print("ALL-GREEN:", ",".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
