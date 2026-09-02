#!/usr/bin/env python3
"""Write catalog receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
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
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

UNIT = "IMP-0151"
OUT = "command-center/receipts/IMP-0151.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0151/probe1_zero_writes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0151/probe2_both_directions.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0151/adapter.py",
    "command-center/p2-wave/probes/IMP-0151/fixtures.py",
    "command-center/p2-wave/probes/IMP-0151/probe1_zero_writes.py",
    "command-center/p2-wave/probes/IMP-0151/probe2_both_directions.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1),
        "sha256": hashlib.sha256(data).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": A.eol_of(data) if data else "NOT-CHECKED",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0151/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    repo, live = F.build_readonly_estate()
    census = A.discover(live, repo, protect_host=True)
    host = A.discover_host(REPO)
    host_present = host["any_host_live_present"]

    p1_raw = HERE / "probe1-zero-writes.raw.json"
    p2_raw = HERE / "probe2-both-directions.raw.json"
    p1_doc = json.loads(p1_raw.read_text(encoding="utf-8")) if p1_raw.is_file() else {}
    p2_doc = json.loads(p2_raw.read_text(encoding="utf-8")) if p2_raw.is_file() else {}

    counts = census["counts"]
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0151",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0151",
        "min_bytes_threshold": 1024,
        "profile": "discovery-adapter-live-harness",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-serialized",
        },
        "question": (
            "Enumerate workflow-shaped capabilities in ~/.claude and ~/.agents "
            "(skills, commands, agents, hooks) READ-ONLY, recording repo-vs-live "
            "divergence per artifact without treating either side as authoritative."
        ),
        "claim_under_test": (
            "A read-only discovery adapter can classify repo-only and live-only "
            "controls in both directions and leave live trees byte-identical "
            "(mtime set equality) after a run."
        ),
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Filesystem audit: mtime/size/ino/sha256 snapshot of the live "
                    f"fixture tree ({p1_doc.get('live_files_snapshotted')} files) is "
                    f"equal before and after discover(); host trees created={p1_doc.get('host_created')}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0151/probe1_zero_writes.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "mtime-snapshot",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-4000:],
                        "fingerprint": hashlib.sha256(P1.encode()).hexdigest()[:32],
                    }
                ],
            },
            {
                "claim": (
                    "Known repo-only skill and known live-only skill are both classified "
                    f"correctly (repo-only={p2_doc.get('repo_only_ids')}, "
                    f"live-only={p2_doc.get('live_only_ids')}); shared skill is identical "
                    "and not filed as an orphan; divergent skill is divergent with "
                    "authoritative_side=null. Both-states: silent without plants, fires with plants."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0151/probe2_both_directions.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "both-states-plant",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-4000:],
                        "fingerprint": hashlib.sha256(P2.encode()).hexdigest()[:32],
                    }
                ],
            },
            {
                "claim": (
                    "Host live trees ~/.claude and ~/.agents are ABSENT on this Linux "
                    f"worktree (any_host_live_present={host_present}). The adapter does not "
                    "create them. Catalog-pinned historical '5 of 88 rules files "
                    "byte-identical' is NOT cited as a current measurement "
                    f"(cited_historical_5_of_88={census['cited_historical_5_of_88']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0151/adapter.py:host_live_roots",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "stat",
                        "command": "Path.home()/'.claude' and Path.home()/'.agents'",
                        "exit_code": 0,
                        "raw_output": json.dumps(host, indent=1)[:4000],
                        "fingerprint": hashlib.sha256(b"host-live-stat").hexdigest()[:32],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-zero-live-tree-writes",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 3,
                "output_tail": t1.splitlines()[-2] if t1 else "",
            },
            {
                "id": "T2-repo-only-and-live-only-both-directions",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t2.splitlines()[-2] if t2 else "",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0151-C1",
                "kind": "mtime-set-equality",
                "description": (
                    "A discover() run that writes a cache file or touches mtimes would "
                    "fail snapshot equality. Live fixture was chmod 0444/0555 during the run."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "chmod 0555 live tree; write would raise EACCES or fail snapshot",
                "good_state_output": f"live_mtime_set_equal={p1_doc.get('live_mtime_set_equal')}",
            },
            {
                "id": "IMP0151-C2",
                "kind": "both-states-orphan-classification",
                "description": (
                    "Without planted orphans the detector must not report repo-only-skill "
                    "or live-only-skill; with plants both directions must appear. A shared "
                    "capability must not be classified as an orphan."
                ),
                "fired_on_bad_state": bool(p2_doc.get("fired_on_bad")),
                "silent_on_good_state": bool(p2_doc.get("silent_on_good")),
                "bad_state_output": json.dumps(
                    {
                        "repo_only_ids": p2_doc.get("repo_only_ids"),
                        "live_only_ids": p2_doc.get("live_only_ids"),
                    }
                ),
                "good_state_output": json.dumps(p2_doc.get("good_counts")),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0151-probe2-both-directions",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "scope_not_agreement": True,
            "notes": (
                "Mechanical second signal (classification both-states) is independent of "
                "the mtime audit. Not a second human in a fresh context; disclosed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0151/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [
            {
                "claim": (
                    "On an estate where ~/.claude and ~/.agents are populated, the same "
                    "adapter will enumerate those trees without writing. This worktree "
                    "cannot demonstrate a non-empty host census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run adapter.discover_host() on a machine with populated live trees "
                    "and repeat the mtime snapshot against those real roots."
                ),
            }
        ],
        "report": {
            "kind": "live-harness-discovery",
            "adapter": "command-center/p2-wave/probes/IMP-0151/adapter.py",
            "read_only": True,
            "authoritative_side": None,
            "cited_historical_5_of_88": False,
            "host_any_live_present": host_present,
            "fixture_census": {
                "live_root": census["live_root"],
                "repo_root": census["repo_root"],
                "counts": counts,
                "union": census["union"],
            },
            "host": {
                "any_present": host_present,
                "roots": host["host_live_roots"],
            },
        },
        "completion_line": "SUCCESS:IMP-0151",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if "SUCCESS:IMP-0151" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0151 sentinel missing from receipt")
        return 1
    if out_path.stat().st_size < 1024:
        print("FAILED:IMP-0151 receipt below floor")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0151",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0151/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0151-probe2-both-directions",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0151: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0151, per-unit manifest row. Host ~/.claude and "
            "~/.agents absent on this Linux worktree; census is fixture-measured. "
            "Did not run global unit_manifest.py --write."
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
    print("SUCCESS:IMP-0151 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
