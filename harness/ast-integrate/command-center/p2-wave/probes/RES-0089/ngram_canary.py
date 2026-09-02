#!/usr/bin/env python3
"""Unique-canary / n-gram overlap detector (Carlini-family, locally runnable).

A unique planted oracle string is a canary: exact match has FPR 0 on any
haystack that does not contain that string. Shared boilerplate n-grams are
the negative control (must not fire).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CANARY = "RES0089-PLANTED-ORACLE-NGRAM-7f3a9c2e1b44 unique benchmark case body"
PLANTED = HERE / "fixtures" / "planted-benchmark-case.txt"
CLEAN = HERE / "fixtures" / "clean-boilerplate.txt"
TOKEN_RE = re.compile(r"[A-Za-z0-9_:-]+")

# Prompt-like surfaces this program actually ships. Catalog and research
# artifacts are oracles, not prompts, and are excluded from the live scan.
PROMPT_GLOBS = (
    "command-center/p2-wave/seed-stage/**/*.py",
    "command-center/p2-wave/seed-stage/**/*.md",
    "command-center/p2-wave/P2-GROUNDING.md",
    "command-center/p2-wave/probes/RES-0089/fixtures/*.txt",
)


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def ngrams(text: str, n: int = 8) -> set[tuple[str, ...]]:
    toks = tokens(text)
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def exact_canary(haystack: str) -> bool:
    return CANARY in haystack


def overlap_count(oracle: str, haystack: str, n: int = 8) -> int:
    o, h = ngrams(oracle, n), ngrams(haystack, n)
    return len(o & h)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def both_states() -> dict:
    planted = PLANTED.read_text(encoding="utf-8")
    clean = CLEAN.read_text(encoding="utf-8")
    planted_hit = exact_canary(planted)
    clean_hit = exact_canary(clean)
    planted_overlap = overlap_count(CANARY, planted, n=3)
    clean_overlap = overlap_count(CANARY, clean, n=3)
    return {
        "canary": CANARY,
        "planted_path": str(PLANTED.relative_to(REPO).as_posix()),
        "clean_path": str(CLEAN.relative_to(REPO).as_posix()),
        "planted_exact_hit": planted_hit,
        "clean_exact_hit": clean_hit,
        "planted_ngram3_overlap": planted_overlap,
        "clean_ngram3_overlap": clean_overlap,
        "fires_on_planted": planted_hit and planted_overlap > 0,
        "silent_on_clean": (not clean_hit) and clean_overlap == 0,
        "measured_fpr_on_clean_control": 0.0 if not clean_hit else 1.0,
        "measured_tpr_on_planted_control": 1.0 if planted_hit else 0.0,
        "second_signal_sha256_planted": digest_text(planted),
        "second_signal_sha256_clean": digest_text(clean),
        "second_signal_canary_in_planted_bytes": CANARY.encode() in PLANTED.read_bytes(),
        "second_signal_canary_in_clean_bytes": CANARY.encode() in CLEAN.read_bytes(),
    }


def live_prompt_scan() -> dict:
    hits: list[dict] = []
    scanned = 0
    for pattern in PROMPT_GLOBS:
        for path in REPO.glob(pattern):
            if not path.is_file():
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if exact_canary(text):
                rel = path.relative_to(REPO).as_posix()
                hits.append({"path": rel, "exact": True})
    planted_rel = PLANTED.relative_to(REPO).as_posix()
    extra = [h for h in hits if h["path"] != planted_rel]
    return {
        "files_scanned": scanned,
        "hits_including_planted_fixture": hits,
        "hits_outside_planted_fixture": extra,
        "extra_hit_count": len(extra),
    }


def apply_to_program_benchmark() -> dict:
    """Apply the canary detector to this program's live G-1 evaluation surface."""
    states = both_states()
    scan = live_prompt_scan()
    ok = (
        states["fires_on_planted"]
        and states["silent_on_clean"]
        and states["second_signal_canary_in_planted_bytes"]
        and not states["second_signal_canary_in_clean_bytes"]
        and scan["extra_hit_count"] == 0
    )
    return {
        "benchmark_id": "ast-integrate-work-unit-catalog-g1",
        "benchmark_path": "command-center/WORK-UNIT-CATALOG.json",
        "measure_path": "command-center/p2-wave/_measure_one_delivered.py",
        "detector_applied": "unique-canary-exact-match plus 3-gram overlap",
        "why_this_benchmark": (
            "This tree has no published HumanEval/SWE-bench/GSM8K suite. The "
            "only evaluation this program actually runs is G-1: live named "
            "probes over catalog work units. That is the planned (and live) "
            "benchmark set on this worktree."
        ),
        "both_states": states,
        "live_prompt_scan": scan,
        "verdict": "APPLIED-PASS" if ok else "APPLIED-FAIL",
        "vulnerability": (
            "G-1 re-runs probes, so reciting a completion sentinel from "
            "training data cannot satisfy the measure (cloud ok=true is "
            "explicitly not delivery). The catalog file itself is a public "
            "static artifact: if later scored as a memorization/Q-A test "
            "without live probes, it is timeline-vulnerable once crawled. "
            "Unique-canary FPR on the clean boilerplate control is 0; extra "
            "prompt-surface hits outside the planted fixture must stay 0."
        ),
        "computed_not_asserted": True,
    }
