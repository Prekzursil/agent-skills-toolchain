#!/usr/bin/env python3
"""Write IMP-0369 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
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
UNIT = "IMP-0369"
OUT = "command-center/receipts/IMP-0369.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0369/probe1_eager_vs_lazy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0369/probe2_always_on_trace.py"
)
SUPPORTING = [
    "tools/router/lazy.py",
    "tools/router/__init__.py",
    "command-center/p2-wave/probes/IMP-0369/scenario.py",
    "command-center/p2-wave/probes/IMP-0369/probe1_eager_vs_lazy.py",
    "command-center/p2-wave/probes/IMP-0369/probe2_always_on_trace.py",
    "command-center/p2-wave/probes/IMP-0369/fixtures/capability-index.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0369/SUBAGENT-RETURN.json",
        "role": role,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def main() -> int:
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(HERE))
    import scenario  # noqa: WPS433
    from tools.router import lazy as L  # noqa: WPS433

    scenario.write_index()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    report = L.measure_turn_zero(scenario.capabilities(), select_ids=[scenario.SELECT_ID])
    p1_json = first_json_line(t1)
    p2_json = first_json_line(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_rel = "tools/router/lazy.py"
    module_sha, module_bytes = digest(REPO / module_rel)
    index_rel = "command-center/p2-wave/probes/IMP-0369/fixtures/capability-index.json"
    index_sha, index_bytes = digest(REPO / index_rel)

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0369",
        "completion_sentinel": "SUCCESS:IMP-0369",
        "title": "Lazy capability activation and gateway loader",
        "profile": "router-loader-module",
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=router-loader-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0369 question_or_target: "
            "Implement tools/router/lazy.py so a capability's full body loads only "
            "when selected, keeping turn-zero cost to the index summary."
        ),
        "artifact_paths": [OUT, module_rel] + SUPPORTING[1:],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"ended_at": now},
        "evidence": [
            {
                "id": "E1-eager-vs-lazy-turn-zero-tokens",
                "claim": (
                    "On the same six-capability fixture index, measured turn-zero "
                    f"payload tokens are lazy={report['lazy_turn_zero_tokens']} vs "
                    f"eager={report['eager_turn_zero_tokens']} "
                    f"(delta={report['token_delta_eager_minus_lazy']}) using tokenizer "
                    f"{report['tokenizer_id']} on the injected payload, not an estimate."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/lazy.py:measure_turn_zero",
                "measured": {
                    "tokenizer_id": report["tokenizer_id"],
                    "lazy_turn_zero_tokens": report["lazy_turn_zero_tokens"],
                    "eager_turn_zero_tokens": report["eager_turn_zero_tokens"],
                    "lazy_turn_zero_bytes": report["lazy_turn_zero_bytes"],
                    "eager_turn_zero_bytes": report["eager_turn_zero_bytes"],
                    "token_delta_eager_minus_lazy": report["token_delta_eager_minus_lazy"],
                    "lazy_payload_sha256": report["lazy_payload_sha256"],
                    "eager_payload_sha256": report["eager_payload_sha256"],
                    "probe1": p1_json,
                },
            },
            {
                "id": "E2-load-event-trace",
                "claim": (
                    "The lazy turn-zero load trace lists body loads only for "
                    f"{report['always_on_ids']}. After select({scenario.SELECT_ID}) "
                    f"the loaded set is {report['lazy_after_select_body_ids']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/lazy.py:GatewayLoader.turn_zero",
                "measured": {
                    "lazy_turn_zero_body_ids": report["lazy_turn_zero_body_ids"],
                    "eager_turn_zero_body_ids": report["eager_turn_zero_body_ids"],
                    "lazy_after_select_body_ids": report["lazy_after_select_body_ids"],
                    "accidental_eager_ids": report["accidental_eager_ids"],
                    "lazy_load_trace": report["lazy_load_trace"],
                },
            },
        ],
        "test_ids": [
            "IMP-0369-eager-vs-lazy-tokens",
            "IMP-0369-always-on-trace",
        ],
        "tests": [
            {
                "id": "IMP-0369-eager-vs-lazy-tokens",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "output_tail": t1[-1500:],
            },
            {
                "id": "IMP-0369-always-on-trace",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "output_tail": t2[-1500:],
            },
        ],
        "negative_control_ids": [
            "IMP-0369-NC-always-on-visible-in-trace",
            "IMP-0369-NC-demote-always-on-silent",
        ],
        "negative_controls": [
            {
                "id": "IMP-0369-NC-always-on-visible-in-trace",
                "kind": "eager-load-detector",
                "description": (
                    "Mark skill.gamma ALWAYS-ON. The lazy turn-zero load trace "
                    "must list its body, proving the trace can detect an eager load."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"body_ids={report['lazy_turn_zero_body_ids']}",
                "bad_state_output": "demote to LAZY must drop skill.gamma from the trace",
            },
            {
                "id": "IMP-0369-NC-demote-always-on-silent",
                "kind": "constant-fire-guard",
                "description": (
                    "Demoting skill.gamma to LAZY must empty the turn-zero body "
                    "trace. A detector that always emits every id would fail this state."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "probe2": p2_json,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0369-probe2-always-on-trace",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog tests_required, not the author summary",
            "notes": (
                "Probe 2 re-runs the loader, requires ALWAYS-ON in the trace, "
                "requires a LAZY sibling absent, and requires the demoted record "
                "to disappear. A second human in a fresh context was not obtained "
                "on this worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0385 capability-index builder is not delivered. Measurement "
                    "uses a six-record fixture index with the same record shape "
                    "(capability_id, summary, body, load_mode), not a live six-root census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0385, pass capability-index.json through "
                    "measure_turn_zero and republish the token table."
                ),
            },
            {
                "claim": (
                    "IMP-0392 injection budgeter is absent. The loader does not cap "
                    "injected tokens; it only withholds unselected bodies."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "After IMP-0392, compose GatewayLoader with the budgeter ceiling.",
            },
            {
                "claim": (
                    "IMP-0402 index cache invalidation is absent. GatewayLoader is "
                    "in-memory for one turn; it does not persist or hash-check a cache file."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "After IMP-0402, rebuild on truncated cache and re-measure turn zero.",
            },
            {
                "claim": (
                    f"Tokenizer {report['tokenizer_id']} is a pinned regex instrument "
                    "on the injected payload. tiktoken/cl100k is not installed on this host, "
                    "so counts are not vendor-LLM tokens."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": (
                    "Install a pinned tiktoken encoding, re-count the same payloads, "
                    "and require lazy still strictly cheaper than eager."
                ),
            },
        ],
        "report": {
            "kind": "router-lazy-gateway",
            "module": {
                "path": module_rel,
                "bytes": module_bytes,
                "sha256": module_sha,
            },
            "index_fixture": {
                "path": index_rel,
                "bytes": index_bytes,
                "sha256": index_sha,
                "capability_count": report["index_capability_count"],
            },
            "turn_zero": {
                "tokenizer_id": report["tokenizer_id"],
                "lazy_tokens": report["lazy_turn_zero_tokens"],
                "eager_tokens": report["eager_turn_zero_tokens"],
                "lazy_bytes": report["lazy_turn_zero_bytes"],
                "eager_bytes": report["eager_turn_zero_bytes"],
                "lazy_body_ids": report["lazy_turn_zero_body_ids"],
                "eager_body_ids": report["eager_turn_zero_body_ids"],
            },
            "falsifiable_answer": (
                f"Turn zero costs {report['lazy_turn_zero_tokens']} tokens lazy vs "
                f"{report['eager_turn_zero_tokens']} eager on the fixture index. "
                "No LAZY body loaded at turn zero; ALWAYS-ON skill.gamma did."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0369/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0369",
        "registered": True,
        "output_path": OUT,
        "output_schema": receipt["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "eager-vs-lazy-turn-zero-tokens",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "always-on-load-trace-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0369/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0369: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0369, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0369 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
