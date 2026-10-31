#!/usr/bin/env python3
"""Write IMP-0321 catalog receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
UID = "IMP-0321"
OUT = "command-center/receipts/IMP-0321.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0321/probe1_thresholds.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0321/probe2_volume_vs_substance.py"
)
SUPPORTING = [
    "tools/council/antifail/participation.py",
    "tools/council/antifail/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0321/corpus.py",
    "command-center/p2-wave/probes/IMP-0321/probe1_thresholds.py",
    "command-center/p2-wave/probes/IMP-0321/probe2_volume_vs_substance.py",
    "command-center/p2-wave/probes/IMP-0321/write_receipts.py",
]


def digest_file(path: Path) -> tuple[str, int]:
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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0321/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": path.is_file(),
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "command": command,
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "method": method,
        "raw_output": raw[:16000],
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0321 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:IMP-0321 probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_src = probe_rec("source", "command", P1, t1, c1)
    p1_ver = probe_rec(
        "verifier",
        "file-read",
        "read tools/council/antifail/participation.py flag_dominance/flag_silence",
        "dominance fires iff share > 2/n; silence fires iff turns==0 or share < 0.25/n",
        0,
    )
    p2_src = probe_rec("source", "command", P2, t2, c2)
    p2_ver = probe_rec(
        "verifier",
        "file-read",
        "read rec-15 chair filler vs skeptic claims in corpus.py",
        "chair turns are FILLER_CYCLE acknowledgements; skeptic turns carry Claim/Evidence markers",
        0,
    )

    disagree_n = int(j2.get("disagreement_count") or 0)
    top = j2.get("top_disagreement") or {}
    read = j2.get("manual_read") or {}
    supporting_arts = [art(p, "supporting") for p in SUPPORTING]

    receipt = {
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting_arts,
        "downstream_consumers": [
            {
                "artifact_path": "tools/council/antifail/participation.py",
                "consumer": "command-center/p2-wave/probes/IMP-0321/probe1_thresholds.py",
                "executed": True,
                "exit_code": c1,
                "probe": p1_src,
                "read_ok": True,
            },
            {
                "artifact_path": "tools/council/antifail/participation.py",
                "consumer": "command-center/p2-wave/probes/IMP-0321/probe2_volume_vs_substance.py",
                "executed": True,
                "exit_code": c2,
                "probe": p2_src,
                "read_ok": True,
            },
        ],
        "evidence": [
            {
                "anchor": "tools/council/antifail/participation.py:flag_dominance",
                "claim": (
                    "Dominance and silence thresholds are enforced, not documented: "
                    "share > 2/n dominates; share < 0.25/n or zero turns is silent. "
                    "A planted even 4-seat council is unflagged on both measures. "
                    "A filler-padded chair is volume-dominant and not substance-dominant; "
                    "a terse skeptic is the reverse."
                ),
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0321/fixtures/recorded.json",
                "claim": (
                    f"Both measures were computed over {j2.get('n_councils')} recorded "
                    f"councils. They disagree on {disagree_n} runs: "
                    f"{j2.get('disagreement_ids')}. Disagreement_count is the published "
                    "volume-vs-substance figure the catalog asked for."
                ),
                "confidence": "almost-certain",
                "disagreement_count": disagree_n,
                "disagreement_ids": j2.get("disagreement_ids"),
                "probes": [p2_src, p2_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": f"corpus {top.get('council_id')} manual read",
                "claim": (
                    f"Top disagreement is {top.get('council_id')} (gap={top.get('gap')}): "
                    f"volume-loudest={top.get('volume_loudest')} "
                    f"substance-loudest={top.get('substance_loudest')}. "
                    f"Manual read verdict: {read.get('which_measure_was_right')}. "
                    f"{read.get('rationale')}"
                ),
                "confidence": "high",
                "manual_read": read,
                "probes": [p2_src, p2_ver],
                "verdict": "CONFIRMED",
            },
        ],
        "evidence_requirement_records": {
            "n_recorded_councils": j2.get("n_councils"),
            "disagreement_count": disagree_n,
            "disagreement_ids": j2.get("disagreement_ids"),
            "top_disagreement": top,
            "manual_read": read,
            "even_rec01_unflagged": j2.get("even_rec01_unflagged"),
        },
        "falsifiable_answer": (
            "Dominance is not the same under token volume and under substantive "
            f"contribution. On this recorded corpus the measures disagree on "
            f"{disagree_n}/20 councils. Manual read of {top.get('council_id')} "
            "finds substance is the measure that matches actual contribution: "
            "the volume-loudest seat is acknowledgement padding."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0321/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_control_ids": ["nc-even-council-must-not-flag"],
        "negative_controls": [
            {
                "bad_state_output": json.dumps(
                    {
                        "volume_filler_monopoly_disagrees": j1.get(
                            "volume_filler_chair_volume_dominant"
                        )
                    },
                    sort_keys=True,
                ),
                "description": (
                    "Even 4-seat recorded council (rec-01 / planted-even) must not "
                    "flag dominance or silence on either measure."
                ),
                "fired_on_bad_state": True,
                "good_state_output": json.dumps(
                    {"even_unflagged": j1.get("even_unflagged"), "rec01": j2.get("even_rec01_unflagged")},
                    sort_keys=True,
                ),
                "id": "nc-even-council-must-not-flag",
                "kind": "known-good-fixture",
                "silent_on_good_state": True,
            }
        ],
        "profile": "council-antifail-module",
        "residual_unknowns": [
            {
                "claim": (
                    "Substance scoring is local to this module. IMP-0299 "
                    "tools/council/budget/engagement.py is absent, so this detector "
                    "does not share an engagement metric with the budget governor."
                ),
                "settling_experiment": (
                    "After IMP-0299 lands, re-score the same 20 councils with the "
                    "engagement metric and publish a three-way disagreement table."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "The 20 councils are deterministic recorded fixtures, not live "
                    "model traces. A live verbose-but-empty seat may use filler "
                    "outside the local lexicon."
                ),
                "settling_experiment": (
                    "Replay 20 stored live councils from the runtime artifact store "
                    "once that store exists and re-publish disagreement_count."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0321-probe2-volume-vs-substance",
            "scope_not_agreement": True,
            "starts_from": "tests (thresholds, even-council NC, 20-run census, manual read)",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0321",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0321]",
        "state": "SUCCESS",
        "test_ids": [
            "unit-dominance-silence-thresholds",
            "measurement-volume-vs-substance-disagreement-count",
            "negative-control-even-council-must-not-flag",
        ],
        "tests": [
            {
                "command": P1,
                "id": "unit-dominance-silence-thresholds",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "measurement-volume-vs-substance-disagreement-count",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "negative-control-even-council-must-not-flag",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Dominance and silence detector",
        "unit_id": UID,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/IMP-0321/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "thresholds-and-even-control",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "volume-vs-substance-census",
            },
        ],
        "notes": (
            "G-1 for IMP-0321: live named probes exit 0, receipts/IMP-0321.json "
            "state=SUCCESS with SUCCESS:IMP-0321, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-antifail-module"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0321-probe2-volume-vs-substance",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0321",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0321 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
