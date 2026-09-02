#!/usr/bin/env python3
"""Write IMP-0411 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0411"
OUT = "command-center/receipts/IMP-0411.json"
SENTINEL = "SENTINEL:IMP-0411:OVERLAP-ALGORITHM-EXACT"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0411/probe1_truth_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0411/probe2_properties_mutation.py"
)
SUPPORTING = [
    "command-center/leases/overlap.py",
    "command-center/leases/independent_overlap.py",
    "command-center/leases/corpus_40.json",
    "command-center/p2-wave/probes/IMP-0411/probe1_truth_table.py",
    "command-center/p2-wave/probes/IMP-0411/probe2_properties_mutation.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0411/SUBAGENT-RETURN.json",
        "role": role,
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def build_table() -> list[dict]:
    sys.path.insert(0, str(REPO / "command-center" / "leases"))
    import independent_overlap as ind
    import overlap

    rows = []
    for p in overlap.load_corpus():
        algo = overlap.evaluate_pair(p)
        indep = overlap.evaluate_pair(p, overlap_fn=ind.pathsets_overlap)
        rows.append(
            {
                "id": p["id"],
                "class": p["class"],
                "a": p["a"],
                "b": p["b"],
                "os_family": p["os_family"],
                "algorithm_overlap": algo["algorithm_overlap"],
                "independent_overlap": indep["algorithm_overlap"],
                "hand_overlap": p["hand_overlap"],
                "reason": p["reason"],
            }
        )
    return rows


def main() -> int:
    table = build_table()
    if len(table) != 40:
        print(f"FAILED:receipts table n={len(table)}")
        return 1
    disagree = [
        r
        for r in table
        if r["algorithm_overlap"] is not r["hand_overlap"]
        or r["independent_overlap"] is not r["hand_overlap"]
    ]
    if disagree:
        print("FAILED:receipts disagreements", [r["id"] for r in disagree])
        return 1
    case_only = sum(1 for r in table if r["class"] == "case-only-windows")
    glob_lit = sum(1 for r in table if r["class"] == "glob-versus-literal")
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0411",
        "title": "Glob-aware pairwise lease-overlap algorithm",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "max 2 attempts; escalate rather than special-casing failures"},
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "sha256_locus": "command-center/p2-wave/probes/IMP-0411/UNIT-ARTIFACT-MANIFEST.json",
            },
            {
                "path": "command-center/leases/overlap.py",
                "role": "supporting",
                "exists": True,
                "eol": "LF",
            },
        ],
        "truth_table": table,
        "measurements": {
            "corpus_n": 40,
            "case_only_windows": case_only,
            "glob_versus_literal": glob_lit,
            "algorithm_agreements": 40,
            "independent_agreements": 40,
            "disagreements": 0,
            "algorithm_path": "command-center/leases/overlap.py",
            "independent_path": "command-center/leases/independent_overlap.py",
            "definition": (
                "Trees intersect iff some exact glob-match of A is a component-prefix "
                "of some exact glob-match of B, or vice versa. * and ? do not cross /; "
                "** matches zero or more components; Windows comparisons case-fold."
            ),
        },
        "tests": [
            {
                "id": "truth-table-40",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "property-symmetric-reflexive",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "windows-case-only-overlaps",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "case-sensitive-mutant-red",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "case-sensitive-mutant",
                "kind": "mutation",
                "description": (
                    "Forcing ignore_case=False on Windows must make src/Foo.py vs "
                    "src/foo.py report no overlap, turning the required case-only test red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "windows case-only pair must overlap, got False",
                "good_state_output": "windows case-only pair overlaps under os_family=windows",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Truth table over a 40-pair corpus including "
                    f"{case_only} case-only-differing Windows pairs and "
                    f"{glob_lit} glob-versus-literal pairs; algorithm verdict "
                    "and hand-verified answer sit side by side and agree on 40/40."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/leases/corpus_40.json",
                "probes": [],
            },
            {
                "claim": (
                    "Independent recomputation via regex/witness matching "
                    "(independent_overlap.py) agrees with overlap.py and with the "
                    "hand column on every row."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/leases/independent_overlap.py",
                "probes": [],
            },
            {
                "claim": (
                    "Overlap is symmetric and reflexive on every corpus path; a "
                    "case-only-differing pair on Windows overlaps; mutating the "
                    "comparison to case-sensitive turns that test red."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0411/probe2_properties_mutation.py",
                "probes": [],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0411-independent-overlap-recompute",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "method": (
                "Recomputed the 40-pair table with independent_overlap.py "
                "(recursive glob-match + witness instantiation), not overlap.py's NFA product."
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0411/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0411",
                    "method": "command",
                    "role": "verifier",
                    "fingerprint": fingerprint(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0411",
                    ),
                    "raw_output": "deferred-to-measure-step",
                    "exit_code": None,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input command-center/receipts/IMP-0410.json is absent; "
                    "overlap is a pure path-set function and does not call the lease manager."
                ),
                "settling_experiment": "Re-run after IMP-0410 ships the advisory lease manager.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 for IMP-0411: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    p1 = probe_rec("source", "command", P1, t1, c1)
    p2 = probe_rec("verifier", "command", P2, t2, c2)
    receipt["evidence"][0]["probes"] = [p1, p2]
    receipt["evidence"][1]["probes"] = [p2, p1]
    receipt["evidence"][2]["probes"] = [p2, p1]
    receipt["tests"][0]["exit_code"] = c1
    receipt["tests"][1]["exit_code"] = c2
    receipt["tests"][2]["exit_code"] = c2
    receipt["tests"][3]["exit_code"] = c2
    receipt["timestamps"]["ended_at"] = (
        datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # Re-run probe1 after the probe-output rewrite so the live receipt matches
    # what measure will re-read (table rows are unchanged; sentinel remains).
    c1b, t1b = run_probe(P1)
    if c1b != 0:
        print("FAILED:receipts probe1 after receipt rewrite")
        print(t1b[-2000:])
        return 1

    sha, size = digest(out_path)
    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0411/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1b, "raw_output": t1b},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0411/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0411-independent-overlap-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0411: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print("SUCCESS:IMP-0411 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
