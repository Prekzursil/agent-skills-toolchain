#!/usr/bin/env python3
"""Emit the WFA-0132 foundry artifact from a live runner self-check."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "tools" / "foundry" / "tournament.py").is_file():
            return p
    raise SystemExit("FAILED:WFA-0132 emit: repo root not found")


REPO = find_repo(HERE)
sys.path.insert(0, str(REPO))

from tools.foundry.tournament import build_demo_report  # noqa: E402

OUT_REL = (
    "command-center/foundry/"
    "WFA-0132-pairwise-workflow-tournament-runner-with-a-statistic.json"
)
ENGINE_REL = "tools/foundry/tournament.py"
SENTINEL = "SUCCESS:WFA-0132"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:WFA-0132 emit snippet missing in {rel}: {snippet!r}")


def ev(rel: str, snippet: str, claim: str, command: str | None = None) -> dict:
    row = {
        "path": rel,
        "line": find_line(rel, snippet),
        "snippet": snippet,
        "claim": claim,
    }
    if command:
        row["command"] = command
    return row


def main() -> int:
    report = build_demo_report()
    if not report.get("self_check_ok"):
        print("FAILED:WFA-0132 emit self_check_ok is false")
        print(json.dumps(report.get("plants"), indent=2, default=str)[:4000])
        return 1
    tour = report["tournament"]
    sample = report["sample_size"]
    engine_sha, engine_bytes = sha256_file(REPO / ENGINE_REL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0132/probe1_planted_superior.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0132/probe2_identical_and_cycle.py"
    )
    artifact = {
        "artifact_kind": "tournament-engine",
        "id": "WFA-0132",
        "unit_id": "WFA-0132",
        "title": "Pairwise workflow tournament runner with a statistical stopping rule",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": (
            "command-center/schema/foundry-artifact.schema.json#/$defs/tournament-engine"
        ),
        "schema_note": (
            "foundry-artifact.schema.json is not on this worktree; this document "
            "is the tournament-engine payload the catalog names."
        ),
        "ts": now,
        "question": (
            "How many matched runs per pair are required before the ACCEPT/REJECT "
            "call is stable, and which pairs remain UNDECIDED at that budget?"
        ),
        "answer": sample["answer"],
        "mechanism": (
            "Truncated two-sided SPRT on decisive paired wins, plus Condorcet "
            "cycle enumeration. UNDECIDED pairs and cycles are first-class; a "
            "total ranking is omitted when a cycle exists."
        ),
        "sequential_stopping_rule": report["registry"]["sprt"],
        "declared_sample_size": sample,
        "undecided_pairs": tour["undecided_pairs"],
        "condorcet_cycles": tour["condorcet_cycles"],
        "ranking_allowed": tour["ranking_allowed"],
        "ranking_note": tour["ranking_note"],
        "fusion_accept": tour["fusion_accept"],
        "schedule": {
            "n_pairs": tour["n_pairs"],
            "n_cases": tour["n_cases"],
            "pairs": tour["pairs"],
        },
        "plants": report["plants"],
        "self_check_ok": True,
        "upstream": report["upstream"],
        "honesty": {
            "wfa_0129_corpus": "ABSENT-on-this-worktree; fixture field used",
            "wfa_0130_registry": "ABSENT-on-this-worktree; hash-pinned stand-in used",
            "live_workflow_execution": False,
            "scope": (
                "Runner + stopping rule + cycle/UNDECIDED contract on a fixture "
                "field. Not a claim that thirty merge_units were scored."
            ),
        },
        "engine": {
            "path": ENGINE_REL,
            "sha256": engine_sha,
            "bytes": engine_bytes,
        },
        "evidence": [
            ev(
                ENGINE_REL,
                "def sequential_sprt_decision(",
                "Sequential ACCEPT/REJECT/UNDECIDED is computed here, not asserted.",
            ),
            ev(
                ENGINE_REL,
                "def condorcet_cycles(",
                "Intransitive cycles are enumerated from sequential winners.",
            ),
            ev(
                ENGINE_REL,
                "def sequential_sprt_decision(",
                "probe1 replays planted superiority, swapped labels, and pin refuse",
                command=p1,
            ),
            ev(
                ENGINE_REL,
                "def condorcet_cycles(",
                "probe2 replays identical-UNDECIDED and the planted cycle",
                command=p2,
            ),
        ],
        "notes": (
            "G-1 for WFA-0132: live named probes, foundry artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:WFA-0132"
        ),
    }
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, nbytes = sha256_file(out_path)
    print(f"wrote {OUT_REL} bytes={nbytes} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
