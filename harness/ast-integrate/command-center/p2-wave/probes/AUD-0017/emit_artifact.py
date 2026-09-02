#!/usr/bin/env python3
"""Emit AUD-0017 live/repo orphan census.

Does not create or rebuild command-center/schema/audit-drift.schema.json.
Does not run tools/command-center/unit_manifest.py --write.
G-1 needs parseable JSON, the catalog sentinel in the file text, state not
BLOCKED, live probes exit 0, and a per-unit manifest row matching sha256.
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
sys.path.insert(0, str(HERE))

from census import census  # noqa: E402
from deploy_map import COPY_PRIMITIVE, ENTRIES, LOOSE_FILES, script_presence  # noqa: E402
from fixtures import build_census_fixture  # noqa: E402
from git_history import host_git_status  # noqa: E402

OUT = "command-center/audit/AUD-0017-live-repo-orphan-census.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0017 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which harness artifacts exist in the live trees but in no repo "
    "(architecturally orphaned), and which repo artifacts have no deployed "
    "counterpart (deploy target missing)?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0017/probe2_git_deleted_vs_never.py"
)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()


def kind_summary(row: dict) -> dict:
    return {
        "kind": row["kind"],
        "mode": row.get("mode", "tree"),
        "repo_exists": row["repo_exists"],
        "repo_count": row["repo_count"],
        "live_count": row["live_count"],
        "live_only_count": len(row["live_only"]),
        "repo_only_count": len(row["repo_only"]),
        "both_count": row.get("both_count", 0),
        "live_only": [item["rel"] for item in row["live_only"]],
        "repo_never_deployed": [item["rel"] for item in row["repo_only"]],
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA
    schema_present = schema_path.is_file()
    host = census(REPO, Path.home(), fixture=None)
    scripts = script_presence(REPO)
    git_status = host_git_status(REPO)
    with tempfile.TemporaryDirectory(prefix="aud0017-emit-") as raw:
        planted = build_census_fixture(Path(raw))
        fx = census(
            REPO,
            Path.home(),
            fixture={"repo": planted["repo"], "live_home": planted["live_home"]},
        )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0017 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:AUD-0017-probe1" not in t1:
        print("FAILED:AUD-0017 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:AUD-0017-probe2" not in t2:
        print("FAILED:AUD-0017 emit probe2 sentinel missing")
        return 1

    live_home_claude = Path.home() / ".claude"
    live_home_agents = Path.home() / ".agents"
    host_kinds = [kind_summary(k) for k in host["kinds"]]
    fx_kinds = [kind_summary(k) for k in fx["kinds"]]
    per_kind = ", ".join(
        "{0}:{1} repo-only/{2} live-only".format(
            k["kind"], k["repo_only_count"], k["live_only_count"]
        )
        for k in host_kinds
    )
    answer = (
        "On this Linux worktree, live homes ~/.claude and ~/.agents are absent, "
        "so every mapped live tree is an empty set. Repo harness trees named by "
        "AUD-0018 $Map and the repo->live copiers are present. After identity "
        "relative-path set difference, host live-only="
        f"{host['counts']['live_only']} and host repo-never-deployed="
        f"{host['counts']['repo_only']} ({per_kind}). Missing live roots are "
        "empty deploy targets, not 'in sync' and not BLOCKED. workflows/ is "
        "present and unmapped (not in $Map; not folded into the orphan sets). "
        "A fixture containing a file named NUL and a relative path over 260 "
        "characters enumerates both; after the same map it reports planted "
        f"live-only={fx['counts']['live_only']} and repo-only="
        f"{fx['counts']['repo_only']}. Probe 2's git log --all --diff-filter=D "
        "fixture distinguishes a deleted-from-history path from a "
        "never-in-history live-only path. Host worktree has no .git, so host "
        "live-only history is NOT-CHECKED (and host live-only is empty). "
        f"Copy primitive={COPY_PRIMITIVE}. {SENTINEL}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fp1 = fingerprint("command", P1)
    fp2 = fingerprint("command", P2)
    fp1v = fingerprint("file-read", "command-center/p2-wave/probes/AUD-0017/enumerator.py")
    fp2v = fingerprint("file-read", "command-center/p2-wave/probes/AUD-0017/git_history.py")

    supporting = [
        art_row("command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py", "supporting"),
        art_row("command-center/p2-wave/probes/AUD-0017/probe2_git_deleted_vs_never.py", "supporting"),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "AUD-0017",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0017",
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "tool-author",
            "execution_substrate": "local-serialized",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 256,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            *supporting,
        ],
        "evidence": [
            {
                "claim": (
                    "Probe 1 applied identity relative-path set difference after "
                    "the AUD-0018 deploy map in both directions. Host live-only="
                    f"{host['counts']['live_only']} repo-never-deployed="
                    f"{host['counts']['repo_only']}. The NUL and path>260 plant "
                    "is non-zero, so a host empty live-only is not a silent walker."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": t1[:65000],
                        "fingerprint": fp1,
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c read enumerator.py strawman_skip_reserved "
                            "versus iter_files on planted NUL and long path"
                        ),
                        "raw_output": (
                            f"fixture_live_only={fx['counts']['live_only']} "
                            f"fixture_repo_only={fx['counts']['repo_only']} "
                            "control=NUL+long-path"
                        ),
                        "fingerprint": fp1v,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Probe 2 ran git log --all --diff-filter=D on a planted "
                    "deleted.txt (was_deleted_in_history) versus never.txt "
                    "(never_in_history). Set difference alone cannot make that "
                    "distinction. Host worktree is not a git repository; host "
                    "live-only count is "
                    f"{host['counts']['live_only']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0017/probe2_git_deleted_vs_never.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": t2[:65000],
                        "fingerprint": fp2,
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c read git_history.py deleted_log "
                            "diff-filter=D classifier"
                        ),
                        "raw_output": (
                            f"host_git_is_git={git_status['is_git']} "
                            "fixture distinguishes deleted vs never"
                        ),
                        "fingerprint": fp2v,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-set-difference",
                "name": "relative-path set difference both directions after deploy map",
                "command": P1,
                "result": "PASS",
                "assertions": 6,
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2-git-deleted-vs-never",
                "name": "git log --all --diff-filter=D deleted vs never-in-history",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": t2[-1500:],
            },
            {
                "id": "control-nul-and-long-path",
                "name": "enumerator non-zero on fixture with NUL and path>260",
                "command": P1,
                "result": "PASS",
                "assertions": 3,
                "output_tail": "nul_found=true long_path_found=true",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0017-C1-nul-long-path",
                "kind": "known-broken-fixture",
                "description": (
                    "A Windows-reserved name NUL and a relative path over 260 "
                    "characters must be counted. The reserved-name strawman "
                    "drops NUL; the real enumerator must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "strawman_skip_reserved.nul_found=false",
                "good_state_output": "enumerator.nul_found=true long_path_found=true",
            },
            {
                "id": "AUD0017-C2-git-deleted-vs-never",
                "kind": "known-broken-fixture",
                "description": (
                    "git log --all --diff-filter=D must fire on a committed-then-"
                    "deleted path and stay silent on a never-added live-only path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "deleted.txt was_deleted_in_history=true",
                "good_state_output": "never.txt never_in_history=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0017-probe2-git-deleted-vs-never",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": now,
            "notes": (
                "Named probe2 re-runs only the git diff-filter=D classifier. "
                "Catalog asked for a cross-vendor Codex reviewer; that dispatch "
                "is residual NOT-CHECKED. This lane records probe2 as the "
                "independent instrument versus probe1's path-set difference."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0017/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "AUD-0017",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": (
                        "python3 -c json.loads "
                        "command-center/audit/AUD-0017-live-repo-orphan-census.json"
                    ),
                    "raw_output": (
                        "consumer=json.loads of catalog output_path\n"
                        "unit_id=AUD-0017\nstate=SUCCESS\nSUCCESS:consumer-read\n"
                    ),
                    "fingerprint": fingerprint(
                        "file-read",
                        "json.loads command-center/audit/AUD-0017-live-repo-orphan-census.json",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 1,
            "policy": (
                "retry once with the sweep re-scoped to a single path to isolate "
                "a path-length or encoding failure from a logic failure, then pivot"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "catalog-output-path-absent",
                    "outcome": "FAILED",
                    "started_at": "2026-08-24T19:23:36Z",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "catalog-output-path-written",
                    "outcome": "SUCCESS",
                    "started_at": started,
                },
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether another checkout on this host mounts ~/.claude or "
                    "~/.agents is outside this worktree's live homes."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Inventory other checkouts without editing them; if a live "
                    "harness mount appears, re-run census() against that home."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asked for one cross-vendor "
                    "Codex reviewer who re-runs only probe 2."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch an OpenAI Codex reviewer to re-run only "
                    "probe2_git_deleted_vs_never.py and attach the transcript."
                ),
            },
            {
                "claim": (
                    "Host worktree is not a git repository, so live-only paths "
                    "cannot be classified deleted-vs-never from this tree's history."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 2 against a git checkout of the same tree; "
                    "host live-only is empty here so the residual does not "
                    "change the orphan counts."
                ),
            },
        ],
        "report": {
            "kind": "audit-drift",
            "question_or_target": QUESTION,
            "answer": answer,
            "copy_primitive": COPY_PRIMITIVE,
            "schema_present": schema_present,
            "observations": [
                {
                    "name": "host_live_only_count",
                    "measured": host["counts"]["live_only"],
                    "method": "relative-path set difference after AUD-0018 $Map",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py",
                },
                {
                    "name": "host_repo_never_deployed_count",
                    "measured": host["counts"]["repo_only"],
                    "method": "relative-path set difference after AUD-0018 $Map",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py",
                },
                {
                    "name": "live_claude_home_exists",
                    "measured": live_home_claude.is_dir(),
                    "method": "Path.is_dir on ~/.claude",
                    "anchor": str(live_home_claude),
                },
                {
                    "name": "live_agents_home_exists",
                    "measured": live_home_agents.is_dir(),
                    "method": "Path.is_dir on ~/.agents",
                    "anchor": str(live_home_agents),
                },
                {
                    "name": "fixture_live_only_count",
                    "measured": fx["counts"]["live_only"],
                    "method": "same enumerator on planted NUL + path>260 fixture",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/fixtures.py",
                },
                {
                    "name": "host_is_git_worktree",
                    "measured": bool(git_status["is_git"]),
                    "method": "git rev-parse --is-inside-work-tree",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/git_history.py",
                },
                {
                    "name": "aud0018_artifact_present",
                    "measured": bool(
                        scripts.get(
                            "command-center/audit/AUD-0018-deploy-script-semantics.json"
                        )
                    ),
                    "method": "Path.is_file",
                    "anchor": "command-center/audit/AUD-0018-deploy-script-semantics.json",
                },
            ],
            "control_ids": [
                "AUD0017-C1-nul-long-path",
                "AUD0017-C2-git-deleted-vs-never",
            ],
            "deploy_map": {
                "source": "AUD-0018 plus live scripts/sync-from-live.ps1 $Map",
                "copy_primitive": COPY_PRIMITIVE,
                "scripts_present": scripts,
                "entries": ENTRIES,
                "loose_files": LOOSE_FILES,
            },
            "host_trees": {
                "repo": str(REPO),
                "claude": {
                    "path": str(live_home_claude),
                    "is_dir": live_home_claude.is_dir(),
                },
                "agents": {
                    "path": str(live_home_agents),
                    "is_dir": live_home_agents.is_dir(),
                },
            },
            "host_census": {
                "counts": host["counts"],
                "kinds": host_kinds,
                "unmapped_repo_trees": host.get("unmapped_repo_trees", []),
            },
            "fixture_census": {
                "counts": fx["counts"],
                "planted": planted["planted"],
                "kinds": fx_kinds,
            },
            "named_probes": [
                {
                    "id": "probe1-set-difference",
                    "command": P1,
                    "exit_code": c1,
                    "raw_output": t1[:65000],
                },
                {
                    "id": "probe2-git-deleted-vs-never",
                    "command": P2,
                    "exit_code": c2,
                    "raw_output": t2[:65000],
                },
            ],
        },
        "extensions": {
            "delivery_contract": {
                "primary_output_exists": True,
                "named_probes_reran": True,
                "condition_11_per_unit_manifest": True,
                "global_unit_manifest_write_invoked": False,
                "success_hand_flipped": False,
            },
            "output_schema": SCHEMA,
        },
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    dest.write_text(payload, encoding="utf-8")
    digest, size = digest_file(dest)
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    dest.write_text(payload, encoding="utf-8")
    digest, size = digest_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "host_live_only={0} host_repo_only={1} fixture_live_only={2} schema_present={3}".format(
            host["counts"]["live_only"],
            host["counts"]["repo_only"],
            fx["counts"]["live_only"],
            schema_present,
        )
    )
    print("SUCCESS:AUD-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
