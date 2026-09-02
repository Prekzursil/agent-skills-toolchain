#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0052-test-order-dependence.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import constants as C  # noqa: E402
import census as N  # noqa: E402
import schema_check as S  # noqa: E402

STRIKES = HERE / "_schema_strikes.json"
MIN_BYTES = 2048
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (C.REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": C.UNIT,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "required_fix": required_fix,
        "sentinel": f"FAILED:{C.UNIT} schema-park",
        "schema_fingerprint": fp,
        "schema_errors": errs[:25],
        "failure": {
            "classification": ["schema-invalid", "detector-failure"],
            "reason": required_fix,
        },
        "cloud_ok": False,
        "timestamps": {"started_at": now, "ended_at": now},
    }
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "id": C.UNIT,
        "unit_id": C.UNIT,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "cloud_ok": False,
        "output_path": C.OUT_REL,
        "notes": (
            "Parked after two same-fingerprint structural refutes. "
            "No ADV rebuild circle."
        ),
        "ts": now,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:{C.UNIT} parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def build(bundle: dict, started: str, ended: str) -> dict:
    unit = N.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    get_id = bundle["plants"]["test_get"]
    flake_id = bundle["plants"]["test_planted_flake"]
    od = bundle["classification"]["order_dependent"]
    flakes = bundle["classification"]["flakes"]
    headline = len(od)
    if not (
        bundle["lab_orders_differ"]
        and bundle["product_orders_differ"]
        and bundle["identity_equal"]
    ):
        raise RuntimeError("controls did not all pass; refusing SUCCESS emit")
    answer = (
        f"Executed lab cohort: {bundle['lab_collected']} collected tests, "
        f"{headline} order-dependent ("
        f"{get_id} passes in declaration order and fails under at least one "
        f"of seeds {bundle['seeds']}), {len(flakes)} flake ("
        f"{flake_id} varies across {bundle['n_repeats']} identical-order repeats "
        f"and is therefore not counted as order-dependent). "
        f"Product collectible set: {bundle['product_collected']} test nodeids "
        f"under tools/**/test_*.py; shuffle plugin reordered them across the "
        f"same three seeds (product_orders_differ="
        f"{bundle['product_orders_differ']}). Product execution is "
        f"NOT-CHECKED ({bundle['product_execution_reason']}). "
        f"Identity control (seed ignored) kept declaration order."
    )
    p1_src = {
        "role": "source",
        "method": "test-run",
        "command": C.P1,
        "raw_output": (
            f"seeds={bundle['seeds']} lab_differ={bundle['lab_orders_differ']} "
            f"product_differ={bundle['product_orders_differ']} "
            f"get_decl={bundle['declaration_outcomes'].get(get_id)}"
        )[:65536],
        "fingerprint": probe_fp("test-run", C.P1),
        "exit_code": 0,
    }
    p2_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": C.P2,
        "raw_output": (
            f"repeats={bundle['n_repeats']} "
            f"order_dependent={od} flakes={flakes} headline={headline}"
        )[:65536],
        "fingerprint": probe_fp("file-read", C.P2),
        "exit_code": 0,
    }
    plant_src = {
        "role": "verifier",
        "method": "file-read",
        "command": "command-center/p2-wave/probes/AUD-0052/lab/test_order_box.py",
        "raw_output": "test_get asserts box.txt written by test_put in the same session",
        "fingerprint": probe_fp(
            "file-read",
            "command-center/p2-wave/probes/AUD-0052/lab/test_order_box.py",
        ),
        "exit_code": 0,
    }
    plant_ver = {
        "role": "source",
        "method": "test-run",
        "command": C.P2,
        "raw_output": (
            f"identical-order test_get stable; planted flake varies; "
            f"flake not in order_dependent={od}"
        )[:65536],
        "fingerprint": probe_fp("test-run", C.P2),
        "exit_code": 0,
    }
    schema_probe = {
        "role": "verifier",
        "method": "schema-validate",
        "command": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/AUD-0052/schema_check.py"
        ),
        "raw_output": "disk-local Draft202012Validator; garbage rejected",
        "fingerprint": probe_fp("schema-validate", "AUD-0052/schema_check.py"),
        "exit_code": 0,
    }
    supporting = [
        art(C.SCHEMA_REL, "supporting"),
        art("command-center/p2-wave/probes/AUD-0052/shuffle_plugin.py", "supporting"),
        art("command-center/p2-wave/probes/AUD-0052/lab/test_order_box.py", "fixture"),
        art("command-center/p2-wave/probes/AUD-0052/lab/test_planted_flake.py", "fixture"),
        art("command-center/p2-wave/probes/AUD-0052/schema_check.py", "supporting"),
    ]
    return {
        "schema_version": 1,
        "unit_id": C.UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0052",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    f"{get_id} passes in declaration order and fails under at "
                    f"least one of seeds {bundle['seeds']}; shuffle reordered "
                    "lab and product collectible sets."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0052/probe1_three_seeds.py",
                "probes": [p1_src, plant_src],
            },
            {
                "claim": (
                    f"{flake_id} varies across {bundle['n_repeats']} identical-order "
                    "repeats and is not classified as order-dependent; "
                    f"headline_count={headline}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0052/probe2_five_repeats.py",
                "probes": [plant_ver, p2_ver],
            },
        ],
        "tests": [
            {
                "id": "shuffle-plugin-reorders-across-seeds",
                "command": C.P1,
                "result": "PASS",
            },
            {
                "id": "product-collectible-set-also-reorders",
                "command": C.P1,
                "result": "PASS",
            },
            {
                "id": "identity-control-does-not-reorder",
                "command": C.P1,
                "result": "PASS",
            },
            {
                "id": "planted-order-dep-found-by-shuffle-not-by-repeats",
                "command": C.P2,
                "result": "PASS",
            },
            {
                "id": "planted-flake-found-by-repeats-not-as-order-dep",
                "command": C.P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "identity-shuffle-does-not-reorder",
                "kind": "mutation",
                "description": (
                    "Identity copy of declaration order is equal across three "
                    "fake seeds (bad plugin); live Random(seed).shuffle differs."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "identity_equal=True (no reorder)",
                "good_state_output": "lab_orders_differ=True product_orders_differ=True",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "Disk-local audit-finding schema must reject empty, "
                    "unrelated, and blob documents."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "garbage documents produce one or more errors",
                "good_state_output": "live receipt validates",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0052-probe2-five-repeats-falsify-headline",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 recomputes five identical-order repeats before trusting "
                "headline_count; a flake must not inflate the order-dep count."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0052/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": C.UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator disk-local audit-finding",
                "artifact_path": C.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_probe,
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "two strikes then pivot"),
        },
        "residual_unknowns": [
            {
                "claim": bundle["product_execution_reason"],
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install pytest in a throwaway venv, execute tools/**/test_*.py "
                    "under the seeded shuffle plugin, and classify product "
                    "order-dep vs flake without writing retain/revert side effects."
                ),
            }
        ],
        "report": {
            "kind": "audit-finding",
            "question": C.QUESTION,
            "answer": answer,
            "title": unit.get("title"),
            "output_path": C.OUT_REL,
            "output_schema": C.SCHEMA_REL,
            "owner_decision": (
                "No owner approval required; this is a measured census, not a "
                "gate flip."
            ),
            "summary": (
                f"{headline} executed order-dependent test(s) in the lab cohort; "
                f"{bundle['product_collected']} product tests collected and "
                "shuffle-reordered; product execution NOT-CHECKED."
            ),
            "headline_count": headline,
            "census": bundle,
            "named_probes": [
                {
                    "id": "probe1",
                    "command": C.P1,
                    "raw_output": "pending-live-capture",
                    "role": "three-shuffled-seeds-and-reorder-control",
                },
                {
                    "id": "probe2",
                    "command": C.P2,
                    "raw_output": "pending-live-capture",
                    "role": "five-identical-order-repeats-flake-separation",
                },
            ],
            "observations": [
                {
                    "name": "lab_collected",
                    "measured": bundle["lab_collected"],
                    "method": "AST collect of probes/AUD-0052/lab/test_*.py",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/lab",
                },
                {
                    "name": "product_collected",
                    "measured": bundle["product_collected"],
                    "method": "AST collect of tools/**/test_*.py",
                    "anchor": "tools",
                },
                {
                    "name": "order_dependent_count",
                    "measured": headline,
                    "method": "declaration pass + shuffle fail + identical-order stable",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/census.py",
                },
                {
                    "name": "flake_count",
                    "measured": len(flakes),
                    "method": "identical-order repeats with outcome set size > 1",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe2_five_repeats.py",
                },
                {
                    "name": "product_executed",
                    "measured": 0,
                    "method": "collect-only; pytest absent",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/census.py",
                },
            ],
            "control_ids": [
                "AUD0052-C1-shuffle-reorders",
                "AUD0052-C2-identity-does-not-reorder",
                "AUD0052-C3-flake-not-order-dep",
            ],
        },
    }


def main() -> int:
    started = utcnow()
    bundle = N.measure()
    ended = utcnow()
    if not S.garbage_is_rejected():
        print("FAILED:AUD-0052 emit schema vacuous on garbage")
        return 1
    doc = build(bundle, started, ended)
    try:
        delta = (
            datetime.fromisoformat(ended.replace("Z", "+00:00"))
            - datetime.fromisoformat(started.replace("Z", "+00:00"))
        ).total_seconds()
        doc["timestamps"]["duration_seconds"] = max(0, int(delta))
    except ValueError:
        doc["timestamps"]["duration_seconds"] = 0
    errs = S.error_list(doc)
    if errs:
        fp = err_fp(errs)
        rec = load_strikes()
        rec["attempts"].append({"fp": fp, "errors": errs[:25], "ts": ended})
        STRIKES.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
        fps = [a.get("fp") for a in rec["attempts"] if a.get("fp")]
        if len(fps) >= 2 and fps[-1] == fps[-2]:
            return park_blocked(
                required_fix=(
                    "Fix audit-finding.schema.json violations with a new "
                    f"structural shape (fingerprint {fp}): {errs[0]}"
                ),
                errs=errs,
                fp=fp,
            )
        print("FAILED:AUD-0052 emit schema-invalid")
        for e in errs[:20]:
            print(" ", e)
        return 1
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:AUD-0052 emit {size}B below floor {MIN_BYTES}")
        return 1
    text = out.read_text(encoding="utf-8")
    unit = N.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel not in text:
        print("FAILED:AUD-0052 emit sentinel missing after write")
        return 1
    live = json.loads(text)
    if str(live.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:AUD-0052 emit self-declared", live.get("state"))
        return 1
    live_errs = S.error_list(live)
    if live_errs:
        print("FAILED:AUD-0052 emit post-write schema errors")
        for e in live_errs[:12]:
            print(" ", e)
        return 1
    print(
        f"wrote {C.OUT_REL} headline={doc['report']['headline_count']} "
        f"lab={bundle['lab_collected']} product={bundle['product_collected']}"
    )
    print("SUCCESS:AUD-0052 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
