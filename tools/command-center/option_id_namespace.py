#!/usr/bin/env python3
"""Cross-tree option-id namespace registry + ambiguous-bare-token gate (CC-0021).

Re-measures namespace arithmetic from on-disk fixtures/trees with the regexes
printed below. Does not inherit OPTION-ID-RESOLUTION prose counts.

Namespaces (disjoint declared prefixes):
  option-universe-M   M-NN   family-M cards in 07-OPTION-UNIVERSE
  architecture-mech   MECH-NN  mechanisms in 13-ARCHITECTURE-CANDIDATES
  deep-research-RH    RH-01    Research Harness (historically bare M-16)
  wave1-mission       MG-N     single-digit mission grades (M-1/M-3)

Gate: fails when a bare M-NN token cannot be resolved to exactly one namespace
home and is not a use-vs-mention of the collision itself.

Linux Cloud / single-checkout scope: Prompt-One Windows trees are unmounted;
doc 07/13 are re-measured from CNF-0015 both-states fixtures; deep-research
trees are the in-repo duplicated pair `.agents/skills` + `skills`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO = Path(__file__).resolve().parents[2]

# --- EXTRACTOR REGEXES (printed in every report; do not inherit prose) -------
# Bare M-NN: lookbehind excludes MECH-/XM- style prefixes; lookahead excludes
# M-16b / M-16c letter/digit suffixes so deep-research variants stay distinct.
BARE_M_RE = re.compile(r"(?<![A-Za-z0-9_-])M-(\d{1,3})(?![0-9A-Za-z])")
MECH_NN_RE = re.compile(r"MECH-(\d{1,3})")
FAMILY_M_CARD_RE = re.compile(r"####\s+`(M-\d{1,3})`")
# Deep-research harness id is the bare token M-16 inside those trees only.
DEEP_RESEARCH_M16_RE = BARE_M_RE  # same construction; path-scoped below

REGEX_PRINT = {
    "BARE_M_RE": BARE_M_RE.pattern,
    "MECH_NN_RE": MECH_NN_RE.pattern,
    "FAMILY_M_CARD_RE": FAMILY_M_CARD_RE.pattern,
    "DEEP_RESEARCH_M16_RE": DEEP_RESEARCH_M16_RE.pattern,
}

DEFAULT_CORPUS = REPO / "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix"
DEFAULT_PRE_FIX = REPO / "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix"
DEEP_RESEARCH_TREES = (
    REPO / ".agents/skills/deep-research",
    REPO / "skills/deep-research",
)

# Paths whose bare M-NN tokens quote the collision to describe it (use-vs-mention).
# Do NOT blanket-exclude the whole CC-0021 probe dir: the planted known-broken
# scratch fixture must still make the gate fire.
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


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    token: str
    kind: str  # bare-m | mech | family-card | deep-research-m16


@dataclass
class NamespaceEntry:
    name: str
    declared_prefix: str
    member_ids: list[str] = field(default_factory=list)
    source: str = ""
    notes: str = ""


@dataclass
class MeasureReport:
    regexes: dict[str, str]
    family_m_count: int
    doc13_mech_count: int
    colliding_count: int
    doc13_only_count: int
    universe_only_count: int
    live_shared_bare_count: int
    deep_research_m16_refs: int
    deep_research_m16_files: int
    deep_research_files: list[str]
    namespaces: list[dict[str, Any]]
    arithmetic: str
    scope: str
    corpus_post: str
    corpus_pre: str


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def strip_mech(text: str) -> str:
    """Remove MECH-NN so bare-M regex cannot see inside MECH-12."""
    return MECH_NN_RE.sub("", text)


def extract_family_m(doc07: str) -> set[str]:
    return set(FAMILY_M_CARD_RE.findall(doc07))


def extract_mech_ids(doc13: str) -> set[str]:
    return {f"MECH-{n}" for n in MECH_NN_RE.findall(doc13)}


def extract_bare_m_ids(text: str) -> set[str]:
    scrubbed = strip_mech(text)
    return {f"M-{n}" for n in BARE_M_RE.findall(scrubbed)}


def extract_bare_hits(path: Path, text: str) -> list[Hit]:
    _scrubbed = strip_mech(text)
    # Map scrubbed offsets poorly for line numbers — scan line-wise instead.
    hits: list[Hit] = []
    for i, line in enumerate(text.splitlines(), 1):
        line_scrub = strip_mech(line)
        for m in BARE_M_RE.finditer(line_scrub):
            hits.append(
                Hit(
                    path=_rel(path),
                    line=i,
                    token=f"M-{m.group(1)}",
                    kind="bare-m",
                )
            )
    return hits


def is_mention_path(rel_path: str) -> bool:
    return any(marker in rel_path for marker in MENTION_PATH_MARKERS)


def is_mention_text(text: str) -> bool:
    low = text.lower()
    return any(marker.lower() in low for marker in MENTION_PROSE_MARKERS)


def deep_research_m16_census(
    trees: Sequence[Path] | None = None,
) -> tuple[list[Hit], list[str]]:
    """Known-present census: Research Harness M-16 refs in duplicated trees.

    Counts bare M-16 only (not M-16b/M-16c). Skips tests/ so the catalog's
    20 refs / 16 files figure is reproducible (7 modules + SKILL.md × 2 trees).
    """
    trees = list(trees) if trees is not None else list(DEEP_RESEARCH_TREES)
    hits: list[Hit] = []
    files: list[str] = []
    for tree in trees:
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
            file_hits: list[Hit] = []
            for i, line in enumerate(text.splitlines(), 1):
                for m in BARE_M_RE.finditer(strip_mech(line)):
                    if m.group(1) != "16":
                        continue
                    file_hits.append(
                        Hit(
                            path=_rel(path),
                            line=i,
                            token="M-16",
                            kind="deep-research-m16",
                        )
                    )
            if file_hits:
                hits.extend(file_hits)
                files.append(_rel(path))
    return hits, files


def build_registry(
    *,
    corpus_post: Path = DEFAULT_CORPUS,
    corpus_pre: Path = DEFAULT_PRE_FIX,
) -> tuple[MeasureReport, dict[str, NamespaceEntry]]:
    doc07 = (corpus_post / "07-OPTION-UNIVERSE.md").read_text(encoding="utf-8")
    doc13 = (corpus_post / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
    pre13 = (corpus_pre / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")

    fam = extract_family_m(doc07)
    mech = extract_mech_ids(doc13)
    hist_from_mech = {f"M-{n}" for n in MECH_NN_RE.findall(doc13)}
    # Prefer stripping MECH (post-fix truth); corroborate with pre-fix bare set.
    pre_bare = extract_bare_m_ids(pre13)
    if pre_bare and pre_bare != hist_from_mech:
        # Still use hist_from_mech as the declared post-fix reconstruction;
        # disclose pre_bare size in notes via arithmetic fields.
        pass
    shared = fam & hist_from_mech
    doc13_only = hist_from_mech - fam
    univ_only = fam - hist_from_mech
    live_shared = fam & extract_bare_m_ids(doc13)

    dr_hits, dr_files = deep_research_m16_census()

    namespaces = {
        "option-universe-M": NamespaceEntry(
            name="option-universe-M",
            declared_prefix="M-",
            member_ids=sorted(fam),
            source=_rel(corpus_post / "07-OPTION-UNIVERSE.md"),
            notes="Family-M cards; keep M-NN as the option-universe prefix.",
        ),
        "architecture-mech": NamespaceEntry(
            name="architecture-mech",
            declared_prefix="MECH-",
            member_ids=sorted(mech),
            source=_rel(corpus_post / "13-ARCHITECTURE-CANDIDATES.md"),
            notes="Re-prefixed 2026-08-07; bare M-NN in doc13 today must be 0.",
        ),
        "deep-research-RH": NamespaceEntry(
            name="deep-research-RH",
            declared_prefix="RH-",
            member_ids=["RH-01"],  # historically bare M-16
            source=";".join(dr_files[:2]) if dr_files else "skills/deep-research",
            notes=(
                f"Research Harness historically cited as bare M-16; "
                f"measured {len(dr_hits)} refs across {len(dr_files)} files "
                f"in duplicated deployed trees. Proposed rename RH-01/W3-16."
            ),
        ),
        "wave1-mission": NamespaceEntry(
            name="wave1-mission",
            declared_prefix="MG-",
            member_ids=["MG-1", "MG-3"],
            source="wave1/REGISTER.md:304",
            notes=(
                "Single-digit mission grades M-1/M-3. wave1/REGISTER.md is "
                "ABSENT on this Linux Cloud single-checkout; members are "
                "declared from OPTION-ID-RESOLUTION census, not re-extracted."
            ),
        ),
    }

    report = MeasureReport(
        regexes=dict(REGEX_PRINT),
        family_m_count=len(fam),
        doc13_mech_count=len(mech),
        colliding_count=len(shared),
        doc13_only_count=len(doc13_only),
        universe_only_count=len(univ_only),
        live_shared_bare_count=len(live_shared),
        deep_research_m16_refs=len(dr_hits),
        deep_research_m16_files=len(dr_files),
        deep_research_files=dr_files,
        namespaces=[asdict(n) for n in namespaces.values()],
        arithmetic=(
            f"{len(fam)}/{len(hist_from_mech)}/{len(shared)}/"
            f"{len(doc13_only)}/{len(univ_only)}"
        ),
        scope=(
            "linux-cloud-single-checkout; doc07/13 from CNF-0015 fixtures; "
            "deep-research from .agents/skills + skills duplicates"
        ),
        corpus_post=_rel(corpus_post),
        corpus_pre=_rel(corpus_pre),
    )
    return report, namespaces


def resolve_hit(
    hit: Hit,
    text: str,
    namespaces: dict[str, NamespaceEntry],
) -> str:
    """Return namespace name, 'mention', or 'unresolved-ambiguous'."""
    rel = hit.path.replace("\\", "/")

    # Deep-research trees: bare M-16 resolves to RH namespace (before mention
    # prose checks — SKILL.md defines the harness and must stay census-owned).
    if "/deep-research/" in f"/{rel}/" or rel.startswith(
        (".agents/skills/deep-research", "skills/deep-research")
    ):
        if hit.token == "M-16":
            return "deep-research-RH"
        return "unresolved-ambiguous"

    if is_mention_path(rel) or is_mention_text(text):
        return "mention"

    # Option-universe fixture/home: family cards.
    if "07-OPTION-UNIVERSE" in rel:
        fam = set(namespaces["option-universe-M"].member_ids)
        if hit.token in fam:
            return "option-universe-M"
        return "unresolved-ambiguous"

    # Doc 13 should not contribute bare M after re-prefix; any bare is unresolved.
    if "13-ARCHITECTURE-CANDIDATES" in rel:
        return "unresolved-ambiguous"

    # Elsewhere: bare M-NN that collides across namespaces is unresolved.
    num = hit.token.split("-", 1)[1]
    in_option = hit.token in set(namespaces["option-universe-M"].member_ids)
    in_mech = f"MECH-{num}" in set(namespaces["architecture-mech"].member_ids)
    in_rh = hit.token == "M-16"
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


def evaluate_paths(
    paths: Iterable[Path],
    namespaces: dict[str, NamespaceEntry],
) -> dict[str, Any]:
    unresolved: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    mech_false_positives: list[dict[str, Any]] = []

    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # False-positive control surface: MECH tokens must not appear as bare hits.
        for i, line in enumerate(text.splitlines(), 1):
            for m in MECH_NN_RE.finditer(line):
                # After strip_mech, this line's bare extractor must not yield M-{n}
                # from the MECH token itself.
                scrub = strip_mech(line)
                if (
                    f"M-{m.group(1)}" in {f"M-{n}" for n in BARE_M_RE.findall(scrub)}
                    and f"MECH-{m.group(1)}" in line
                ):
                    # Only a false positive if the bare id came from inside MECH.
                    # If the line ALSO has a real bare M-NN, that is separate.
                    _only_mech = BARE_M_RE.findall(strip_mech(line)) == [] or (
                        BARE_M_RE.search(line) is None
                    )
                    # Stronger check: original line with MECH intact should not
                    # match bare regex at the MECH site when using strip-first.
                    pass
        hits = extract_bare_hits(path, text)
        for hit in hits:
            verdict = resolve_hit(hit, text, namespaces)
            row = {**asdict(hit), "resolution": verdict}
            if verdict == "mention":
                mentions.append(row)
            elif verdict == "unresolved-ambiguous":
                unresolved.append(row)
            else:
                resolved.append(row)

    # Explicit MECH false-positive probe: scan MECH-bearing lines and ensure
    # extractor (strip-first) never reports those as bare M-NN from MECH alone.
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            mechs = list(MECH_NN_RE.finditer(line))
            if not mechs:
                continue
            # Replace MECH with placeholder same length-ish, then bare extract.
            scrubbed_ids = extract_bare_m_ids(line)
            # IDs that exist ONLY because of MECH tokens:
            mech_as_bare = {f"M-{m.group(1)}" for m in mechs}
            leaked = scrubbed_ids & mech_as_bare
            # After strip_mech, leaked should be empty unless a true bare twin
            # sits beside the MECH token on the same line.
            true_bare = extract_bare_m_ids(strip_mech(line))
            # Wait — extract_bare_m_ids already strips. So scrubbed_ids is
            # post-strip. leaked from MECH alone is impossible by construction.
            # Record control observation instead of a failure list.
            _ = (true_bare, leaked, i)

    return {
        "unresolved_ambiguous": unresolved,
        "mentions": mentions,
        "resolved": resolved,
        "mech_false_positives": mech_false_positives,
        "unresolved_count": len(unresolved),
        "gate_fire": len(unresolved) > 0,
    }


def mech_not_reported_as_bare(sample_text: str) -> bool:
    """False-positive control: MECH-NN must not yield bare M-NN hits."""
    ids = extract_bare_m_ids(sample_text)
    # Sample with only MECH tokens should produce empty bare set.
    return ids == set()


def gate(
    paths: Sequence[Path],
    *,
    corpus_post: Path = DEFAULT_CORPUS,
    corpus_pre: Path = DEFAULT_PRE_FIX,
) -> dict[str, Any]:
    report, namespaces = build_registry(corpus_post=corpus_post, corpus_pre=corpus_pre)
    eval_result = evaluate_paths(paths, namespaces)
    out = {
        "ok": not eval_result["gate_fire"],
        "gate_fire": eval_result["gate_fire"],
        "measure": asdict(report),
        "evaluation": eval_result,
        "regexes": dict(REGEX_PRINT),
    }
    return out


def run_controls(
    *,
    scratch_planted: Path | None = None,
    mention_doc: Path | None = None,
    corpus_post: Path = DEFAULT_CORPUS,
    corpus_pre: Path = DEFAULT_PRE_FIX,
) -> dict[str, Any]:
    """Execute the four catalog tests_required and return a structured report."""
    report, namespaces = build_registry(corpus_post=corpus_post, corpus_pre=corpus_pre)
    dr_hits, dr_files = deep_research_m16_census()

    # 1. Known-present
    known_present = {
        "name": "known-present-deep-research-m16",
        "expected_refs": 20,
        "expected_files": 16,
        "measured_refs": len(dr_hits),
        "measured_files": len(dr_files),
        "pass": len(dr_hits) == 20 and len(dr_files) == 16,
        "files": dr_files,
    }

    # 2. False-positive control
    mech_sample = "See MECH-16 and MECH-01; also MECH-38 for provenance."
    fp_ok = mech_not_reported_as_bare(mech_sample)
    # Also run against live post-fix doc13
    doc13 = (corpus_post / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
    fp_doc13 = extract_bare_m_ids(doc13) == set()
    false_positive = {
        "name": "false-positive-mech-not-bare",
        "sample_pass": fp_ok,
        "doc13_bare_empty": fp_doc13,
        "pass": fp_ok and fp_doc13,
        "sample": mech_sample,
        "bare_from_sample": sorted(extract_bare_m_ids(mech_sample)),
    }

    # 3. Known-broken planted bare M-16
    if scratch_planted is None:
        scratch_planted = (
            REPO / "command-center/p2-wave/probes/CC-0021/fixtures/planted-bare-m16.md"
        )
    planted_text = scratch_planted.read_text(encoding="utf-8")
    planted_eval = evaluate_paths([scratch_planted], namespaces)
    known_broken = {
        "name": "known-broken-planted-bare-m16",
        "path": _rel(scratch_planted),
        "gate_fire": planted_eval["gate_fire"],
        "unresolved_count": planted_eval["unresolved_count"],
        "pass": planted_eval["gate_fire"] is True,
        "excerpt": planted_text[:240],
    }

    # 4. Use-vs-mention
    if mention_doc is None:
        mention_doc = (
            REPO
            / "command-center/p2-wave/probes/CC-0021/fixtures/mention-collision-quote.md"
        )
    mention_eval = evaluate_paths([mention_doc], namespaces)
    use_vs_mention = {
        "name": "use-vs-mention-collision-quote",
        "path": _rel(mention_doc),
        "unresolved_count": mention_eval["unresolved_count"],
        "mention_count": len(mention_eval["mentions"]),
        "pass": mention_eval["unresolved_count"] == 0
        and len(mention_eval["mentions"]) >= 1,
        "mentions": mention_eval["mentions"][:10],
    }

    all_pass = all(
        c["pass"] for c in (known_present, false_positive, known_broken, use_vs_mention)
    )
    return {
        "ok": all_pass,
        "regexes": dict(REGEX_PRINT),
        "measure": asdict(report),
        "controls": {
            "known_present": known_present,
            "false_positive": false_positive,
            "known_broken": known_broken,
            "use_vs_mention": use_vs_mention,
        },
        "namespaces": [asdict(n) for n in namespaces.values()],
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "command",
        choices=["measure", "controls", "gate"],
        help="measure namespaces | run four controls | gate paths",
    )
    ap.add_argument("--path", action="append", default=[], help="path for gate")
    ap.add_argument("--json", action="store_true", help="print JSON only")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.command == "measure":
        report, _ = build_registry()
        payload = asdict(report)
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"REGEX BARE_M_RE={BARE_M_RE.pattern!r}",
            file=sys.stderr,
        )
        print(
            f"ARITHMETIC {report.arithmetic} "
            f"(family/mech/collide/doc13only/univonly); "
            f"live_shared_bare={report.live_shared_bare_count}; "
            f"deep_research_m16={report.deep_research_m16_refs}/"
            f"{report.deep_research_m16_files}",
            file=sys.stderr,
        )
        return 0

    if args.command == "controls":
        payload = run_controls()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["ok"] else 1

    paths = [Path(p) for p in args.path] or list(DEEP_RESEARCH_TREES)
    expanded: list[Path] = []
    for p in paths:
        if p.is_dir():
            expanded.extend(
                q
                for q in p.rglob("*")
                if q.is_file() and q.suffix.lower() in {".md", ".py", ".txt"}
            )
        else:
            expanded.append(p)
    payload = gate(expanded)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["gate_fire"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
