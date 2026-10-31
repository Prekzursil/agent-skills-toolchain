#!/usr/bin/env python3
"""Probe 2: fatigue before/after + overclaim + two reviewers + anchors.

Dropping defect_locus from a REFUTED row must make the overclaim checker fail.
Fatigue rates re-derived from the session census must match the artifact.
Live transcripts must still exist (real sessions, not a slogan).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import fatigue as F  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/phase3/A8/SECURITY.json"
DOSSIER_PREFIXES = (
    "command-center/phase3/A1/",
    "command-center/phase3/A2/",
    "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A1/",
    "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A2/",
)


def _close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= max(tol, 1e-6 * max(1.0, abs(float(a))))


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0055-probe2 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0055-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0055-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0055-probe2 mutant without defect_locus was accepted")
        return 1

    census = F.load_census(REPO)
    summary = F.summarize(census["rows"])
    art_fat = doc.get("fatigue") or {}
    for key in (
        "session_count",
        "tool_use",
        "owner_prompts",
        "explicit_tools",
        "before_actual_pph_wall",
        "after_proposed_pph_wall",
        "before_naive_every_tool_pph_wall",
    ):
        if not _close(art_fat.get(key), summary.get(key)):
            print(f"FAILED:ARC-0055-probe2 fatigue {key} artifact={art_fat.get(key)} live={summary.get(key)}")
            return 1
    if int(summary["session_count"]) < 1:
        print("FAILED:ARC-0055-probe2 no real session in census")
        return 1
    if int(summary["owner_prompts"]) != 0:
        print("FAILED:ARC-0055-probe2 unexpected owner prompts in snapshot")
        return 1
    # Keep both duration signals: if they disagree, both must still be present.
    if art_fat.get("both_signals_kept") is not True:
        print("FAILED:ARC-0055-probe2 dropped a duration signal")
        return 1
    naive_w = float(summary["before_naive_every_tool_pph_wall"] or 0)
    after_w = float(summary["after_proposed_pph_wall"] or 0)
    if not (naive_w > after_w):
        print(f"FAILED:ARC-0055-probe2 after rate not below naive {after_w} vs {naive_w}")
        return 1

    live_rows = F.scan_transcripts(F.DEFAULT_TRANSCRIPTS)
    print(f"live_sessions={len(live_rows)} snapshot_sessions={summary['session_count']}")
    if F.DEFAULT_TRANSCRIPTS.is_dir() and len(live_rows) < 1:
        print("FAILED:ARC-0055-probe2 transcripts dir present but empty")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0055-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            rel_n = rel.replace("\\", "/")
            if not any(rel_n.startswith(p) for p in DOSSIER_PREFIXES):
                print(f"FAILED:ARC-0055-probe2 dossier kind but path {rel}")
                return 1
            dossier += 1
        elif kind == "live-tree":
            live += 1
        else:
            print(f"FAILED:ARC-0055-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 3 or live < 1:
        print(f"FAILED:ARC-0055-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0055-probe2 reviewer is not independent scope-only")
        return 1
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-ZERO-PROMPT-FAIL-OPEN":
        print("FAILED:ARC-0055-probe2 reviewer did not add FM-ZERO-PROMPT-FAIL-OPEN")
        return 1
    second = rev.get("second_reviewer") or {}
    if second.get("codex_session") != "NOT-RUN":
        print("FAILED:ARC-0055-probe2 fabricated Codex session")
        return 1
    if second.get("recount_ok") is not True:
        print("FAILED:ARC-0055-probe2 second reviewer recount failed")
        return 1
    if second.get("independent") is not True:
        print("FAILED:ARC-0055-probe2 second reviewer not independent")
        return 1
    ad = doc.get("a8_design") or {}
    if ad.get("present") is True and ad.get("owned_by_dependency") is not True:
        print("FAILED:ARC-0055-probe2 A8 DESIGN present without ARC-0052 ownership")
        return 1
    if "SUCCESS:ARC-0055" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0055-probe2 sentinel absent")
        return 1
    print(
        f"fatigue actual_pph_wall={summary['before_actual_pph_wall']} "
        f"naive_pph_wall={summary['before_naive_every_tool_pph_wall']} "
        f"after_pph_wall={summary['after_proposed_pph_wall']}"
    )
    print("SUCCESS:ARC-0055-probe2 fatigue overclaim reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
