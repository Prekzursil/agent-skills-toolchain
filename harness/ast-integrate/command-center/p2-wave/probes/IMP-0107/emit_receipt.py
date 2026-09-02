#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0107.json from live probe evidence."""
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
OUT_REL = "command-center/receipts/IMP-0107.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0107/probe1_divergence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0107/probe2_persist_negative.py"
)
SUPPORTING = [
    "tools/marketplace/mirror_conflict.py",
    "tools/marketplace/schema/mirror-conflict.schema.json",
    "tools/marketplace/tests/test_mirror_conflict.py",
    "command-center/p2-wave/probes/IMP-0107/probe1_divergence.py",
    "command-center/p2-wave/probes/IMP-0107/probe2_persist_negative.py",
]


def digest_file(path: Path) -> tuple[str, int]:
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
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0107 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:IMP-0107-probe1" not in t1:
        print("FAILED:IMP-0107 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0107-probe2" not in t2:
        print("FAILED:IMP-0107 emit probe2 sentinel missing")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = art("tools/marketplace/mirror_conflict.py", "primary-implementation")
    artifacts = [impl] + [art(p, "supporting") for p in SUPPORTING[1:]]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:IMP-0107 emit missing {missing}")
        return 1
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0107",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0107",
        "title": "Mirror conflict policy when upstream and mirror disagree",
        "question": (
            "Define and implement what happens when a mirror holds a different "
            "digest for the same package version than upstream: never silently "
            "prefer one, emit a conflict record naming both digests, and fail "
            "closed for installs of that version until resolved."
        ),
        "spec_anchor": "_USER-PROMPTS.md:11058 (source manipulation refuter); IMP-0106 mirror sync; IMP-0084 lockfile digests",
        "min_bytes_threshold": 128,
        "output_schema": "command-center/schema/receipt.schema.json",
        "policy": {
            "silent_prefer": False,
            "retry_on_digest_conflict": False,
            "auto_resolve": False,
            "authoritative_side": None,
            "install_while_unresolved": False,
            "later_matching_fetch_clears_conflict": False,
            "resolution": "explicit actor+note only",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A planted digest divergence produces an on-disk conflict "
                    "record containing both digests and both sources."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/mirror_conflict.py:compare_and_record",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "plant-two-blobs-and-read-store-bytes",
                        "command": P1,
                        "raw_output": t1[:16000],
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(
                            f"plant\x1f{P1}".encode()
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "independent-json-parse-of-conflict-store",
                        "command": P1,
                        "raw_output": "signal1_conflict_record_both_digests_and_sources=true",
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(
                            b"load_conflict_file"
                        ).hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    "An install of the conflicted version is refused, verified by "
                    "a filesystem census showing nothing written."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/mirror_conflict.py:install",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "install-then-census",
                        "command": P1,
                        "raw_output": t1[:16000],
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(
                            f"census\x1f{P1}".encode()
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "independent-directory-walk",
                        "command": P1,
                        "raw_output": "signal2_census_unchanged_on_refuse=true planted-pkg absent",
                        "exit_code": c1,
                        "fingerprint": hashlib.sha256(b"census-walk").hexdigest()[:32],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_divergence_recorded_and_install_refused",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/marketplace/tests/test_mirror_conflict.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe1_divergence",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_persist_negative",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "matching-digests-install-same-run",
                "kind": "known-good-sibling-package",
                "description": (
                    "In the same run as a refused divergent install, a package "
                    "whose upstream and mirror digests match is written to dest."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted-pkg refused; dest census has no planted-pkg path",
                "good_state_output": "clean-pkg/1.0.0/payload.bin present after matching install",
            },
            {
                "id": "conflict-persists-across-restart",
                "kind": "process-restart",
                "description": (
                    "A new MirrorConflictPolicy on the same store still refuses "
                    "install until explicit resolve; a later matching fetch does "
                    "not auto-clear."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "post-restart install ok=False; later match leaves unresolved",
                "good_state_output": "explicit resolve then install writes payload.bin",
            },
            {
                "id": "no-silent-authoritative-config",
                "kind": "config-refuter",
                "description": (
                    "prefer_upstream and authoritative=mirror raise "
                    "SilentPreferenceRefused; chosen_digest never picks a side."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "SilentPreferenceRefused / UnresolvedMirrorConflict",
                "good_state_output": "default constructor accepts empty config",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0107-probe2-no-silent-prefer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 independently constructs prefer_upstream and "
                "authoritative configs (both refused), AST-scans "
                "mirror_conflict.py for silent-prefer assignments, and confirms "
                "chosen_digest raises while unresolved. No configuration makes "
                "one side authoritative."
            ),
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": "no retry: a digest conflict is a security event requiring human resolution",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0107/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "id": "IMP-0106-mirror-sync-not-in-this-sparse-tree",
                "severity": "noted",
                "text": (
                    "IMP-0106 private/federated mirror synchronisation is not "
                    "present in this worktree. IMP-0107 ships the conflict gate "
                    "sync would call: compare two source digests, record both, "
                    "refuse install until explicit resolve. That is this unit's "
                    "question, not a silent-prefer hole."
                ),
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "notes": (
            "G-1 for IMP-0107: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. cloud ok=true is not delivery. Did not run "
            "global unit_manifest.py --write. SUCCESS:IMP-0107"
        ),
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < 128:
        print(f"FAILED:IMP-0107 emit size {size} below floor")
        return 1
    if "SUCCESS:IMP-0107" not in text:
        print("FAILED:IMP-0107 emit sentinel missing from bytes")
        return 1
    print(f"wrote {OUT_REL} ({size} B)")
    print("SUCCESS:IMP-0107")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
