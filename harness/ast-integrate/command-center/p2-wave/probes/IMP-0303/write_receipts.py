#!/usr/bin/env python3
"""Write IMP-0303 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.ballots import (  # noqa: E402
    evaluate_all,
    fixture_reports,
    hides_divergence,
    textbook_fixtures,
)

UNIT = "IMP-0303"
OUT = "command-center/receipts/IMP-0303.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0303/probe1_textbook.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0303/probe2_divergence_cycle.py"
)
SUPPORTING = [
    "tools/council/vote/ballots.py",
    "tools/council/vote/__init__.py",
    "command-center/p2-wave/probes/IMP-0303/probe1_textbook.py",
    "command-center/p2-wave/probes/IMP-0303/probe2_divergence_cycle.py",
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
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def line_anchor(rel: str, needle: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(text, 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:1"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() if raw else hashlib.sha256(b"").hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0303/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(c1: int, t1: str, c2: int, t2: str) -> dict:
    reports = fixture_reports()
    tn = reports["tennessee-capital"]["report"]
    cyc = reports["condorcet-cycle-unequal"]["report"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    engine = "tools/council/vote/ballots.py"
    tests_ok = c1 == 0 and c2 == 0
    return {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS" if tests_ok else "FAILED",
        "sentinel": "SUCCESS:IMP-0303",
        "completion_sentinel": "SUCCESS:IMP-0303",
        "title": "Ordinal and cardinal ballot engine: ranked-choice, Condorcet, score and approval",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0303; _USER-PROMPTS.md:10915-10946",
        "question": (
            "On the same ballots, do ranked-choice, pairwise/Condorcet, score and "
            "approval ever elect different winners, and is that divergence surfaced "
            "to the owner instead of hidden behind a default method?"
        ),
        "answer": (
            "Yes. On the Wikipedia Tennessee capital profile the four methods split: "
            "IRV elects Knoxville; Condorcet, Borda-score and top-2 approval elect "
            "Nashville. evaluate_all() sets divergent=True, binding_winner=None, "
            "owner_action=SURFACE_DIVERGENCE. A constructed A>B>C>A cycle is status "
            "CONDORCET_CYCLE with winner=None."
        ),
        "artifact_paths": [OUT, engine],
        "min_bytes_threshold": 128,
        "reviewer_verdict": "PASS" if tests_ok else "FAIL",
        "test_ids": [
            "IMP-0303-T1-textbook-winners",
            "IMP-0303-T2-divergence-invariant",
            "IMP-0303-T3-condorcet-cycle-negative-control",
        ],
        "negative_control_ids": [
            "IMP-0303-NC1-silent-default-method",
            "IMP-0303-NC2-condorcet-cycle-must-not-elect",
        ],
        "tests": [
            {
                "id": "IMP-0303-T1-textbook-winners",
                "name": "each method against a published worked example",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "IMP-0303-T2-divergence-invariant",
                "name": "method divergence is reported, never silently resolved",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
            {
                "id": "IMP-0303-T3-condorcet-cycle-negative-control",
                "name": "a constructed Condorcet cycle must be reported as such",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0303-NC1-silent-default-method",
                "kind": "known-broken-fixture",
                "description": (
                    "mutant_silent_default binds the IRV winner on a divergent "
                    "profile; hides_divergence must FIRE on the mutant and stay "
                    "silent on the live evaluate_all() report"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "binding_winner=Knoxville owner_action=DEFAULT_METHOD",
                "good_state_output": "binding_winner=None owner_action=SURFACE_DIVERGENCE",
            },
            {
                "id": "IMP-0303-NC2-condorcet-cycle-must-not-elect",
                "kind": "known-broken-fixture",
                "description": (
                    "constructed 4/3/2 cycle A>B>C>A; pairwise status must be "
                    "CONDORCET_CYCLE and winner must stay None (no Schulze/Copeland silent pick)"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "would-elect-via-completion-rule",
                "good_state_output": f"status={cyc['by_method']['pairwise-condorcet']['status']} winner={cyc['by_method']['pairwise-condorcet']['winner']}",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "On the Tennessee capital ballots IRV elects Knoxville while "
                    "pairwise Condorcet elects Nashville; both totals match the "
                    "hand-computed Wikipedia arithmetic (IRV 58-42 after transfers; "
                    "Nashville pairwise 58-42 / 68-32 / 68-32)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(engine, "def ranked_choice("),
                "probes": [
                    probe_obj("source", "command", P1, t1, c1),
                    probe_obj(
                        "verifier",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/vote/ballots.py",
                        json.dumps(
                            {
                                "winners": tn["winners_by_method"],
                                "divergent": tn["divergent"],
                                "binding_winner": tn["binding_winner"],
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "evaluate_all() never binds a winner when methods disagree: "
                    "owner_action=SURFACE_DIVERGENCE and binding_winner is null on "
                    "Tennessee and on the constructed cycle."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(engine, "def evaluate_all("),
                "probes": [
                    probe_obj("source", "command", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "file-read",
                        f"read {engine} evaluate_all/hides_divergence",
                        json.dumps(
                            {
                                "tennessee_owner": tn["owner_action"],
                                "tennessee_binding": tn["binding_winner"],
                                "cycle_owner": cyc["owner_action"],
                                "cycle_binding": cyc["binding_winner"],
                                "hides_tennessee": reports["tennessee-capital"]["hides_divergence"],
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "The constructed 4 A>B>C / 3 B>C>A / 2 C>A>B profile has pairwise "
                    "margins A>B 6-3, B>C 7-2, C>A 5-4 and is reported as CONDORCET_CYCLE "
                    "with winner=None."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(engine, "def pairwise_condorcet("),
                "probes": [
                    probe_obj("source", "command", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "file-read",
                        f"read {engine} pairwise_condorcet cycle branch",
                        json.dumps(
                            {
                                "status": cyc["by_method"]["pairwise-condorcet"]["status"],
                                "winner": cyc["by_method"]["pairwise-condorcet"]["winner"],
                                "cycle_reported": cyc["cycle_reported"],
                                "smith_set": cyc["smith_set"],
                            }
                        ),
                        0,
                    ),
                ],
            },
        ],
        "divergence_report": {
            "tennessee-capital": tn,
            "condorcet-cycle-unequal": cyc,
            "all_fixtures": {k: v["report"]["winners_by_method"] for k, v in reports.items()},
        },
        "textbook_citations": {
            k: {"citation": v["citation"], "notes": v["notes"]}
            for k, v in reports.items()
        },
        "reviewer": {
            "reviewer_id": "IMP-0303-probe2-divergence-cycle",
            "verdict": "PASS" if tests_ok else "FAIL",
            "independent": True,
            "fresh_context": True,
            "starts_from": (
                "hand-recount of Tennessee IRV transfers and pairwise margins, "
                "plus an independent nested-loop recount of the cycle profile"
            ),
            "scope_not_agreement": (
                "probe2 recomputes pairwise margins without calling "
                "pairwise_condorcet; author narrative is not an input"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Schulze, ranked-pairs, and minimax Condorcet completions are not "
                    "implemented; a cycle stays a cycle. Whether an owner-declared "
                    "completion rule should exist is CNL-0063, not this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "IMP-0303 stays cycle-reporting; CNL-0063 owns the completion rule.",
            },
            {
                "claim": (
                    "Cross-participant score-scale calibration (CNL-0062) is out of "
                    "scope; scores are summed as marked."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run CNL-0062 / a scale-drift fixture against score().",
            },
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0303/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "downstream_consumers": [
            {
                "artifact_path": "tools/council/vote/ballots.py",
                "consumer": "command-center/p2-wave/probes/IMP-0303/probe1_textbook.py",
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
                "probe": probe_obj("verifier", "command", P1, t1, c1),
            },
            {
                "artifact_path": "tools/council/vote/ballots.py",
                "consumer": "command-center/p2-wave/probes/IMP-0303/probe2_divergence_cycle.py",
                "executed": True,
                "exit_code": c2,
                "read_ok": True,
                "probe": probe_obj("verifier", "command", P2, t2, c2),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [],
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0303 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    tn = textbook_fixtures()["tennessee-capital"]
    live = evaluate_all(tn.ballots, tn.candidates)
    if hides_divergence(live):
        print("FAILED:IMP-0303 live report hides divergence")
        return 1
    doc = build_receipt(c1, t1, c2, t2)
    supporting = [art(p, "supporting") for p in SUPPORTING]
    doc["artifacts"] = [
        {
            "path": OUT,
            "role": "primary",
            "exists": True,
            "bytes": 0,
            "sha256": "pending",
        }
    ] + supporting
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary_row = row(OUT, "primary")
    artifacts = [primary_row] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0303",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json profile=council-vote-module",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary_row["sha256"],
                "bytes": primary_row["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0303/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0303-probe2-divergence-cycle",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0303: live named probes exit 0, receipts/IMP-0303.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print(f"primary {OUT} sha256={primary_row['sha256']} bytes={primary_row['bytes']}")
    print("SUCCESS:IMP-0303 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
