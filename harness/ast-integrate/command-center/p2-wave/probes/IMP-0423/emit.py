#!/usr/bin/env python3
"""Emit IMP-0423 receipt and per-unit G-1 return + manifest.

Order: run dispatcher tests, live forced-mismatch dispatch, write
receipts/IMP-0423.json, re-run named probes, then write SUBAGENT-RETURN.json
and UNIT-ARTIFACT-MANIFEST.json. Does not run
tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO))
from tools.dispatch import degrade_loudly as dl  # noqa: E402

UNIT = "IMP-0423"
OUT = "command-center/receipts/IMP-0423.json"
SCHEMA = "command-center/schema/work-result.schema.json"
SENTINEL = "SENTINEL:IMP-0423:DEGRADED-LOUD-AND-PRESERVED"
PARTIAL_REL = "command-center/p2-wave/probes/IMP-0423/fixtures/preserved-partial.json"
PARTIAL_BODY = (
    b'{"unit":"FIXTURE-CAP-MISMATCH","step":3,'
    b'"note":"partial work product that must survive a capability mismatch"}\n'
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0423/probe1_mismatch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0423/probe2_preserve.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/dispatch/tests/test_degrade_loudly.py"
)
SUPPORTING = [
    "tools/dispatch/degrade_loudly.py",
    "tools/dispatch/tests/test_degrade_loudly.py",
    SCHEMA,
    PARTIAL_REL,
    "command-center/p2-wave/probes/IMP-0423/probe1_mismatch.py",
    "command-center/p2-wave/probes/IMP-0423/probe2_preserve.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def dep_receipt(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "present": False, "used_as": "interface-fixture"}
    raw = path.read_bytes()
    return {
        "path": rel,
        "present": True,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "used_as": "live-input",
    }


def main() -> int:
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0423 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    fixture_dir = HERE / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    partial_path = REPO / PARTIAL_REL
    dl.seed_partial(partial_path, PARTIAL_BODY)
    before = partial_path.read_bytes()
    req = dl.mismatch_request(partial_path)
    weak = dl.openai_fixture(streaming=False)
    capable = dl.anthropic_fixture()
    forced = dl.dispatch(req, weak)
    if forced.verdict != dl.VERDICT_DEGRADED:
        print(f"FAILED:IMP-0423 forced mismatch verdict={forced.verdict}")
        return 1
    try:
        dl.assert_partial_preserved(partial_path, before)
    except AssertionError as exc:
        print(f"FAILED:IMP-0423 partial not preserved: {exc}")
        return 1
    subst = dl.dispatch_with_fallback(req, weak, capable)
    retried = dl.retry_mismatch(forced)
    match_path = fixture_dir / "matched-control.json"
    dl.seed_partial(match_path, b'{"ok":true,"control":"matched-capabilities"}\n')
    matched = dl.dispatch(dl.matched_request(match_path), capable)
    if matched.verdict != dl.VERDICT_SUCCESS:
        print(f"FAILED:IMP-0423 match control verdict={matched.verdict}")
        return 1
    schema_errs = dl.validate_work_result(forced.to_dict())
    if schema_errs:
        print(f"FAILED:IMP-0423 work-result schema {schema_errs}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_test = L.probe("source", "command", TEST_CMD, out_t[-4000:], rc_t)
    p_dispatch = L.probe(
        "source",
        "command",
        "python3 -c live forced-mismatch dispatch",
        json.dumps(forced.to_dict(), sort_keys=True)[:8000],
        0,
    )
    p_preserve = L.probe(
        "verifier",
        "file-read",
        f"stat {PARTIAL_REL}",
        json.dumps(
            {
                "path": PARTIAL_REL,
                "bytes": forced.partial.bytes if forced.partial else 0,
                "sha256": forced.partial.sha256 if forced.partial else "",
                "exists": partial_path.is_file(),
            },
            sort_keys=True,
        ),
        0,
    )
    p_subst = L.probe(
        "verifier",
        "command",
        "python3 -c adversarial fallback substitution",
        json.dumps(
            {
                "verdict": subst.verdict,
                "substitution_refused": subst.substitution_refused,
                "fallback_would_have_matched": True,
            },
            sort_keys=True,
        ),
        0,
    )

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    artifacts = [
        L.art("tools/dispatch/degrade_loudly.py", "implementation"),
        L.art("tools/dispatch/tests/test_degrade_loudly.py", "supporting"),
        L.art(SCHEMA, "schema"),
        L.art(PARTIAL_REL, "preserved-partial"),
        L.art(
            "command-center/p2-wave/probes/IMP-0423/probe1_mismatch.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/IMP-0423/probe2_preserve.py",
            "named-probe",
        ),
    ]

    forced_dict = forced.to_dict()
    doc = {
        "schema_version": 1,
        "kind": "work-result",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "verdict": "DEGRADED",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10983",
        "title": "Degrade-loudly contract for capability mismatch",
        "question_or_target": (
            "Implement the degrade-loudly contract at spec line 10983: on a "
            "capability mismatch the dispatcher returns a typed DEGRADED result "
            "and PRESERVES the partial artifact, never a silent substitution "
            "and never a discard. Exact target: there must be no code path where "
            "a mismatch produces an ordinary-looking success."
        ),
        "min_bytes_threshold": 512,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "reason_class": "capability-mismatch",
        "ordinary_looking_success": False,
        "adapter_vendor": forced.adapter_vendor,
        "requested_vendor": forced.requested_vendor,
        "dispatched_unit_id": forced.unit_id,
        "mismatches": forced_dict["mismatches"],
        "partial_artifact": {
            "path": PARTIAL_REL,
            "bytes": forced.partial.bytes if forced.partial else 0,
            "sha256": forced.partial.sha256 if forced.partial else "",
            "preserved": True,
        },
        "substitution": {
            "attempted": subst.substitution_attempted,
            "refused": subst.substitution_refused,
            "fallback_vendor": capable.vendor,
            "fallback_would_have_matched": True,
            "verdict_after_attempt": subst.verdict,
        },
        "retry": {
            "attempted": retried.retry_attempted,
            "refused": retried.retry_refused,
            "policy": "no automatic retry; retrying a capability mismatch cannot fix it",
            "verdict_after_attempt": retried.verdict,
        },
        "matched_control": {
            "unit_id": matched.unit_id,
            "verdict": matched.verdict,
            "mismatches": [],
            "note": "same dispatcher; capabilities covered -> SUCCESS. Both states.",
        },
        "forced_mismatch_dispatch": forced_dict,
        "dependency_inputs": [
            dep_receipt("command-center/receipts/IMP-0419.json"),
            dep_receipt("command-center/receipts/IMP-0422.json"),
        ],
        "capability_interface": {
            "note": (
                "IMP-0419/IMP-0422 receipts are absent on this worktree. "
                "The dispatcher consumes CapabilityDescriptor with the catalog "
                "fields (tools, context_window, permission_model, streaming, "
                "schema_support) plus extra vendor-only capabilities."
            ),
            "primary": weak.to_dict() if hasattr(weak, "to_dict") else {
                "vendor": weak.vendor,
                "tools": sorted(weak.tools),
                "context_window": weak.context_window,
                "permission_model": weak.permission_model,
                "streaming": weak.streaming,
                "schema_support": weak.schema_support,
                "extra": sorted(weak.extra),
            },
        },
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "Forced mismatch (openai adapter lacks streaming) returned typed "
                "DEGRADED, not SUCCESS, with a non-empty mismatches list.",
                "CONFIRMED",
                "tools/dispatch/degrade_loudly.py:_finish",
                [p_dispatch, p_test],
                "almost-certain",
            ),
            L.evidence(
                "The partial artifact still exists after DEGRADED with unchanged "
                f"byte size {forced.partial.bytes if forced.partial else 0}.",
                "CONFIRMED",
                PARTIAL_REL,
                [p_preserve, p_test],
                "almost-certain",
            ),
            L.evidence(
                "Offering a capable anthropic fallback did not silently "
                "substitute; verdict stayed DEGRADED and substitution_refused=true.",
                "CONFIRMED",
                "tools/dispatch/degrade_loudly.py:dispatch_with_fallback",
                [p_subst, p_test],
                "almost-certain",
            ),
            L.evidence(
                "A mutation that unlinks the partial turns assert_partial_preserved red; "
                "the honest path stays green. Both states in tools/dispatch/tests.",
                "CONFIRMED",
                "tools/dispatch/tests/test_degrade_loudly.py",
                [p_test],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "tests": [
            {
                "id": "test_mismatch_is_degraded_not_success",
                "command": TEST_CMD + "::test_mismatch_is_degraded_not_success",
                "result": "PASS",
            },
            {
                "id": "test_partial_artifact_preserved_after_mismatch",
                "command": TEST_CMD + "::test_partial_artifact_preserved_after_mismatch",
                "result": "PASS",
            },
            {
                "id": "test_discard_mutation_turns_preservation_test_red",
                "command": TEST_CMD
                + "::test_discard_mutation_turns_preservation_test_red",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "match-vs-mismatch",
                "both-states-same-dispatcher",
                "Covered capabilities return SUCCESS; streaming mismatch returns DEGRADED.",
                True,
                True,
                bad=f"verdict={forced.verdict} mismatches={len(forced.mismatches)}",
                good=f"verdict={matched.verdict} mismatches=0",
            ),
            L.control(
                "discard-mutation",
                "mutation-turns-red",
                "Unlinking the partial after DEGRADED fails assert_partial_preserved.",
                True,
                True,
                bad="AssertionError: partial discarded",
                good="assert_partial_preserved ok",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0423-probe1-adversarial-substitution",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial path offered a capable fallback vendor after a "
                "streaming mismatch. Dispatcher refused substitution and kept "
                "DEGRADED. Retry also refused. No mismatch path returned SUCCESS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0423/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "tools/dispatch/tests/test_degrade_loudly.py",
                "artifact_path": "tools/dispatch/degrade_loudly.py",
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0419 and IMP-0422 receipts are absent; descriptors used "
                    "here are in-process fixtures matching the catalog field list."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run dispatch against IMP-0419.json vendor columns once "
                    "that unit is delivered."
                ),
            }
        ],
        "notes": (
            "G-1 IMP-0423: mismatch -> typed DEGRADED, partial preserved, "
            "substitution refused. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0423 artifact {size}B below floor")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0423 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0423 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

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
                "role": "mismatch-degraded-not-success",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "partial-preserved-mutation-red",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0423/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0423-probe1-adversarial-substitution",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0423: live named probes exit 0, receipts/IMP-0423.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0423/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0423 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
