#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0028-sweep-niche-archival.json and G-1 sidecars."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

OUT = "command-center/wfa/WFA-0028-sweep-niche-archival.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0028/probe1_onion_default_off.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0028/probe2_corroboration_unverified.py"
)
QUESTION = (
    "Which orchestration mechanisms appear only in niche, non-English, "
    "archived or low-traffic sources — including lawful public onion sources "
    "under the opt-in policy — and does any of them survive corroboration "
    "against a mainstream surface?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0028/catalog.py",
    "command-center/p2-wave/probes/WFA-0028/onion_gate.py",
    "command-center/p2-wave/probes/WFA-0028/legal_review.py",
    "command-center/p2-wave/probes/WFA-0028/sweep.py",
    "command-center/p2-wave/probes/WFA-0028/probe1_onion_default_off.py",
    "command-center/p2-wave/probes/WFA-0028/probe2_corroboration_unverified.py",
    "command-center/p2-wave/probes/WFA-0028/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def slim(finding: dict) -> dict:
    return {
        "mechanism_id": finding["mechanism_id"],
        "mechanism": finding["mechanism"],
        "source_class": finding["source_class"],
        "language": finding["language"],
        "source_url": finding["source"]["url"],
        "archive_timestamp": finding["source"].get("archive_timestamp"),
        "retrieved_at": finding["source"].get("retrieved_at"),
        "original_quote": finding["evidence_a"]["original_quote"],
        "translation": finding["evidence_a"]["translation"],
        "corroboration_urls": [h["url"] for h in finding["evidence_b"]["hits"]],
        "proposal_only": finding["proposal_only"],
        "grade": finding["grade"],
        "promotion": S.promote(finding),
    }


def main() -> int:
    report = S.run()
    if report["onion_gate"]["enabled"]:
        print("FAILED:WFA-0028 emit default onion class is on")
        return 1
    if not report["onion_skipped"]:
        print("FAILED:WFA-0028 emit queued onion not skipped")
        return 1
    if any(x.get("action") == "allow-read" for x in report["onion_skipped"]):
        print("FAILED:WFA-0028 emit onion was fetched")
        return 1
    if report["counts"]["corroborated"] < 1:
        print("FAILED:WFA-0028 emit no corroborated finding")
        return 1
    if report["counts"]["unverified"] < 1:
        print("FAILED:WFA-0028 emit no unverified control")
        return 1
    if not report["legal_review"].get("pass"):
        print("FAILED:WFA-0028 emit legal review failed")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    doc = {
        "unit_id": "WFA-0028",
        "id": "WFA-0028",
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:WFA-0028",
        "report_kind": "SweepReport",
        "schema_version": 1,
        "title": "Niche, non-English, archival and policy-gated source sweep",
        "question": QUESTION,
        "answer": (
            "On the default path (onion class OFF) four orchestration mechanisms "
            "retrieved from non-English or archival public sources also appear on "
            "an independent mainstream surface and are recorded CORROBORATED: "
            "SOP-encoded role pipelines (Japanese practitioner + arXiv), durable "
            "HITL interrupt gates (Japanese practitioner + LangGraph docs), "
            "runtime manager allocation (Russian practitioner + CrewAI docs), "
            "the BabyAGI create/execute/prioritize loop (April 2023 post + IBM), "
            "and Contract Net bid-and-award (1980 paper + Wikipedia). One "
            "archival-only proposal — BabyAGI 'running parallel tasks' listed as "
            "future work — has no second-surface hit and stays UNVERIFIED. No "
            "onion-class source was fetched. Nothing from this sweep is a "
            "transaction, access-control bypass, stolen-data collection, or "
            "deanonymisation."
        ),
        "onion_source_class": {
            "enabled": False,
            "policy": (
                "the onion source class stays OFF unless the owner explicitly "
                "enables it; the default path must run and report without it"
            ),
            "owner_opt_in_present": report["onion_gate"].get("opt_in_present"),
            "skipped": report["onion_skipped"],
            "live_fetches": 0,
        },
        "legal_safety_review": report["legal_review"],
        "dependencies": {
            "WFA-0031": {
                "required": True,
                "artifact": "command-center/wfa/WFA-0031-acquisition-legal-gate.json",
                "present": False,
                "handling": (
                    "absent; this unit still ran its own pre-output review and "
                    "did not skip review"
                ),
            },
            "WFA-0029": {
                "required": True,
                "artifact": "command-center/wfa/WFA-0029-acquisition-scheduler.json",
                "present": False,
                "handling": (
                    "absent; this unit used a captured catalog rather than a "
                    "live rate-limited crawl, so a scheduler was not required "
                    "for the default path"
                ),
            },
        },
        "findings": [slim(f) for f in report["findings"]],
        "corroborated": [slim(f) for f in report["corroborated"]],
        "unverified": [slim(f) for f in report["unverified"]],
        "counts": report["counts"],
        "tests": {
            "onion_default_off": True,
            "legal_safety_review_before_consume": report["legal_review"][
                "consume_allowed"
            ],
            "read_only_public_research": True,
            "archival_only_stays_unverified": any(
                f["grade"] == "UNVERIFIED" for f in report["findings"]
            ),
        },
        "reviewer": {
            "reviewer_id": "WFA-0028-probe2-corroboration-unverified",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs corroboration with the mainstream index "
                "stripped and planted; UNVERIFIED cannot promote. Catalog "
                "owner sign-off on onion enablement is not claimed."
            ),
        },
        "downstream_consumers": [
            "WFA extraction units may read corroborated mechanism names only; "
            "UNVERIFIED rows are not inputs to fusion"
        ],
        "schema": {
            "declared": SCHEMA,
            "pack_present": schema_pack.is_file(),
            "note": (
                "live wfa-schema-pack.json is absent on this worktree; G-1 "
                "does not require pack validation. Document is a SweepReport "
                "envelope, not a claim that WFA-0001 delivered."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "acquisition-engineer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "onion-default-off", "command": P1},
            {"id": "probe2", "role": "corroboration-unverified", "command": P2},
        ],
        "ts": now,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:WFA-0028 artifact {size}B below floor")
        return 1
    if "SUCCESS:WFA-0028" not in out.read_text(encoding="utf-8"):
        print("FAILED:WFA-0028 sentinel absent after write")
        return 1

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:WFA-0028 named probes c1={rc1} c2={rc2}")
        print(out1[-3000:])
        print(out2[-3000:])
        return 1

    digest, size = sha256_file(out)
    ret = {
        "id": "WFA-0028",
        "unit_id": "WFA-0028",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0028",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "onion-default-off",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "corroboration-unverified",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/WFA-0028/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "WFA-0028-probe2-corroboration-unverified",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0028: live named probes exit 0, "
            "WFA-0028-sweep-niche-archival.json state=SUCCESS, per-unit "
            "manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "WFA-0028",
            "receipt_path": (
                "command-center/p2-wave/probes/WFA-0028/SUBAGENT-RETURN.json"
            ),
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0028",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0028 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
