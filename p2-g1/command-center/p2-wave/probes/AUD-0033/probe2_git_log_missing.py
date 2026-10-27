#!/usr/bin/env python3
"""Probe 2: git log --all on each MISSING path.

Separates never-existed (typo) from deleted (dangling reference).
Existence-alone is the known-broken mutant. Guessing NEVER-EXISTED when
git is unavailable is banned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import gitlog as G  # noqa: E402
import sweep as S  # noqa: E402

ART = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    planted = G.classify_one(C.FENCE_MISSING, C.REPO)
    mutant = G.classify_without_git(C.FENCE_MISSING)
    live = S.run_sweep(C.REPO)
    git_ctl = live["git_control"]

    art_ok = False
    art_state = None
    recorded_class = None
    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        art_ok = C.SENTINEL in text
        try:
            doc = json.loads(text)
            art_state = doc.get("state")
            recorded_class = (
                ((doc.get("git_history") or {}).get("planted_missing") or {}).get(
                    "classification"
                )
            )
        except json.JSONDecodeError:
            art_state = "UNPARSEABLE"

    guessed_without_git = (
        planted["classification"] == "NEVER-EXISTED" and not planted["git_available"]
    )
    independent = mutant["git_invoked"] is False and planted["git_invoked"] is True
    ok = (
        git_ctl["pass"]
        and independent
        and planted["git_invoked"]
        and not guessed_without_git
        and art_ok
        and str(art_state or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and (recorded_class is None or recorded_class == planted["classification"])
        and live["git_summary"]["available"] == planted["git_available"]
    )
    payload = {
        "probe": "probe2-git-log-missing",
        "unit_id": C.UNIT,
        "pass": bool(ok),
        "planted_missing": planted,
        "mutant_existence_alone": mutant,
        "git_control": {
            "pass": git_ctl["pass"],
            "fired_on_bad_state": git_ctl["fired_on_bad_state"],
            "silent_on_good_state": git_ctl["silent_on_good_state"],
        },
        "live": {
            "missing_count": live["missing_count"],
            "git_available": live["git_summary"]["available"],
            "git_counts": live["git_summary"]["counts"],
            "run_each": live["git_summary"]["run_each"],
        },
        "artifact_has_sentinel": art_ok,
        "artifact_state": art_state,
        "recorded_classification": recorded_class,
        "guessed_without_git": guessed_without_git,
        "independent_of_existence": independent,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return fail(
            f"git_invoked={planted['git_invoked']} class={planted['classification']} "
            f"mutant={mutant['classification']} guessed={guessed_without_git} "
            f"art={art_ok}/{art_state}"
        )
    print(
        "SUCCESS:AUD-0033-probe2 git log --all ran on the planted missing path; "
        f"classification={planted['classification']} (existence-alone mutant="
        f"{mutant['classification']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
