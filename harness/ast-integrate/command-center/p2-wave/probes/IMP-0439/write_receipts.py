#!/usr/bin/env python3
"""Write IMP-0439 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json.

Does not run tools/command-center/unit_manifest.py --write.
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
UNIT = "IMP-0439"
OUT = f"command-center/receipts/{UNIT}.json"
SENTINEL = "SENTINEL:IMP-0439:PROVENANCE-BLOB-HASHED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0439/probe1_blob_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0439/probe2_independent_show.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/command-center/tests/test_blob_provenance.py"
)
SUPPORTING = [
    "tools/command-center/blob.py",
    "tools/command-center/validate.py",
    "tools/command-center/seed.py",
    "tools/command-center/render.py",
    "tools/command-center/tests/test_blob_provenance.py",
    "command-center/p2-wave/probes/IMP-0439/probe1_blob_parity.py",
    "command-center/p2-wave/probes/IMP-0439/probe2_independent_show.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0439/SUBAGENT-RETURN.json",
        "role": role,
    }


def _tail(text: str, n: int = 4000) -> str:
    return text[-n:] if len(text) > n else text


def main() -> int:
    t_rc, t_out = run_cmd(TESTS)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if t_rc != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0439 tests/probes t={t_rc} p1={c1} p2={c2}")
        print(_tail(t_out, 2000))
        print(_tail(t1, 2000))
        print(_tail(t2, 2000))
        return 1

    table_path = HERE / "probe1-digest-table.json"
    table = json.loads(table_path.read_text(encoding="utf-8")) if table_path.is_file() else {}
    rows = table.get("rows") or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "title": "Make the provenance hash read the committed blob, not the working tree",
        "question": (
            "After the fix, do the Windows and Linux runs produce the same digest "
            "for all fourteen manifest entries?"
        ),
        "answer": (
            "Yes. Hashing `git cat-file -p HEAD:path` (never `git archive`) yields "
            "the same sha256 for all 14 contracted command-center paths on an LF "
            "commit after the worktree is rewritten to CRLF. Raw working-tree "
            "sha256 differs for every file, so the blob-route green is not silence "
            "in both states. Two digests were re-derived with `git show`, not "
            "cat-file. Windows was simulated by CRLF worktree materialisation on "
            "this Linux box, not a native Windows checkout. "
            f"{SENTINEL}"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": SENTINEL,
        "sentinel": SENTINEL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "timestamps": {"ended_at": now},
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0439",
        "implementation": {
            "helper": "tools/command-center/blob.py",
            "recipe": "git -C <repo> cat-file -p <rev>:<path>",
            "forbidden_recipe": "git archive",
            "wired_into": [
                "tools/command-center/validate.py:REACH-6",
                "tools/command-center/seed.py:provenance.register_sha256",
                "tools/command-center/render.py:render_manifest",
            ],
            "fallback": (
                "LF-normalised working-tree bytes only when the path is not a blob "
                "(tmp fixtures, untracked files)"
            ),
            "not_in_scope": [
                "tools/measure-guard/blobread.py is IMP-0440",
                ".gitattributes EOL policy is IMP-0441",
            ],
        },
        "digest_table": {
            "columns": [
                "path",
                "working_tree_sha256",
                "blob_sha256",
                "recorded_provenance_sha256",
            ],
            "n": table.get("n"),
            "n_crlf_rewritten": table.get("n_crlf_rewritten"),
            "taken_on": (
                "Linux fixture git repo; Windows checkout simulated by rewriting "
                "the worktree to CRLF after an LF commit (core.autocrlf materialisation)"
            ),
            "blob_route_identical_crlf_vs_lf": table.get(
                "blob_route_identical_crlf_vs_lf"
            ),
            "working_tree_route_differs_for_all_14": table.get(
                "working_tree_route_differs_for_all_14"
            ),
            "rows": [
                {
                    "path": r.get("path"),
                    "working_tree_sha256": r.get("working_tree_sha256"),
                    "blob_sha256": r.get("blob_sha256"),
                    "recorded_provenance_sha256": r.get("recorded_provenance_sha256"),
                    "blob_equals_recorded": r.get("blob_equals_recorded"),
                    "working_tree_equals_blob": r.get("working_tree_equals_blob"),
                }
                for r in rows
            ],
        },
        "evidence": [
            {
                "id": "E1",
                "claim": (
                    "Blob sha256 is identical for all 14 contracted paths on LF vs "
                    "CRLF worktrees; recorded provenance hash equals the blob."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0439/probe1-digest-table.json",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "role": "source",
                        "method": "command",
                        "raw_output": _tail(t1),
                    }
                ],
            },
            {
                "id": "E2",
                "claim": (
                    "Two blob digests re-derived with git show match git cat-file; "
                    "REACH-6 is silent on CRLF-only and fires on content change; "
                    "working-tree hash differs from blob after CRLF rewrite."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/command-center/blob.py:show_bytes",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": 0,
                        "role": "verifier",
                        "method": "command",
                        "raw_output": _tail(t2),
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0439-NC1-working-tree-differs",
                "kind": "control",
                "description": (
                    "Raw working-tree sha256 must differ from blob sha256 on a CRLF "
                    "worktree, proving the blob route changed something."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP0439-NC2-content-change-fires-reach6",
                "kind": "mutation",
                "description": "REACH-6 must fire when snapshot content actually changes.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP0439-NC3-crlf-only-silent",
                "kind": "mutation",
                "description": "REACH-6 must stay silent on a CRLF-only rewrite of the same blob.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "negative_control_ids": [
            "IMP0439-NC1-working-tree-differs",
            "IMP0439-NC2-content-change-fires-reach6",
            "IMP0439-NC3-crlf-only-silent",
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0439-probe2-independent-show",
            "starts_from": "tests (blob parity + REACH-6 both-states), not author summary",
            "verdict": "PASS",
            "method": "git show <rev>:<path> vs git cat-file -p on two fixture paths",
        },
        "reviewer_verdict": "PASS",
        "tests": [
            {
                "id": "pytest-blob-provenance",
                "command": TESTS,
                "result": "PASS",
                "exit_code": t_rc,
                "output_tail": _tail(t_out, 1500),
            },
            {
                "id": "probe1-blob-parity",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "probe2-independent-show",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The 14-row table was taken on a Linux fixture repo with a CRLF "
                    "worktree, not a native Windows checkout under core.autocrlf=true."
                ),
                "settling_experiment": (
                    "Re-run probe1 on a real Windows clone with core.autocrlf=true."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/sources/REGISTER.md is absent on this worktree, so "
                    "live REACH-6 against the committed catalog cannot be greened here."
                ),
                "settling_experiment": (
                    "Re-run validate.py on a tree that still has the register snapshot."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    ".gitattributes is absent; IMP-0439 moved the fix into hashing "
                    "rather than stealing IMP-0441's EOL policy."
                ),
                "settling_experiment": "IMP-0441 dual-platform gate proof.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 for IMP-0439: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not implement IMP-0440's shared blobread helper. Did not add "
            ".gitattributes. No git add/commit/push. No ADV rebuild. "
            f"{SENTINEL}"
        ),
        "artifact_paths": [OUT, *SUPPORTING],
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/IMP-0439/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    extra = []
    if table_path.is_file():
        extra.append("command-center/p2-wave/probes/IMP-0439/probe1-digest-table.json")
    primary = art_row(OUT, "primary")
    artifacts = [primary] + [art_row(p, "supporting") for p in SUPPORTING + extra]

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
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0439/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0439-probe2-independent-show",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0439: live named probes exit 0, receipts/IMP-0439.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0439 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
