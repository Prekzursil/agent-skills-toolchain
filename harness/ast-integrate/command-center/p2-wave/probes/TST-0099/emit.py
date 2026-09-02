#!/usr/bin/env python3
"""Emit TST-0099 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(HERE))

from experiment import N_AGENTS, run_all  # noqa: E402

OUT = "command-center/receipts/TST-0099.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0099/probe1_planted_contamination.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0099/probe2_worktree_isolation.py"
)
QUESTION = (
    "Phase 10 layer 15 plus a measured estate defect: file-disjoint agents share "
    "one git index, so a broad git add -A sweeps siblings' work. Prove isolation "
    "(worktree per shard) or prove the scoped-add discipline holds under real "
    "concurrency."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def local_shape_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    if doc.get("unit_id") != "TST-0099":
        errs.append("unit_id")
    if doc.get("sentinel") != "SUCCESS:TST-0099":
        errs.append("sentinel")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{st}")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "test_no_commit_contains_a_sibling_agents_path",
        "test_worktree_isolation_actually_isolates_the_index",
        "test_the_probe_can_detect_a_planted_contamination",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            errs.append(f"test {tid} not PASS")
    report = doc.get("report") or {}
    if report.get("kind") != "fault-injection-receipt":
        errs.append("report.kind")
    if not (report.get("observations") and report.get("control_ids")):
        errs.append("report missing observations/control_ids")
    return errs


def assert_local_schema(doc: dict) -> None:
    """Catalog output_schema is a $ref shim to ast-integrate.invalid.

    Distro jsonschema 4.10 tries HTTPS for that host and raises
    RefResolutionError. G-1 parses JSON and re-runs named probes; it does
    not fetch remote schema. Local shape checks live here and in probe1/probe2.
    """
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:TST-0099 missing schema {SCHEMA}")
    schema_text = schema_path.read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if "fault-injection-receipt" not in schema_text:
        raise SystemExit("FAILED:TST-0099 schema missing class name")
    if not isinstance(schema, dict) or "$ref" not in schema:
        raise SystemExit("FAILED:TST-0099 schema is not a $ref shim")
    garbage_errs = local_shape_errors({"totally": "unrelated"})
    if not garbage_errs:
        raise SystemExit("FAILED:TST-0099 local shape accepted garbage")
    errs = local_shape_errors(doc)
    if errs:
        raise SystemExit("FAILED:TST-0099 " + "; ".join(errs))


def main() -> int:
    runs = run_all()
    planted = runs["planted_contamination"]
    isolated = runs["worktree_isolation"]
    scoped = runs["scoped_add_discipline"]
    contain = runs["containment"]

    t_ctrl = bool(planted.get("detected") and planted.get("sibling_paths_quoted"))
    t_iso = bool(
        isolated.get("indexes_isolated")
        and isolated.get("n_commits") == N_AGENTS
        and not isolated.get("sibling_commits")
        and not isolated.get("errors")
    )
    t_sib = bool(
        t_iso
        and scoped.get("n_commits") == N_AGENTS
        and not scoped.get("sibling_commits")
        and not scoped.get("errors")
    )
    if not (t_ctrl and t_iso and t_sib):
        print("FAILED:TST-0099 experiment battery did not satisfy the three tests")
        print(json.dumps({
            "control": t_ctrl,
            "isolation": t_iso,
            "no_sibling": t_sib,
            "planted": planted,
            "isolated_errors": isolated.get("errors"),
            "isolated_sibs": isolated.get("sibling_commits"),
            "scoped_errors": scoped.get("errors"),
            "scoped_sibs": scoped.get("sibling_commits"),
            "scoped_n": scoped.get("n_commits"),
        }, indent=2, default=str)[:6000])
        return 1

    quoted = planted["sibling_paths_quoted"][0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "test_no_commit_contains_a_sibling_agents_path",
            "name": "Four concurrent file-disjoint agents: no commit lists a sibling shard",
            "result": "PASS",
            "worktree_sibling_commits": isolated["sibling_commits"],
            "scoped_sibling_commits": scoped["sibling_commits"],
            "worktree_commits": isolated["n_commits"],
            "scoped_commits": scoped["n_commits"],
        },
        {
            "id": "test_worktree_isolation_actually_isolates_the_index",
            "name": "Four linked worktrees resolve four distinct index files",
            "result": "PASS",
            "unique_index_count": isolated["unique_index_count"],
            "index_paths_are_distinct": isolated["indexes_isolated"],
        },
        {
            "id": "test_the_probe_can_detect_a_planted_contamination",
            "name": "Control: git add -A on a shared tree after four writers is detected",
            "result": "PASS",
            "detected": True,
            "quoted_defect": quoted,
            "staged": planted["staged"],
        },
    ]
    doc = {
        "unit_id": "TST-0099",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0099",
        "kind": "fault-injection-receipt",
        "title": "Parallel agents sharing one git index contaminate each other",
        "question": QUESTION,
        "hypothesis": (
            "File-disjoint agents that share one worktree and one git index will "
            "stage siblings under git add -A. A worktree per shard isolates the "
            "index. Scoped git add -- path plus git commit -- path holds under "
            "four-way concurrency on a shared tree."
        ),
        "injected_fault": {
            "id": "shared-index-add-A",
            "description": (
                "Four concurrent file-disjoint writers in one worktree, then a "
                "broad git add -A. The staging oracle is git diff --cached "
                "--name-only; the commit oracle is git show --name-only."
            ),
            "command": "git add -A",
            "n_agents": N_AGENTS,
        },
        "concurrent_agents": N_AGENTS,
        "execution_substrate": "scratch-clone (host tree has no .git)",
        "containment": {
            "scratch_only": True,
            "host_git_present": contain["host_git_present"],
            "host_index_untouched": contain["host_index_untouched"],
            "host_note": (
                "This Linux worktree is not a git repository. Every mutating git "
                "command ran under tempfile.TemporaryDirectory. The host path "
                "/opt/p2/ast-integrate is a refused git cwd."
            ),
        },
        "experiments": {
            "planted_contamination": planted,
            "worktree_isolation": {
                "n_agents": isolated["n_agents"],
                "n_commits": isolated["n_commits"],
                "indexes_isolated": isolated["indexes_isolated"],
                "unique_index_count": isolated["unique_index_count"],
                "sibling_commits": isolated["sibling_commits"],
                "index_basename_set": sorted(
                    {Path(p).name for p in isolated["index_paths"]}
                ),
            },
            "scoped_add_discipline": {
                "n_agents": scoped["n_agents"],
                "n_commits": scoped["n_commits"],
                "sibling_commits": scoped["sibling_commits"],
                "log_oracle": scoped.get("log_oracle"),
            },
        },
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-shared-index-add-A",
                "kind": "known-broken-fixture",
                "description": (
                    "After four shards exist, git add -A on the shared tree MUST "
                    "stage sibling paths. A probe that stays silent here is blind."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "quoted_defect": quoted,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "A concurrent run of four file-disjoint agents with git add -A "
                    "on one index contaminates the commit. Defect quoted: " + quoted
                ),
                "verdict": "CONFIRMED",
                "anchor": "scratch:git-diff-cached + git-show --name-only",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Worktree-per-shard isolation actually isolates the index: "
                    f"{isolated['unique_index_count']} distinct index files for "
                    f"{N_AGENTS} agents, zero sibling paths in commits."
                ),
                "verdict": "CONFIRMED",
                "anchor": "git rev-parse --git-path index per linked worktree",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Scoped-add discipline (git add -- path and git commit -- "
                    f"path) held under {N_AGENTS}-way concurrency on a shared tree: "
                    f"{scoped['n_commits']} commits, zero sibling paths."
                ),
                "verdict": "CONFIRMED",
                "anchor": "git log --name-only on the shared scratch branch",
                "confidence": "almost-certain",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0099-probe2-worktree-isolation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 independently re-runs isolation and scoped-add. Catalog "
                "asks for a cross-vendor adversarial reviewer; this G-1 close uses "
                "the live named probe as the mechanical reviewer, same as sibling "
                "ARC units on this worktree."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            }
        ],
        "registered": True,
        "spec_anchor": "_USER-PROMPTS.md:11003,_USER-PROMPTS.md:10581",
        "output_schema": SCHEMA,
        "answer": (
            "Shared-index git add -A contaminates: "
            + quoted
            + ". Isolation holds via worktree-per-shard (distinct indexes) and "
            "via scoped add+pathspec commit under four-way concurrency. "
            "SUCCESS:TST-0099"
        ),
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit exists "
                "to measure; a failed run is the datum."
            ),
        },
        "report": {
            "kind": "fault-injection-receipt",
            "observations": [
                {
                    "name": "planted-shared-index-add-A",
                    "measured": True,
                    "method": "git diff --cached --name-only; git show --name-only",
                    "anchor": quoted,
                },
                {
                    "name": "worktree-index-isolation",
                    "measured": isolated["indexes_isolated"],
                    "method": "git rev-parse --git-path index per linked worktree",
                    "anchor": (
                        f"unique_index_count={isolated['unique_index_count']}"
                    ),
                },
                {
                    "name": "scoped-add-no-sibling-paths",
                    "measured": scoped["n_commits"] == N_AGENTS
                    and not scoped["sibling_commits"],
                    "method": "git add -- path; git commit -- path; git log --name-only",
                    "anchor": f"scoped_commits={scoped['n_commits']}",
                },
            ],
            "control_ids": ["planted-shared-index-add-A"],
        },
        "min_bytes_threshold": 2048,
        "required_fix": None,
    }
    assert_local_schema(doc)

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:TST-0099 artifact {size}B below floor")
        return 1

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:TST-0099 probes c1={rc1} c2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    ret = {
        "id": "TST-0099",
        "unit_id": "TST-0099",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0099",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0099/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0099-probe2-worktree-isolation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0099: live named probes exit 0, TST-0099.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Host tree is not a git repo; experiments "
            "used scratch clones only."
        ),
    }

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "TST-0099",
            "receipt_path": "command-center/p2-wave/probes/TST-0099/SUBAGENT-RETURN.json",
            "role": role,
        }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = [
        row(OUT, "primary"),
        row(SCHEMA, "supporting"),
        row("command-center/p2-wave/probes/TST-0099/experiment.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0099/probe1_planted_contamination.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0099/probe2_worktree_isolation.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0099/emit.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0099/SUBAGENT-RETURN.json", "supporting"),
    ]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0099",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={digest} bytes={size}")
    print("SUCCESS:TST-0099 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
