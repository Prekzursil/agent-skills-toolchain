"""SYN-0014 unsupported-certainty lens: band/hedge in USE voice with no anchor."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from role import (
    anchors_in_text,
    classify_text_span,
    iter_json_strings,
    load_subject,
    path_role,
    record_anchors,
)

LENS_ID = "SYN-0014"

DECLARED_FIVE: list[tuple[str, re.Pattern[str]]] = [
    ("almost-certain", re.compile(r"almost[\s-]+certain", re.I)),
    ("likely", re.compile(r"\blikely\b", re.I)),
    ("roughly-even", re.compile(r"roughly[\s-]+even", re.I)),
    ("unlikely", re.compile(r"\bunlikely\b", re.I)),
    ("remote", re.compile(r"\bremote(?:\s+(?:chance|probability|likelihood))?\b", re.I)),
]

UNKNOWN_HEDGES: list[tuple[str, re.Pattern[str]]] = [
    ("should-work", re.compile(r"should work", re.I)),
    ("looks-fine", re.compile(r"looks fine", re.I)),
    ("likely-fine", re.compile(r"likely fine", re.I)),
    ("definitely", re.compile(r"\bdefinitely\b", re.I)),
    ("guaranteed", re.compile(r"\bguaranteed\b", re.I)),
]


def _overlaps(a: int, b: int, ranges: list[tuple[int, int]]) -> bool:
    for x, y in ranges:
        if a < y and b > x:
            return True
    return False


def _iter_matches(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    taken: list[tuple[int, int]] = []
    for vocab, group in (("unknown-hedge", UNKNOWN_HEDGES), ("declared-five", DECLARED_FIVE)):
        for name, cre in group:
            for m in cre.finditer(text):
                if _overlaps(m.start(), m.end(), taken):
                    continue
                taken.append((m.start(), m.end()))
                hits.append(
                    {
                        "band_or_hedge": name,
                        "band_vocabulary": vocab,
                        "span": m.group(0),
                        "start": m.start(),
                        "end": m.end(),
                    }
                )
    hits.sort(key=lambda h: h["start"])
    return hits


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _finding(
    *,
    seq: int,
    source: Path,
    span: str,
    role: str,
    band: str,
    vocab: str,
    anchors: list[str],
    locator: str,
    reason: str,
) -> dict[str, Any]:
    use = role == "USE"
    unsupported = use and not anchors
    return {
        "id": f"SYN-0014-F{seq:03d}",
        "lens": LENS_ID,
        "kind": "unsupported-certainty",
        "use_or_mention": role if role in {"USE", "MENTION"} else "USE",
        "counted_as_defect": bool(unsupported),
        "span": span,
        "band_or_hedge": band,
        "band_vocabulary": vocab,
        "anchors": anchors,
        "source_path": source.as_posix(),
        "source_locator": locator,
        "reason": reason,
    }


def scan_text(path: Path, text: str, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seq = 1
    for hit in _iter_matches(text):
        role = classify_text_span(
            text, hit["start"], hit["end"], ignore_wrappers=ignore_wrappers
        )
        if role == "ABSENT":
            continue
        window_a = max(0, hit["start"] - 180)
        window_b = min(len(text), hit["end"] + 180)
        anchors = anchors_in_text(text[window_a:window_b])
        line = _line_no(text, hit["start"])
        if role == "MENTION":
            reason = "certainty text is quoted/fenced (MENTION); not counted as a defect"
        elif anchors:
            reason = "band/hedge is paired with a nearby evidence anchor"
        else:
            reason = "certainty band or hedge asserted in USE voice with empty nearby anchor set"
        rec = _finding(
            seq=seq,
            source=path,
            span=hit["span"],
            role=role,
            band=hit["band_or_hedge"],
            vocab=hit["band_vocabulary"],
            anchors=anchors,
            locator=f"{path.as_posix()}:{line}",
            reason=reason,
        )
        rec["start"] = hit["start"]
        rec["end"] = hit["end"]
        findings.append(rec)
        seq += 1
    return findings


def scan_json(path: Path, obj: Any, text: str, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seq = 1
    for jpath, value in iter_json_strings(obj):
        base_role = path_role(jpath)
        parent = obj
        # Walk to parent dict for structured anchors.
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
        struct_anchors = record_anchors(parent)
        for hit in _iter_matches(value):
            inner_role = classify_text_span(
                value, hit["start"], hit["end"], ignore_wrappers=ignore_wrappers
            )
            if base_role == "MENTION" or inner_role == "MENTION":
                role = "MENTION"
            else:
                role = "USE" if inner_role != "ABSENT" else "USE"
            anchors = list(struct_anchors) + anchors_in_text(value)
            if role == "MENTION":
                reason = "certainty text sits in a mention/quote field or wrapper"
            elif anchors:
                reason = "band/hedge is paired with record or in-string anchors"
            else:
                reason = "certainty band or hedge asserted in USE voice with empty anchor set"
            rec = _finding(
                seq=seq,
                source=path,
                span=hit["span"],
                role=role,
                band=hit["band_or_hedge"],
                vocab=hit["band_vocabulary"],
                anchors=anchors,
                locator=f"{path.as_posix()}#{'/'.join(str(p) for p in jpath)}",
                reason=reason,
            )
            rec["json_path"] = jpath
            findings.append(rec)
            seq += 1
    return findings


def scan_path(path: Path, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    sub = load_subject(path)
    rel = Path(path)
    if sub["kind"] == "json":
        return scan_json(rel, sub["parsed"], sub["text"], ignore_wrappers=ignore_wrappers)
    return scan_text(rel, sub["text"], ignore_wrappers=ignore_wrappers)
