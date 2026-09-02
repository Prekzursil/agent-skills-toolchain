#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0023.json from live named probes.

Does not call tools/command-center/unit_manifest.py --write.
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
sys.path.insert(0, str(REPO / "tools"))

from baseline.anchoring import (  # noqa: E402
    ANCHORED_FIELD_NAMES,
    SAMPLED_FIELD_NAMES,
    schema_anchoring_gaps,
)
from baseline.capture import CLASS_INDEX, capture  # noqa: E402

UNIT = "TST-0023"
OUT = "command-center/receipts/TST-0023.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SNAP_SCHEMA = "command-center/schema/baseline-snapshot.schema.json"
TOOL = "tools/baseline/capture.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0023/probe1_every_field_declares_anchoring.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0023/probe2_recapture_same_sha.py"
)
QUESTION = (
    "Spec Phase 0 requires a snapshot of repo, branches, worktrees, live "
    "deployments, caches, plugin settings, marketplaces, hooks, skills, MCPs. "
    "Target: a typed schema plus a capture tool whose every count is anchored "
    "to the commit SHA, so the artifact is a rollback anchor rather than a "
    "timestamped sample. Which captured facts are SHA-anchored and which are "
    "only wall-clock samples?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
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
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                doc, _end = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    lf = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(lf),
        "sha256": hashlib.sha256(lf).hexdigest(),
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0023 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0023 probe JSON pass!=true")
        return 1

    schema_path = REPO / SNAP_SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    gaps = schema_anchoring_gaps(schema)
    if gaps:
        print("FAILED:TST-0023 schema anchoring gaps", gaps)
        return 1

    this_tree = capture(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_sha, schema_n = digest(schema_path)
    tool_sha, tool_n = digest(REPO / TOOL)
    receipt_schema_sha, receipt_schema_n = digest(REPO / SCHEMA)

    supporting = [
        SNAP_SCHEMA,
        SCHEMA,
        TOOL,
        "tools/baseline/anchoring.py",
        "tools/baseline/__init__.py",
        "command-center/p2-wave/probes/TST-0023/probe1_every_field_declares_anchoring.py",
        "command-center/p2-wave/probes/TST-0023/probe2_recapture_same_sha.py",
        "command-center/p2-wave/probes/TST-0023/fixtures.py",
        "command-center/p2-wave/probes/TST-0023/emit_receipt.py",
    ]
    artifacts = [art_row(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:TST-0023 missing supporting", missing)
        return 1

    sha_anchored = [
        {
            "field": row["class"] if len(row["fields"]) == 1 and row["fields"][0] == row["class"] else None,
            "class": row["class"],
            "fields": row["fields"],
            "kind": "SHA-ANCHORED",
        }
        for row in CLASS_INDEX
        if row["sha_anchored"]
    ]
    # Flatten to field names for the answer.
    sha_fields = list(ANCHORED_FIELD_NAMES)
    sampled_fields = list(SAMPLED_FIELD_NAMES)

    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "report_kind": "test-receipt",
        "sentinel": "SUCCESS:TST-0023",
        "completion_sentinel": "SUCCESS:TST-0023",
        "title": "Pinned-SHA baseline snapshot schema and capture tool",
        "question": QUESTION,
        "output_schema": SCHEMA,
        "snapshot_schema": SNAP_SCHEMA,
        "execution_substrate": "local-serialized",
        "worktree_is_git_repo": (REPO / ".git").exists(),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-test-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "implementation": {
            "snapshot_schema": {
                "path": SNAP_SCHEMA,
                "sha256": schema_sha,
                "bytes": schema_n,
                "anchoring_keyword": "x-anchoring",
                "schema_anchoring_gaps": gaps,
            },
            "test_receipt_schema": {
                "path": SCHEMA,
                "sha256": receipt_schema_sha,
                "bytes": receipt_schema_n,
            },
            "capture_tool": {
                "path": TOOL,
                "sha256": tool_sha,
                "bytes": tool_n,
                "reader": "git-ls-tree-and-cat-file",
                "working_tree_is_not_oracle_for_anchored_counts": True,
            },
        },
        "answer": {
            "sha_anchored_fields": sha_fields,
            "sampled_at_time_fields": sampled_fields,
            "class_index": CLASS_INDEX,
            "rule": (
                "A count is SHA-ANCHORED only when it is read from git cat-file / "
                "ls-tree at pinned_sha. Refs, worktrees, caches, deployments, and "
                "worktree-only files are SAMPLED-AT-TIME and carry sampled_at. "
                "kind (BASELINE vs SAMPLE) is a quiescence sample, not a SHA fact."
            ),
        },
        "this_worktree_capture": {
            "kind": this_tree.get("kind"),
            "pinned_sha": this_tree.get("pinned_sha"),
            "repo_status": this_tree.get("repo", {}).get("status"),
            "repo_not_checked_reason": this_tree.get("repo", {}).get("not_checked_reason"),
            "is_rollback_anchor": False,
            "note": (
                "This delivery worktree has no .git. Capture honestly emits SAMPLE "
                "with repo NOT-CHECKED. Rollback-anchor proofs are from isolated "
                "fixture repositories in the named probes, not from this tree."
            ),
        },
        "signals": [
            {
                "id": "signal-1-schema-field-anchoring",
                "command_or_method": P1,
                "ok": True,
                "schema_anchoring_gaps": 0,
                "sampled_objects_timestamped": len(j1.get("sampled_objects_with_timestamp") or []),
            },
            {
                "id": "signal-2-recapture-same-sha",
                "command_or_method": P2,
                "ok": True,
                "reader": j2.get("reader"),
                "same_sha_anchored_equal": j2.get("same_sha_anchored_equal"),
                "untracked_hook_does_not_move_tree_count": j2.get("tree_hooks_stable"),
                "hooks_live_before": j2.get("hooks_live_before"),
                "hooks_live_after": j2.get("hooks_live_after"),
            },
        ],
        "tests_required": {
            "test_every_field_declares_its_anchoring_kind": {
                "result": "PASS",
                "schema_anchoring_gaps": gaps,
                "probe": "probe1",
            },
            "test_recapture_at_the_same_sha_reproduces_the_anchored_fields": {
                "result": "PASS",
                "same_sha_anchored_equal": j2.get("same_sha_anchored_equal"),
                "different_sha_anchored_differs": j2.get("different_sha_anchored_differs"),
                "probe": "probe2",
            },
        },
        "evidence": [
            {
                "claim": (
                    "command-center/schema/baseline-snapshot.schema.json tags every "
                    "captured field with x-anchoring SHA-ANCHORED or SAMPLED-AT-TIME; "
                    "object-typed sampled fields require sampled_at."
                ),
                "verdict": "CONFIRMED",
                "anchor": SNAP_SCHEMA,
                "probe": "probe1",
            },
            {
                "claim": (
                    "tools/baseline/capture.py recapture at the same SHA reproduces "
                    "SHA-ANCHORED fields exactly; an untracked hook and cache file "
                    "move only SAMPLED-AT-TIME counts; a new commit changes the "
                    "anchored projection."
                ),
                "verdict": "CONFIRMED",
                "anchor": TOOL,
                "probe": "probe2",
            },
        ],
        "tests": [
            {
                "id": "test_every_field_declares_its_anchoring_kind",
                "command": P1,
                "result": "PASS" if c1 == 0 and j1.get("pass") else "FAIL",
            },
            {
                "id": "test_recapture_at_the_same_sha_reproduces_the_anchored_fields",
                "command": P2,
                "result": "PASS" if c2 == 0 and j2.get("pass") else "FAIL",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "every-field-declares-anchoring-kind",
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "recapture-same-sha-reproduces-anchored-fields",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0023-probe2-recapture-same-sha",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe2 recaptures from git ls-tree, not from the author's summary. "
                "Catalog reviewer_requirement also asks for a fresh-context human "
                "and a Windows-shell re-run; those are residual and not claimed."
            ),
        },
        "cloud_ok": False,
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "this worktree HEAD is a rollback anchor",
            "command-center/BASELINE-SNAPSHOT.json is a SHA-anchored BASELINE",
            "a human Windows-shell reviewer re-ran the probes",
        ],
        "residual_unknowns": [
            {
                "id": "delivery-worktree-has-no-git",
                "text": (
                    "The Linux delivery worktree is not a git repository. A "
                    "BASELINE rollback artifact cannot be minted from this tree. "
                    "The capture tool reports SAMPLE / NOT-CHECKED instead of inventing a SHA."
                ),
            },
            {
                "id": "human-and-windows-reviewer-residual",
                "text": (
                    "G-1 named probes are green on Linux. The catalog's two "
                    "fresh-context reviewers (cross-vendor + Windows PowerShell vs "
                    "Git Bash) have not scored this unit."
                ),
            },
        ],
        "timestamps": {"ended_at": now},
        "ts": now,
        "notes": (
            "G-1 for TST-0023: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild."
        ),
        "artifact_paths": [OUT] + supporting,
        "artifacts": artifacts,
        "sha_anchored_class_rows": sha_anchored,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:TST-0023" not in payload:
        print("FAILED:TST-0023 emit sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0023 artifact {size}B below floor")
        return 1
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:TST-0023 emit self-declared not delivering")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:TST-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
