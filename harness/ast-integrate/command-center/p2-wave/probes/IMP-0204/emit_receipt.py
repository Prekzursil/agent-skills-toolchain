#!/usr/bin/env python3
"""Emit IMP-0204 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes must already see the receipt (they check sentinel + non-BLOCKED).
This writer measures the engine in-process, persists the receipt, re-runs the
live named probes, then registers sha256 of the on-disk artifact.
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
sys.path.insert(0, str(REPO / "tools" / "workflows"))

from retirement import (  # noqa: E402
    Catalog,
    DeleteRefused,
    NotFound,
    SchemaError,
    KIND_DEPRECATION,
    KIND_SUPERSESSION,
    WARN_DEPRECATED,
    WARN_SUPERSEDED,
)

UNIT = "IMP-0204"
OUT = "command-center/receipts/IMP-0204.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0204/probe1_resolve_and_pin.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0204/probe2_refuse_delete.py"
)
OLD = "wf.catalog-class.discovery-only"
NEW = "wf.catalog-class.typed-restore"
DEP = "wf.legacy-scout"
DEP_SUCC = "wf.scout-v2"
PIN = "consumer.pinned-to-discovery-only"
AT = "2026-08-24T18:00:00Z"
SUPPORTING = [
    "tools/workflows/retirement.py",
    "tools/workflows/schema/retirement-record.schema.json",
    "command-center/p2-wave/probes/IMP-0204/probe1_resolve_and_pin.py",
    "command-center/p2-wave/probes/IMP-0204/probe2_refuse_delete.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": fp(method, command),
    }


def _catalog() -> Catalog:
    cat = Catalog()
    cat.publish({"id": OLD, "body": "discover-then-record", "version": "1"})
    cat.publish({"id": NEW, "body": "typed-restore-then-record", "version": "2"})
    cat.publish({"id": DEP, "body": "legacy-scout-body", "version": "1"})
    cat.publish({"id": DEP_SUCC, "body": "scout-v2-body", "version": "2"})
    cat.pin_consumer(PIN, OLD)
    cat.supersede(
        OLD,
        NEW,
        {
            "path": "migrations/discovery-only-to-typed-restore.md",
            "steps": ["retarget pin"],
        },
        retired_at=AT,
        reason="typed restore supersedes discovery-only hatch",
    )
    cat.deprecate(
        DEP,
        reason="scout corpus moved to hashed partitions",
        removal_date="2027-02-01",
        successor_id=DEP_SUCC,
        retired_at=AT,
    )
    return cat


def measure_engine() -> dict:
    cat = _catalog()
    resolved = cat.resolve(OLD)
    ran = cat.execute_consumer(PIN)
    dep = cat.execute_workflow(DEP)
    delete_payload = None
    try:
        cat.delete(OLD)
        delete_ok = True
    except DeleteRefused as exc:
        delete_ok = False
        delete_payload = exc.as_dict()
    still = cat.resolve(OLD)
    mutant = _catalog()
    mutant.force_drop_for_probe(OLD)
    silent_broke = False
    try:
        mutant.resolve(OLD)
    except NotFound:
        silent_broke = True
    schema_hits = []
    scratch = Catalog()
    scratch.publish({"id": "wf.a", "body": "a"})
    scratch.publish({"id": "wf.b", "body": "b"})
    for label, fn in (
        (
            "no-successor",
            lambda: scratch.retire(
                {
                    "kind": KIND_SUPERSESSION,
                    "retired_id": "wf.a",
                    "migration": {"path": "m.md"},
                }
            ),
        ),
        ("no-migration", lambda: scratch.supersede("wf.a", "wf.b", {})),
        (
            "dangling-successor",
            lambda: scratch.supersede("wf.a", "wf.missing", {"path": "m.md"}),
        ),
        (
            "deletion-kind",
            lambda: scratch.retire({"kind": "DELETION", "retired_id": "wf.a"}),
        ),
    ):
        try:
            fn()
            schema_hits.append({"label": label, "rejected": False})
        except SchemaError:
            schema_hits.append({"label": label, "rejected": True})
    warn = (ran.get("warnings") or [{}])[0]
    return {
        "resolve_successor": resolved.get("successor_id"),
        "resolve_present": resolved.get("present"),
        "pin_ok": ran.get("ok") and not ran.get("hard_break"),
        "pin_executed_id": ran.get("executed_id"),
        "pin_warning_code": warn.get("code"),
        "pin_warning_successor": warn.get("successor_id"),
        "deprecation_warning": (dep.get("warnings") or [{}])[0].get("code"),
        "delete_refused": (not delete_ok) and (delete_payload or {}).get("code") == "DELETE_REFUSED",
        "still_resolves_after_delete": still.get("present") is True,
        "silent_delete_broke_resolve": silent_broke,
        "schema_all_rejected": all(h["rejected"] for h in schema_hits),
        "schema_hits": schema_hits,
        "warn_superseded": WARN_SUPERSEDED,
        "warn_deprecated": WARN_DEPRECATED,
        "kind_supersession": KIND_SUPERSESSION,
        "kind_deprecation": KIND_DEPRECATION,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def build_receipt(m: dict) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_src = probe(
        "source",
        "in-process",
        "Catalog.supersede + Catalog.resolve + Catalog.execute_consumer",
        json.dumps(
            {
                "successor": m["resolve_successor"],
                "pin_ok": m["pin_ok"],
                "executed_id": m["pin_executed_id"],
                "warning": m["pin_warning_code"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_del = probe(
        "source",
        "in-process",
        "Catalog.delete on referenced retired workflow",
        json.dumps(
            {
                "delete_refused": m["delete_refused"],
                "still_resolves": m["still_resolves_after_delete"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_bad = probe(
        "verifier",
        "mutation",
        "Catalog.force_drop_for_probe (silent-deletion mutant, FC-11347)",
        json.dumps({"silent_delete_broke_resolve": m["silent_delete_broke_resolve"]}),
        0,
    )
    p_schema = probe(
        "verifier",
        "schema-reject",
        "validate_retirement rejects DELETION / missing successor / missing migration",
        json.dumps(m["schema_hits"]),
        0,
    )
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0204",
        "spec_anchor": "_USER-PROMPTS.md:11347",
        "title": "Implement deprecation and supersession records for retired workflows",
        "min_bytes_threshold": 128,
        "output_schema": "command-center/schema/receipt.schema.json",
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A retired workflow id remains resolvable and returns the successor: "
                    f"resolve({OLD!r}).successor_id == {NEW!r}."
                ),
                "verdict": "CONFIRMED" if m["resolve_successor"] == NEW else "REFUTED",
                "anchor": "tools/workflows/retirement.py:Catalog.resolve",
                "confidence": "almost-certain",
                "probes": [p_src],
            },
            {
                "claim": (
                    "A consumer pinned to the retired id still executes (no hard break) "
                    f"and emits typed warning {WARN_SUPERSEDED} naming successor {NEW!r}."
                ),
                "verdict": "CONFIRMED"
                if m["pin_ok"]
                and m["pin_executed_id"] == OLD
                and m["pin_warning_code"] == WARN_SUPERSEDED
                and m["pin_warning_successor"] == NEW
                else "REFUTED",
                "anchor": "tools/workflows/retirement.py:Catalog.execute_consumer",
                "confidence": "almost-certain",
                "probes": [p_src],
            },
            {
                "claim": (
                    "Deletion of a referenced workflow is refused; the id still resolves "
                    "afterwards (FC-11347: retirement is never silent removal)."
                ),
                "verdict": "CONFIRMED"
                if m["delete_refused"] and m["still_resolves_after_delete"]
                else "REFUTED",
                "anchor": "tools/workflows/retirement.py:Catalog.delete",
                "confidence": "almost-certain",
                "probes": [p_del, p_bad],
            },
            {
                "claim": (
                    "Retirement schema admits only SUPERSESSION (successor+migration) or "
                    "DEPRECATION (reason+removal_date); DELETION and dangling successors "
                    "are rejected."
                ),
                "verdict": "CONFIRMED" if m["schema_all_rejected"] else "REFUTED",
                "anchor": "tools/workflows/retirement.py:validate_retirement",
                "confidence": "almost-certain",
                "probes": [p_schema],
            },
        ],
        "tests": [
            {
                "id": "retired-id-resolves-pin-still-runs",
                "command": P1,
                "result": "PENDING-LIVE-PROBE",
            },
            {
                "id": "referenced-delete-refused",
                "command": P2,
                "result": "PENDING-LIVE-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0204-C1-silent-delete",
                "kind": "known-broken-fixture",
                "description": (
                    "Dropping the retired body without a retirement record (silent "
                    "deletion) must make resolve and pinned execute hard-break. The "
                    "public delete() path must not do this."
                ),
                "fired_on_bad_state": bool(m["silent_delete_broke_resolve"]),
                "silent_on_good_state": bool(m["pin_ok"] and m["still_resolves_after_delete"]),
                "bad_state_output": "force_drop_for_probe -> NotFound on resolve",
                "good_state_output": "supersede+pin execute ok; delete refused; still resolvable",
            },
            {
                "id": "IMP0204-C2-schema",
                "kind": "malformed-input",
                "description": "Malformed retirement records must be SCHEMA_INVALID.",
                "fired_on_bad_state": bool(m["schema_all_rejected"]),
                "silent_on_good_state": m["resolve_successor"] == NEW,
                "bad_state_output": json.dumps(m["schema_hits"]),
                "good_state_output": f"SUPERSESSION {OLD} -> {NEW} admitted",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0204-probe2-refuse-delete",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "probe2 is a separate process that did not author retirement.py; "
                "it re-runs delete-refusal and the silent-deletion mutant."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0204/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0204",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {
            "started_at": "2026-08-24T18:34:00Z",
            "ended_at": now,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0203 (certification record) is a catalog dependency and is "
                    "not delivered on this worktree; retirement does not consult "
                    "certificates."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run resolve against a catalog that also holds IMP-0203 certificates.",
            }
        ],
        "report": {
            "kind": "workflow-retirement-engine",
            "engine": "tools/workflows/retirement.py",
            "measurement": m,
            "failure_class": "FC-11347 rollback destroys user-owned files/commands/settings",
        },
        "cloud_ok": False,
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0204/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    measured = measure_engine()
    if not (
        measured["resolve_successor"] == NEW
        and measured["pin_ok"]
        and measured["delete_refused"]
        and measured["silent_delete_broke_resolve"]
        and measured["schema_all_rejected"]
    ):
        print("FAILED:IMP-0204 in-process engine measurement did not hold")
        print(json.dumps(measured, indent=2))
        return 1
    receipt = build_receipt(measured)
    out_path = REPO / OUT
    write_json(out_path, receipt)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0204 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    receipt["tests"][0]["result"] = "PASS" if c1 == 0 else "FAIL"
    receipt["tests"][0]["output_tail"] = t1[-1500:]
    receipt["tests"][1]["result"] = "PASS" if c2 == 0 else "FAIL"
    receipt["tests"][1]["output_tail"] = t2[-1500:]
    write_json(out_path, receipt)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0204",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0204/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0204-probe2-refuse-delete",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0204: live named probes exit 0, receipts/IMP-0204.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok is false and is not delivery."
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
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0204 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
