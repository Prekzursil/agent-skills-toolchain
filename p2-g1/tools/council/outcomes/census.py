"""Downstream-consumer census for council outcome kinds (IMP-0311).

Static scan that classifies every reader of the outcome `kind` field as
PRESERVES (keeps the typed kind) or COERCES (maps a protected kind onto the
PASS/FAIL binary).  The census exists because the unit's falsifiable question
is whether NO-DECISION / CONDITIONAL / PROOF-OF-IMPOSSIBILITY are ever coerced
by a consumer that only understands PASS/FAIL -- and whether such a consumer is
CAUGHT.  Planted-defect fixtures in the unit's probe fixtures directory carry
the both-states proof: coercers are caught, a preserving consumer stays silent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PROTECTED: tuple[str, ...] = (
    "NO-DECISION",
    "CONDITIONAL",
    "PROOF-OF-IMPOSSIBILITY",
)
KIND_RE = re.compile(r"[\"']([A-Z][A-Z-]+)[\"']")

# `return "PASS"` / `return "FAIL"` (both quote styles), as a statement.
_RETURN_BINARY_RE = re.compile(r"\breturn\s+[\"'](PASS|FAIL)[\"']")
# Ternary remap: return "PASS" if <expr referencing kind> == "DECISION" else "FAIL"
_TERNARY_RE = re.compile(
    r"\breturn\s+[\"'](PASS|FAIL)[\"']\s+if\b.*\belse\s+[\"'](PASS|FAIL)[\"']"
)
# Comparison context for a kind literal: x == "NO-DECISION" / in {"NO-DECISION", ...}
_CMP_RE = re.compile(r"(==|!=|in\s*\{|in\s*\[|in\s+\()")
# Causal markers: the clause's answer is needed to even pose the other question.
_CAUSAL_MARKERS: tuple[str, ...] = (
    "given the",
    "given",
    "based on",
    "depending on",
    "depends on",
    "as measured",
    "according to",
)

# Bind tokens so generic they never indicate coupling by themselves.
_BIND_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "what",
    "which",
    "who",
    "how",
    "many",
    "much",
    "should",
    "set",
    "give",
    "given",
    "is",
    "are",
    "of",
    "in",
    "on",
    "to",
    "a",
    "an",
    "does",
    "do",
    "we",
    "be",
    "by",
    "as",
    "at",
    "it",
    "its",
    "our",
    "us",
    "per",
    "or",
    "if",
    "text",
    "id",
    "domain",
    "needs",
    "binds",
    "clauses",
    "answers",
    "claims",
    "value",
    "variable",
}

LOOKBACK_LINES = 6


@dataclass
class Coercion:
    kind: str
    line: int
    how: str


@dataclass
class FileClassification:
    path: str
    classification: str  # COERCES | PRESERVES
    coercions: list[Coercion] = field(default_factory=list)
    n_binary_returns: int = 0
    handles: dict[str, bool] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        h = self.handles
        return {
            "path": self.path,
            "classification": self.classification,
            "coercions": [
                {"kind": c.kind, "line": c.line, "how": c.how} for c in self.coercions
            ],
            "n_binary_returns": self.n_binary_returns,
            "handles_no_decision": h.get("NO-DECISION", True),
            "handles_conditional": h.get("CONDITIONAL", True),
            "handles_proof": h.get("PROOF-OF-IMPOSSIBILITY", True),
        }


def _kind_literals_near(text_lines: list[str], idx: int) -> set[str]:
    """Protected-kind literals in a comparison context within the lookback window."""
    found: set[str] = set()
    for j in range(max(0, idx - LOOKBACK_LINES), idx + 1):
        line = text_lines[j]
        if not _CMP_RE.search(line):
            continue
        for lit in KIND_RE.findall(line):
            if lit in PROTECTED:
                found.add(lit)
    return found


def _binary_only_remap(line: str) -> bool:
    """A single expression mapping kind==DECISION to PASS and everything else to FAIL."""
    if not _TERNARY_RE.search(line):
        return False
    return '"kind"' in line or "'kind'" in line


def classify_source(source: str) -> FileClassification:
    lines = source.splitlines()
    out = FileClassification(path="", classification="PRESERVES")
    attributed: set[str] = set()
    for i, line in enumerate(lines):
        m = _RETURN_BINARY_RE.search(line)
        if not m:
            continue
        out.n_binary_returns += 1
        if _binary_only_remap(line):
            for kind in PROTECTED:
                if kind not in attributed:
                    attributed.add(kind)
                    out.coercions.append(
                        Coercion(kind=kind, line=i + 1, how="binary-only-remap")
                    )
            continue
        kinds = _kind_literals_near(lines, i)
        for kind in kinds:
            if kind not in attributed:
                attributed.add(kind)
                out.coercions.append(
                    Coercion(kind=kind, line=i + 1, how="kind-to-binary-return")
                )
    out.classification = "COERCES" if out.coercions else "PRESERVES"
    out.handles = {kind: (kind not in attributed) for kind in PROTECTED}
    return out


def classify_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {
            "path": str(p),
            "classification": "ABSENT",
            "coercions": [],
            "error": "file-not-found",
        }
    result = classify_source(p.read_text(encoding="utf-8", errors="replace"))
    result.path = str(p)
    return result.as_row()


def _py_files(entry: Path) -> Iterable[Path]:
    if entry.is_file():
        if entry.suffix == ".py":
            yield entry
        return
    for path in sorted(entry.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def census(entries: list[str | Path]) -> dict[str, Any]:
    """Census every .py reader under entries (files or directories)."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        for path in _py_files(Path(entry)):
            row = classify_file(path)
            rows.append(row)
    coercers = [r for r in rows if r.get("classification") == "COERCES"]
    return {
        "ok": not coercers,
        "rows": rows,
        "coercers": len(coercers),
        "preservers": sum(1 for r in rows if r.get("classification") == "PRESERVES"),
        "scanned": len(rows),
    }


def count_kinds(entries: list[str | Path]) -> dict[str, int]:
    """Census-lite: how many scanned readers coerce each protected kind."""
    result = census(entries)
    counts = {kind: 0 for kind in PROTECTED}
    for row in result["rows"]:
        for c in row.get("coercions") or []:
            if c.get("kind") in counts:
                counts[c["kind"]] += 1
    return counts


def assert_coercer_caught(
    result: dict[str, Any],
    filename: str,
    kind: str,
) -> bool:
    """Fail loudly when the planted coercer of `kind` escaped the census."""
    for row in result.get("rows") or []:
        if filename in str(row.get("path", "")):
            hits = [
                c for c in row.get("coercions") or [] if c.get("kind") == kind
            ]
            if hits:
                return True
            raise AssertionError(
                f"census missed planted coercion of {kind} in {filename}"
            )
    raise AssertionError(f"census has no row for {filename}")
