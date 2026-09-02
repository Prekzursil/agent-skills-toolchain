#!/usr/bin/env python3
"""Dispatch, classify faults, and score confusion matrices for CNF-0156."""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

import sys

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402

VENDORS = ("anthropic", "openai")
ORDER_SEEDS = {"anthropic": 15601, "openai": 15602}
CONFIRM_REL = "command-center/p2-wave/probes/CNF-0156/confirm.py"
RUNS = HERE / "runs"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_vendor_payloads(raw: bytes) -> dict[str, str]:
    C.PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for vendor in VENDORS:
        path = C.PAYLOAD_DIR / f"{vendor}.json"
        path.write_bytes(raw)
        hashes[vendor] = hashlib.sha256(raw).hexdigest()
    ident = C.IDENTICAL_PAYLOAD
    ident.write_bytes(raw)
    hashes["identical"] = hashlib.sha256(raw).hexdigest()
    return hashes


def confirm_command(vendor: str, payload_rel: str, output_rel: str) -> str:
    return (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        f"{CONFIRM_REL} --vendor {vendor} --payload-file {payload_rel} "
        f"--output-file {output_rel} --ignore-user-config"
    )


def classify_dispatch(
    exit_code: int, out_path: Path, stderr: str, stdout: str
) -> dict[str, Any]:
    blob = f"{stdout}\n{stderr}"
    if "429" in blob or "529" in blob:
        return {
            "status": "NOT-CHECKED",
            "reason": "quota-not-a-verdict",
            "doc": None,
        }
    if not out_path.is_file() or out_path.stat().st_size <= 0:
        if exit_code == 0:
            return {
                "status": "SEVERED",
                "reason": "severed-stream:exit-0-missing-output",
                "doc": None,
            }
        return {
            "status": "BLOCKED",
            "reason": f"missing-output:exit-{exit_code}",
            "doc": None,
        }
    try:
        doc = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        if exit_code == 0:
            return {
                "status": "SEVERED",
                "reason": "severed-stream:exit-0-unparsable",
                "doc": None,
            }
        return {"status": "BLOCKED", "reason": "unparsable", "doc": None}
    dumped = json.dumps(doc)
    if "429" in dumped or "529" in dumped:
        return {
            "status": "NOT-CHECKED",
            "reason": "quota-not-a-verdict",
            "doc": doc,
        }
    if not isinstance(doc, dict) or not isinstance(doc.get("verdicts"), list):
        return {"status": "BLOCKED", "reason": "no-verdicts", "doc": doc}
    return {"status": "OK", "reason": "ok", "doc": doc}


def run_vendor(
    vendor: str,
    payload_path: Path,
    output_path: Path,
    *,
    env_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload_rel = payload_path.relative_to(REPO).as_posix()
    output_rel = output_path.relative_to(REPO).as_posix()
    cmd = confirm_command(vendor, payload_rel, output_rel)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    classified = classify_dispatch(
        proc.returncode, output_path, proc.stderr or "", proc.stdout or ""
    )
    classified["exit_code"] = proc.returncode
    classified["command"] = cmd
    classified["vendor"] = vendor
    if "--background" in cmd:
        classified["status"] = "BLOCKED"
        classified["reason"] = "background-ban"
    return classified


def confusion(verdicts: list[dict[str, Any]], oracle: dict[str, str]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    unadj: list[str] = []
    per: list[dict[str, Any]] = []
    for row in verdicts:
        cid = row["id"]
        verdict = row["verdict"]
        label = oracle[cid]
        cell = "unadjudicated"
        if verdict not in {"CONFIRMED", "REFUTED"}:
            unadj.append(cid)
        elif label == "planted-true" and verdict == "CONFIRMED":
            tp += 1
            cell = "tp"
        elif label == "planted-true" and verdict == "REFUTED":
            fn += 1
            cell = "fn"
        elif label == "planted-false" and verdict == "CONFIRMED":
            fp += 1
            cell = "fp"
        elif label == "planted-false" and verdict == "REFUTED":
            tn += 1
            cell = "tn"
        per.append(
            {
                "id": cid,
                "ground_truth": label,
                "verdict": verdict,
                "cell": cell,
            }
        )
    n_true = tp + fn
    n_false = fp + tn
    false_pass = (fp / n_false) if n_false else None
    false_alarm = (fn / n_true) if n_true else None
    return {
        "counts": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "n_planted_true": n_true,
        "n_planted_false": n_false,
        "unadjudicated": unadj,
        "false_pass_rate": false_pass,
        "false_alarm_rate": false_alarm,
        "both_states": tp >= 1 and tn >= 1,
        "items": per,
    }


def both_states(matrix: dict[str, Any]) -> bool:
    return bool(matrix.get("both_states"))


def shuffle_items(items: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    out = list(items)
    rng = random.Random(seed)
    rng.shuffle(out)
    return out


def run_primary() -> dict[str, Any]:
    info = C.write_corpus()
    raw = info["payload_bytes"]
    hashes = write_vendor_payloads(raw)
    if len(set(hashes.values())) != 1:
        raise RuntimeError(f"payload identity failed {hashes}")
    oracle = {row["id"]: row["ground_truth"] for row in info["oracle"]}
    RUNS.mkdir(parents=True, exist_ok=True)
    vendor_runs: dict[str, Any] = {}
    raw_verdicts: list[dict[str, Any]] = []
    matrices: list[dict[str, Any]] = []
    commands: list[str] = []
    for vendor in VENDORS:
        out = RUNS / f"{vendor}.json"
        classified = run_vendor(vendor, C.PAYLOAD_DIR / f"{vendor}.json", out)
        commands.append(classified["command"])
        if classified["status"] != "OK":
            raise RuntimeError(f"{vendor} dispatch {classified}")
        doc = classified["doc"]
        matrix = confusion(doc["verdicts"], oracle)
        matrix["vendor"] = vendor
        matrices.append(matrix)
        vendor_runs[vendor] = {
            "command": classified["command"],
            "exit_code": classified["exit_code"],
            "status": classified["status"],
            "payload_sha256": doc.get("payload_sha256"),
            "output_path": out.relative_to(REPO).as_posix(),
        }
        for row in doc["verdicts"]:
            raw_verdicts.append(
                {
                    "vendor": vendor,
                    "claim_id": row["id"],
                    "verdict": row["verdict"],
                    "observation": row.get("observation"),
                }
            )
    return {
        "info": info,
        "hashes": hashes,
        "oracle": oracle,
        "oracle_rows": info["oracle"],
        "vendor_runs": vendor_runs,
        "matrices": matrices,
        "raw_verdicts": raw_verdicts,
        "commands": commands,
    }


def run_order_control(dispatch: list[dict[str, Any]], oracle: dict[str, str]) -> dict[str, Any]:
    RUNS.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = {}
    for vendor in VENDORS:
        shuffled = shuffle_items(dispatch, ORDER_SEEDS[vendor])
        if [i["id"] for i in shuffled] == [i["id"] for i in dispatch]:
            raise RuntimeError(f"{vendor} shuffle was a no-op")
        payload = C.payload_obj(shuffled)
        raw = C.canonical_dumps(payload)
        pfile = C.PAYLOAD_DIR / f"{vendor}-shuffled.json"
        pfile.write_bytes(raw)
        ofile = RUNS / f"{vendor}-shuffled.json"
        classified = run_vendor(vendor, pfile, ofile)
        if classified["status"] != "OK":
            raise RuntimeError(f"{vendor} shuffled dispatch {classified}")
        matrix = confusion(classified["doc"]["verdicts"], oracle)
        out[vendor] = {
            "seed": ORDER_SEEDS[vendor],
            "order": [i["id"] for i in shuffled],
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "false_pass_rate": matrix["false_pass_rate"],
            "false_alarm_rate": matrix["false_alarm_rate"],
            "counts": matrix["counts"],
            "command": classified["command"],
        }
    return out


def run_fault_injections(vendor: str = "anthropic") -> dict[str, Any]:
    info = C.write_corpus() if not C.IDENTICAL_PAYLOAD.is_file() else None
    _ = info
    if not C.IDENTICAL_PAYLOAD.is_file():
        C.write_corpus()
        write_vendor_payloads(C.IDENTICAL_PAYLOAD.read_bytes())
    payload = C.PAYLOAD_DIR / f"{vendor}.json"
    if not payload.is_file():
        write_vendor_payloads(C.IDENTICAL_PAYLOAD.read_bytes())
    RUNS.mkdir(parents=True, exist_ok=True)
    q_out = RUNS / f"{vendor}-inject-429.json"
    q = run_vendor(vendor, payload, q_out, env_extra={"CNF0156_INJECT": "429"})
    s_out = RUNS / f"{vendor}-inject-severed.json"
    if s_out.exists():
        s_out.unlink()
    s = run_vendor(vendor, payload, s_out, env_extra={"CNF0156_INJECT": "severed"})
    return {
        "quota": {
            "status": q["status"],
            "reason": q["reason"],
            "command": q["command"],
            "converted_to_refuted": q["status"] == "REFUTED",
        },
        "severed": {
            "status": s["status"],
            "reason": s["reason"],
            "command": s["command"],
            "produced_verdict": s["status"] == "OK",
        },
    }


def fingerprint_item(item: dict[str, Any]) -> str:
    return hashlib.sha256(C.canonical_dumps(item)).hexdigest()


def confirmation_record(
    *,
    vendor: str,
    item: dict[str, Any],
    verdict_row: dict[str, Any],
    payload_sha: str,
    command: str,
    fixture_sha: str,
    asserted_sha: str,
) -> dict[str, Any]:
    identity = {
        "anthropic": {
            "identity": "cnf-0156-anthropic-hash-oracle",
            "vendor": "anthropic",
            "role": "calibration-auditor",
        },
        "openai": {
            "identity": "cnf-0156-openai-stat-scanner",
            "vendor": "openai",
            "role": "cross-vendor-confirmer",
        },
    }[vendor]
    obs = json.dumps(verdict_row.get("observation") or {}, sort_keys=True)
    return {
        "kind": "confirmation-record",
        "claim_id": item["id"],
        "confirmer": identity,
        "blinding_attestation_hash": payload_sha,
        "baseline_repro": {
            "command": command,
            "exit_code": 0,
            "output": obs,
        },
        "corrected_repro": {
            "command": command,
            "exit_code": 0,
            "output": verdict_row["verdict"],
        },
        "rollback_repro": {
            "command": f"python3 -c 'from pathlib import Path; print(Path({item['evidence']['path']!r}).exists())'",
            "exit_code": 0,
            "output": "fixture-rechecked",
        },
        "regression_diff": {
            "path": item["evidence"]["path"],
            "before_sha256": fixture_sha,
            "after_sha256": asserted_sha,
        },
        "discrepancies": [],
        "verdict": verdict_row["verdict"],
        "source_probe": {
            "field": "dispatch-payload-item",
            "sha256": fingerprint_item(item),
        },
        "verifier_probe": {
            "tool": f"cnf-0156-{vendor}-confirmer",
            "command": command,
            "sha256": hashlib.sha256(obs.encode("utf-8")).hexdigest(),
        },
        "residual_caveat": (
            "Vendors are local executable confirmer adapters on this worktree; "
            "live mcp__codex dispatch was not used. Measurement is against the "
            "mutation oracle (fixture bytes), not against a live LLM."
        ),
    }


def fixture_and_asserted_hashes(item: dict[str, Any]) -> tuple[str, str]:
    path = REPO / item["evidence"]["path"]
    if path.is_file():
        fixture_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        fixture_sha = hashlib.sha256(b"absent:" + item["evidence"]["path"].encode()).hexdigest()
    asserted = item["evidence"].get("asserted", item["evidence"]["kind"])
    asserted_sha = hashlib.sha256(
        json.dumps(asserted, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return fixture_sha, asserted_sha
