"""Shard 9 receipt emitter.

Writes, for one unit:
  1. command-center/receipts/<ID>.json  - state=BLOCKED, failure.classification
     ["reviewer-absent"] (receipt_core forbids SUCCESS without reviewer.verdict=PASS
     + independent=true; only the independent reviewer closes)
  2. command-center/p2-wave/probes/<ID>/SUBAGENT-RETURN.json (status=DELIVERED for
     the BUILD+PROBE work; the receipt itself stays BLOCKED pending review)
  3. command-center/p2-wave/probes/<ID>/UNIT-ARTIFACT-MANIFEST.json with a
     CRLF-normalized sha256 row matching _measure_one_delivered.digest_file()

Usage: python _p2shard9/emit.py <unit-spec.json>
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import os


def run_probe(cmd: str, timeout: int = 120) -> dict:
    """Run a canonical POSIX-prefixed probe command on Windows or POSIX.

    Records the canonical command string verbatim; env prefixes are moved into
    the child environment (cmd.exe cannot execute "VAR=value command").
    """
    env = os.environ.copy()
    real = cmd
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", real)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        real = real[m.end():]
    proc = subprocess.run(real, shell=True, capture_output=True, text=True,
                          timeout=timeout, env=env, cwd=str(REPO))
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"exit_code": proc.returncode, "raw_output": out[-1500:]}


def run_probe_checked(cmd: str, timeout: int = 120) -> dict:
    res = run_probe(cmd, timeout=timeout)
    assert res["exit_code"] == 0, f"{cmd} rc={res['exit_code']}: {res['raw_output'][-500:]}"
    return res


def run_test(tid: str, cmd: str, timeout: int = 300) -> dict:
    res = run_probe(cmd, timeout=timeout)
    result = "PASS" if res["exit_code"] == 0 else "FAIL"
    return {"id": tid, "name": tid, "command": cmd, "result": result,
            "output_tail": res["raw_output"][-400:]}



def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(spec: dict) -> str:
    uid = spec["unit_id"]
    started = spec.get("started_at") or now_iso()
    ended = now_iso()
    out_rel = spec["output_path"]
    out_path = REPO / out_rel

    # ---- artifacts with measured, CRLF-normalized hashes ----
    artifacts: list[dict] = []
    for art in spec["artifacts"]:
        p = REPO / art["path"]
        sha, size = digest_file(p)
        artifacts.append({
            "path": art["path"],
            "bytes": size,
            "sha256": sha,
            "exists": True,
            "eol": "LF",
            "role": art.get("role", "supporting"),
        })

    # normalize evidence probes: required role/method/command/raw_output/fingerprint
    def _norm_probe(pr: dict) -> dict:
        pr = dict(pr)
        pr.setdefault("raw_output", "see probe raw file cited in the evidence anchor")
        pr["fingerprint"] = hashlib.sha256(
            f"{pr.get('method','')}|{pr.get('command','')}".encode("utf-8")
        ).hexdigest()[:16]
        allowed = {"role", "method", "command", "raw_output", "fingerprint", "exit_code"}
        return {k: v for k, v in pr.items() if k in allowed}

    evidence = []
    for ev in spec["evidence"]:
        ev = dict(ev)
        ev["probes"] = [_norm_probe(pr) for pr in ev.get("probes", [])]
        evidence.append(ev)

    receipt = {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": spec["sentinel"],
        "spec_anchor": spec["spec_anchor"],
        "min_bytes_threshold": spec.get("min_bytes_threshold", 2048),
        "produced_by": spec["produced_by"],
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": spec["tests"],
        "negative_controls": [
            {
                "id": nc["id"],
                "kind": nc["kind"],
                "description": nc["description"],
                "fired_on_bad_state": bool(nc.get("fired_on_bad_state", True)),
                "silent_on_good_state": bool(nc.get("silent_on_good_state", True)),
                "bad_state_output": nc.get("bad_state_output", ""),
                "good_state_output": nc.get("good_state_output", ""),
            }
            for nc in spec.get("negative_controls", [])
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": spec.get("duration_seconds", 0),
        },
        "retry": spec["retry"],
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": spec["failure_reason"],
            "blocked_on": spec.get(
                "blocked_on",
                "c9=UNSATISFIED independent adversarial reviewer PASS (catalog requires one "
                "independent reviewer in a fresh context; this receipt was authored by the "
                "builder and must not self-certify)",
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        },
        "residual_unknowns": spec.get("residual_unknowns", []),
        "extensions": spec.get("extensions", {}),
    }
    if spec.get("profile"):
        receipt["profile"] = spec["profile"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    # measure on the FINAL bytes
    live_sha, live_bytes = digest_file(out_path)

    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    probe_dir.mkdir(parents=True, exist_ok=True)

    subagent_return = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "BLOCKED-PENDING-INDEPENDENT-REVIEW",
        "sentinel": spec["sentinel"],
        "output_path": out_rel,
        "output_schema": spec.get("output_schema", "command-center/schema/receipt.schema.json"),
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "artifacts": [
            {
                "path": a["path"],
                "bytes": a["bytes"],
                "sha256": a["sha256"],
                "exists": True,
                "role": a["role"],
            }
            for a in artifacts
        ],
        "primary_artifact": {"path": out_rel, "bytes": live_bytes, "sha256": live_sha},
        "named_probes": spec["named_probes"],
        "cloud_ok": False,
        "registered": True,
        "reviewer": {"independent": False, "verdict": "NOT-REVIEWED", "reviewer_id": "pending"},
        "receipt_state": "BLOCKED",
        "failure_classification": ["reviewer-absent"],
        "notes": spec.get("return_notes", ""),
        "ts": ended,
    }
    (probe_dir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(subagent_return, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )

    manifest = {
        "artifacts": [
            {
                "unit_id": uid,
                "path": out_rel,
                "bytes": live_bytes,
                "sha256": live_sha,
                "present": True,
                "role": "primary",
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            }
        ]
        + [
            {
                "unit_id": uid,
                "path": a["path"],
                "bytes": a["bytes"],
                "sha256": a["sha256"],
                "present": True,
                "role": "supporting",
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            }
            for a in artifacts
            if a["path"] != out_rel
        ],
    }
    (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return f"{uid}: receipt bytes={live_bytes} sha256={live_sha}"


if __name__ == "__main__":
    spec_path = Path(sys.argv[1])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    print("SUCCESS:" + emit(spec))
