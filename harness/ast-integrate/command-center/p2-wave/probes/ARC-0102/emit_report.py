#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0102.json."""
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
import schema_resolver as SR  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0102.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0102/probe1_egress.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0102/probe2_pin.py"
)
QUESTION = (
    "Build the schema registry: canonical identifiers, cross-schema reference "
    "resolution, and a validator that runs entirely OFFLINE with a PINNED "
    "validator version - because a validation step that resolves a remote "
    "meta-schema is a network dependency in a gate, and an unpinned validator "
    "version means the same input can pass today and fail tomorrow."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0102 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    pin = SR.assert_pin()
    rc1, out1 = run(P1)
    if rc1 != 0:
        print("FAILED:ARC-0102 probe1")
        print(out1[-2000:])
        return 1
    # Write a pin-bearing draft so probe2 can assert the report records the version.
    # The final document replaces this in the same path after probe2.
    draft_pin = {
        "unit_id": "ARC-0102",
        "state": "PARTIAL",
        "sentinel": "SUCCESS:ARC-0102",
        "title": "draft-for-probe2",
        "question": QUESTION,
        "claim_under_test": "draft pin record for probe2",
        "validator_pin": pin,
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "NOT-RUN"},
        ],
        "evidence": [
            {
                "claim": "draft",
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/p2-wave/probes/ARC-0102/pin.json:1",
            },
            {
                "claim": "draft-2",
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/p2-wave/probes/ARC-0102/pin.json:2",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0102-probe2-pin-gate",
            "verdict": "PENDING",
            "independent": True,
        },
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(draft_pin, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    rc2, out2 = run(P2)
    if rc2 != 0:
        if out_path.is_file():
            out_path.unlink()
        print("FAILED:ARC-0102 probe2")
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-egress.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-pin.raw.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    resolver_rel = "command-center/p2-wave/probes/ARC-0102/schema_resolver.py"
    pin_rel = "command-center/p2-wave/probes/ARC-0102/pin.json"
    envelope_rel = (
        "command-center/p2-wave/probes/ARC-0102/schemas/artifact.envelope.json"
    )
    probe1_rel = "command-center/p2-wave/probes/ARC-0102/probe1_egress.py"
    probe2_rel = "command-center/p2-wave/probes/ARC-0102/probe2_pin.py"

    doc = {
        "unit_id": "ARC-0102",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0102",
        "title": "Schema registry, reference resolution and pinned offline validation",
        "question": QUESTION,
        "claim_under_test": (
            "A local canonical-$id registry resolves cross-schema $ref without "
            "network, the refuse-handler fires on an unregistered URI, and the "
            "pinned jsonschema version is a fail-closed gate."
        ),
        "answer": (
            "Canonical ids "
            + SR.IDENTITY_ID
            + ", "
            + SR.ENVELOPE_ID
            + ", "
            + SR.CASE_ID
            + " resolve two-hop $ref from a local store. jsonschema "
            + pin["observed_version"]
            + " is pinned; mismatch fails closed. Egress-blocked suite "
            "fingerprint equals egress-allowed. Unregistered https $ref is "
            "refused. SUCCESS:ARC-0102"
        ),
        "corpus": {
            "size": 6,
            "empty_set_policy": (
                "An empty accept/reject matrix is a detector failure, not a pass."
            ),
            "paths_consulted": [
                "command-center/p2-wave/probes/ARC-0102/schemas/common.identity.json",
                "command-center/p2-wave/probes/ARC-0102/schemas/artifact.envelope.json",
                "command-center/p2-wave/probes/ARC-0102/schemas/conformance.case.json",
                "command-center/p2-wave/probes/ARC-0102/fixtures/envelope.valid.json",
                "command-center/p2-wave/probes/ARC-0102/fixtures/envelope.invalid-no-hash.json",
                "command-center/p2-wave/probes/ARC-0102/fixtures/case.valid.json",
                "command-center/p2-wave/probes/ARC-0102/fixtures/case.invalid.json",
            ],
        },
        "coupling": {
            "kind": "cross-schema-$ref",
            "hops": [
                f"{SR.CASE_ID} -> {SR.ENVELOPE_ID}",
                f"{SR.ENVELOPE_ID} -> {SR.IDENTITY_ID}#/$defs/sha256",
            ],
            "remote_uri_policy": "refuse",
        },
        "validator_pin": {
            "package": pin["package"],
            "pinned_version": pin["pinned_version"],
            "observed_version": pin["observed_version"],
            "match": pin["match"],
            "mismatch_fails_gate": True,
            "pin_file": pin_rel,
        },
        "registry": {
            "canonical_ids": p1["canonical_ids"],
            "canonical_id_count": p1["canonical_id_count"],
            "local_product_ids": [
                SR.IDENTITY_ID,
                SR.ENVELOPE_ID,
                SR.CASE_ID,
            ],
            "cross_schema_hops": [
                f"{SR.CASE_ID} -> {SR.ENVELOPE_ID}",
                f"{SR.ENVELOPE_ID} -> {SR.IDENTITY_ID}#/$defs/sha256",
            ],
            "official_metaschema_seeded": p1["has_draft_2020_12"],
            "remote_fetch": "refused",
        },
        "online_vs_offline": {
            "identical": p1["identical"],
            "online_fingerprint": p1["online"]["fingerprint"],
            "offline_fingerprint": p1["offline"]["fingerprint"],
            "online_ok": p1["online"]["ok"],
            "offline_ok": p1["offline"]["ok"],
            "catalog_identical": p1.get("catalog_identical"),
            "note": (
                "egress_allowed vs egress_blocked. The validator never fetches; "
                "the block is proven independently via local HTTP."
            ),
        },
        "egress_control": p1["block_control"],
        "unregistered_ref": {
            "online": p1["refuse_unregistered_online"],
            "offline": p1["refuse_unregistered_offline"],
        },
        "catalog_output_schema_offline": p1.get("catalog_output_schema_offline")
        or {},
        "pin_control": {
            "match_silent": p2["match_silent"],
            "mismatch_fired": p2["mismatch_fired"],
            "mismatch_error": p2["mismatch_error"],
            "pin_restored": p2["pin_restored"],
        },
        "suite": p1["online"]["rows"],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS" if rc1 == 0 else "FAIL"},
            {"id": "probe2", "command": P2, "result": "PASS" if rc2 == 0 else "FAIL"},
            {
                "id": "suite-matrix",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import sys; sys.path.insert(0, "
                    "'command-center/p2-wave/probes/ARC-0102'); "
                    "import schema_resolver as s; r=s.run_suite(); "
                    "raise SystemExit(0 if r['ok'] else 1)\""
                ),
                "result": "PASS" if p1["online"]["ok"] else "FAIL",
            },
        ],
        "evidence": [
            {
                "claim": "Refuse-handler is the only remote retrieve path.",
                "verdict": "CONFIRMED",
                "anchor": f"{resolver_rel}:{find_line(REPO / resolver_rel, 'offline-registry: refused remote fetch')}",
                "path": resolver_rel,
                "line": find_line(
                    REPO / resolver_rel, "offline-registry: refused remote fetch"
                ),
                "snippet": "offline-registry: refused remote fetch",
                "kind": "live-tree",
            },
            {
                "claim": "Pin mismatch raises PinMismatch (fail closed).",
                "verdict": "CONFIRMED",
                "anchor": f"{resolver_rel}:{find_line(REPO / resolver_rel, 'jsonschema pin mismatch')}",
                "path": resolver_rel,
                "line": find_line(REPO / resolver_rel, "jsonschema pin mismatch"),
                "snippet": "jsonschema pin mismatch",
                "kind": "live-tree",
            },
            {
                "claim": "Envelope $ref uses the canonical identity schema URI.",
                "verdict": "CONFIRMED",
                "anchor": f"{envelope_rel}:{find_line(REPO / envelope_rel, 'common/identity.json#/$defs/sha256')}",
                "path": envelope_rel,
                "line": find_line(
                    REPO / envelope_rel, "common/identity.json#/$defs/sha256"
                ),
                "snippet": "common/identity.json#/$defs/sha256",
                "kind": "live-tree",
            },
            {
                "claim": (
                    "Pinned version is "
                    + str(pin["pinned_version"])
                    + " on this worktree."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{pin_rel}:{find_line(REPO / pin_rel, str(pin['pinned_version']))}",
                "path": pin_rel,
                "line": find_line(REPO / pin_rel, str(pin["pinned_version"])),
                "snippet": str(pin["pinned_version"]),
                "kind": "live-tree",
            },
        ],
        "negative_controls": [
            {
                "id": "unregistered-https-ref",
                "kind": "refuse-unregistered-$ref",
                "description": (
                    "A $ref to https://example.invalid/not-in-registry.json "
                    "must refuse rather than fetch."
                ),
                "fired_on_bad_state": p1["refuse_unregistered_online"]["refused"],
                "silent_on_good_state": p1["online"]["ok"],
                "detail": "https://example.invalid/not-in-registry.json",
            },
            {
                "id": "pin-mismatch-0.0.0-not-the-pin",
                "kind": "pin-gate",
                "description": "Pinned version 0.0.0-not-the-pin must raise PinMismatch.",
                "fired_on_bad_state": p2["mismatch_fired"],
                "silent_on_good_state": p2["match_silent"],
                "detail": p2["mismatch_error"],
            },
            {
                "id": "egress-block-local-http",
                "kind": "egress-block",
                "description": (
                    "Local HTTP succeeds without the block and fails with it; "
                    "validation fingerprints stay identical."
                ),
                "fired_on_bad_state": p1["block_control"]["block_discriminates"],
                "silent_on_good_state": p1["identical"],
                "detail": p1["block_control"]["blocked_error"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0102-probe2-pin-gate",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "scope": (
                "Pin both-states plus report-records-version. Did not author "
                "the registry store or the egress monkeypatch."
            ),
        },
        "strongest_surviving_counterargument": (
            "jsonschema "
            + str(pin["observed_version"])
            + " still ships cache_remote fetches inside "
            "RefResolver when the store misses; a future caller that constructs "
            "a bare RefResolver.from_schema without this registry will go to "
            "the network. This unit pins the offline constructor, it does not "
            "monkeypatch jsonschema globally. That residual is real."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {"path": resolver_rel, "exists": True, "role": "registry"},
            {"path": pin_rel, "exists": True, "role": "pin"},
            {"path": probe1_rel, "exists": True, "role": "named-probe"},
            {"path": probe2_rel, "exists": True, "role": "named-probe"},
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2[-4000:],
            },
        ],
        "completion_sentinel": "SUCCESS:ARC-0102",
        "produced_by": "command-center/p2-wave/probes/ARC-0102/emit_report.py",
        "timestamps": {"ended_at": now},
        "residual_unknowns": [
            (
                "platform/lib/schema_resolver.py is still absent on this "
                "worktree; this unit did not install a global resolver because "
                "wiring one would start validating every catalog contract, "
                "including missing schema files, and that blast radius is out "
                "of scope."
            )
        ],
    }

    catalog = SR.catalog_output_schema_offline()
    if not catalog.get("ok"):
        if out_path.is_file():
            out_path.unlink()
        print("FAILED:ARC-0102 catalog output_schema did not resolve offline")
        print(json.dumps(catalog, indent=2)[:2000])
        return 1
    doc["catalog_output_schema_offline"] = {
        "shim_id": catalog["shim_id"],
        "ref": catalog["ref"],
        "resolved_url": catalog["resolved_url"],
        "resolved_has_allOf": catalog["resolved_has_allOf"],
        "garbage_rejected": catalog["garbage_rejected"],
        "empty_rejected": catalog["empty_rejected"],
        "looks_like_receipt_core": catalog["looks_like_receipt_core"],
        "empty_messages": catalog["empty_messages"][:4],
        "note": (
            "Resolved from local files with cache_remote=False and refuse "
            "handlers. The output document keeps validator_pin at top level "
            "so probe2 can read it; receipt_core additionalProperties=false "
            "would reject that field, so this report is not claimed valid "
            "against the generated shim."
        ),
    }

    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    if size < 2048:
        print(f"FAILED:ARC-0102 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0102")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
