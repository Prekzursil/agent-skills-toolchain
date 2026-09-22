#!/usr/bin/env python3
"""CC-0021 independent reviewer alternate-regex re-measure (stdlib re only).

Mechanically DIFFERENT from implementer BARE_M_RE lookbehind/lookahead:
  implementer: (?<![A-Za-z0-9_-])M-(\\d{1,3})(?![0-9A-Za-z])
  alternate:   finditer on M-(\\d{1,3}) then Python char-class neighbor filter

Does NOT import option_id_namespace.BARE_M_RE. Does NOT touch the receipt.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

# Alternate bare-M: candidate finder ONLY (no lookbehind/lookahead).
# Boundary filtering is done in Python after each match.
ALT_BARE_CANDIDATE_RE = re.compile(r"M-(\d{1,3})")
# Documented alternate_regex string (candidate + explicit neighbor filter).
ALTERNATE_REGEX = (
    r"M-(\d{1,3})"
    r" + explicit left not in [A-Za-z0-9_-]"
    r" + explicit right not in [0-9A-Za-z]"
)
LEFT_FORBIDDEN = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
RIGHT_FORBIDDEN = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")

# MECH / family constructions also independent (not copied from implementer module).
ALT_MECH_RE = re.compile(r"MECH-([0-9]{1,3})")
ALT_FAMILY_CARD_RE = re.compile(r"^####[ \t]+`(M-[0-9]{1,3})`", re.MULTILINE)

POST = REPO / "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix"
PRE = REPO / "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix"
DR_TREES = (
    REPO / ".agents/skills/deep-research",
    REPO / "skills/deep-research",
)
PLANTED = REPO / "command-center/p2-wave/probes/CC-0021/fixtures/planted-bare-m16.md"
MENTION = (
    REPO / "command-center/p2-wave/probes/CC-0021/fixtures/mention-collision-quote.md"
)

MENTION_PATH_MARKERS = (
    "OPTION-ID-RESOLUTION",
    "option_id_collision",
    "mention-collision-quote",
    "CNF-0015",
    "ADV-0007",
    "17-DECISION-LOG",
    "command-center/receipts/",
    "_fb02_",
    "_optid_",
)
MENTION_PROSE_MARKERS = (
    "quoting the collision",
    "use-vs-mention",
    "option-id collision",
    "option id collision",
    "namespace collision",
    "three-ways ambiguous",
    "three-way ambiguous",
    "re-prefixed to MECH",
)


def strip_mech(text: str) -> str:
    return ALT_MECH_RE.sub("", text)


def is_bare_boundary_ok(text: str, start: int, end: int) -> bool:
    """Two-pass neighbor filter (replaces lookbehind/lookahead)."""
    if start > 0 and text[start - 1] in LEFT_FORBIDDEN:
        return False
    if end < len(text) and text[end] in RIGHT_FORBIDDEN:
        return False
    return True


def find_bare_m_nums(text: str) -> list[str]:
    """Find bare M-NN digit groups via candidate re + explicit boundaries."""
    scrubbed = strip_mech(text)
    out: list[str] = []
    for m in ALT_BARE_CANDIDATE_RE.finditer(scrubbed):
        if is_bare_boundary_ok(scrubbed, m.start(), m.end()):
            out.append(m.group(1))
    return out


def extract_bare_m_ids(text: str) -> set[str]:
    return {f"M-{n}" for n in find_bare_m_nums(text)}


def extract_family_m(doc07: str) -> set[str]:
    return set(ALT_FAMILY_CARD_RE.findall(doc07))


def extract_mech_ids(doc13: str) -> set[str]:
    return {f"MECH-{n}" for n in ALT_MECH_RE.findall(doc13)}


def deep_research_m16_census() -> tuple[int, int, list[str]]:
    refs = 0
    files: list[str] = []
    for tree in DR_TREES:
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            if not path.is_file():
                continue
            if "tests" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".py", ".txt", ".rst"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            file_refs = 0
            for line in text.splitlines():
                for n in find_bare_m_nums(line):
                    if n == "16":
                        file_refs += 1
            if file_refs:
                refs += file_refs
                rel = str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
                files.append(rel)
    return refs, len(files), files


def is_mention_path(rel: str) -> bool:
    return any(m in rel for m in MENTION_PATH_MARKERS)


def is_mention_text(text: str) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in MENTION_PROSE_MARKERS)


def resolve_bare(
    rel: str,
    token: str,
    text: str,
    fam: set[str],
    mech: set[str],
) -> str:
    if "/deep-research/" in f"/{rel}/" or rel.startswith(
        (".agents/skills/deep-research", "skills/deep-research")
    ):
        return "deep-research-RH" if token == "M-16" else "unresolved-ambiguous"
    if is_mention_path(rel) or is_mention_text(text):
        return "mention"
    if "07-OPTION-UNIVERSE" in rel:
        return "option-universe-M" if token in fam else "unresolved-ambiguous"
    if "13-ARCHITECTURE-CANDIDATES" in rel:
        return "unresolved-ambiguous"
    num = token.split("-", 1)[1]
    in_option = token in fam
    in_mech = f"MECH-{num}" in mech
    in_rh = token == "M-16"
    homes = sum([in_option, in_mech, in_rh])
    if homes >= 2:
        return "unresolved-ambiguous"
    if homes == 1:
        if in_option:
            return "option-universe-M"
        if in_mech:
            return "architecture-mech"
        return "deep-research-RH"
    return "unresolved-ambiguous"


def evaluate_path(path: Path, fam: set[str], mech: set[str]) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    unresolved = 0
    mentions = 0
    for line in text.splitlines():
        for n in find_bare_m_nums(line):
            token = f"M-{n}"
            verdict = resolve_bare(rel, token, text, fam, mech)
            if verdict == "mention":
                mentions += 1
            elif verdict == "unresolved-ambiguous":
                unresolved += 1
    return {
        "unresolved_count": unresolved,
        "mention_count": mentions,
        "gate_fire": unresolved > 0,
    }


def main() -> int:
    doc07 = (POST / "07-OPTION-UNIVERSE.md").read_text(encoding="utf-8")
    doc13 = (POST / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")

    fam = extract_family_m(doc07)
    mech = extract_mech_ids(doc13)
    hist_from_mech = {f"M-{n}" for n in ALT_MECH_RE.findall(doc13)}
    shared = fam & hist_from_mech
    doc13_only = hist_from_mech - fam
    univ_only = fam - hist_from_mech
    live_shared = fam & extract_bare_m_ids(doc13)

    dr_refs, dr_files, dr_file_list = deep_research_m16_census()

    arithmetic = (
        f"{len(fam)}/{len(hist_from_mech)}/{len(shared)}/"
        f"{len(doc13_only)}/{len(univ_only)}"
    )

    # Controls
    known_present = dr_refs == 20 and dr_files == 16

    mech_sample = "See MECH-16 and MECH-01; also MECH-38 for provenance."
    mech_not_bare = extract_bare_m_ids(mech_sample) == set()
    doc13_bare_empty = extract_bare_m_ids(doc13) == set()
    mech_nn_ok = mech_not_bare and doc13_bare_empty

    planted_eval = evaluate_path(PLANTED, fam, mech)
    planted_ok = planted_eval["gate_fire"] is True

    mention_eval = evaluate_path(MENTION, fam, mech)
    mention_ok = (
        mention_eval["unresolved_count"] == 0 and mention_eval["mention_count"] >= 1
    )

    expected_arith = "33/38/31/7/2"
    counts_agree = (
        arithmetic == expected_arith
        and live_shared == set()
        and dr_refs == 20
        and dr_files == 16
        and known_present
        and mech_nn_ok
        and planted_ok
        and mention_ok
    )

    payload = {
        "alternate_regex": ALTERNATE_REGEX,
        "alternate_candidate_pattern": ALT_BARE_CANDIDATE_RE.pattern,
        "construction": (
            "two-pass: re.finditer(M-(\\d{1,3})) then Python left/right "
            "char-class boundary filter; no lookbehind/lookahead"
        ),
        "implementer_regex": r"(?<![A-Za-z0-9_-])M-(\d{1,3})(?![0-9A-Za-z])",
        "arithmetic": arithmetic,
        "family_m_count": len(fam),
        "doc13_mech_count": len(hist_from_mech),
        "colliding_count": len(shared),
        "doc13_only_count": len(doc13_only),
        "universe_only_count": len(univ_only),
        "live_shared_bare_count": len(live_shared),
        "deep_research_m16_refs": dr_refs,
        "deep_research_m16_files": dr_files,
        "deep_research_files": dr_file_list,
        "counts_agree": counts_agree,
        "controls": {
            "known_present_20_16": "PASS" if known_present else "FAIL",
            "mech_nn_not_bare": "PASS" if mech_nn_ok else "FAIL",
            "planted_bare_fires": "PASS" if planted_ok else "FAIL",
            "use_vs_mention_not_unresolved": "PASS" if mention_ok else "FAIL",
        },
        "planted_eval": planted_eval,
        "mention_eval": mention_eval,
        "receipt_untouched": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"ALT_REGEX={ALTERNATE_REGEX!r} ARITH={arithmetic} "
        f"DR={dr_refs}/{dr_files} agree={counts_agree}",
        file=sys.stderr,
    )
    return 0 if counts_agree else 1


if __name__ == "__main__":
    raise SystemExit(main())
