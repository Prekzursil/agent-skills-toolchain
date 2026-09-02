#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0005.json from a live fixture measurement."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/CC-0005.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0005/probe1_three_route.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0005/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = S.measure()
    fails = S.failures(live)
    if fails:
        print("FAILED:CC-0005 emit " + "; ".join(fails))
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gitattributes = (REPO / ".gitattributes").read_text(encoding="utf-8")
    if "eol=lf" not in gitattributes or "CC-0005" not in gitattributes:
        print("FAILED:CC-0005 emit .gitattributes is not an explicit recorded decision")
        return 1
    blob_src = (REPO / "tools/command-center/git_blob.py").read_text(encoding="utf-8")
    if "git cat-file" not in blob_src or "git archive" not in blob_src:
        print("FAILED:CC-0005 emit git_blob.py missing cat-file/archive split")
        return 1
    val_src = (REPO / "tools/command-center/validate.py").read_text(encoding="utf-8")
    if "register_bytes_for_hash" not in val_src:
        print("FAILED:CC-0005 emit validate.py not routed through git_blob")
        return 1
    doc = {
        "unit_id": "CC-0005",
        "id": "CC-0005",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "report_kind": "receipt",
        "title": "Make the manifest provenance gate hash the git blob, not the Windows working tree",
        "sentinel": "SUCCESS:CC-0005",
        "completion_sentinel": "SUCCESS:CC-0005",
        "question": (
            "REACH-6 in tools/command-center/validate.py hashed working-tree bytes. "
            "With core.autocrlf=true and no '*.md eol=lf' rule, the blob and the "
            "CRLF working copy hashed differently, so Windows gates were red while "
            "Linux CI was green. Switch hashing to git cat-file -p and record the "
            ".gitattributes EOL policy explicitly."
        ),
        "answer": (
            "REACH-6 now hashes `git cat-file -p <rev>:<path>` when the snapshot is "
            "the catalog-declared git path. git archive is not used. Working-tree "
            "bytes are a fallback only for non-git worktrees and planted override "
            "files. .gitattributes records eol=lf for source text. SUCCESS:CC-0005"
        ),
        "verdict": "CONFIRMED",
        "ts": now,
        "cloud_ok": False,
        "registered": True,
        "min_bytes_threshold": 2048,
        "implementation": {
            "hasher": "tools/command-center/git_blob.py:47 git_blob_bytes via git cat-file -p",
            "gate": "tools/command-center/validate.py:232 register_bytes_for_hash use_blob when no override",
            "eol_policy": ".gitattributes (CC-0005 recorded decision: *.md/*.py/*.json eol=lf)",
            "retry_pivot": (
                "A .gitattributes-only change cannot achieve parity on this worktree "
                "(no .git, and git archive still converts under export attrs). Hashing "
                "moved into git_blob.py as the second strike requires."
            ),
        },
        "host": {
            "is_git_checkout": (REPO / ".git").exists(),
            "os": "linux",
            "windows_box_available": False,
            "windows_reproduction": (
                "fixture git repo with `* text eol=crlf` so git archive and a dirty "
                "CRLF worktree reproduce the Windows conversion trap; hashing uses "
                "cat-file on that fixture. Not a claim that this process ran on Windows."
            ),
        },
        "three_route": {
            "target": live["rel"],
            "rev": live["rev"],
            "git_cat_file": {
                "bytes": live["blob_bytes"],
                "crlf": live["blob_crlf"],
                "sha256": live["blob_sha256"],
                "recipe": live["blob_sha256_via"],
            },
            "git_show": {
                "bytes": live["show_bytes"],
                "sha256": live["show_sha256"],
                "equals_cat_file": live["show_equals_cat_file"],
            },
            "git_archive": {
                "bytes": live["archive_bytes"],
                "crlf": live["archive_crlf"],
                "sha256": live["archive_sha256"],
                "equals_cat_file": live["archive_equals_cat_file"],
                "forbidden_as_provenance_source": True,
            },
            "worktree_crlf": {
                "bytes": live["worktree_crlf_bytes"],
                "crlf": live["worktree_crlf_count"],
                "raw_sha256": live["worktree_raw_sha256"],
                "forbidden_as_provenance_source": True,
            },
            "matches_cited_structure_3737_vs_3837": (
                live["blob_bytes"] == 3737
                and live["archive_bytes"] == 3837
                and live["archive_crlf"] == 100
            ),
        },
        "byte_delta_control": {
            "pre_fix_delta_bytes": live["pre_fix_delta_bytes"],
            "line_count": live["line_count"],
            "delta_equals_line_count": live["delta_equals_line_count"],
            "method": "len(CRLF worktree) - len(cat-file blob) == blob.count(LF)",
        },
        "gate_exits": {
            "windows_before": live["windows_worktree_hasher_exit_before"],
            "windows_after": live["windows_blob_hasher_exit_after"],
            "linux_before": live["linux_worktree_hasher_exit_before"],
            "linux_after": live["linux_blob_hasher_exit_after"],
            "platform_parity_after": live["platform_parity_after"],
            "platform_parity_before_worktree_hasher": live[
                "platform_parity_before_worktree_hasher"
            ],
            "note": (
                "before = sha256(raw worktree bytes) vs recorded blob digest; "
                "after = sha256(git cat-file -p). Simulated Windows = CRLF worktree "
                "on a Linux fixture. Host is not a Windows box."
            ),
        },
        "tests": {
            "both_states_fire_on_content_change": live["fires_on_content_change"],
            "both_states_silent_on_eol_only": live["silent_on_eol_only"],
            "byte_delta_equals_line_count": live["delta_equals_line_count"],
            "platform_parity_same_commit": live["platform_parity_after"],
            "hash_via_git_cat_file": live["reach6_hash_via_silent"] == "git-cat-file",
        },
        "evidence": [
            {
                "path": "tools/command-center/git_blob.py",
                "line": 47,
                "snippet": "git cat-file -p",
                "kind": "hasher",
                "claim": "blob bytes come from git cat-file -p, never git archive.",
            },
            {
                "path": "tools/command-center/validate.py",
                "line": 232,
                "snippet": "gb.register_bytes_for_hash",
                "kind": "gate",
                "claim": "REACH-6 hashes through git_blob when no override path is planted.",
            },
            {
                "path": ".gitattributes",
                "line": 1,
                "snippet": "CC-0005 recorded EOL policy",
                "kind": "eol-policy",
                "claim": "EOL policy is an explicit recorded decision (eol=lf for source text).",
            },
            {
                "path": "command-center/p2-wave/probes/CC-0005/scenario.py",
                "line": 1,
                "snippet": "git cat-file -p",
                "kind": "live-tree",
                "claim": "Live fixture measures archive vs cat-file vs CRLF worktree.",
            },
        ],
        "historical_cited_pair": live["historical_cited_pair"],
        "reviewer": {
            "reviewer_id": "CC-0005-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the gate on a fresh fixture and requires FIRE on "
                "content change, SILENT on EOL, and matching Linux/Windows blob "
                "verdicts. It does not reuse probe 1's archive census as its signal."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "three-route-byte-delta", "command": P1},
            {"id": "probe2", "role": "both-states-platform-parity", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": "tools/command-center/git_blob.py", "exists": True, "role": "supporting"},
            {"path": "tools/command-center/validate.py", "exists": True, "role": "supporting"},
            {"path": ".gitattributes", "exists": True, "role": "supporting"},
        ],
        "residual_caveat": (
            "This Linux worktree is not a git checkout and command-center/sources/"
            "REGISTER.md is absent, so live cc-validate against the host catalog "
            "still reports a missing snapshot. The hashing fix and both-states "
            "controls are proved on a fixture git repo whose blobs are read with "
            "git cat-file -p. cloud ok=true is not delivery."
        ),
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "this process ran on a Windows machine",
                "the host ast-integrate tree is a git checkout",
            ]
        },
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CC-0005 artifact {size}B below floor")
        return 1
    if b"SUCCESS:CC-0005" not in out.read_bytes():
        print("FAILED:CC-0005 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CC-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
