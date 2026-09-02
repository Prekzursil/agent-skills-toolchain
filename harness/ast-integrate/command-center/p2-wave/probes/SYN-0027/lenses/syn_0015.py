"""SYN-0015 quantifier-versus-measured-N overclaim scan."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from role import (
    classify_text_span,
    iter_json_strings,
    load_subject,
    path_role,
    record_anchors,
)

LENS_ID = "SYN-0015"

# Catalog: every, all, none, zero, never, always, no unit, 100 percent.
QUANT_RE = re.compile(
    r"\bno unit\b|\b100\s*percent\b|\b100\s*%\b|\b(?:every|all|none|never|always|zero)\b",
    re.I,
)
DENOM_RE = re.compile(
    r"\b\d+\s+of\s+\d+\b|\bn\s*=\s*\d+\b|\bdenominator\b|\bmeasured\s+\d+\b|\b\d+\s*/\s*\d+\b",
    re.I,
)
SCOPED_RE = re.compile(
    r"\b(?:all|every|none|zero)\s+\d+\s+of(?:\s+the)?\s+\d+\b"
    r"|\ball\s+\d+\s+(?:measured|listed|admitted)\b"
    r"|\b(?:every|all)\s+\d+\b",
    re.I,
)


def _sentence(text: str, start: int, end: int) -> str:
    a = max(0, text.rfind(".", 0, start) + 1)
    b = text.find(".", end)
    if b < 0:
        b = len(text)
    return text[a:b].strip()


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _finding(
    *,
    seq: int,
    source: Path,
    span: str,
    role: str,
    sentence: str,
    scoped: bool,
    denom: list[str],
    locator: str,
) -> dict[str, Any]:
    use = role == "USE"
    overclaim = use and not scoped
    if role == "MENTION":
        reason = "quantifier is quoted/fenced or sits in a mention field; not a defect"
    elif scoped:
        reason = "quantifier is already scoped to its measured denominator"
    else:
        reason = (
            "universal quantifier in USE voice is wider than any measured "
            "denominator in the same sentence"
        )
    return {
        "id": f"SYN-0015-F{seq:03d}",
        "lens": LENS_ID,
        "kind": "overclaim",
        "use_or_mention": role if role in {"USE", "MENTION"} else "USE",
        "counted_as_defect": bool(overclaim),
        "span": span,
        "sentence": sentence,
        "scoped_to_denominator": scoped,
        "nearby_denominator": denom,
        "source_path": source.as_posix(),
        "source_locator": locator,
        "reason": reason,
        "corrected_sentence": (
            sentence
            if scoped or role == "MENTION"
            else (
                sentence.rstrip(".")
                + " (scope unknown: rewrite to the measured N before asserting a universal)"
            )
        ),
    }


def scan_text(path: Path, text: str, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seq = 1
    for m in QUANT_RE.finditer(text):
        role = classify_text_span(text, m.start(), m.end(), ignore_wrappers=ignore_wrappers)
        if role == "ABSENT":
            continue
        sent = _sentence(text, m.start(), m.end())
        scoped = bool(SCOPED_RE.search(sent))
        denom = [d.group(0) for d in DENOM_RE.finditer(sent)]
        # A nearby smaller N next to an unscoped universal is evidence of overclaim,
        # not a scope. Only SCOPED_RE binds the quantifier to N.
        rec = _finding(
            seq=seq,
            source=path,
            span=m.group(0),
            role=role,
            sentence=sent,
            scoped=scoped,
            denom=denom,
            locator=f"{path.as_posix()}:{_line_no(text, m.start())}",
        )
        rec["start"] = m.start()
        rec["end"] = m.end()
        findings.append(rec)
        seq += 1
    return findings


def scan_json(path: Path, obj: Any, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seq = 1
    for jpath, value in iter_json_strings(obj):
        base_role = path_role(jpath)
        parent: Any = obj
        cur: Any = obj
        for part in jpath[:-1]:
            if isinstance(cur, dict) and isinstance(part, str):
                cur = cur.get(part)
            elif isinstance(cur, list) and isinstance(part, int) and 0 <= part < len(cur):
                cur = cur[part]
            else:
                cur = None
                break
        parent = cur if isinstance(cur, dict) else {}
        _ = record_anchors(parent)
        for m in QUANT_RE.finditer(value):
            inner = classify_text_span(
                value, m.start(), m.end(), ignore_wrappers=ignore_wrappers
            )
            role = "MENTION" if base_role == "MENTION" or inner == "MENTION" else "USE"
            sent = _sentence(value, m.start(), m.end())
            scoped = bool(SCOPED_RE.search(sent))
            denom = [d.group(0) for d in DENOM_RE.finditer(sent)]
            rec = _finding(
                seq=seq,
                source=path,
                span=m.group(0),
                role=role,
                sentence=sent,
                scoped=scoped,
                denom=denom,
                locator=f"{path.as_posix()}#{'/'.join(str(p) for p in jpath)}",
            )
            rec["json_path"] = jpath
            findings.append(rec)
            seq += 1
    return findings


def scan_path(path: Path, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    sub = load_subject(path)
    if sub["kind"] == "json":
        return scan_json(path, sub["parsed"], ignore_wrappers=ignore_wrappers)
    return scan_text(path, sub["text"], ignore_wrappers=ignore_wrappers)
