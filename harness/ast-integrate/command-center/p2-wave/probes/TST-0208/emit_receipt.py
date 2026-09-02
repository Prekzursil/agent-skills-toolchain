#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0208.json from a live structured-redaction run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.lib import security as G  # noqa: E402

UNIT = "TST-0208"
OUT = "command-center/receipts/TST-0208.json"
GATE = "tools/lib/security.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0208/probe1_raw_text_and_json_bypass.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0208/probe2_field_walk.py"
)
QUESTION = (
    "Does a secret carried in a STRUCTURED field (`{\"password\": \"...\"}`, "
    "a nested token field, a base64 blob) get redacted, or only ones matching "
    "a raw-text regex? PASS requires both paths."
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0208] "
    "question_or_target + tests_required + evidence_requirement"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report = G.run_required_controls()
    fails = G.control_failures(report)
    if fails:
        print("FAILED:TST-0208 emit live assertions")
        for item in fails:
            print(f"  {item}")
        return 1

    named_inputs = [
        "_USER-PROMPTS.md:11018 (Phase 10 layer 30, secret-leak tests)",
        "_USER-PROMPTS.md:11345 (credentials or decrypted secrets enter an artifact bundle)",
        "AGENTS.md:9 (security non-negotiables)",
        "tools/lib/security.mjs",
    ]
    named_inputs_resolved = []
    for rel in ("_USER-PROMPTS.md", "AGENTS.md", "tools/lib/security.mjs"):
        named_inputs_resolved.append({"path": rel, "present": (REPO / rel).is_file()})

    gate_sha, gate_bytes = sha256_file(REPO / GATE)
    supporting = [
        GATE,
        "tools/lib/__init__.py",
        "command-center/p2-wave/probes/TST-0208/probe1_raw_text_and_json_bypass.py",
        "command-center/p2-wave/probes/TST-0208/probe2_field_walk.py",
    ]
    artifact_records = [art(p, "supporting") for p in supporting]
    if any(not a["exists"] for a in artifact_records):
        print("FAILED:TST-0208 missing supporting artifact")
        return 1

    jp = report["json_password"]
    nest = report["nested_token"]
    blob = report["base64_blob"]
    walk = report["field_walk"]
    both = report["both_states"]
    raw_pw = report["raw_text_password"]

    answer = (
        "Both paths. Catalog-named tools/lib/security.mjs is absent; the measured "
        f"gate is {GATE}. Raw-text `password=VALUE` and `Bearer TOKEN` are redacted "
        f"by the regex-only redactor and by the dual-path redactor "
        f"(regex_retains={raw_pw['regex_only_retains_secret']}, "
        f"dual_retains={raw_pw['dual_retains_secret']}). A JSON "
        '`{"password": "..."}` field bypasses the regex-only redactor '
        f"(regex_retains={jp['regex_only_retains_secret']}) and is redacted by "
        "the structured walk "
        f"(password_redacted={jp['password_redacted']}, "
        f"username_preserved={jp['username_preserved']}). A nested session.token "
        f"is redacted (token_redacted={nest['token_redacted']}, "
        f"user_preserved={nest['user_preserved']}). A base64 JSON blob whose "
        "decoded body carries password is left intact by regex-only "
        f"(regex_retains={blob['regex_only_retains_secret']}) and redacted after "
        f"decode by the structured path (inner_password_redacted="
        f"{blob['inner_password_redacted']}). Independent field-by-field walk: "
        f"n_sensitive={walk['n_sensitive']} n_retaining_secret="
        f"{walk['n_retaining_secret']} all_sensitive_redacted="
        f"{walk['all_sensitive_redacted']}. SUCCESS:TST-0208"
    )

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0208",
        "completion_sentinel": "SUCCESS:TST-0208",
        "title": "Redaction operates on parsed structure as well as raw text",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "report_kind": "security_report",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "output_schema_note": (
            "command-center/schema/receipt.schema.json is absent on this "
            "worktree; command-center/schema/security-report.schema.json exists "
            "but constrains unit_id to CNF-*. This receipt follows the security "
            "report field set without claiming that CNF-only schema validates."
        ),
        "named_inputs": named_inputs,
        "named_inputs_resolved": named_inputs_resolved,
        "gate": {
            "path": GATE,
            "sha256": gate_sha,
            "bytes": gate_bytes,
            "catalog_js_path": report["catalog_js_path"],
            "catalog_js_present": report["catalog_js_present"],
            "redaction_marker": report["redaction_marker"],
        },
        "live_controls": {
            "both_states": both,
            "raw_text_password": raw_pw,
            "raw_text_bearer": report["raw_text_bearer"],
            "json_password": jp,
            "nested_token": nest,
            "base64_blob": blob,
            "field_walk": walk,
            "canary_fingerprints": report["canary_fingerprints"],
            "report_omits_canaries": report["report_omits_canaries"],
        },
        "tests": [
            {
                "id": "TST0208-T1-RAW-TEXT-NO-REGRESSION",
                "command": P1,
                "result": "PASS",
                "name": "both-states control: the raw-text form is redacted too",
                "regex_only_retains_secret": raw_pw["regex_only_retains_secret"],
                "dual_retains_secret": raw_pw["dual_retains_secret"],
            },
            {
                "id": "TST0208-T2-JSON-PASSWORD-BYPASS-SEED",
                "command": P1,
                "result": "PASS",
                "name": "regression seed: a JSON password field bypassing a regex redactor",
                "regex_only_retains_secret": jp["regex_only_retains_secret"],
                "structured_password_redacted": jp["password_redacted"],
            },
            {
                "id": "TST0208-T3-NESTED-TOKEN",
                "command": P2,
                "result": "PASS",
                "token_redacted": nest["token_redacted"],
                "user_preserved": nest["user_preserved"],
            },
            {
                "id": "TST0208-T4-BASE64-BLOB-AND-FIELD-WALK",
                "command": P2,
                "result": "PASS",
                "inner_password_redacted": blob["inner_password_redacted"],
                "n_sensitive": walk["n_sensitive"],
                "n_retaining_secret": walk["n_retaining_secret"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0208-probe2-field-walk",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "grants_owner_signoff": False,
            "notes": (
                "Probe 2 independently mints nested-token and base64-JSON "
                "canaries, walks every sensitive key, and requires the regex-only "
                "path to leave the decoded blob intact. Catalog asked for two "
                "fresh-context reviewers; this headless worker records probe2 as "
                "the independent executable reviewer, not a second human."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"}
        ]
        + [{"path": a["path"], "exists": True, "role": a["role"]} for a in artifact_records],
        "artifact_records": artifact_records,
        "evidence": [
            {
                "path": GATE,
                "kind": "redacted-structured-payload",
                "claim": (
                    "Structured redaction of JSON password, nested token, and "
                    "base64 JSON blob produced marker="
                    f"{report['redaction_marker']}; regex-only retained the JSON "
                    "password field and the decoded base64 password."
                ),
            },
            {
                "path": GATE,
                "kind": "field-by-field-walk",
                "claim": (
                    f"Walked {walk['n_sensitive']} sensitive keys; "
                    f"n_retaining_secret={walk['n_retaining_secret']}; "
                    f"all_sensitive_redacted={walk['all_sensitive_redacted']}."
                ),
            },
        ],
        "evidence_requirement": {
            "a_redacted_output_for_structured_payloads": {
                "json_password_redacted": jp["password_redacted"],
                "nested_token_redacted": nest["token_redacted"],
                "base64_inner_password_redacted": blob["inner_password_redacted"],
                "structured_parsed": jp["structured_parsed"],
            },
            "b_field_by_field_walk": {
                "n_sensitive": walk["n_sensitive"],
                "n_retaining_secret": walk["n_retaining_secret"],
                "all_sensitive_redacted": walk["all_sensitive_redacted"],
                "rows": walk["rows"],
            },
        },
        "negative_controls": [
            {
                "id": "regex-only-json-password",
                "kind": "json-field-bypassing-raw-text-regex",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "regex_only_retains_secret=true",
                "good_state_output": "password_redacted=true",
            },
            {
                "id": "regex-only-base64-json-password",
                "kind": "base64-blob-bypassing-raw-text-regex",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "regex_only_retains_secret=true",
                "good_state_output": "inner_password_redacted=true",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/lib/security.mjs, _USER-PROMPTS.md, and root AGENTS.md "
                    "are not on this worktree, so this unit measures the Python "
                    "dual-path redactor rather than a catalog-named JS harness."
                ),
                "settling_experiment": (
                    "Re-run against tools/lib/security.mjs if that file lands."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "named_probe_commands": [P1, P2],
        "timestamps": {"started_at": started, "ended_at": ended},
        "cloud_ok": False,
        "notes": (
            "G-1 delivery for TST-0208. Live named probes are "
            "probe1_raw_text_and_json_bypass and probe2_field_walk. Did not "
            "run global unit_manifest.py --write. SUCCESS:TST-0208"
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:TST-0208 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0208 receipt")
    return 0


SENTINEL = "SUCCESS:TST-0208"


if __name__ == "__main__":
    raise SystemExit(main())
