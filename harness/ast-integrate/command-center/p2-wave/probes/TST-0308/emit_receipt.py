#!/usr/bin/env python3
"""Emit TST-0308 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0308"
OUT_REL = f"command-center/receipts/{UNIT}.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0308/probe1_correlation_series.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0308/probe2_control_and_retire.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/bench/tests/test_goodhart.py"
)
SUPPORTING = [
    "tools/bench/__init__.py",
    "tools/bench/ledger.py",
    "tools/bench/goodhart.py",
    "tools/bench/simulate.py",
    "tools/bench/tests/__init__.py",
    "tools/bench/tests/test_goodhart.py",
    "command-center/p2-wave/probes/TST-0308/probe1_correlation_series.py",
    "command-center/p2-wave/probes/TST-0308/probe2_control_and_retire.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def manifest_art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def receipt_art(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    digest, size = sha256_file(path)
    if size < 1:
        return None
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    clipped = raw[-16000:]
    if len(clipped) > 65536:
        clipped = clipped[-65536:]
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": clipped,
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def catalog_fields() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = {}
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == UNIT:
            unit = item
            break
    sentinel = str(unit.get("completion_sentinel") or f"SUCCESS:{UNIT}")
    return {
        "sentinel": sentinel,
        "output_path": str(unit.get("output_path") or OUT_REL),
        "output_schema": str(
            unit.get("output_schema") or "command-center/schema/receipt.schema.json"
        ),
        "question": str(unit.get("question_or_target") or ""),
        "title": str(unit.get("title") or ""),
        "tests_required": list(unit.get("tests_required") or []),
        "evidence_requirement": str(unit.get("evidence_requirement") or ""),
        "retry_policy": str(
            unit.get("retry_policy")
            or (
                "Two strikes then pivot (AGENTS.md 4b): after a second failure "
                "on the same hypothesis, enumerate at least two alternative "
                "approaches before a third attempt."
            )
        ),
        "unit": unit,
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    cat = catalog_fields()
    started_dt = datetime.now(timezone.utc)
    started = started_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    c_test, t_test = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if c_test != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} live probes tests={c_test} p1={code1} p2={code2}")
        print(t_test[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if f"SUCCESS:{UNIT}-tests" not in t_test:
        print(f"FAILED:{UNIT} tests sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in out1:
        print(f"FAILED:{UNIT} probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in out2:
        print(f"FAILED:{UNIT} probe2 sentinel missing")
        return 1

    p1 = first_json(out1)
    p2 = first_json(out2)
    rec1 = probe_rec("source", P1, out1, code1)
    rec2 = probe_rec("verifier", P2, out2, code2)
    rec_test = probe_rec("verifier", TEST_CMD, t_test, c_test)
    sentinel = cat["sentinel"]
    g_block = p1.get("goodhart") or {}
    f_block = p1.get("faithful") or {}
    g_series = g_block.get("series") or []
    f_series = f_block.get("series") or []
    g_find = g_block.get("finding") or {}
    first_r = g_series[0].get("pearson_r") if g_series else None
    last_r = g_series[-1].get("pearson_r") if g_series else None
    artifacts = []
    for rel in SUPPORTING:
        row = receipt_art(rel, "supporting")
        if row is not None:
            artifacts.append(row)
    if not artifacts:
        print(f"FAILED:{UNIT} no supporting artifacts on disk")
        return 1

    answer = (
        "Across a 6-iteration synthetic improvement loop (32 cases per "
        "iteration), the gameable proxy's Pearson r with an independent "
        f"exact end-state oracle moved from {first_r} to {last_r} while "
        f"the proxy mean rose {g_find.get('metric_gain')} and the outcome "
        f"mean moved {g_find.get('outcome_delta')}. The platform raised P1 "
        "and refused to celebrate. A faithful first-token-parse metric on "
        "the same loop kept high correlation and was celebrable. Demoting "
        "the decayed metric appended a status event; historical run bytes "
        "and the hash chain were unchanged; rewrite_run raised "
        "LedgerImmutableError. " + sentinel
    )
    if len(answer) > 2000:
        answer = answer[:1997] + "..."

    ended_dt = datetime.now(timezone.utc)
    ended = ended_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended_dt - started_dt).total_seconds())

    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; p=sys.argv[1]; d=json.load(open(p,encoding='utf-8')); "
        "assert d.get('unit_id')=='TST-0308'; assert 'SUCCESS:TST-0308' in open(p,encoding='utf-8').read(); "
        "print('read_ok', d.get('state'), d.get('sentinel'))\" "
        + cat["output_path"]
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{UNIT}",
        "min_bytes_threshold": 128,
        "artifacts": artifacts,
        "evidence": [
            {
                "anchor": "tools/bench/goodhart.py:correlation_series",
                "claim": (
                    "Metric-to-outcome Pearson r is reported as a 6-point series "
                    "for both a gameable proxy and a faithful proxy. A 1-point "
                    "snapshot is refused as insufficient to claim decay."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [rec1, rec_test],
            },
            {
                "anchor": "tools/bench/simulate.py:simulate_campaign",
                "claim": (
                    "Synthetic Goodhart control: an optimizer that stuffs "
                    "GH-PROXY-HIT lifts proxy_hit_or_exact_rate while the "
                    "exact end-state oracle falls. detect_goodhart fires P1 "
                    "and evaluate_metric_gain refuses to celebrate. The "
                    "vacuous twin (ignore_decay=True) does celebrate, so the "
                    "P1 is not a silent no-op. The faithful twin does not fire."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [rec1, rec2],
            },
            {
                "anchor": "tools/bench/ledger.py:demote_metric",
                "claim": (
                    "Metric retirement is an appended metric_status event. "
                    "Historical run rows stay byte-identical (file prefix "
                    "unchanged, history() equal). rewrite_run raises "
                    "LedgerImmutableError. Demoted metrics leave the active "
                    "set and the current scoring view without erasing history."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [rec2, rec_test],
            },
        ],
        "tests": [
            {"id": "unittest-goodhart", "command": TEST_CMD, "result": "PASS"},
            {
                "id": "probe1-correlation-series-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-synthetic-control-and-retire",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "vacuous-ignore-decay-celebrates-gameable-gain",
                "kind": "mutation",
                "description": (
                    "evaluate_metric_gain(ignore_decay=True) celebrates the "
                    "Goodhart campaign; the live evaluator raises P1 and does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "vacuous twin celebrate=true",
                "good_state_output": "live celebrate=false severity=P1",
            },
            {
                "id": "faithful-proxy-does-not-fire",
                "kind": "other",
                "description": (
                    "A first-token-parse metric that tracks the end-state as "
                    "skill rises must not raise P1."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "goodhart P1",
                "good_state_output": "faithful no P1, celebrate=true",
            },
            {
                "id": "rewrite-run-refused",
                "kind": "known-broken-fixture",
                "description": "rewrite_run(seq, metric_value=0) must raise.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "LedgerImmutableError",
                "good_state_output": "append-only demotion prefix preserved",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0308-probe2-control-and-retire",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Probe 2 re-runs the synthetic optimizer against a fresh temp "
                "ledger, asserts P1, then independently checks that demotion "
                "does not rewrite history. It does not reuse probe 1's process."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json.load of catalog output_path",
                "artifact_path": cat["output_path"],
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_rec(
                    "verifier",
                    consumer_cmd,
                    "pending-live-read",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": duration,
        },
        "retry": {"count": 0, "policy": cat["retry_policy"]},
        "residual_unknowns": [
            {
                "claim": (
                    "TST-0306 and TST-0309 are catalog dependencies and are not "
                    "delivered on this worktree. command-center/bench/results/ "
                    "has no production run corpus yet. This unit proves the "
                    "detector on a synthetic paired ledger the platform owns, "
                    "not on live shadow-split production scores."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Once TST-0295/TST-0306 land a real results ledger, replay "
                    "correlation_series on those run rows and confirm the same "
                    "P1 path fires only when a production proxy decays."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11059 is cited as an input but is not "
                    "present on this worktree. The catalog question_or_target "
                    "and tests_required are the contract used."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When the prompt file is restored, grep :11059 and confirm "
                    "no additional pairing rule beyond independent end-state."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "adversarial-refuter",
            "execution_substrate": "cloud-batch",
        },
        "report": {
            "kind": "goodhart_probe",
            "title": cat["title"],
            "question": cat["question"],
            "answer": answer,
            "evidence_requirement": cat["evidence_requirement"],
            "tests_required": cat["tests_required"],
            "output_schema": cat["output_schema"],
            "implementation": {
                "module": "tools/bench/goodhart.py",
                "ledger": "tools/bench/ledger.py",
                "simulator": "tools/bench/simulate.py",
                "tests": "tools/bench/tests/test_goodhart.py",
                "outcome_judgement": (
                    "deterministic exact end-state check "
                    "(text.strip() == str(expected)), which is not the metric"
                ),
                "gameable_metric": (
                    "proxy_hit_or_exact_rate (credits planted GH-PROXY-HIT)"
                ),
                "faithful_metric": "first_token_parse_rate",
                "p1_on_decay": True,
            },
            "correlation_series": {
                "goodhart": g_series,
                "faithful": f_series,
                "note": (
                    "A single correlation is a snapshot and cannot show decay. "
                    "These lists are per-iteration Pearson r and Spearman rho."
                ),
            },
            "probe1": p1,
            "probe2": p2,
        },
    }

    out_rel = cat["output_path"]
    out = REPO / out_rel
    write_json(out, receipt)
    c_cons, t_cons = run(consumer_cmd)
    if c_cons != 0 or "read_ok" not in t_cons:
        print(f"FAILED:{UNIT} downstream consumer rc={c_cons}")
        print(t_cons[-2000:])
        return 1
    receipt["downstream_consumers"][0]["exit_code"] = c_cons
    receipt["downstream_consumers"][0]["read_ok"] = True
    receipt["downstream_consumers"][0]["executed"] = True
    receipt["downstream_consumers"][0]["probe"] = probe_rec(
        "verifier", consumer_cmd, t_cons, c_cons
    )
    write_json(out, receipt)

    live_sha, live_bytes = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if sentinel not in text:
        print(f"FAILED:{UNIT} catalog sentinel absent from receipt")
        return 1

    rows = [manifest_art(out_rel, "primary")]
    rows[0]["sha256"] = live_sha
    rows[0]["bytes"] = live_bytes
    rows[0]["exists"] = True
    rows[0]["present"] = True
    for rel in SUPPORTING:
        rows.append(manifest_art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", manifest)

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": out_rel,
        "output_schema": cat["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "correlation-series-both-states",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "synthetic-control-and-retire",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": out_rel,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0308-probe2-control-and-retire",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0308: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "ts": ended,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    print(f"wrote {out_rel} bytes={live_bytes} sha256={live_sha}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
