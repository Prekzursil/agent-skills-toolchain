#!/usr/bin/env python3
"""Caveat-position classifier for BLD-0030.

Primary method is section-structure: a tag inside a trailing Limitations or
Residual section is BURIED even when the file is short and the tag is the next
sentence after the claim. Character-offset position is reported as the
distribution (the defect is concentration in the final decile) and is NOT the
burial rule — a short Limitations file is the catalog control that makes that
distinction load-bearing.

INLINE: the tag sits in the same sentence as the claim it qualifies, or in the
immediately following sentence, AND is not inside a trailing caveat section.

Use-vs-mention: fenced blocks and inline code spans are masked before harvest,
so a backticked `UNVERIFIED` is a vocabulary mention, not a live caveat.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

TAG_RE = re.compile(r"\b(UNVERIFIED|NOT-CHECKED)\b")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
CAVEAT_HEADING = re.compile(
    r"^(limitations?|residuals?|caveats?|unknowns?|not[- ]checked|unverified items)\b",
    re.I,
)
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
    ".tox",
}
SKIP_FILES = {
    "WORK-UNIT-CATALOG.json",
    "package-lock.json",
    "package.json",
    "UNIT-ARTIFACT-MANIFEST.json",
    "SUBAGENT-RETURN.json",
}
MAX_BYTES = 1_000_000
# Narrative documents a reader can follow. JSON receipts and catalogs mention
# the vocabulary as data; harvesting them is a use-versus-mention miss.
EXTS = {".md", ".txt"}
SKIP_PREFIXES = (
    "command-center/schema/",
    "command-center/p2-wave/",
    "command-center/receipts/",
    "command-center/catalog-slices/",
)


@dataclass
class TagHit:
    path: str
    tag: str
    start: int
    end: int
    line: int
    snippet: str
    position_fraction: float
    decile: int
    in_final_15: bool
    verdict: str
    reason: str
    claim_line: int
    claim_snippet: str
    method: str


@dataclass
class DocResult:
    path: str
    n_chars: int
    n_lines: int
    n_tags: int
    document_class: str
    tags: list[TagHit] = field(default_factory=list)


def mask_code(text: str) -> str:
    def blanks(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    out = re.sub(r"```[\s\S]*?```", blanks, text)
    out = re.sub(r"`[^`\n]*`", blanks, out)
    return out


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, min(offset, len(text)))) + 1


def snippet_at(text: str, offset: int, width: int = 180) -> str:
    if not text:
        return ""
    a = text.rfind("\n", 0, offset) + 1
    b = text.find("\n", offset)
    if b < 0:
        b = len(text)
    line = text[a:b].strip()
    if len(line) > width:
        return line[: width - 3] + "..."
    return line


def headings(text: str) -> list[dict]:
    found: list[dict] = []
    for m in HEADING_RE.finditer(text):
        title = m.group(2).strip()
        found.append(
            {
                "start": m.start(),
                "end": m.end(),
                "title": title,
                "caveat": bool(CAVEAT_HEADING.match(title)),
                "line": line_of(text, m.start()),
            }
        )
    n = len(text)
    for i, h in enumerate(found):
        nxt = found[i + 1]["start"] if i + 1 < len(found) else n
        h["body_end"] = nxt
        later = found[i + 1 :]
        h["trailing"] = bool(h["caveat"] and all(x["caveat"] for x in later))
    return found


def section_at(heads: list[dict], offset: int) -> dict | None:
    for h in heads:
        if h["start"] <= offset < h["body_end"]:
            return h
    return None


def split_sentences(text: str) -> list[dict]:
    if not text:
        return []
    bounds = {0, len(text)}
    for m in re.finditer(r"(?<=[.!?])(?:[ \t]+|\n+)", text):
        bounds.add(m.end())
    for m in re.finditer(r"\n{2,}", text):
        bounds.add(m.end())
    for m in HEADING_RE.finditer(text):
        bounds.add(m.start())
        bounds.add(m.end())
    marks = sorted(bounds)
    out: list[dict] = []
    for a, b in zip(marks, marks[1:]):
        chunk = text[a:b]
        if not chunk.strip():
            continue
        stripped = chunk.strip()
        out.append(
            {
                "start": a,
                "end": b,
                "text": stripped,
                "line": line_of(text, a),
                "is_heading": bool(HEADING_RE.match(stripped)),
            }
        )
    return out


def sentence_index(sents: list[dict], offset: int) -> int:
    for i, s in enumerate(sents):
        if s["start"] <= offset < s["end"]:
            return i
    for i, s in enumerate(sents):
        if offset < s["start"]:
            return max(0, i - 1)
    return max(0, len(sents) - 1)


def is_claim_sentence(sent: dict) -> bool:
    if sent.get("is_heading"):
        title = sent["text"].lstrip("#").strip()
        if CAVEAT_HEADING.match(title):
            return False
        return len(title) >= 3
    body = TAG_RE.sub("", sent["text"])
    body = re.sub(r"[^\w]+", " ", body).strip()
    return len(body) >= 8


def prior_claim(sents: list[dict], idx: int) -> dict | None:
    for j in range(idx, -1, -1):
        if is_claim_sentence(sents[j]):
            return sents[j]
    for s in sents:
        if is_claim_sentence(s):
            return s
    return None


def classify_text(
    text: str,
    rel_path: str,
    *,
    method: str = "section-structure",
) -> DocResult:
    n = len(text)
    n_lines = text.count("\n") + (0 if (not text or text.endswith("\n")) else 1)
    masked = mask_code(text)
    heads = headings(text)
    sents = split_sentences(text)
    hits: list[TagHit] = []
    for m in TAG_RE.finditer(masked):
        start, end, tag = m.start(), m.end(), m.group(1)
        pos = start / n if n else 0.0
        decile = 9 if pos >= 1.0 else min(9, int(pos * 10))
        in_final_15 = pos >= 0.85
        sec = section_at(heads, start)
        si = sentence_index(sents, start) if sents else 0
        containing = sents[si] if sents else None
        prev = sents[si - 1] if sents and si > 0 else None
        claim = prior_claim(sents, si) if sents else None
        if claim is None:
            claim = {"line": 1, "text": snippet_at(text, 0) or rel_path}

        same_sentence = bool(
            containing
            and is_claim_sentence(containing)
            and containing["start"] <= start < containing["end"]
        )
        following = bool(
            prev
            and is_claim_sentence(prev)
            and containing is not None
            and not containing.get("is_heading")
            and containing["start"] <= start < containing["end"]
        )
        adjacent = same_sentence or following

        if method == "character-offset":
            if in_final_15:
                verdict, reason = "BURIED", "character-offset-final-15-percent"
            elif adjacent:
                verdict, reason = "INLINE", "adjacent-same-or-next-sentence"
            else:
                verdict, reason = "BURIED", "not-adjacent-character-offset"
        else:
            if sec and sec.get("trailing"):
                verdict, reason = "BURIED", "trailing-caveat-section:" + sec["title"]
                before = [
                    s for s in sents if s["end"] <= sec["start"] and is_claim_sentence(s)
                ]
                if before:
                    claim = before[-1]
            elif adjacent:
                verdict, reason = "INLINE", "adjacent-same-or-next-sentence"
            else:
                verdict, reason = "BURIED", "not-adjacent-to-claim"

        hits.append(
            TagHit(
                path=rel_path,
                tag=tag,
                start=start,
                end=end,
                line=line_of(text, start),
                snippet=snippet_at(text, start),
                position_fraction=round(pos, 6),
                decile=decile,
                in_final_15=in_final_15,
                verdict=verdict,
                reason=reason,
                claim_line=int(claim["line"]),
                claim_snippet=str(claim["text"])[:160],
                method=method,
            )
        )

    if not hits:
        klass = "NO-TAGS"
    elif all(h.verdict == "INLINE" for h in hits):
        klass = "ALL-INLINE"
    elif all(h.verdict == "BURIED" for h in hits):
        klass = "ALL-BURIED"
    else:
        klass = "MIXED"
    return DocResult(
        path=rel_path,
        n_chars=n,
        n_lines=max(n_lines, 1 if text else 0),
        n_tags=len(hits),
        document_class=klass,
        tags=hits,
    )


def classify_path(
    path: Path, repo: Path = REPO, *, method: str = "section-structure"
) -> DocResult:
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    return classify_text(text, rel, method=method)


def should_skip(path: Path, repo: Path) -> bool:
    rel_parts = path.resolve().relative_to(repo.resolve()).parts
    if any(p in SKIP_DIRS for p in rel_parts):
        return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix.lower() not in EXTS:
        return True
    try:
        if path.stat().st_size > MAX_BYTES:
            return True
    except OSError:
        return True
    rel = "/".join(rel_parts)
    if any(rel.startswith(p) for p in SKIP_PREFIXES):
        return True
    if rel == "command-center/receipts/BLD-0030.json":
        return True
    return False


def harvest(repo: Path = REPO, *, method: str = "section-structure") -> list[DocResult]:
    docs: list[DocResult] = []
    roots = [repo / "command-center", repo / "docs", repo / "rules"]
    extra = [repo / "AGENTS.md", repo / "README.md", repo / "CLAUDE.md"]
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or should_skip(p, repo):
                continue
            rel = p.resolve().relative_to(repo.resolve()).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            docs.append(classify_path(p, repo, method=method))
    for p in extra:
        if p.is_file() and not should_skip(p, repo):
            rel = p.resolve().relative_to(repo.resolve()).as_posix()
            if rel not in seen:
                seen.add(rel)
                docs.append(classify_path(p, repo, method=method))
    return docs


def fixture_docs(*, method: str = "section-structure") -> list[DocResult]:
    out: list[DocResult] = []
    for name in (
        "control-inline.md",
        "control-buried-short.md",
        "control-no-tags.md",
        "control-mention.md",
        "control-residual.md",
    ):
        p = FIXTURES / name
        if p.is_file():
            out.append(classify_path(p, REPO, method=method))
    return out


def distribution(tags: list[TagHit]) -> dict:
    n = len(tags)
    deciles = [0] * 10
    final15 = 0
    total_pos = 0.0
    for t in tags:
        deciles[t.decile] += 1
        if t.in_final_15:
            final15 += 1
        total_pos += t.position_fraction
    mean = (total_pos / n) if n else 0.0
    final_decile = deciles[9]
    return {
        "n_tags": n,
        "mean": round(mean, 6),
        "deciles": deciles,
        "final_decile": {
            "count": final_decile,
            "fraction_of_tags": round(final_decile / n, 6) if n else 0.0,
        },
        "final_15_percent": {
            "count": final15,
            "fraction_of_tags": round(final15 / n, 6) if n else 0.0,
        },
        "not_just_a_mean": True,
    }


def buried_rows(tags: list[TagHit]) -> list[dict]:
    rows = []
    for t in tags:
        if t.verdict != "BURIED":
            continue
        rows.append(
            {
                "path": t.path,
                "tag": t.tag,
                "tag_line": t.line,
                "tag_snippet": t.snippet,
                "claim_line": t.claim_line,
                "claim_snippet": t.claim_snippet,
                "position_fraction": t.position_fraction,
                "reason": t.reason,
            }
        )
    return rows


def doc_class_counts(docs: list[DocResult]) -> dict:
    counts = {"NO-TAGS": 0, "ALL-INLINE": 0, "ALL-BURIED": 0, "MIXED": 0}
    for d in docs:
        counts[d.document_class] = counts.get(d.document_class, 0) + 1
    return counts


def as_jsonable(doc: DocResult) -> dict:
    return {
        "path": doc.path,
        "n_chars": doc.n_chars,
        "n_lines": doc.n_lines,
        "n_tags": doc.n_tags,
        "document_class": doc.document_class,
        "tags": [asdict(t) for t in doc.tags],
    }


def run_catalog_controls() -> list[dict]:
    inline = classify_path(FIXTURES / "control-inline.md")
    buried = classify_path(FIXTURES / "control-buried-short.md")
    none = classify_path(FIXTURES / "control-no-tags.md")
    mention = classify_path(FIXTURES / "control-mention.md")
    residual = classify_path(FIXTURES / "control-residual.md")
    char_buried = classify_path(
        FIXTURES / "control-buried-short.md", method="character-offset"
    )

    inline_ok = inline.n_tags >= 2 and all(t.verdict == "INLINE" for t in inline.tags)
    buried_ok = (
        buried.n_tags >= 1
        and all(t.verdict == "BURIED" for t in buried.tags)
        and buried.n_chars < 2048
        and all(t.reason.startswith("trailing-caveat-section") for t in buried.tags)
    )
    none_ok = none.document_class == "NO-TAGS" and none.document_class != "ALL-INLINE"
    mention_ok = mention.document_class == "NO-TAGS" and mention.n_tags == 0
    residual_ok = residual.n_tags >= 1 and all(
        t.verdict == "BURIED" and t.reason.startswith("trailing-caveat-section")
        for t in residual.tags
    )

    return [
        {
            "id": "C1-INLINE",
            "name": "tag in same sentence or immediately following sentence scores INLINE",
            "want": "INLINE",
            "got": ",".join(t.verdict for t in inline.tags) or "NO-TAGS",
            "pass": inline_ok,
            "path": inline.path,
            "n_chars": inline.n_chars,
            "document_class": inline.document_class,
        },
        {
            "id": "C2-BURIED-SHORT",
            "name": "tag in trailing Limitations section scores BURIED even when the document is short",
            "want": "BURIED",
            "got": ",".join(t.verdict for t in buried.tags) or "NO-TAGS",
            "pass": buried_ok,
            "path": buried.path,
            "n_chars": buried.n_chars,
            "reasons": [t.reason for t in buried.tags],
            "character_offset_verdicts": [t.verdict for t in char_buried.tags],
            "character_offset_positions": [t.position_fraction for t in char_buried.tags],
        },
        {
            "id": "C3-NO-TAGS",
            "name": "zero-tag document classifies NO-TAGS, distinct from ALL-INLINE",
            "want": "NO-TAGS",
            "got": none.document_class,
            "pass": none_ok,
            "path": none.path,
            "inline_fixture_class": inline.document_class,
            "classes_distinct": none.document_class != inline.document_class,
        },
        {
            "id": "C4-MENTION",
            "name": "backticked UNVERIFIED is a mention and must not harvest",
            "want": "NO-TAGS",
            "got": mention.document_class,
            "pass": mention_ok,
            "path": mention.path,
        },
        {
            "id": "C5-RESIDUAL",
            "name": "tag in trailing Residual section scores BURIED",
            "want": "BURIED",
            "got": ",".join(t.verdict for t in residual.tags) or "NO-TAGS",
            "pass": residual_ok,
            "path": residual.path,
        },
    ]


if __name__ == "__main__":
    ctrls = run_catalog_controls()
    print(json.dumps({"controls": ctrls}, indent=2))
    if not all(c["pass"] for c in ctrls):
        raise SystemExit(1)
