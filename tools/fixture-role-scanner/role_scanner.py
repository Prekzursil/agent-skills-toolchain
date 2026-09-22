#!/usr/bin/env python3
"""Role-based fixture/content scanners (TST-0341).

A fixture that DOCUMENTS a forbidden pattern necessarily CONTAINS that pattern.
Scanners that match raw payload text therefore flag their own documentation and
miss nothing real — the use-versus-mention defect measured ~8 times on this
estate, mostly inside verification probes.

This module rebuilds the programme's fixture/content scanners so each match is
judged by its semantic ROLE (tool-call verb, JSON field vs value, AST / prose
position) via ``hooks/_shared/use_vs_mention.py``, not by substring presence.

Public surface
--------------
* ``scan_raw``     — baseline: every regex hit fires (the broken instrument).
* ``scan_role``    — rebuilt: only USE verdicts fire; MENTION is silent.
* ``SCANNERS``     — one rebuilt scanner per corpus kind (command/marker/stub/
                     result/secret/pathword).
* ``evaluate_corpus_row`` / ``measure_kind`` — FP and TP rates per scanner.
* ``self_reference_silent`` — the unit's own receipt (or any doc quoting the
  patterns) must not be flagged by the scanners it ships.

Stdlib only at the call boundary; the discriminator is imported from
``hooks/_shared`` (the shared role library, not a copy).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
_SHARED = REPO / "hooks" / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from use_vs_mention import Context, Judgement, Verdict, classify  # noqa: E402

CORPUS_PATH = _SHARED / "use-vs-mention-corpus.jsonl"

# Default needles the programme's content scanners historically hunted. Kept as
# module constants so the self-reference probe can quote them without inventing
# a second pattern list.
FORBIDDEN_NEEDLES: dict[str, re.Pattern[str]] = {
    "command": re.compile(r"Remove-Item|git push --force|rm\s+-rf\s+/", re.IGNORECASE),
    "marker": re.compile(r"\b(?:TODO|FIXME)\b", re.IGNORECASE),
    "stub": re.compile(
        r"\b(?:TODO|FIXME|NotImplementedError|placeholder|stub|not implemented)\b",
        re.IGNORECASE,
    ),
    "result": re.compile(r"timedout|timeout|timed out|failed|MCP error", re.IGNORECASE),
    "secret": re.compile(
        r"ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA )?PRIVATE KEY-----"
    ),
    "pathword": re.compile(r"credential", re.IGNORECASE),
}

KINDS = tuple(FORBIDDEN_NEEDLES.keys())


@dataclass(frozen=True)
class Hit:
    """One match a scanner reported."""

    kind: str
    start: int
    end: int
    text: str
    rule: str = ""
    verdict: str = ""

    @property
    def snippet(self) -> str:
        return self.text[self.start : self.end]


def scan_raw(
    text: str,
    *,
    kind: str,
    pattern: re.Pattern[str] | None = None,
) -> list[Hit]:
    """Baseline scanner: every regex hit fires. No role discrimination."""
    if not text:
        return []
    pat = pattern or FORBIDDEN_NEEDLES[kind]
    return [
        Hit(kind=kind, start=m.start(), end=m.end(), text=text, rule="raw:substring")
        for m in pat.finditer(text)
    ]


def scan_role(
    text: str,
    *,
    kind: str,
    ctx: Context | None = None,
    pattern: re.Pattern[str] | None = None,
) -> list[Hit]:
    """Rebuilt scanner: fire only when classify() returns USE (not MENTION)."""
    if not text:
        return []
    pat = pattern or FORBIDDEN_NEEDLES[kind]
    context = ctx or Context(source="file")
    hits: list[Hit] = []
    for m in pat.finditer(text):
        judgement: Judgement = classify(text, (m.start(), m.end()), context, kind=kind)
        if judgement.verdict is Verdict.USE:
            hits.append(
                Hit(
                    kind=kind,
                    start=m.start(),
                    end=m.end(),
                    text=text,
                    rule=judgement.rule,
                    verdict=judgement.verdict.value,
                )
            )
    return hits


@dataclass(frozen=True)
class CorpusRowResult:
    row_id: str
    kind: str
    expect: str
    raw_fired: bool
    role_fired: bool
    role_ok: bool
    covered: bool


def load_corpus(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or CORPUS_PATH
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _span_for(text: str, pattern: str) -> tuple[int, int] | None:
    try:
        m = re.search(pattern, text, re.IGNORECASE)
    except re.error:
        m = None
    if m is not None:
        return m.start(), m.end()
    try:
        i = text.index(pattern)
        return i, i + len(pattern)
    except ValueError:
        return None


def evaluate_corpus_row(row: dict[str, Any]) -> CorpusRowResult:
    """Evaluate one historical corpus row under both raw and role scanners."""
    text = row["text"]
    kind = row["kind"]
    expect = row["expect"]
    ctx = Context(**row["ctx"])
    span = _span_for(text, row["pattern"])
    raw_fired = span is not None  # raw = presence of the needle
    if span is None:
        role_fired = False
    else:
        # Authority is classify() — the same judge scan_role uses per hit.
        judgement = classify(text, span, ctx, kind=kind)
        role_fired = judgement.verdict is Verdict.USE
    role_ok = (role_fired and expect == "FIRE") or (
        (not role_fired) and expect == "SILENT"
    )
    return CorpusRowResult(
        row_id=row["id"],
        kind=kind,
        expect=expect,
        raw_fired=raw_fired,
        role_fired=role_fired,
        role_ok=role_ok,
        covered=bool(row.get("covered", False)),
    )


def measure_kind(
    kind: str, rows: Iterable[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Report FP and TP counts for one rebuilt scanner on the historical corpus.

    Both numbers are mandatory (catalog evidence_requirement): fixing false
    positives by loosening into uselessness is the wrong repair.
    """
    corpus = [
        r for r in (rows if rows is not None else load_corpus()) if r["kind"] == kind
    ]
    fp_rows = [r for r in corpus if r["expect"] == "SILENT"]
    tp_rows = [r for r in corpus if r["expect"] == "FIRE"]
    fp_eval = [evaluate_corpus_row(r) for r in fp_rows]
    tp_eval = [evaluate_corpus_row(r) for r in tp_rows]
    fp_flags = sum(1 for e in fp_eval if e.role_fired)
    tp_flags = sum(1 for e in tp_eval if e.role_fired)
    raw_fp_flags = sum(1 for e in fp_eval if e.raw_fired)
    return {
        "kind": kind,
        "fp_corpus_size": len(fp_rows),
        "tp_corpus_size": len(tp_rows),
        "role_fp_flags": fp_flags,
        "role_tp_flags": tp_flags,
        "raw_fp_flags": raw_fp_flags,
        "role_fp_zero": fp_flags == 0,
        "role_tp_complete": tp_flags == len(tp_rows) and len(tp_rows) > 0,
        "all_role_ok": all(e.role_ok for e in fp_eval + tp_eval),
        "fp_row_ids": [e.row_id for e in fp_eval],
        "tp_row_ids": [e.row_id for e in tp_eval],
        "fp_still_firing": [e.row_id for e in fp_eval if e.role_fired],
        "tp_still_silent": [e.row_id for e in tp_eval if not e.role_fired],
    }


def measure_all(rows: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    corpus = list(rows) if rows is not None else load_corpus()
    kinds = sorted({r["kind"] for r in corpus})
    per = {k: measure_kind(k, corpus) for k in kinds}
    return {
        "corpus_path": str(CORPUS_PATH.relative_to(REPO)),
        "corpus_rows": len(corpus),
        "scanners": per,
        "role_fp_total": sum(p["role_fp_flags"] for p in per.values()),
        "role_tp_missed": sum(len(p["tp_still_silent"]) for p in per.values()),
        "raw_fp_total": sum(p["raw_fp_flags"] for p in per.values()),
        "ok": all(p["all_role_ok"] for p in per.values()),
    }


def self_reference_silent(
    document: str,
    *,
    kinds: Iterable[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Scan a document that QUOTES forbidden patterns (e.g. this unit's receipt).

    Must produce zero role flags: the document's semantic role is documentation,
    not an executable / pending / secret occurrence.
    """
    context = ctx or Context(
        tool_name="Write",
        file_path="command-center/receipts/TST-0341.json",
        source="tool_input",
    )
    # Receipts are JSON prose about the defect; treat as a .md-equivalent doc by
    # forcing the prose path via an .md file_path when the caller did not.
    if not context.file_path.endswith((".md", ".markdown", ".txt", ".rst")):
        context = Context(
            tool_name=context.tool_name or "Write",
            file_path="command-center/receipts/TST-0341.md",
            source=context.source or "tool_input",
        )
    chosen = list(kinds) if kinds is not None else list(KINDS)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for kind in chosen:
        # pathword/secret scanners are not applied to receipt prose that merely
        # names the kinds; command/marker/stub/result are the ones that historically
        # self-amplified inside verification probes.
        if kind in ("pathword",):
            by_kind[kind] = []
            continue
        hits = scan_role(document, kind=kind, ctx=context)
        by_kind[kind] = [
            {"snippet": h.snippet, "rule": h.rule, "start": h.start} for h in hits
        ]
        total += len(hits)
    return {
        "flags": total,
        "silent": total == 0,
        "by_kind": by_kind,
        "context": {
            "tool_name": context.tool_name,
            "file_path": context.file_path,
            "source": context.source,
        },
    }


# One rebuilt scanner callable per kind — the programme surface TST-0341 ships.
SCANNERS: dict[str, Any] = {
    kind: (lambda text, ctx=None, _k=kind: scan_role(text, kind=_k, ctx=ctx))
    for kind in KINDS
}


def main(argv: list[str] | None = None) -> int:
    report = measure_all()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
