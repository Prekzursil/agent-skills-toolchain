#!/usr/bin/env python3
"""Fixture estate, both-states writes, production discovery for TST-0087."""
from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures" / "estate"
DEPLOYED_REL = "hooks/_dispatch/manifest.json"
SCRATCH_REL = "scratch/session-notes.txt"
PREFIX_ONLY_REL = "hooks/_dispatch/local-override.json"
UNIT = "TST-0087"
SENTINEL = "SUCCESS:TST-0087"
ARTIFACT_REL = "command-center/receipts/TST-0087.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0087/probe1_deployed_fires.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0087/probe2_scratch_silent.py"
)

import guard as G  # noqa: E402


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def compact(decision: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "fired",
        "silent",
        "permit",
        "exit_code",
        "reason",
        "write_rel",
        "repo_counterpart",
        "advisory",
        "fail_open",
        "tree",
        "tool",
        "wrote",
        "write_path",
        "repo_counterpart_named_in_advisory",
    )
    return {k: decision.get(k) for k in keep}


def materialize(dest: Path) -> dict[str, Any]:
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FIX, dest)
    repo_root = dest / "repo"
    live_root = dest / "live"
    prov_path = dest / "provenance.json"
    provenance = G.load_provenance(prov_path)
    repo_file = repo_root / DEPLOYED_REL
    row = dict(provenance[DEPLOYED_REL])
    row["source_blob_sha"] = sha256_file(repo_file)
    provenance[DEPLOYED_REL] = row
    prov_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "dest": dest,
        "repo_root": repo_root,
        "live_root": live_root,
        "provenance_path": prov_path,
        "provenance": provenance,
        "fail_open": True,
        "deployed_live": live_root / DEPLOYED_REL,
        "deployed_repo": repo_file,
        "scratch_live": live_root / SCRATCH_REL,
        "prefix_only_live": live_root / PREFIX_ONLY_REL,
    }


def _write_after_guard(estate: dict[str, Any], target: Path, content: str) -> dict[str, Any]:
    event = {"tool": "Write", "path": str(target), "content": content}
    decision = G.pre_tool_use(event, estate)
    target.parent.mkdir(parents=True, exist_ok=True)
    before = target.read_bytes() if target.is_file() else b""
    target.write_text(content, encoding="utf-8", newline="\n")
    after = target.read_bytes()
    advisory = str(decision.get("advisory") or "")
    counterpart = decision.get("repo_counterpart")
    decision.update(
        {
            "wrote": True,
            "write_path": str(target),
            "before_sha256": sha256_bytes(before),
            "after_sha256": sha256_bytes(after),
            "bytes_written": len(after),
            "repo_counterpart_named_in_advisory": bool(
                counterpart and counterpart in advisory
            ),
        }
    )
    return decision


def run_deployed_fire(dest: Path) -> dict[str, Any]:
    estate = materialize(dest)
    target = estate["deployed_live"]
    decision = _write_after_guard(
        estate,
        target,
        '{"hooks":["pre-tool"],"source":"hand-edit-of-deployed-copy"}\n',
    )
    pass_ok = (
        decision.get("fired") is True
        and decision.get("silent") is False
        and decision.get("permit") is True
        and decision.get("exit_code") == 0
        and decision.get("write_rel") == DEPLOYED_REL
        and decision.get("repo_counterpart") == DEPLOYED_REL
        and decision.get("repo_counterpart_named_in_advisory") is True
        and decision.get("wrote") is True
        and target.is_file()
        and estate["deployed_repo"].is_file()
    )
    return {
        "id": "test_guard_fires_on_a_deployed_path_with_a_repo_counterpart",
        "pass": pass_ok,
        "deployed_rel": DEPLOYED_REL,
        "repo_counterpart": DEPLOYED_REL,
        "live_write_path": str(target),
        "repo_path": str(estate["deployed_repo"]),
        "decision": compact(decision),
        "advisory": decision.get("advisory"),
        "source_blob_sha": estate["provenance"][DEPLOYED_REL]["source_blob_sha"],
    }


def run_scratch_silent(dest: Path) -> dict[str, Any]:
    estate = materialize(dest)
    target = estate["scratch_live"]
    decision = _write_after_guard(
        estate, target, "scratch write; must not warn\n"
    )
    pass_ok = (
        decision.get("fired") is False
        and decision.get("silent") is True
        and decision.get("permit") is True
        and decision.get("exit_code") == 0
        and decision.get("write_rel") == SCRATCH_REL
        and decision.get("advisory") in (None, "")
        and decision.get("reason") == "live-only-no-provenance"
        and decision.get("wrote") is True
    )
    return {
        "id": "test_guard_is_silent_on_a_live_only_scratch_path",
        "pass": pass_ok,
        "scratch_rel": SCRATCH_REL,
        "live_write_path": str(target),
        "decision": compact(decision),
    }


def run_prefix_only_silent(dest: Path) -> dict[str, Any]:
    """Same live prefix as the deployed file; no provenance row → silent."""
    estate = materialize(dest)
    target = estate["prefix_only_live"]
    decision = _write_after_guard(estate, target, '{"note":"prefix-only"}\n')
    pass_ok = (
        decision.get("fired") is False
        and decision.get("silent") is True
        and decision.get("write_rel") == PREFIX_ONLY_REL
        and decision.get("reason") == "live-only-no-provenance"
    )
    return {
        "id": "prefix-not-the-trigger",
        "pass": pass_ok,
        "rel": PREFIX_ONLY_REL,
        "live_write_path": str(target),
        "decision": compact(decision),
    }


def run_provenance_removed(dest: Path) -> dict[str, Any]:
    """Negative control: drop the provenance row; the same deployed path goes silent."""
    estate = materialize(dest)
    estate["provenance"] = {}
    target = estate["deployed_live"]
    decision = _write_after_guard(
        estate, target, '{"source":"deployed-without-provenance"}\n'
    )
    pass_ok = (
        decision.get("fired") is False
        and decision.get("silent") is True
        and decision.get("write_rel") == DEPLOYED_REL
        and decision.get("reason") == "live-only-no-provenance"
    )
    return {
        "id": "negative-control-provenance-removed",
        "pass": pass_ok,
        "rel": DEPLOYED_REL,
        "live_write_path": str(target),
        "decision": compact(decision),
        "note": "the provenance record, not the path prefix, is the trigger",
    }


def run_repo_source_silent(dest: Path) -> dict[str, Any]:
    estate = materialize(dest)
    target = estate["deployed_repo"]
    decision = _write_after_guard(
        estate, target, '{"hooks":["pre-tool"],"source":"repo-edit-ok"}\n'
    )
    pass_ok = (
        decision.get("fired") is False
        and decision.get("silent") is True
        and decision.get("reason") == "repo-source-of-truth"
        and decision.get("exit_code") == 0
    )
    return {
        "id": "repo-source-silent",
        "pass": pass_ok,
        "rel": DEPLOYED_REL,
        "repo_write_path": str(target),
        "decision": compact(decision),
    }


def run_fail_open(dest: Path) -> dict[str, Any]:
    estate = materialize(dest)
    broken = deepcopy(estate)
    broken["live_root"] = object()  # type: ignore[assignment]
    decision = G.inspect_write(
        write_path=estate["deployed_live"],
        live_root=broken["live_root"],
        repo_root=estate["repo_root"],
        provenance=estate["provenance"],
        fail_open=True,
    )
    pass_ok = (
        decision.get("fail_open") is True
        and decision.get("permit") is True
        and decision.get("exit_code") == 0
        and decision.get("fired") is False
    )
    return {
        "id": "fail-open-internal-error",
        "pass": pass_ok,
        "decision": compact(decision),
        "error": decision.get("error"),
    }


def discover_production() -> dict[str, Any]:
    rels = [
        "rules/common/harness-vcs-hygiene.md",
        "tools/plugin/deployed_copy_guard.py",
        "tools/plugin/hooks/deployed_copy.py",
        "hooks/_dispatch/manifest.json",
        "agent-self/hooks/_dispatch/manifest.json",
        "scripts/sync-hooks.ps1",
        "scripts/sync-skills.ps1",
        "scripts/sync-rules.ps1",
        "skills/DEPLOYED-MANIFEST.json",
    ]
    candidates = []
    for rel in rels:
        p = REPO / rel
        candidates.append(
            {
                "path": rel,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    home_live = Path.home() / ".claude"
    home = {
        "path": str(home_live),
        "exists": home_live.is_dir(),
        "hooks_dir": str(home_live / "hooks"),
        "hooks_exists": (home_live / "hooks").is_dir(),
    }
    needle = "deployed copy"
    grep_hits = []
    for root_rel in ("tools/plugin", "hooks", "agent-self"):
        root = REPO / root_rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".md", ".json", ".ps1", ".sh"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle in text.lower() or "harness-vcs-hygiene" in text:
                try:
                    rel = path.resolve().relative_to(REPO.resolve()).as_posix()
                except ValueError:
                    rel = str(path)
                grep_hits.append(rel)
                if len(grep_hits) >= 12:
                    break
        if len(grep_hits) >= 12:
            break
    any_guard = any(
        c["exists"]
        for c in candidates
        if "deployed_copy" in c["path"] or c["path"].endswith("harness-vcs-hygiene.md")
    )
    return {
        "any_production_guard": any_guard,
        "candidates": candidates,
        "home_claude": home,
        "grep_hits": grep_hits,
        "note": (
            "IMP-0037 production PreToolUse hook is the subject; this TST unit "
            "does not ship that hook. The instrument under test is "
            "command-center/p2-wave/probes/TST-0087/guard.py."
        ),
    }


def measure(dest: Path) -> dict[str, Any]:
    fire = run_deployed_fire(dest / "fire")
    scratch = run_scratch_silent(dest / "scratch")
    prefix = run_prefix_only_silent(dest / "prefix")
    removed = run_provenance_removed(dest / "removed")
    repo_ok = run_repo_source_silent(dest / "repo")
    fail_open = run_fail_open(dest / "failopen")
    production = discover_production()
    instrument_ok = all(
        row["pass"]
        for row in (fire, scratch, prefix, removed, repo_ok, fail_open)
    )
    return {
        "fire": fire,
        "scratch": scratch,
        "prefix_only": prefix,
        "provenance_removed": removed,
        "repo_source": repo_ok,
        "fail_open": fail_open,
        "production": production,
        "instrument_ok": instrument_ok,
        "both_states_ok": bool(fire["pass"] and scratch["pass"]),
    }
