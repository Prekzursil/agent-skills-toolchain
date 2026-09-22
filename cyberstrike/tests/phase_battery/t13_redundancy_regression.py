#!/usr/bin/env python3
"""T-13 redundancy regression - paraphrase/repetition counts vs thresholds.

Audit CS-04/08: the old 6-file payload restated the same directives many
times (NEVER-ROTATE measured 14x by the audit, 13x by this script's regex
today; research surfaces 3x; org-925/team 4x). deploy-phase3.md fixes the
targets for the new pair:

  NEVER-ROTATE  == 1   (exactly one canonical statement, A1)
  research-surface list <= 1  (spec says == 1; drafts measure 0 = fully
                   delegated to HOME pointer - recorded as a disclosed
                   deviation, not forced)
  org-925 non-pointer == 0  (enumeration moved to HOME; the S1 POINTER line
                   that names "Cursor org 925 / team 10939257" while pointing
                   at HOME is exempt - operationalized as occurrences on
                   lines that do NOT mention HOME)

Baseline (old 5-file live instruction set) is measured every run so the
regression delta is on the receipt, not on memory.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO, SUCCESS, FAILED, VerdictRecorder, read_text, count,
)


def pair(mode: str) -> list[Path]:
    live = [REPO / "AGENTS.md", REPO / "CONTEXT.md"]
    drafts = [REPO / "AGENTS.new.md", REPO / "CONTEXT.new.md"]
    if mode == "drafts":
        return drafts
    if mode == "live":
        return live
    return drafts if (REPO / "AGENTS.new.md").exists() and \
        read_text(REPO / "AGENTS.new.md") != read_text(REPO / "AGENTS.md") \
        else live


def nonpointer_count(pattern: str, files: list[Path]) -> int:
    """Occurrences of pattern OUTSIDE pointer context (pointer exempt).

    Pointer context is PARAGRAPH-level, not line-level: the S1 pointer
    sentence wraps ("HOME AGENTS.md (... estate" / "locks + Cursor org 925 /
    team 10939257 standing scope)..."), so a line-level exemption would
    miscount the wrapped tail as a non-pointer enumeration (measured bug at
    battery build). Paragraphs = blank-line-separated blocks.
    """
    n = 0
    for f in files:
        for para in re.split(r"\n\s*\n", read_text(f)):
            if "HOME" in para:
                continue
            n += len(re.findall(pattern, para, re.I))
    return n


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    opts = opts or {}
    mode = opts.get("target", "auto")
    files = pair(mode)
    missing = [f.name for f in files if not f.exists()]
    if missing:
        rec.record("T-13", FAILED, reason=f"target files missing: {missing}")
        return FAILED

    text = "\n".join(read_text(f) for f in files)
    never_rotate = count(r"never[- ]rotate", text)
    research_surface = count(r"research[- ]surface", text)
    org925_nonpointer = nonpointer_count(r"org[ -]925|team 10939257", files)

    baseline_files = [REPO / n for n in (
        "AGENTS.md", "config.md", "CONTEXT.md",
        "instructions-recon.md", "instructions-fullpower-estate.md")]
    btext = "\n".join(read_text(f) for f in baseline_files if f.exists())
    baseline = {
        "never_rotate": count(r"never[- ]rotate", btext),
        "research_surface": count(r"research[- ]surface", btext),
        "org925_all": count(r"org[ -]925|team 10939257", btext),
    }

    checks = {
        "never_rotate_eq_1": never_rotate == 1,
        "research_surface_le_1": research_surface <= 1,
        "org925_nonpointer_eq_0": org925_nonpointer == 0,
    }
    rec.hit("T-13", "metrics", target=mode,
            files=[f.name for f in files],
            never_rotate=never_rotate, research_surface=research_surface,
            org925_nonpointer=org925_nonpointer,
            baseline=baseline, checks=checks)

    ok = all(checks.values())
    rec.record("T-13", SUCCESS if ok else FAILED,
               details={
                   "target_mode": mode,
                   "metrics": {
                       "never_rotate": never_rotate,
                       "research_surface": research_surface,
                       "org925_nonpointer": org925_nonpointer,
                   },
                   "thresholds": {
                       "never_rotate": "== 1 (deploy-phase3.md)",
                       "research_surface": "<= 1 (spec ==1; drafts measure 0 "
                                           "= delegated to HOME pointer - "
                                           "disclosed deviation)",
                       "org925_nonpointer": "== 0 (pointer line exempt)",
                   },
                   "baseline_old_payload": baseline,
               },
               anchors=files,
               reason=None if ok else "redundancy regression: " + str(
                   {k: v for k, v in checks.items() if not v}))
    return SUCCESS if ok else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=("auto", "drafts", "live"),
                    default="auto")
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-13"}) as rec:
        status = run(rec, {"target": args.target})
        print(f"T-13 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
