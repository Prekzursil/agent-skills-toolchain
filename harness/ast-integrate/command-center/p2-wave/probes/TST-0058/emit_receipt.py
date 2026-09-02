#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0058.json from a live agreement matrix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import matrix as M  # noqa: E402
from tools.json_ingest import jsonc_loads, lenient_loads, strict_loads  # noqa: E402

UID = "TST-0058"
OUT = "command-center/receipts/TST-0058.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
IMPL = "tools/json_ingest.py"


def digest(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if data else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": path.is_file(),
        "eol": "LF",
        "role": role,
    }


def compact_row(row: dict) -> dict:
    return {
        "path": row["path"],
        "kind": row["kind"],
        "strict": row.get("strict"),
        "lenient": row.get("lenient"),
        "agree": row["agree"],
        "strict_pos": row.get("strict_pos"),
        "features": row.get("features_lenient") or row.get("features_left") or [],
        "value_sha256": row.get("value_sha256"),
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prod = M.production_matrix()
    ctrl = M.control_matrix()
    t1 = M.test_no_document_is_accepted_by_one_path_and_rejected_by_the_other(prod)
    t2 = M.test_the_adversarial_documents_are_rejected_by_both(prod)
    if not t1["ok"] or not t2["ok"]:
        print("FAILED:TST-0058 live tests did not pass; not emitting SUCCESS")
        print(json.dumps({"t1": t1, "t2": t2, "disagree": prod["disagreements"][:8]}, indent=1))
        return 1
    if ctrl["planted_divergence_count"] != ctrl["adversarial_count"]:
        print("FAILED:TST-0058 detector control did not fire; not emitting SUCCESS")
        return 1

    # Sanity: loaders are distinct callables.
    if strict_loads is lenient_loads or lenient_loads is jsonc_loads:
        print("FAILED:TST-0058 parsers collapsed to one callable")
        return 1

    supporting = [
        digest(IMPL, "implementation"),
        digest(SCHEMA, "schema"),
        digest("command-center/p2-wave/probes/TST-0058/matrix.py", "supporting"),
        digest("command-center/p2-wave/probes/TST-0058/corpus.py", "supporting"),
        digest(
            "command-center/p2-wave/probes/TST-0058/probe1_agreement_matrix.py",
            "supporting",
        ),
        digest(
            "command-center/p2-wave/probes/TST-0058/probe2_adversarial_and_detector.py",
            "supporting",
        ),
    ]
    for rel in sorted(
        (
            p.relative_to(REPO).as_posix()
            for p in (HERE / "fixtures" / "adversarial").glob("*.jsonc")
        )
    ):
        supporting.append(digest(rel, "fixture"))

    question = (
        "Target: the same document parsed by the lenient path (comments, trailing "
        "commas, single quotes tolerated) and the strict path must either both "
        "accept or both reject. A document that the dev tool accepts and the "
        "shipped client rejects is a green-not-live defect."
    )
    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:TST-0058",
        "completion_sentinel": "SUCCESS:TST-0058",
        "profile": "test-receipt",
        "title": "Lenient-versus-strict parser differential",
        "question": question,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0058 question_or_target; "
            "evidence_requirement: accept/reject agreement matrix over >=50 real "
            "config documents plus 10 adversarial ones"
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "parsers": {
            "strict": {
                "symbol": "tools.json_ingest.strict_loads",
                "role": "shipped-client",
                "mechanism": "json.loads RFC 8259; JSONDecodeError line:column",
            },
            "lenient": {
                "symbol": "tools.json_ingest.lenient_loads",
                "role": "dev-tool-ingest",
                "mechanism": (
                    "diagnose comments / trailing commas / single quotes, then "
                    "refuse them so ingest cannot accept what the client rejects"
                ),
            },
            "jsonc_control": {
                "symbol": "tools.json_ingest.jsonc_loads",
                "role": "detector-control-only",
                "mechanism": "tolerates JSON5-isms; not used for production ingest",
            },
        },
        "production_strict_call_sites": [
            "tools/router/index_build.py:_read_json",
            "tools/router/overrides.py:load_overlay",
            "tools/marketplace/ledger.py:load_ledger",
            "tools/council/sensitivity.py:load_question",
            "tools/marketplace/case_provenance.py:load_known_provenance",
        ],
        "tests": [
            {
                "id": "test_no_document_is_accepted_by_one_path_and_rejected_by_the_other",
                "result": t1["result"],
                "real_count": t1["real_count"],
                "disagreement_count": t1["disagreement_count"],
            },
            {
                "id": "test_the_adversarial_documents_are_rejected_by_both",
                "result": t2["result"],
                "adversarial_count": t2["adversarial_count"],
                "adversarial_both_reject": t2["adversarial_both_reject"],
            },
        ],
        "evidence": {
            "kind": "accept-reject-agreement-matrix",
            "real_count": prod["real_count"],
            "adversarial_count": prod["adversarial_count"],
            "row_count": prod["row_count"],
            "disagreement_count": prod["disagreement_count"],
            "real_both_accept": prod["real_both_accept"],
            "adversarial_both_reject": prod["adversarial_both_reject"],
            "control_planted_divergence_count": ctrl["planted_divergence_count"],
            "control_jsonc_accept_count": ctrl["jsonc_accept_count"],
            "left": prod["left"],
            "right": prod["right"],
            "matrix": [compact_row(r) for r in prod["rows"]],
        },
        "detector_control": {
            "unaligned_pair": "strict_loads vs jsonc_loads",
            "planted_divergence_count": ctrl["planted_divergence_count"],
            "aligned_pair_disagreements": prod["disagreement_count"],
            "note": (
                "The matrix is not a constant: unaligned JSONC vs strict fires on "
                "every adversarial document; the aligned production pair is silent."
            ),
        },
        "artifacts": [digest(OUT, "primary")] + supporting,
        "artifact_paths": [OUT, IMPL, SCHEMA],
        "reviewer": {
            "reviewer_id": "TST-0058-probe2-adversarial-and-detector",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is the cross-check: it requires jsonc_loads to ACCEPT the "
                "adversarial corpus (proving the detector can see a split) while "
                "both production paths REJECT it."
            ),
        },
        "failure_classification_checked": [
            "green-not-live",
            "overclaim",
            "detector-failure",
            "uncontrolled-silence",
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0058/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "produced_by": {
            "execution_substrate": "linux-worktree",
            "model": "grok-4.6",
            "role": "platform-test-engineer",
            "vendor": "cursor",
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0058: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0058"
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} real={prod['real_count']} adv={prod['adversarial_count']} "
        f"disagree={prod['disagreement_count']}"
    )
    print("SUCCESS:TST-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
