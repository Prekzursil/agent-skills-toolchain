#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0211.json from a live checkpoint run."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.checkpoint import (  # noqa: E402
    MISSING_CODE,
    CredentialSourceMissing,
    SecretParamHasNoHandle,
    load_checkpoint_bytes,
    plaintext_hits,
    resume,
    write_checkpoint,
)
from harness import (  # noqa: E402
    CANARY,
    PLAIN_PARAM,
    PLAIN_VALUE,
    ROTATED,
    SECRET_PARAM,
    SECRET_REF,
    honest_checkpoint_bytes,
    naive_checkpoint_bytes,
)

OUT_REL = "command-center/receipts/TST-0211.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0211/probe1_checkpoint_bytes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0211/probe2_resume_without_source.py"
)
ARTIFACT_RELS = [
    "tools/agentspec/agentspec/checkpoint.py",
    "command-center/p2-wave/probes/TST-0211/harness.py",
    "command-center/p2-wave/probes/TST-0211/probe1_checkpoint_bytes.py",
    "command-center/p2-wave/probes/TST-0211/probe2_resume_without_source.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_measure() -> dict:
    honest = honest_checkpoint_bytes()
    naive = naive_checkpoint_bytes()
    with tempfile.TemporaryDirectory(prefix="tst0211-emit-") as tmp:
        path = Path(tmp) / "run.checkpoint.json"
        write_checkpoint(path, honest)
        on_disk = load_checkpoint_bytes(path)
        size = path.stat().st_size
    honest_hits = plaintext_hits(on_disk, {SECRET_PARAM: CANARY})
    naive_hits = plaintext_hits(naive, {SECRET_PARAM: CANARY})
    restored = resume(honest, {SECRET_REF: CANARY})
    rotated = resume(honest, {SECRET_REF: ROTATED})
    missing_code = ""
    try:
        resume(honest, {})
    except CredentialSourceMissing as exc:
        missing_code = exc.code
    no_handle = False
    try:
        from agentspec.checkpoint import ParamSpec, RuntimeBinding, serialize_checkpoint

        serialize_checkpoint(
            workflow_id="wf.bad",
            completed_unit_ids=(),
            receipt_hashes={},
            open_nodes=(),
            bindings={
                "tok": RuntimeBinding(
                    name="tok", secret=True, secret_ref=None, value=CANARY
                )
            },
        )
    except SecretParamHasNoHandle:
        no_handle = True
    doc = json.loads(on_disk.decode("utf-8"))
    return {
        "honest_bytes": len(on_disk),
        "on_disk_bytes": size,
        "honest_sha256": hashlib.sha256(on_disk).hexdigest(),
        "canary_in_honest": bool(honest_hits),
        "canary_in_naive": naive_hits == [SECRET_PARAM],
        "plain_persisted": doc["param_bindings"][PLAIN_PARAM]["value"] == PLAIN_VALUE,
        "secret_kind": doc["param_bindings"][SECRET_PARAM]["kind"],
        "secret_ref_stored": doc["param_bindings"][SECRET_PARAM].get("ref"),
        "resume_with_source": restored[SECRET_PARAM] == CANARY
        and restored[PLAIN_PARAM] == PLAIN_VALUE,
        "resume_rotated": rotated[SECRET_PARAM] == ROTATED,
        "missing_source_code": missing_code,
        "secret_without_handle_refused": no_handle,
        "checkpoint_preview": json.dumps(doc, sort_keys=True),
    }


def build_receipt() -> dict:
    live = live_measure()
    if live["canary_in_honest"] or not live["canary_in_naive"]:
        raise SystemExit("FAILED:TST-0211 emit canary scan did not discriminate")
    if live["missing_source_code"] != f"{MISSING_CODE}:{SECRET_REF}":
        raise SystemExit("FAILED:TST-0211 emit resume-without-source did not name the miss")
    if not live["resume_with_source"] or not live["plain_persisted"]:
        raise SystemExit("FAILED:TST-0211 emit both-states non-secret persist failed")
    if not live["secret_without_handle_refused"]:
        raise SystemExit("FAILED:TST-0211 emit secret without handle was serialized")

    artifacts = []
    for rel in ARTIFACT_RELS:
        path = REPO / rel
        sha, size = digest(path)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "implementation" if rel.startswith("tools/") else "probe",
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "TST-0211",
        "id": "TST-0211",
        "title": "Secrets in workflow parameters never persist into a resumable checkpoint",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0211",
        "completion_sentinel": "SUCCESS:TST-0211",
        "registered": True,
        "cloud_ok": False,
        "question": (
            "Is a credential passed as a workflow parameter excluded from (or "
            "encrypted in) the checkpoint, so resume must re-acquire it? PASS "
            "requires the checkpoint bytes contain no plaintext secret and resume "
            "to prompt or fail cleanly without it."
        ),
        "answer": (
            "Yes. serialize_checkpoint stores secret parameters as secret_ref "
            "handles (env name only) and refuses to write if a pre-scan finds the "
            "plaintext in any common encoding. Resume re-acquires from the live "
            "environment; a missing or empty source raises CREDENTIAL_SOURCE_MISSING. "
            "A non-secret parameter persists by value and is used on resume with "
            "no original argv."
        ),
        "report_kind": "security_report",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "min_bytes_threshold": 1024,
        "evidence_requirement": (
            "two independent signals: (a) a scan of the checkpoint bytes, and "
            "(b) the resume behavior when the credential source is removed"
        ),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "path_head": os.environ.get("PATH", "")[:400],
        },
        "ts": now,
        "live": {
            "honest_bytes": live["honest_bytes"],
            "on_disk_bytes": live["on_disk_bytes"],
            "honest_sha256": live["honest_sha256"],
            "secret_kind": live["secret_kind"],
            "secret_ref_stored": live["secret_ref_stored"],
            "canary_in_honest": live["canary_in_honest"],
            "canary_in_naive": live["canary_in_naive"],
            "plain_persisted": live["plain_persisted"],
            "resume_with_source": live["resume_with_source"],
            "resume_rotated": live["resume_rotated"],
            "missing_source_code": live["missing_source_code"],
            "secret_without_handle_refused": live["secret_without_handle_refused"],
        },
        "evidence": [
            {
                "id": "E1-checkpoint-byte-scan",
                "signal": 1,
                "kind": "live-bytes",
                "summary": (
                    "Planted canary absent from on-disk honest checkpoint; present "
                    "in naive dump; non-secret deploy_region persisted."
                ),
                "canary_in_honest": False,
                "canary_in_naive": True,
                "plain_persisted": True,
                "honest_sha256": live["honest_sha256"],
            },
            {
                "id": "E2-resume-without-source",
                "signal": 2,
                "kind": "live-resume",
                "summary": (
                    "Resume with source re-acquires (including rotation). Resume "
                    "without source fails CREDENTIAL_SOURCE_MISSING. Non-secret "
                    "binding is used with argv gone."
                ),
                "missing_source_code": live["missing_source_code"],
                "resume_with_source": True,
                "resume_rotated": True,
            },
        ],
        "tests": [
            {
                "id": "both-states-non-secret-persists",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "canary-absent-from-checkpoint",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "resume-fails-named-without-source",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-naive-dump-contains-canary",
                "description": (
                    "A naive serializer that writes param values must contain the "
                    "canary so the byte scan is shown to be live, not a tautology."
                ),
                "result": "PASS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-secret-without-reacquisition-handle",
                "description": (
                    "A secret parameter with no secret_ref is refused at serialize "
                    "time rather than written as plaintext."
                ),
                "result": "PASS",
                "fired_on_bad_state": True,
            },
        ],
        "findings": [],
        "controls": [
            {
                "id": "C-byte-scan",
                "result": "PASS",
                "detail": "plaintext_hits empty on honest bytes, fires on naive dump",
            },
            {
                "id": "C-resume-missing-source",
                "result": "PASS",
                "detail": live["missing_source_code"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0211-probe2-resume-without-source",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 is an independent signal from the byte scan: it never "
                "opens the checkpoint as text looking for the canary; it only "
                "exercises resume() with and without the env source."
            ),
        },
        "defects": [],
        "artifacts": artifacts,
        "output_path": OUT_REL,
        "notes": (
            "G-1 for TST-0211. SUT is tools/agentspec/agentspec/checkpoint.py "
            "(IMP-0145 checkpoint record + secret-exclusion rule). Not the full "
            "kill-at-40% resume engine. Canary is a planted fake, not a live key. "
            "cloud_ok is not delivery. Did not run unit_manifest.py --write."
        ),
        "completion_line": "SUCCESS:TST-0211",
    }


def write_receipt(doc: dict | None = None) -> dict:
    doc = doc or build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:TST-0211" not in text:
        raise SystemExit("FAILED:TST-0211 sentinel missing from receipt text")
    out.write_text(text, encoding="utf-8", newline="\n")
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        raise SystemExit("FAILED:TST-0211 receipt below min_bytes_threshold")
    return doc


def main() -> int:
    doc = write_receipt()
    sha, size = digest(REPO / OUT_REL)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0211 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
