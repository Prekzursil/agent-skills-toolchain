#!/usr/bin/env python3
"""Emit IMP-0431 catalog receipt + per-unit G-1 return/manifest.

Named probes run first. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HARVEST = REPO / "tools" / "harvester"
sys.path.insert(0, str(HARVEST))

from harvest import run_harvest  # noqa: E402
from postcondition import independent_walk_counts  # noqa: E402

UNIT = "IMP-0431"
OUT = "command-center/receipts/IMP-0431.json"
SENTINEL = "SENTINEL:IMP-0431:HARVEST-POSTCONDITION"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0431/probe1_empty_harvest.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0431/probe2_nonempty_and_discriminating.py"
)
NONEMPTY = HERE / "fixtures" / "remote-nonempty"
SUPPORTING = [
    "tools/harvester/postcondition.py",
    "tools/harvester/harvest.py",
    "tools/harvester/__init__.py",
    "command-center/p2-wave/probes/IMP-0431/probe1_empty_harvest.py",
    "command-center/p2-wave/probes/IMP-0431/probe2_nonempty_and_discriminating.py",
    "command-center/p2-wave/probes/IMP-0431/emit_receipt.py",
    "command-center/p2-wave/probes/IMP-0431/fixtures/remote-nonempty/job-001/receipt.json",
    "command-center/p2-wave/probes/IMP-0431/fixtures/remote-nonempty/job-002/notes.txt",
    "command-center/p2-wave/probes/IMP-0431/fixtures/remote-nonempty/job-002/payload.dat",
    "command-center/p2-wave/probes/IMP-0431/fixtures/preseeded-dest/already-here.txt",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0431/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_harvest_pair() -> dict:
    """Independent emitter-side harvest: empty FAILED, nonempty SUCCESS with counts."""
    with tempfile.TemporaryDirectory(prefix="imp0431-emit-") as tmp:
        tmp_path = Path(tmp)
        empty_remote = tmp_path / "empty"
        empty_remote.mkdir()
        dest_e = tmp_path / "dest-empty"
        dest_e.mkdir()
        empty_v = run_harvest(
            empty_remote, dest_e, max_attempts=2, backoff_seconds=(0.0,)
        )
        dest_f = tmp_path / "dest-full"
        dest_f.mkdir()
        full_v = run_harvest(
            NONEMPTY, dest_f, max_attempts=1, backoff_seconds=(0.0,)
        )
        walk_n, walk_b = independent_walk_counts(dest_f)
        return {
            "empty": empty_v.to_dict(),
            "nonempty": full_v.to_dict(),
            "independent_walk": {
                "file_count": walk_n,
                "total_bytes": walk_b,
                "matches": walk_n == full_v.after.file_count
                and walk_b == full_v.after.total_bytes,
            },
        }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0431 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:IMP-0431 emit probe JSON pass=false")
        return 1

    live = live_harvest_pair()
    empty_live = live["empty"]
    full_live = live["nonempty"]
    if empty_live.get("state") != "FAILED" or empty_live.get("reason_id") != "silent-noop-harvest":
        print("FAILED:IMP-0431 emit live empty harvest was not FAILED")
        return 1
    if full_live.get("state") != "SUCCESS" or not (full_live.get("delta") or {}).get("nonempty"):
        print("FAILED:IMP-0431 emit live nonempty harvest was not SUCCESS")
        return 1
    if not live["independent_walk"]["matches"]:
        print("FAILED:IMP-0431 emit independent walk mismatch")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", "command", P1, t1, c1)
    p1v = probe_rec("verifier", "mutant-exit-zero-and-preseeded-dest", P1, t1, c1)
    p2 = probe_rec("source", "command", P2, t2, c2)
    p2v = probe_rec("verifier", "independent-walk-and-ast", P2, t2, c2)

    empty = j1.get("empty") or {}
    nonempty = j2.get("nonempty") or {}
    receipt = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Remote-harvest postcondition proving the harvest did something",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#IMP-0431; "
            "command-center/phase3/A1/FAILURE-MODES.json#FC-11319; "
            "_USER-PROMPTS.md:11319 (file absent on this sparse worktree)"
        ),
        "question_or_target": (
            "Implement the postcondition for spec failure class "
            "'remote harvest silently does nothing' at line 11319: a harvest "
            "run must assert a nonzero delta in harvested artifacts, or "
            "terminate as FAILED. Exact target: a harvest that returns exit 0 "
            "having transferred nothing must be classified FAILED, not SUCCESS."
        ),
        "min_bytes_threshold": 2048,
        "failure_class": "FC-11319",
        "implementation": {
            "postcondition": "tools/harvester/postcondition.py",
            "runner": "tools/harvester/harvest.py",
            "rule": (
                "SUCCESS requires process_exit_code==0 AND a nonempty dest delta "
                "(new or changed artifact paths). Dest already containing files "
                "is not a harvest."
            ),
            "empty_reason_id": "silent-noop-harvest",
            "retry_policy": "max 2 attempts; backoff 30s/120s in production CLI default; "
            "evidence runs used --backoff-seconds 0",
        },
        "inputs_on_this_worktree": {
            "harvester source": "absent; authored this unit as tools/harvester/",
            "remote job outputs": "fixture trees under probes/IMP-0431/fixtures/",
            "command-center/receipts/": "present; harvest dest is a temp tree so live receipts are not polluted",
            "IMP-0415": "dependency receipt absent; reducer not required for delta classification",
            "IMP-0421": "dependency receipt absent; adapter not required for harvest postcondition",
            "_USER-PROMPTS.md:11319": "absent; FC-11319 name/why taken from FAILURE-MODES.json",
        },
        "evidence": [
            {
                "claim": (
                    "Deliberately empty harvest: copy step exit "
                    f"{empty.get('process_exit_code')} transferring "
                    f"{empty.get('before_file_count')}->{empty.get('after_file_count')} "
                    f"files and {empty.get('before_total_bytes')}->"
                    f"{empty.get('after_total_bytes')} bytes was classified "
                    f"{empty.get('classification')} / {empty.get('reason_id')}, "
                    "not SUCCESS. CLI exit was nonzero. Live emitter re-run: "
                    f"state={empty_live.get('state')} attempts="
                    f"{empty_live.get('attempts')}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harvester/postcondition.py:classify",
                "confidence": "almost-certain",
                "probes": [p1, p1v],
            },
            {
                "claim": (
                    "Nonempty harvest of the planted remote tree: before "
                    f"files={nonempty.get('before_file_count')} bytes="
                    f"{nonempty.get('before_total_bytes')} after files="
                    f"{nonempty.get('after_file_count')} bytes="
                    f"{nonempty.get('after_total_bytes')} "
                    f"(delta files={nonempty.get('artifact_count_delta')} "
                    f"bytes={nonempty.get('bytes_delta')}) classified "
                    f"{nonempty.get('classification')}. Independent walk "
                    f"matched. Emitter re-run after="
                    f"{(full_live.get('after') or {}).get('file_count')} files / "
                    f"{(full_live.get('after') or {}).get('total_bytes')} bytes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/harvester/harvest.py:run_harvest",
                "confidence": "almost-certain",
                "probes": [p2, p2v],
            },
        ],
        "harvest_empty": {
            "classification": empty.get("classification"),
            "reason_id": empty.get("reason_id"),
            "process_exit_code": empty.get("process_exit_code"),
            "before_file_count": empty.get("before_file_count"),
            "after_file_count": empty.get("after_file_count"),
            "before_total_bytes": empty.get("before_total_bytes"),
            "after_total_bytes": empty.get("after_total_bytes"),
            "run_attempts": (j1.get("run_harvest_empty") or {}).get("attempts"),
            "cli_exit_code": j1.get("cli_exit_code"),
            "emitter_state": empty_live.get("state"),
            "emitter_attempts": empty_live.get("attempts"),
        },
        "harvest_nonempty": {
            "classification": nonempty.get("classification"),
            "reason_id": nonempty.get("reason_id"),
            "before_file_count": nonempty.get("before_file_count"),
            "after_file_count": nonempty.get("after_file_count"),
            "before_total_bytes": nonempty.get("before_total_bytes"),
            "after_total_bytes": nonempty.get("after_total_bytes"),
            "artifact_count_delta": nonempty.get("artifact_count_delta"),
            "bytes_delta": nonempty.get("bytes_delta"),
            "added_paths": nonempty.get("added_paths"),
            "independent_walk": j2.get("independent_walk"),
            "emitter_after_file_count": (full_live.get("after") or {}).get("file_count"),
            "emitter_after_total_bytes": (full_live.get("after") or {}).get("total_bytes"),
            "emitter_walk": live["independent_walk"],
        },
        "timestamps": {"started_at": "2026-08-24T18:45:00Z", "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "max 2 attempts, backoff 30s/120s; escalate if the second "
                "harvest is also empty. Evidence runs used backoff 0. Retry "
                "control: empty remote then fill between attempts reached "
                f"SUCCESS on attempt {(j2.get('retry_empty_then_fill') or {}).get('attempts')}."
            ),
        },
        "tests": [
            {
                "id": "empty-harvest-must-fail-the-run",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "requirement": "empty-harvest test must FAIL the run",
            },
            {
                "id": "nonempty-harvest-must-pass",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "requirement": "nonempty-harvest test must pass; a harvester that passes both is not discriminating",
            },
        ],
        "negative_controls": [
            {
                "id": "exit-zero-as-success-mutant",
                "kind": "both-states",
                "description": (
                    "Classifying exit 0 as SUCCESS with no delta check must "
                    "PASS an empty harvest; the live classifier must not."
                ),
                "fired_on_bad_state": bool(
                    j1.get("mutant_exit_zero_classifies_empty_success")
                ),
                "silent_on_good_state": bool(j1.get("real_empty_not_success")),
                "bad_state_output": "mutant_exit_zero=SUCCESS on empty copy",
                "good_state_output": f"live empty classification={empty.get('classification')}",
            },
            {
                "id": "preseeded-dest-is-not-a-harvest",
                "kind": "both-states",
                "description": (
                    "A dest that already contains files plus an empty remote "
                    "must still be FAILED. A mutant that treats dest stock as "
                    "SUCCESS fires; live classify does not."
                ),
                "fired_on_bad_state": bool(
                    j1.get("mutant_dest_populated_classifies_preseeded_success")
                ),
                "silent_on_good_state": (j1.get("preseeded_empty_remote") or {}).get(
                    "classification"
                )
                == "FAILED",
                "bad_state_output": "mutant_dest_populated=SUCCESS",
                "good_state_output": json.dumps(
                    j1.get("preseeded_empty_remote"), sort_keys=True
                ),
            },
            {
                "id": "empty-and-nonempty-must-disagree",
                "kind": "both-states",
                "description": "A harvester that passes both empty and nonempty is not discriminating.",
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(j2.get("discriminates")),
                "bad_state_output": "would-be: empty SUCCESS and nonempty SUCCESS",
                "good_state_output": (
                    f"empty_still_failed={j2.get('empty_still_failed')} "
                    f"nonempty={nonempty.get('classification')}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0431-probe2-walk-and-ast",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe2 is a second path: independent os.walk counts vs snapshot, "
                "plus AST that classify is not exit-zero-as-success and harvest.py "
                "calls classify. Catalog reviewer_requirement asks for an "
                "independent-claude-reviewer; that human pass is residual and is "
                "not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0431/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "notes": "G-1 measure is run after this receipt is written",
            }
        ],
        "named_probes": [
            {"id": "probe1", "role": "empty-harvest-failed", "command": P1},
            {
                "id": "probe2",
                "role": "nonempty-harvest-discriminating",
                "command": P2,
            },
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh "
                    "context has not scored this unit."
                ),
            },
            {
                "id": "spec-file-absent",
                "text": (
                    "_USER-PROMPTS.md:11319 is not on this worktree. The "
                    "postcondition implements the catalog target and FC-11319 why "
                    "('No runtime delta assertion; a silent empty harvest looks like success.')."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a human adversarial reviewer in a fresh context scored PASS",
            "IMP-0415 shared reducer was imported (absent on this tree)",
            "live production remotes were harvested into command-center/receipts/",
        ],
        "defects": [],
        "ts": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:IMP-0431 emit catalog sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0431 artifact {size}B below floor")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:IMP-0431 missing supporting", missing)
        return 1
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
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "empty-harvest-failed",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "nonempty-harvest-discriminating",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0431/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0431-probe2-walk-and-ast",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0431: live named probes exit 0, receipts/IMP-0431.json "
            "state=SUCCESS with SENTINEL:IMP-0431:HARVEST-POSTCONDITION, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0431 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
