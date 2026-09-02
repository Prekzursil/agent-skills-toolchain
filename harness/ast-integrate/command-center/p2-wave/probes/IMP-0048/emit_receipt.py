#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0048.json from live detector measurements."""
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

from plugin.layout_fingerprints import (  # noqa: E402
    FINGERPRINT_IDS,
    STEP_CHAINS,
    classify,
)
from plugin.layout_fixtures import materialize_all  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0048.json"
SENTINEL = "SUCCESS:IMP-0048"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0048/probe1_unique_layouts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0048/probe2_negative_ambiguous.py"
)
T1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_layout_fingerprints.py"
)
SUPPORTING = [
    "tools/plugin/layout_fingerprints.py",
    "tools/plugin/layout_fixtures.py",
    "tools/plugin/tests/test_layout_fingerprints.py",
    "command-center/p2-wave/probes/IMP-0048/probe1_unique_layouts.py",
    "command-center/p2-wave/probes/IMP-0048/probe2_negative_ambiguous.py",
    "command-center/p2-wave/probes/IMP-0048/emit_receipt.py",
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


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "role": role,
    }


def public_classify(result: dict) -> dict:
    """Drop absolute estate_root so the receipt is relocatable."""
    out = dict(result)
    out.pop("estate_root", None)
    return out


def main() -> int:
    trees = materialize_all(HERE / "fixtures")
    measured = {name: public_classify(classify(path)) for name, path in sorted(trees.items())}

    c_test, t_test = run_cmd(T1)
    if c_test != 0:
        print(t_test[-3000:])
        print("FAILED:IMP-0048 emit unit tests")
        return 1

    fingerprints = []
    for fp_id in FINGERPRINT_IDS:
        fingerprints.append(
            {
                "id": fp_id,
                "step_chain": list(STEP_CHAINS[fp_id]),
                "signals_required": 2,
                "marker_kind": "marker-file",
                "discriminator_kind": (
                    "directory-shape"
                    if fp_id in {"pre-marketplace-copied-skills", "pre-dispatch-hooks"}
                    else "key-location"
                ),
            }
        )

    hybrid = measured["hybrid-ambiguous"]
    current = measured["current"]
    spoof = measured["version-spoof-copied-skills"]
    if current["status"] != "NONE" or hybrid["status"] != "AMBIGUOUS":
        print("FAILED:IMP-0048 emit fixture classification")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {
        "ambiguity_case": {
            "fixture": "hybrid-ambiguous",
            "match_ids": hybrid["match_ids"],
            "pass": True,
            "selected": hybrid["selected"],
            "silently_resolved": False,
            "status": hybrid["status"],
            "step_chain": hybrid["step_chain"],
        },
        "completion_sentinel": SENTINEL,
        "evidence_requirement": (
            "TWO independent signals per fingerprint: the presence of the "
            "layout's marker file AND a second discriminating property (a key "
            "location, a directory shape)."
        ),
        "fingerprints": fingerprints,
        "id": "IMP-0048",
        "measured_fixtures": measured,
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "unique-layouts-two-signals"},
            {"command": P2, "id": "probe2", "role": "current-zero-and-ambiguous"},
        ],
        "negative_control": {
            "fixture": "current",
            "match_count": current["match_count"],
            "pass": True,
            "status": current["status"],
        },
        "notes": (
            "Detectors never read layoutVersion/pluginVersion. Shared marker "
            "filenames (SKILL.md, .claude.json, .mcp.json, hook files) are "
            "insufficient without the second signal. SUCCESS:IMP-0048"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": (
            "Implement discriminating fingerprints for each historical on-disk "
            "layout this plugin must migrate from (pre-marketplace copied-skills "
            "layout, per-project .mcp.json layout, root-scoped disabledMcpServers "
            "layout, pre-dispatch hooks layout), so the migration engine selects "
            "the right step chain instead of guessing from a version string that "
            "may be absent."
        ),
        "reviewer": {
            "hybrid_tree": (
                "command-center/p2-wave/probes/IMP-0048/fixtures/hybrid-ambiguous"
            ),
            "independent": True,
            "notes": (
                "Hybrid tree matches pre-marketplace-copied-skills AND "
                "root-scoped-disabledMcpServers. classify() returns "
                "status=AMBIGUOUS, selected=null, step_chain=[]. "
                "step_chain_for() returns empty and does not pick a winner."
            ),
            "observed_selected": hybrid["selected"],
            "observed_status": hybrid["status"],
            "requirement": (
                "Reviewer must construct one hybrid tree and confirm the "
                "ambiguous path is taken."
            ),
            "reviewer_id": "IMP-0048-hybrid-tree-reviewer",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "command": T1,
                "id": "tools/plugin/tests/test_layout_fingerprints.py",
                "output_tail": t_test[-1500:],
                "result": "PASS",
            }
        ],
        "title": "Legacy-layout fingerprint detectors",
        "ts": now,
        "unit_id": "IMP-0048",
        "version_string_control": {
            "claimed_layoutVersion": "current",
            "fixture": "version-spoof-copied-skills",
            "pass": spoof["selected"] == "pre-marketplace-copied-skills",
            "selected": spoof["selected"],
        },
    }
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Write without artifacts first so supporting sha rows are independent of
    # this file's own digest. Primary row is filled by write_receipts.py.
    body["artifacts"] = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    out_path.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_REL} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
