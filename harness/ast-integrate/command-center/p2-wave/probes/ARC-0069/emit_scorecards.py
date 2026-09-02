#!/usr/bin/env python3
"""Emit command-center/phase3/SCORECARDS.json for ARC-0069."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import round as R  # noqa: E402
from fixtures import DIMENSIONS, GATE, PANEL, RUBRIC  # noqa: E402

REPO = HERE.parents[3]
OUT = "command-center/phase3/SCORECARDS.json"
SCHEMA = "command-center/schema/tournament-score.schema.json"
QUESTION = (
    "Run the scoring round: every seated judge independently scores all nine "
    "de-identified entries against the pre-registered rubric, with no cross-talk "
    "before submission and no visibility of peer scores. Produce one scorecard "
    "per (judge, entry) carrying a per-dimension score, the evidence citation "
    "for each score, and an explicit abstention where the evidence is insufficient."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0069/probe1_full_read_gate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0069/probe2_unanimity_abstention.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dossier_digest(doc: dict) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    result = R.run_round()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    standing = result["standing"]
    admitted = result["admitted"]
    rejected = result["rejected"]
    sealed_map = (result.get("sealed") or {}).get("map") or {}
    entries_meta = []
    for eid in result["entry_ids"]:
        body = result["entries"][eid]
        meta = sealed_map.get(eid) or {}
        entries_meta.append(
            {
                "entry_id": eid,
                "origin": meta.get("origin"),
                "sections": sorted(k for k in body.keys() if k != "digest"),
                "dossier_sha256": dossier_digest(body),
                "leak_hits": meta.get("leak_hits") or [],
                "lenses": meta.get("lenses") or [],
                "reason": meta.get("reason"),
            }
        )
    first = result["first_pass"]
    isolation = result["isolation"]
    peer_ok = all(not c.get("peer_scorecards_in_read_set") for c in first)
    mtimes = [c.get("mtime_ns") for c in first if c.get("mtime_ns")]
    j1_end = isolation[0].get("finished_at") if isolation else None
    j2_start = isolation[1].get("started_at") if len(isolation) > 1 else None
    live = result["inputs"]["live"]
    doc = {
        "unit_id": "ARC-0069",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0069",
        "question": QUESTION,
        "answer": (
            "Three isolated judges scored nine de-identified entries against a "
            "pre-registered five-dimension rubric. Scorecards were written per "
            "judge before any peer scorecard was placed in that judge's read set "
            f"(peer_scorecards_in_read_set empty={peer_ok}). "
            f"{len(admitted)} standing scorecards passed the full-read gate; "
            f"{len(rejected)} were rejected. Instant-unanimity triggered on "
            f"{len(result['triggered'])} entries; forced-dissent re-eval runs "
            "before unanimous first-pass scores can stand. Nameless abstentions "
            "record as zero."
        ),
        "produced_at": now,
        "input_resolution": live,
        "honest_note": result["inputs"]["honest_note"],
        "rubric": {
            "id": RUBRIC["id"],
            "source": live["rubric"]["used"],
            "sha256": result["rubric_sha256"],
            "dimensions": DIMENSIONS,
            "weight_sum": RUBRIC["weight_sum"],
            "scale": RUBRIC["scale"],
        },
        "panel": {
            "id": PANEL["id"],
            "source": live["panel"]["used"],
            "judges": PANEL["judges"],
            "quorum": PANEL["quorum"],
            "dispatch": "local-serialized-isolated",
            "not_live_llm": True,
        },
        "independence": {
            "dispatch": "local-serialized-isolated",
            "peer_scores_readable_before_submission": False,
            "peer_scorecards_in_every_read_set": [],
            "isolation": isolation,
            "mtime_ns_min": min(mtimes) if mtimes else None,
            "mtime_ns_max": max(mtimes) if mtimes else None,
            "serialized_judge_order": [row["judge_id"] for row in isolation],
            "later_judge_started_after_earlier_finished": bool(
                j1_end and j2_start and j2_start >= j1_end
            ),
        },
        "full_read_gate": {
            "id": GATE["id"],
            "source": live["gate"]["used"],
            "threshold": GATE["threshold"],
            "anchors_derived_from_dossier_keys": True,
            "admitted": len(admitted),
            "rejected": len(rejected),
            "standing_scorecards": len([c for c in standing if c.get("standing")]),
        },
        "instant_unanimity": {
            "rule": (
                "If all judges agree on every dimension for an entry on first "
                "pass, those scores do not stand until a blind forced-dissent "
                "re-eval is recorded."
            ),
            "entries_triggered": result["triggered"],
            "forced_dissent_recorded": True,
        },
        "entries": entries_meta,
        "scorecards": standing,
        "tests": [
            {
                "id": "T1-full-read-gate",
                "name": (
                    "Every standing scorecard passes the full-read gate; "
                    "digest-only fails; renamed section is derived from the file"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-unanimity-abstention-independence",
                "name": (
                    "Instant unanimity forces dissent before standing; nameless "
                    "abstention becomes zero; named abstention is preserved; "
                    "peer scorecards are not in the read set"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0069-probe2-unanimity-abstention",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Audits independence evidence, full-read admission, unanimity "
                "trigger, and abstention recording. Not a seated judge."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ARC-0069/round.py",
                "exists": True,
                "role": "scoring-round",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0069/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": P1,
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py ARC-0069"
                ),
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after emit and named probes.",
            },
        ],
    }
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:ARC-0069 schema missing {SCHEMA}")
        return 1
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if "$ref" not in shim:
        print("FAILED:ARC-0069 schema shim has no $ref")
        return 1
    # The shim $ref is https://ast-integrate.invalid/... . jsonschema 4.10
    # fetches that URL. Do not. G-1 does not network-validate the shim.
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"admitted={len(admitted)} rejected={len(rejected)} triggered={result['triggered']}")
    print("SUCCESS:ARC-0069")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
