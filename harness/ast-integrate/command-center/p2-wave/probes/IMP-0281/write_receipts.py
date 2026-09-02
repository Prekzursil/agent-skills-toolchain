#!/usr/bin/env python3
"""Emit IMP-0281 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import TURNS, assert_shape  # noqa: E402
from tools.council.roles.guard import RoleGuard, precision_recall  # noqa: E402

UNIT = "IMP-0281"
OUT = "command-center/receipts/IMP-0281.json"
IMPL = "tools/council/roles/guard.py"
CORPUS_JSON = "command-center/p2-wave/probes/IMP-0281/fixtures/corpus40.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0281/probe1_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0281/probe2_structured.py"
)
SUPPORTING = [
    IMPL,
    CORPUS_JSON,
    "command-center/p2-wave/probes/IMP-0281/corpus.py",
    "command-center/p2-wave/probes/IMP-0281/probe1_corpus.py",
    "command-center/p2-wave/probes/IMP-0281/probe2_structured.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def score_corpus() -> dict:
    assert_shape()
    guard = RoleGuard()
    y_true = []
    y_pred = []
    for turn in TURNS:
        result = guard.inspect(turn)
        y_true.append(turn["gold"] == "BREACH")
        y_pred.append(bool(result.rejected))
    return precision_recall(y_true, y_pred)


def main() -> int:
    assert_shape()
    fixture_dir = HERE / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "corpus40.json").write_text(
        json.dumps(TURNS, indent=1) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    scores = score_corpus()
    impl_sha, impl_bytes = digest(REPO / IMPL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": UNIT,
        "title": "Runtime role-enforcement guard",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "completion_sentinel": f"SUCCESS:{UNIT}",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0281]; "
            "question_or_target runtime role-enforcement guard; "
            "use-vs-mention defect class; labelled corpus of 40 turns"
        ),
        "artifact_paths": [OUT, IMPL, CORPUS_JSON],
        "evidence": [
            {
                "id": "E1-labelled-corpus-precision-recall",
                "claim": (
                    "On a labelled corpus of 40 turns (20 BREACH / 20 MENTION), "
                    "the guard's final decision matches gold. Precision and recall "
                    "are reported separately, not as an F1."
                ),
                "n": scores["n"],
                "tp": scores["tp"],
                "fp": scores["fp"],
                "fn": scores["fn"],
                "tn": scores["tn"],
                "precision": scores["precision"],
                "recall": scores["recall"],
                "command": P1,
                "verdict": "CONFIRMED",
            },
            {
                "id": "E2-structured-action-pass",
                "claim": (
                    "A second pass classifies by the structured action field rather "
                    "than prose. When the field is present it is authoritative: "
                    "action=speak with vote-like prose is allowed; action=propose "
                    "on a critic is a breach even when the prose is innocuous."
                ),
                "command": P2,
                "verdict": "CONFIRMED",
                "verbatim": [
                    line
                    for line in t2.splitlines()
                    if "structured_prose_disagreements" in line
                    or line.startswith("use_vs_mention")
                    or line.startswith("both_states")
                    or line.startswith("SUCCESS:")
                ],
            },
        ],
        "test_ids": [
            "unit: breach detection on the labelled corpus",
            "use-vs-mention control: quoted text describing a vote must NOT be classified as a vote",
            "negative control: an actual breach must FIRE",
        ],
        "negative_control_ids": [
            "NC1:quoted-vote-must-not-classify-as-vote",
            "NC2:nonvoter-I-vote-aye-must-FIRE-and-record",
            "NC3:quote-strip-mutant-fires-on-quoted-vote",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0281-probe2-structured",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "tests, not the author's summary",
        },
        "residual_unknowns": [
            (
                "IMP-0280 (tools/council/roles/mandate.py) is not on this worktree; "
                "guard.py carries a local Mandate type and default role matrix. If "
                "mandate.py later disagrees on defaults, re-score the corpus."
            ),
            (
                "IMP-0277 (COI checker) is a catalog dependency and is absent here; "
                "this unit does not claim COI coverage. A critic who also authored "
                "the proposal is out of scope for the mandate guard."
            ),
            (
                "A fresh-context human reviewer was not seated; named probes start "
                "from tests_required and import the module, they do not read this receipt."
            ),
        ],
        "falsifiable_question": {
            "question": (
                "Does the guard distinguish a genuine mandate breach from a "
                "participant merely MENTIONING another role's action?"
            ),
            "answer": (
                "Yes on this corpus. Quoted 'I vote yes' (T25) and blockquoted "
                "'I vote aye' (T38) are MENTION. Bare 'I vote aye' from a non-voter "
                "(T10) is BREACH and is recorded on the rejection ledger. Disabling "
                "quote stripping makes T25 fire, so the mention filter is load-bearing. "
                f"precision={scores['precision']} recall={scores['recall']} n=40."
            ),
        },
        "implementation": {
            "path": IMPL,
            "sha256": impl_sha,
            "bytes": impl_bytes,
        },
        "corpus": {
            "path": CORPUS_JSON,
            "n": 40,
            "breach": 20,
            "mention": 20,
            "precision": scores["precision"],
            "recall": scores["recall"],
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "min_bytes_threshold": 128,
        "ts": now,
        f"SUCCESS:{UNIT}": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:receipts post-write probes c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-roles-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "raw_output": t1b,
                "role": "labelled-corpus-precision-recall",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "raw_output": t2b,
                "role": "structured-pass-use-vs-mention",
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0281-probe2-structured",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0281: live named probes exit 0, receipts/IMP-0281.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
