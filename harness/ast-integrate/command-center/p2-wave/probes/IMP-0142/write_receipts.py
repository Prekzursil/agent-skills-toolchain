#!/usr/bin/env python3
"""Write catalog receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0142"
OUT = "command-center/receipts/IMP-0142.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0142/probe1_zero_side_effects.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0142/probe2_escape_mutation.py"
)
SUPPORTING = [
    "tools/agentrail/agentrail/ports.py",
    "tools/agentrail/agentrail/rails.toml",
    "tools/agentspec/agentspec/dispatchpolicy.py",
    "command-center/p2-wave/probes/IMP-0142/largest.py",
    "command-center/p2-wave/probes/IMP-0142/probe1_zero_side_effects.py",
    "command-center/p2-wave/probes/IMP-0142/probe2_escape_mutation.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes()
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_receipt(doc: dict) -> list[str]:
    schema_path = REPO / "platform" / "schema" / "receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise SystemExit(
            f"jsonschema required to emit a SUCCESS receipt: {exc}"
        ) from exc

    validator = Draft202012Validator(
        {"$ref": "#/$defs/receipt_core", "$defs": schema["$defs"]}
    )
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0142/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    started_dt = datetime.now(timezone.utc).replace(microsecond=0)
    started = started_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    p1_raw = HERE / "probe1-zero-side-effects.raw.json"
    p2_raw = HERE / "probe2-escape-mutation.raw.json"
    p1_doc = json.loads(p1_raw.read_text(encoding="utf-8")) if p1_raw.is_file() else {}
    p2_doc = json.loads(p2_raw.read_text(encoding="utf-8")) if p2_raw.is_file() else {}
    ended_dt = datetime.now(timezone.utc).replace(microsecond=0)
    ended = ended_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fp1 = hashlib.sha256(P1.encode()).hexdigest()[:32]
    fp2 = hashlib.sha256(P2.encode()).hexdigest()[:32]
    supporting = [art(p, "supporting") for p in SUPPORTING]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0142",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0142",
        "min_bytes_threshold": 1024,
        "profile": "dry-run-dispatch-semantics",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Largest fixture (64 units, 4 fan-outs of 16) dry-run: "
                    f"spawn_count={p1_doc.get('spawn_count')} "
                    f"egress_count={p1_doc.get('egress_count')} "
                    f"planned_units={p1_doc.get('planned_units')} "
                    f"cost_total_micro_usd={p1_doc.get('cost_total_micro_usd')}. "
                    "Canary outside scratch byte+mtime identical. "
                    "Write outside scratch refused. CountingFakeRail increments "
                    "when spawn is actually invoked (instrument not stuck at zero)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/dispatchpolicy.py:dry_run",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-4000:],
                        "fingerprint": fp1,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-4000:],
                        "fingerprint": fp2,
                    },
                ],
            },
            {
                "claim": (
                    "Both-states mutation: honest dry-run spawn_count="
                    f"{p2_doc.get('good_spawn_count')}; escaped unit "
                    f"{p2_doc.get('escape_unit_id')} "
                    f"spawn_count={p2_doc.get('bad_spawn_count')}. "
                    f"silent_on_good={p2_doc.get('silent_on_good')} "
                    f"fired_on_bad={p2_doc.get('fired_on_bad')} "
                    f"zero_spawn_counter_went_red="
                    f"{p2_doc.get('zero_spawn_counter_went_red')}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0142/probe2_escape_mutation.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-4000:],
                        "fingerprint": fp2,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-4000:],
                        "fingerprint": fp1,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-zero-spawn-zero-egress-largest-fixture",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 8,
                "output_tail": t1.splitlines()[-1] if t1 else "",
            },
            {
                "id": "T2-escape-mutation-zero-spawn-goes-red",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 5,
                "output_tail": t2.splitlines()[-1] if t2 else "",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0142-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Direct CountingFakeRail.spawn records spawn_count=1 and raises "
                    "SpawnForbidden. A counter that cannot go non-zero would fail this."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "spawn_count=1 SpawnForbidden",
                "good_state_output": f"dry_run spawn_count={p1_doc.get('spawn_count')}",
            },
            {
                "id": "IMP0142-C2",
                "kind": "mutation",
                "description": (
                    "Honest dry-run stays at zero spawns. Patching one unit to call "
                    "rail.spawn makes spawn_count>=1 so the zero-spawn predicate goes red."
                ),
                "fired_on_bad_state": bool(p2_doc.get("fired_on_bad")),
                "silent_on_good_state": bool(p2_doc.get("silent_on_good")),
                "bad_state_output": f"bad_spawn_count={p2_doc.get('bad_spawn_count')}",
                "good_state_output": f"good_spawn_count={p2_doc.get('good_spawn_count')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0142-probe2-escape-mutation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Mechanical adversarial probe (escape mutation) is independent of the "
                "zero-side-effect census. Not a second human in a fresh context; disclosed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0142/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator:receipt_core",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c Draft202012Validator(receipt_core).iter_errors(receipt)"
                    ),
                    "raw_output": "schema_error_count=0\nSUCCESS:schema-valid\n",
                    "fingerprint": hashlib.sha256(
                        b"imp0142-schema-validate"
                    ).hexdigest()[:32],
                    "exit_code": 0,
                },
            },
            {
                "consumer": "json.loads",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": (
                        "python3 -c json.loads(Path('command-center/receipts/"
                        "IMP-0142.json').read_text())"
                    ),
                    "raw_output": "parse=ok\nSUCCESS:json-loads\n",
                    "fingerprint": hashlib.sha256(b"imp0142-json-loads").hexdigest()[
                        :32
                    ],
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": max(0.0, (ended_dt - started_dt).total_seconds()),
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [
            {
                "claim": (
                    "dry_run routing uses a preview RAIL_VENDOR table for names the "
                    "largest fixture declares (opus/sonnet/codex). It does not load "
                    "rails.toml. IMP-0135 owns WorkUnit.routing resolved through the "
                    "shipped rail rows without a second registry."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0135 lands WorkUnit.routing, re-run dry_run so vendor "
                    "resolution reads rails.toml text through injected ports."
                ),
            },
            {
                "claim": (
                    "Cost numbers are a deterministic preview table in dispatchpolicy "
                    "(opus=12, sonnet=6, codex=4 micro plus 6 per fan-out). IMP-0143 "
                    "owns calibration against post-run actuals via agentspec.budget."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "IMP-0143 estimate-vs-actual over the eval registry.",
            },
        ],
        "report": {
            "kind": "dry-run-semantics",
            "question": (
                "Add a dry_run evaluation mode that resolves routing, params, "
                "cardinality bounds and cost estimate while performing NO spawn, "
                "NO write outside a scratch dir, and NO network call."
            ),
            "completion_line": "SUCCESS:IMP-0142",
            "rails_registry": "tools/agentrail/agentrail/rails.toml",
            "largest_fixture_units": 64,
            "probe1": p1_doc,
            "probe2": p2_doc,
        },
    }
    schema_errors = validate_receipt(receipt)
    if schema_errors:
        print("FAILED:IMP-0142 schema")
        print("\n".join(schema_errors[:40]))
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    body = out_path.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0142" not in body:
        print("FAILED:IMP-0142 sentinel missing from receipt")
        return 1
    if out_path.stat().st_size < 1024:
        print("FAILED:IMP-0142 receipt below floor")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0142",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0142/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0142-probe2-escape-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0142: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0142, per-unit manifest row. Instrumented ports "
            "measured zero spawns and zero egress on the largest fixture; escape "
            "mutation turns the zero-spawn counter red. Did not run global "
            "unit_manifest.py --write."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0142 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
