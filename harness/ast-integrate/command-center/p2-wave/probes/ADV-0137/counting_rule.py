"""Published counting rule for ADV-0137 originating sources.

Two harvests (JSON object walk vs string-aware scan) must apply THIS rule
to the input strings they find. The rule is the contract; the harvests are
the independent instruments.
"""
from __future__ import annotations

import re
from typing import Iterable

RULE_ID = "ADV-0137-originating-source-v1"

RULE_TEXT = (
    "Originating-source histogram (units per source). Substrate: the merged "
    "WORK-UNIT-CATALOG.json work_units array. catalog-slices/*.json is a declared "
    "input and is counted as present only when that directory contains a .json "
    "file; slice membership otherwise comes from each unit's _source_slice_file "
    "and is not itself a source unless cited in inputs. "
    "For each work unit, take the set union of document identities extracted from "
    "its inputs[] strings (a unit contributes at most once per source). "
    "Extraction: (1) normalise backslashes to slashes; (2) strip Windows/POSIX "
    "prefixes up to ast-integrate/; (3) rewrite harness-restore absolute prefixes "
    "to harness-restore/<basename>; (4) rewrite other /Users/.../.claude/ prefixes "
    "to external-claude/<basename>; (5) drop #fragments and :line or :start-end "
    "suffixes for SOURCE identity (line ranges are retained separately as spec "
    "passage keys); (6) map well-known basenames (CLAIM-REGISTRY.json, "
    "_USER-PROMPTS.md, AGENTS.md, …) onto one canonical path so Windows, "
    "harness-restore, and repo-relative spellings of the same document do not "
    "fork the histogram; (7) numbered estate docs matching ^\\d{2}- map to "
    "harness-restore/<basename>; (8) named non-file sources: pinned+brief → "
    "named:pinned-program-brief; phase-0/phase 0 + digest → "
    "named:phase0-ground-digest. "
    "Inputs that yield the empty set are prose-only: they are reported as "
    "prose_only_unit_count, not dumped into a fake source bucket. "
    "Gini: on the vector of positive histogram counts x_(1) ≤ … ≤ x_(n), "
    "G = 2*Σ i x_i / (n Σ x_i) − (n+1)/n. Zero-count sources are outside the "
    "support. "
    "Transitive load-bearing rank of source S: let D(S) be unit ids that cite S. "
    "Walk the reverse of the dependencies relation along UNIT-ID edges only "
    "(token T → unit U when U.dependencies contains T and T is a work-unit id). "
    "Rank(S) = |reach(D(S))| including D(S). Bucket tokens (B07, BKT-*) are not "
    "expanded. "
    "A shared premise at rank time is an originating source (file/named key). "
    "Spec line ranges are an inner grain of _USER-PROMPTS.md, reported on that "
    "premise's re-derivation, not as separate histogram keys."
)

PATH_TOKEN = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w./+-]+|[\w./+-]+)\.(?:md|json|jsonl|py|yml|yaml)\b",
    re.I,
)
SPEC_FILE = "_USER-PROMPTS.md"
SPEC_RANGE = re.compile(r"_USER-PROMPTS\.md:(\d+)(?:-(\d+))?")
HARNESS = re.compile(
    r"(?:[A-Za-z]:)?/Users/[^/\s]+/\.claude/harness-restore-\d+/", re.I
)
AST_PREFIX = re.compile(
    r"(?:[A-Za-z]:)?/Users/[^/\s]+/(?:source/)?ast-integrate/", re.I
)
CLAUDE_OTHER = re.compile(
    r"(?:[A-Za-z]:)?/Users/[^/\s]+/\.claude/[^/\s]+/", re.I
)
WIN_USERS = re.compile(r"(?:[A-Za-z]:)?/Users/[^/\s]+/", re.I)
LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")
NUMBERED_DOC = re.compile(r"^\d{2}-[A-Za-z0-9._-]+\.(?:md|json|jsonl)$")
UID = re.compile(r"^[A-Z]{2,5}-\d{4}$")

WELL_KNOWN = {
    "_USER-PROMPTS.md": "_USER-PROMPTS.md",
    "AGENTS.md": "AGENTS.md",
    "CLAIM-REGISTRY.json": "command-center/CLAIM-REGISTRY.json",
    "TEST-REGISTRY.json": "command-center/TEST-REGISTRY.json",
    "BASELINE-SNAPSHOT.json": "command-center/BASELINE-SNAPSHOT.json",
    "ARTIFACT-MANIFEST.json": "command-center/ARTIFACT-MANIFEST.json",
    "WORK-UNIT-CATALOG.json": "command-center/WORK-UNIT-CATALOG.json",
    "OWNER-DECISIONS.md": "command-center/OWNER-DECISIONS.md",
    "DEPENDENCY-GRAPH.json": "command-center/DEPENDENCY-GRAPH.json",
    "PHASE-GRAPH.json": "command-center/PHASE-GRAPH.json",
    "RISK-REGISTER.md": "command-center/RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md": "command-center/UNKNOWNS-REGISTER.md",
    "COMPLETION-GATES.json": "command-center/COMPLETION-GATES.json",
    "EVENTS.jsonl": "command-center/events/EVENTS.jsonl",
    "REGISTER.md": "command-center/sources/REGISTER.md",
    "OWNER-QUESTION-PACKET.md": "command-center/OWNER-QUESTION-PACKET.md",
}


def canon_path(token: str) -> str | None:
    t = token.replace("\\", "/").strip()
    t = t.strip(".,;()[]`\"'")
    if t.startswith("file://"):
        t = t[7:]
    t = AST_PREFIX.sub("", t)
    if HARNESS.search(t):
        base = t.rsplit("/", 1)[-1]
        t = "harness-restore/" + base
    elif CLAUDE_OTHER.search(t):
        base = t.rsplit("/", 1)[-1]
        t = "external-claude/" + base
    elif WIN_USERS.match(t) and "ast-integrate" not in t:
        base = t.rsplit("/", 1)[-1]
        t = "external-user/" + base
    t = t.lstrip("./")
    t = t.split("#")[0]
    t = LINE_SUFFIX.sub("", t)
    t = t.strip(".,;()[]")
    if not t or len(t) < 4 or "." not in t.rsplit("/", 1)[-1]:
        return None
    base = t.rsplit("/", 1)[-1]
    if base in WELL_KNOWN:
        return WELL_KNOWN[base]
    if t in WELL_KNOWN.values():
        return t
    if t == "sources/REGISTER.md" or t.endswith("/sources/REGISTER.md"):
        return "command-center/sources/REGISTER.md"
    if t.startswith("harness-restore/") or t.startswith("external-"):
        return t
    if NUMBERED_DOC.match(base) and "/" not in t:
        return "harness-restore/" + base
    if NUMBERED_DOC.match(base) and not t.startswith(
        ("command-center/", "rules/", "tools/", "platform/")
    ):
        return "harness-restore/" + base
    return t


def spec_passages(text: str) -> set[str]:
    out: set[str] = set()
    for a, b in SPEC_RANGE.findall(text.replace("\\", "/")):
        if b:
            out.add(f"{SPEC_FILE}:{a}-{b}")
        else:
            out.add(f"{SPEC_FILE}:{a}")
    return out


def sources_of(text: str) -> set[str]:
    if not isinstance(text, str) or not text.strip():
        return set()
    t = text.replace("\\", "/")
    found: set[str] = set()
    for raw in PATH_TOKEN.findall(t):
        c = canon_path(raw)
        if c:
            found.add(c)
    low = t.lower()
    if "pinned" in low and "brief" in low:
        found.add("named:pinned-program-brief")
    if "digest" in low and (
        "phase-0" in low or "phase 0" in low or "ground digest" in low
    ):
        found.add("named:phase0-ground-digest")
    return found


def sources_from_inputs(inputs: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for item in inputs:
        if isinstance(item, str):
            out |= sources_of(item)
    return out


def passages_from_inputs(inputs: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for item in inputs:
        if isinstance(item, str):
            out |= spec_passages(item)
    return out


def gini(counts: Iterable[int]) -> float:
    xs = sorted(int(x) for x in counts if int(x) > 0)
    n = len(xs)
    tot = sum(xs)
    if n == 0 or tot == 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * weighted) / (n * tot) - (n + 1) / n
