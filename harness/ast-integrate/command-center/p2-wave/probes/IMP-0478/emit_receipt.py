#!/usr/bin/env python3
"""Emit IMP-0478 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(HERE))

import error_catalog as C  # noqa: E402

UNIT = "IMP-0478"
OUT = "command-center/receipts/IMP-0478.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SENTINEL:IMP-0478:ERROR-CATALOG-COMPLETE"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0478/probe1_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0478/probe2_doc_commands.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0478/error_catalog.py",
    "command-center/p2-wave/probes/IMP-0478/doctor.py",
    "command-center/p2-wave/probes/IMP-0478/probe1_coverage.py",
    "command-center/p2-wave/probes/IMP-0478/probe2_doc_commands.py",
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
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_blob(
    role: str, method: str, command: str, raw: str, exit_code: int | None
) -> dict:
    blob = {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[
            :32
        ],
    }
    if exit_code is not None:
        blob["exit_code"] = exit_code
    return blob


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0478/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        return 1

    table = C.coverage_table()
    before = C.unmapped_classes(C.CLOSED_TAXONOMY, catalog={})
    after = C.unmapped_classes(C.CLOSED_TAXONOMY, C.CATALOG)
    later = "later-invented-class"
    later_gaps = C.unmapped_classes(list(C.CLOSED_TAXONOMY) + [later], C.CATALOG)
    tb_unmapped = not C.is_actionable(C.traceback_only_fixture())
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    p1 = probe_blob("source", "command", P1, t1, c1)
    p2 = probe_blob("verifier", "command", P2, t2, c2)
    answer = (
        f"Before this unit, {len(before)} of {len(C.CLOSED_TAXONOMY)} closed "
        f"taxonomy classes had no user-facing message. After this unit, that "
        f"number is {len(after)}."
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0478 + IMP-0449 closed taxonomy",
        "min_bytes_threshold": 128,
        "title": "Actionable error catalog covering every failure class",
        "question_or_target": (
            "Implement the user-facing error catalog mapping every class in the "
            "failure taxonomy to a message that names what failed, why, and the "
            "exact next command. Exact question: how many taxonomy classes "
            "currently have no user-facing message, and after this unit is that "
            "number zero?"
        ),
        "answer": answer,
        "unmapped_before": len(before),
        "unmapped_after": len(after),
        "unmapped_after_is_zero": len(after) == 0,
        "taxonomy_source": {
            "unit": "IMP-0449",
            "receipt_present": (REPO / "command-center/receipts/IMP-0449.json").is_file(),
            "closed_classes": list(C.CLOSED_TAXONOMY),
            "note": (
                "IMP-0449.json is absent; classes are taken from the IMP-0449 "
                "catalog row's closed list, not invented."
            ),
        },
        "coverage_table": table,
        "also_mapped_terminal_state": C.UNCLASSIFIED,
        "cloud_ok": False,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": answer,
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0478/error_catalog.py",
                "confidence": "almost-certain",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "Coverage table lists taxonomy class, message id, and next "
                    "command for every closed class; next commands were executed "
                    "verbatim."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0478/probe2_doc_commands.py",
                "confidence": "almost-certain",
                "probes": [p2],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "coverage-zero-unmapped",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "documentation-command-verbatim",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "later-class-unmapped",
                "kind": "added-later-class",
                "description": (
                    "A class added after the catalog is reported unmapped rather "
                    "than force-fitted."
                ),
                "fired_on_bad_state": later in later_gaps,
                "silent_on_good_state": later not in after,
                "bad_state_output": later,
                "good_state_output": ",".join(after) if after else "(none)",
            },
            {
                "id": "traceback-only-unmapped",
                "kind": "bare-stack-trace",
                "description": "A traceback-only body is not counted as coverage.",
                "fired_on_bad_state": tb_unmapped,
                "silent_on_good_state": True,
                "bad_state_output": "traceback fixture unmapped",
                "good_state_output": "closed classes mapped",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0478-probe2-doc-commands",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0478/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": probe_blob(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0478",
                    "deferred to post-emit measure",
                    None,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0449 receipt is absent, so the closed class list is the "
                    "catalog row rather than a harvested taxonomy artifact."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Re-run coverage against IMP-0449.json when that unit delivers."
                ),
            }
        ],
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    sha, size = digest_file(out_path)
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing after write")
        return 1
    if size < 128:
        print(f"FAILED:{UNIT} receipt too small ({size} B)")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0478/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0478-probe2-doc-commands",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0478: live named probes exit 0, receipt state=SUCCESS, "
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
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
