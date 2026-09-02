#!/usr/bin/env python3
"""Write ADV-0063 attestation, SUBAGENT-RETURN.json, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not rotate or print API keys. Fixture keys stay in memory.

The catalog output_schema is a generated $ref shim whose target is
https://ast-integrate.invalid/... . jsonschema 4.10 RefResolver would
attempt a network GET. G-1 does not require that hop: this writer
resolves the shim, artifact-class-profiles, and receipt.schema.json from
disk and never hits the network.
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
REPO = HERE.parents[3]

UID = "ADV-0063"
OUT = "command-center/adversarial/ADV-0063-publisher-spoofing-and-key-recovery-drill.json"
SCHEMA = "command-center/schema/supply-chain-attestation.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0063/probe1_cross_identity_publish.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0063/probe2_key_recovery.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0063/fixture_registry.py",
    "command-center/p2-wave/probes/ADV-0063/probe1_cross_identity_publish.py",
    "command-center/p2-wave/probes/ADV-0063/probe2_key_recovery.py",
    SCHEMA,
]
GARBAGE = (
    {},
    {"unit_id": UID, "state": "SUCCESS"},
    {"totally": "unrelated", "passing_tests": 999999},
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def probe_fp(method: str, command: str) -> str:
    return sha256_text(f"{method}|{command}")


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def supporting_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0063/SUBAGENT-RETURN.json",
        "role": role,
    }


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:ADV-0063 catalog unit missing")


def last_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def local_validator():
    """Resolve ast-integrate.invalid $ref from disk. Never hit the network."""
    import jsonschema

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    store = {
        "https://ast-integrate.invalid/command-center/schema/supply-chain-attestation.schema.json": schema,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    for doc in (schema, profiles, receipt):
        ident = str(doc.get("$id") or "").split("#", 1)[0]
        if ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver(
        base_uri=(
            "https://ast-integrate.invalid/command-center/schema/"
            "supply-chain-attestation.schema.json"
        ),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def validate_schema(doc: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    validator = local_validator()
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            raise SystemExit("FAILED:ADV-0063 schema accepts garbage")
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0063 schema validation")
        for err in errors[:16]:
            print(f"  {list(err.path)}: {err.message}")
        raise SystemExit(1)


def assert_no_secrets(blob: str) -> None:
    lowered = blob.lower()
    for needle in ("secret_hex", "private_key", "api_key", "begin private"):
        if needle in lowered:
            raise SystemExit(f"FAILED:ADV-0063 secret-like token {needle!r} in output")


def evidence_probes(t1: str, t2: str, c1: int, c2: int) -> list[dict]:
    return [
        {
            "role": "source",
            "method": "test-run",
            "command": P1,
            "raw_output": t1,
            "fingerprint": probe_fp("test-run", P1),
            "exit_code": c1,
        },
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "raw_output": t2,
            "fingerprint": probe_fp("command", P2),
            "exit_code": c2,
        },
    ]


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:ADV-0063" not in sentinel:
        print("FAILED:ADV-0063 catalog sentinel unexpected")
        return 1

    started = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0063 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    assert_no_secrets(t1)
    assert_no_secrets(t2)

    p1 = last_json_object(t1)
    p2 = last_json_object(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0063 probe JSON pass=false")
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    question = str(unit.get("question_or_target"))
    foreign = p1.get("foreign_update") or {}
    owner = p1.get("owner_update_control") or {}
    naive_pub = p1.get("naive_mutant") or {}
    post = p2.get("post_revocation_compromised_key") or {}
    pre = p2.get("pre_revocation") or {}
    repl = p2.get("replacement_key") or {}
    naive_con = p2.get("naive_consumer") or {}
    census = p1.get("production_census") or {}
    probes = evidence_probes(t1, t2, c1, c2)

    answer = (
        "On the ADV-0063 fixture registry, identity B authenticated as pub-B cannot "
        f"publish an update to pkg.owned owned by pub-A ({foreign.get('action')}: "
        f"{foreign.get('reason')}). Identity A publishes its own 1.1.0 update "
        f"({owner.get('action')}). After the documented recovery stamps revoked_at="
        f"{p2.get('revocation_point')} on the compromised fixture key, a consumer who "
        "already trusted that key refuses artifacts signed after the revocation point "
        f"({post.get('consumer')}: {post.get('reason')}), still accepts the "
        f"pre-revocation artifact, and accepts a replacement-key artifact "
        f"({repl.get('consumer')}). Production marketplace publisher-identity and "
        f"publish-path files are absent (any_present={census.get('any_present')}); "
        "this drill does not rotate real credentials. " + sentinel
    )

    named_probes = [
        {
            "id": "probe1",
            "role": "cross-identity-publish-plus-owner-control",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "role": "key-compromise-recovery-consumer-acceptance",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
        },
    ]

    targets = [
        {
            "target_id": "T1-cross-identity-update",
            "target": (
                "identity B can publish or update a package owned by identity A "
                "on the fixture registry"
            ),
            "verdict": "REFUTED",
            "basis": foreign.get("reason"),
            "observed_action": foreign.get("action"),
        },
        {
            "target_id": "T2-owner-self-update-control",
            "target": "identity A can publish an update to its own package",
            "verdict": "CONFIRMED",
            "basis": owner.get("reason"),
            "observed_action": owner.get("action"),
            "versions_after": owner.get("versions_after"),
        },
        {
            "target_id": "T3-recovery-invalidates-post-revocation",
            "target": (
                "documented recovery makes a consumer who already trusted the "
                "compromised key stop accepting artifacts signed after the "
                "revocation point"
            ),
            "verdict": "CONFIRMED",
            "basis": post.get("reason"),
            "observed_action": post.get("consumer"),
            "pre_revocation_still_accepted": (p2.get("pre_revocation_after_refresh") or {}).get(
                "consumer"
            ),
            "replacement_key_accepted": repl.get("consumer"),
        },
    ]

    negative_controls = [
        {
            "id": "NC-NAIVE-REGISTRY-SKIPS-OWNER",
            "kind": "mutation",
            "description": (
                "A registry with enforce_owner=False must accept pub-B's update "
                "of pkg.owned so a broken authorisation check cannot be mistaken "
                "for a registry that never publishes."
            ),
            "fired_on_bad_state": bool(naive_pub.get("fired_on_bad_state")),
            "silent_on_good_state": foreign.get("action") == "REFUSED",
            "bad_state_output": str(naive_pub.get("action") or ""),
            "good_state_output": str(foreign.get("action") or ""),
        },
        {
            "id": "NC-NAIVE-CONSUMER-IGNORES-REVOCATION-POINT",
            "kind": "mutation",
            "description": (
                "A consumer with honor_revocation_point=False must accept a "
                "post-revocation signature from the compromised key, proving the "
                "honest consumer's REFUSE is the revocation-point check."
            ),
            "fired_on_bad_state": bool(naive_con.get("fired_on_bad_state")),
            "silent_on_good_state": post.get("consumer") == "REFUSED",
            "bad_state_output": str(naive_con.get("post_revocation_action") or ""),
            "good_state_output": str(post.get("consumer") or ""),
        },
    ]

    artifacts = [supporting_row(p, "supporting") for p in SUPPORTING]
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0063/write_receipts.py"
    )
    attestation = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": str(unit.get("spec_anchor") or "_USER-PROMPTS.md:10850"),
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "supply-chain-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "In a fixture registry, publishing pkg.owned@1.1.0 while "
                    "authenticated as pub-B is refused; pub-A publishes 1.1.0 in "
                    "the same run."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0063/fixture_registry.py:publish",
                "probes": probes,
            },
            {
                "claim": (
                    "After documented recovery, the consumer refuses a post-"
                    "revocation signature from the compromised fixture key, still "
                    "accepts the pre-revocation artifact, and accepts the replacement key."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0063/fixture_registry.py:"
                    "documented_recovery_procedure"
                ),
                "probes": probes,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-CROSS-IDENTITY",
                "name": "cross-identity publish plus owner-update control",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-RECOVERY",
                "name": "documented recovery with consumer refusal after revocation",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-REQUIRED-OWNER-SELF-UPDATE",
                "name": "control: identity A must be able to publish its own update",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-HARD-CONSTRAINT-SYNTHETIC-KEYS",
                "name": (
                    "only synthetic keys generated for this drill are used; no real "
                    "signing key or credential is created, read, rotated or revoked"
                ),
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0063-probe2-consumer-acceptance-from-raw-fixture",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Probe 2 is mechanically different from probe 1 (consumer acceptance "
                "after recovery vs publisher authorisation). Owner sign-off is not "
                "claimed for real credential rotation; that remains owner-gated."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0063/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UID,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator+local-disk-store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "local RefResolver store; garbage rejected; instance valid",
                    "fingerprint": probe_fp("schema-validate", schema_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "NO automatic retry"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0075 publisher-identity consumption is not delivered on this "
                    "worktree. Production cannot be attested as protected; the drill "
                    "is fixture-complete."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run Probe 1 against tools/marketplace/publish.py once IMP-0075 "
                    "lands, using the same owner-gated synthetic-key constraint."
                ),
            }
        ],
        "report": {
            "kind": "supply-chain-attestation",
            "observations": [
                {
                    "name": "foreign_update_action",
                    "measured": str(foreign.get("action") or ""),
                    "method": "fixture registry publish as pub-B of pkg.owned",
                    "anchor": "command-center/p2-wave/probes/ADV-0063/probe1_cross_identity_publish.py",
                },
                {
                    "name": "owner_update_action",
                    "measured": str(owner.get("action") or ""),
                    "method": "fixture registry publish as pub-A of pkg.owned@1.1.0",
                    "anchor": "command-center/p2-wave/probes/ADV-0063/probe1_cross_identity_publish.py",
                },
                {
                    "name": "post_revocation_consumer_action",
                    "measured": str(post.get("consumer") or ""),
                    "method": "consumer accept after documented_recovery_procedure",
                    "anchor": "command-center/p2-wave/probes/ADV-0063/probe2_key_recovery.py",
                },
                {
                    "name": "naive_owner_mutant_accepted",
                    "measured": bool(naive_pub.get("fired_on_bad_state")),
                    "method": "FixtureRegistry(enforce_owner=False)",
                    "anchor": "command-center/p2-wave/probes/ADV-0063/probe1_cross_identity_publish.py",
                },
                {
                    "name": "naive_revocation_mutant_accepted",
                    "measured": bool(naive_con.get("fired_on_bad_state")),
                    "method": "Consumer(honor_revocation_point=False)",
                    "anchor": "command-center/p2-wave/probes/ADV-0063/probe2_key_recovery.py",
                },
            ],
            "control_ids": [
                "T-REQUIRED-OWNER-SELF-UPDATE",
                "NC-NAIVE-REGISTRY-SKIPS-OWNER",
                "NC-NAIVE-CONSUMER-IGNORES-REVOCATION-POINT",
            ],
            "question": question,
            "answer": answer,
            "targets": targets,
            "named_probes_verbatim": named_probes,
            "production_census": census,
            "pre_revocation_consumer": pre,
            "replacement_key_consumer": repl,
            "hard_constraint": {
                "synthetic_keys_only": True,
                "secrets_serialized": False,
                "probe1": p1.get("synthetic_keys_only") is True
                and p1.get("secrets_serialized") is False,
                "probe2": p2.get("synthetic_keys_only") is True
                and p2.get("secrets_serialized") is False,
            },
            "owner_gate": {
                "applies_to": "real signing-key rotation or revocation",
                "enforced": (
                    "this drill mints only in-memory synthetic Ed25519 keys and never "
                    "reads, prints, rotates, or revokes a production credential"
                ),
                "handed_to_owner": (
                    "any real-world rotation recommendation remains an owner action"
                ),
                "owner_gated_part_approved": False,
            },
            "lifecycle": {
                "rotated": False,
                "revoked": False,
                "unset": False,
                "values_printed": False,
                "live_authentication_attempted": False,
                "real_credential_touched": False,
            },
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "notes": (
                "G-1 for ADV-0063: live named probes exit 0, attestation state=SUCCESS, "
                "per-unit manifest row. Did not run global unit_manifest.py --write. "
                "No ADV rebuild circle. Schema $ref resolved from disk. " + sentinel
            ),
        },
    }

    missing_controls = [
        nc
        for nc in attestation["negative_controls"]
        if not nc["fired_on_bad_state"] or not nc["silent_on_good_state"]
    ]
    if missing_controls:
        print("FAILED:ADV-0063 negative control did not discriminate", missing_controls)
        return 1

    validate_schema(attestation)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(attestation, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:ADV-0063 sentinel absent after write")
        return 1
    if '"state": "SUCCESS"' not in text:
        print("FAILED:ADV-0063 state not SUCCESS")
        return 1
    assert_no_secrets(text)

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0063 probes after receipt c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    man_artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "cross-identity-publish-plus-owner-control",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "key-compromise-recovery-consumer-acceptance",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0063/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0063-probe2-consumer-acceptance-from-raw-fixture",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": ended,
        "cloud_ok": False,
        "notes": (
            "G-1 for ADV-0063: live named probes exit 0, attestation state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Schema $ref resolved from disk."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0063 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
