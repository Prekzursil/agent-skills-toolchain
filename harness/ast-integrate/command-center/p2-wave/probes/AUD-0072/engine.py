#!/usr/bin/env python3
"""Conservative lexical mapper: Sherman-Kent bands + closed verdict vocab.

Whole-expression aliases only. Hedges such as "should work" are residue, never
silently assigned "likely". A mapper that maps every phrase has guessed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Iterator

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("AUD-0072: repo root not found")


REPO = repo_root()
PLANTED = HERE / "fixtures" / "planted-expressions.json"
OUT_REL = "command-center/audit/AUD-0072-confidence-status-normalization.json"
CATALOG_SCHEMA_REL = "command-center/schema/claim-record.schema.json"
LIVE_CLAIM_SCHEMA_REL = "command-center/phase4/contracts/ARC-0085.json"
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0072 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)

BANDS = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)
STATUSES = (
    "CONFIRMED",
    "REFUTED",
    "PARTIAL",
    "NOT-CHECKED",
    "BLOCKED",
    "UNVERIFIED",
)

# Whole-expression aliases. No substring guessing.
BAND_ALIASES: dict[str, str] = {
    "almost-certain": "almost-certain",
    "almostcertain": "almost-certain",
    "almost-certainly": "almost-certain",
    "likely": "likely",
    "roughly-even": "roughly-even",
    "roughlyeven": "roughly-even",
    "even-chance": "roughly-even",
    "evenchance": "roughly-even",
    "unlikely": "unlikely",
    "remote": "remote",
    "almost-no-chance": "remote",
    "almostnochance": "remote",
}
STATUS_ALIASES: dict[str, str] = {
    "confirmed": "CONFIRMED",
    "refuted": "REFUTED",
    "partial": "PARTIAL",
    "not-checked": "NOT-CHECKED",
    "notchecked": "NOT-CHECKED",
    "blocked": "BLOCKED",
    "unverified": "UNVERIFIED",
}

# Locked residue: never receive a band, even when they contain a band word.
RESIDUE_LOCK = (
    "should work",
    "looks fine",
    "likely fine",
    "should be fine",
    "looks good",
    "pretty sure",
    "i think",
    "we think",
    "high confidence",
    "medium confidence",
    "low confidence",
    "very likely",
    "highly likely",
    "fairly certain",
    "probably",
    "maybe",
    "seems fine",
    "should be ok",
    "should be okay",
)
SKIP_STATUS_VALUES = frozenset(
    {
        "PASS",
        "FAIL",
        "NOT-RUN",
        "NOT-REVIEWED",
        "SUCCESS",
        "FAILED",
        "TIMEOUT",
        "SEVERED",
        "DELIVERED",
        "READY",
    }
)
CONF_KEYS = frozenset(
    {
        "confidence",
        "confidence_band",
        "sherman_kent_band",
        "band",
        "nonstandard_confidence",
        "numeric_confidence",
    }
)
STATUS_KEYS = frozenset({"verification_status", "verdict", "canonical_status"})
TEXT_KEYS = frozenset(
    {
        "statement",
        "claim",
        "canonical_mechanism",
        "question",
        "answer",
        "residual_caveat",
        "notes",
        "text",
        "bare_control_sentence",
        "planted_hedges",
        "spaced_band_aliases",
    }
)
SKIP_DIR_PARTS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        "AUD-0072",
    }
)

_WS = re.compile(r"[\s_]+")
_PAREN_PCT = re.compile(r"-\([^)]*\d[^)]*%?\)\s*$")
_WORDY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\- %();]*")


def norm_key(phrase: str) -> str:
    s = " ".join(str(phrase).strip().lower().split())
    s = s.replace("—", "-").replace("–", "-")
    s = _WS.sub("-", s).strip("-")
    s = _PAREN_PCT.sub("", s)
    return s


def lock_key(phrase: str) -> str:
    return " ".join(str(phrase).strip().lower().split())


def map_band(phrase: str) -> str | None:
    raw = str(phrase).strip()
    if not raw:
        return None
    if lock_key(raw) in RESIDUE_LOCK or norm_key(raw) in {norm_key(p) for p in RESIDUE_LOCK}:
        return None
    return BAND_ALIASES.get(norm_key(raw))


def map_status(phrase: str) -> str | None:
    raw = str(phrase).strip()
    if not raw:
        return None
    key = norm_key(raw)
    if key in {norm_key(p) for p in RESIDUE_LOCK} or lock_key(raw) in RESIDUE_LOCK:
        return None
    return STATUS_ALIASES.get(key)


def phrase_kind(field: str) -> str:
    if field in STATUS_KEYS or field == "status-token":
        return "status"
    return "confidence"


def _line_of(text: str, needle: str) -> int:
    if not needle:
        return 1
    idx = text.find(needle)
    if idx < 0:
        idx = text.lower().find(str(needle).lower())
    if idx < 0:
        return 1
    return text.count("\n", 0, idx) + 1


def iter_json_nodes(obj: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}"
            yield child, v
            yield from iter_json_nodes(v, child)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{path}[{i}]"
            yield child, v
            yield from iter_json_nodes(v, child)


def _hedge_needles() -> list[str]:
    # Do not text-scan bare "likely"/"remote"/"blocked": those are English words.
    # Whole-value JSON fields still capture them as confidence/status expressions.
    items = list(RESIDUE_LOCK) + [
        "almost certain",
        "almost-certain",
        "almost certainly",
        "roughly even",
        "roughly-even",
        "even chance",
        "even-chance",
        "almost no chance",
        "almost-no-chance",
        "not-checked",
        "not checked",
    ]
    items.extend(STATUSES)
    # longest first, then stable
    uniq = []
    seen = set()
    for p in items:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    uniq.sort(key=lambda s: (-len(s), s.lower()))
    return uniq


_NEEDLES = _hedge_needles()


def scan_text(text: str, rel: str, field: str) -> list[dict]:
    rows: list[dict] = []
    low = text.lower()
    occupied = [False] * len(text)
    for needle in _NEEDLES:
        nlow = needle.lower()
        start = 0
        while True:
            at = low.find(nlow, start)
            if at < 0:
                break
            end = at + len(needle)
            start = at + 1
            if any(occupied[at:end]):
                continue
            # require a break at edges so "likely" does not eat "unlikely"
            left_ok = at == 0 or not low[at - 1].isalnum()
            right_ok = end >= len(low) or not low[end].isalnum()
            if not left_ok or not right_ok:
                continue
            for i in range(at, end):
                occupied[i] = True
            excerpt = text[at:end]
            if map_status(excerpt) and map_band(excerpt) is None:
                kind = "status"
            else:
                kind = "confidence"
            rows.append(
                {
                    "phrase": excerpt,
                    "field": field,
                    "kind": kind,
                    "path": rel,
                    "line": text.count("\n", 0, at) + 1,
                    "source": "text-scan",
                }
            )
    return rows


def _record(phrase: Any, rel: str, field: str, line: int, source: str, kind: str) -> dict:
    if isinstance(phrase, bool):
        text = "true" if phrase else "false"
        kind = "confidence"
    elif isinstance(phrase, (int, float)):
        text = repr(phrase) if isinstance(phrase, float) else str(phrase)
        kind = "confidence"
    else:
        text = str(phrase).strip()
    return {
        "phrase": text,
        "field": field,
        "kind": kind,
        "path": rel,
        "line": line,
        "source": source,
    }


def extract_from_json_obj(obj: Any, rel: str, raw: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, int]] = set()

    def add(row: dict) -> None:
        key = (row["phrase"], row["path"], int(row["line"]))
        if not row["phrase"] or key in seen:
            return
        seen.add(key)
        rows.append(row)

    for jpath, val in iter_json_nodes(obj):
        field = jpath.rsplit(".", 1)[-1]
        field = re.sub(r"\[\d+\]$", "", field)
        if field in CONF_KEYS:
            if isinstance(val, (str, int, float)) and not isinstance(val, bool):
                add(
                    _record(
                        val,
                        rel,
                        field,
                        _line_of(raw, str(val)[:80]),
                        "json-field",
                        "confidence",
                    )
                )
        elif field in STATUS_KEYS:
            if isinstance(val, str) and val.strip().upper() not in SKIP_STATUS_VALUES:
                add(
                    _record(
                        val,
                        rel,
                        field,
                        _line_of(raw, val[:80]),
                        "json-field",
                        "status",
                    )
                )
        elif field in {
            "canonical_bands",
            "planted_hedges",
            "spaced_band_aliases",
        } and isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    add(
                        _record(
                            item,
                            rel,
                            field,
                            _line_of(raw, item),
                            "json-field",
                            "confidence",
                        )
                    )
        elif field in TEXT_KEYS:
            if isinstance(val, str) and len(val) >= 8:
                for row in scan_text(val, rel, field):
                    add(row)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        for row in scan_text(item, rel, field):
                            add(row)
        elif field == "sherman_kent" and isinstance(val, list):
            continue
        elif field == "canonical_status" and isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    add(
                        _record(
                            item,
                            rel,
                            "canonical_status",
                            _line_of(raw, item),
                            "json-field",
                            "status",
                        )
                    )
        elif field == "enum" and isinstance(val, list):
            parent_l = jpath.lower()
            if any(
                tok in parent_l
                for tok in (
                    "sherman",
                    "confidence",
                    "verdict",
                    "verification",
                    "confidence_band",
                )
            ):
                kind = (
                    "status"
                    if any(tok in parent_l for tok in ("verdict", "verification"))
                    else "confidence"
                )
                for item in val:
                    if isinstance(item, str):
                        add(
                            _record(
                                item,
                                rel,
                                "enum",
                                _line_of(raw, item),
                                "json-field",
                                kind,
                            )
                        )
    return rows


def corpus_files() -> list[Path]:
    roots = [
        REPO / "command-center" / "receipts",
        REPO / "command-center" / "research",
        REPO / "command-center" / "confirmation",
        REPO / "command-center" / "phase3",
        REPO / "command-center" / "phase4" / "contracts",
        REPO / "command-center" / "schema",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_PARTS for part in p.parts):
                continue
            if p.suffix.lower() not in {".json", ".md"}:
                continue
            if p.name in {"UNIT-ARTIFACT-MANIFEST.json", "SUBAGENT-RETURN.json"}:
                continue
            if p.name.startswith("AUD-0072-"):
                continue
            try:
                if p.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            files.append(p)
    extras = [
        PLANTED,
        REPO / "command-center" / "p2-wave" / "P2-BUILD-ROUND1.md",
        REPO / "command-center" / "p2-wave" / "probes" / "ARC-0085" / "fixtures" / "encoded-claims.json",
    ]
    for p in extras:
        if p.is_file() and p not in files:
            files.append(p)
    files.sort()
    return files


def extract_all() -> list[dict]:
    rows: list[dict] = []
    for path in corpus_files():
        rel = path.relative_to(REPO).as_posix()
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if path.suffix.lower() == ".json":
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                for row in scan_text(raw, rel, "file"):
                    rows.append(row)
                continue
            rows.extend(extract_from_json_obj(obj, rel, raw))
        else:
            rows.extend(scan_text(raw, rel, "file"))
    return rows


def classify(row: dict) -> dict:
    phrase = str(row.get("phrase") or "")
    kind = str(row.get("kind") or "confidence")
    out = dict(row)
    if kind == "status":
        mapped = map_status(phrase)
        out["mapped"] = mapped is not None
        out["status"] = mapped
        out["band"] = None
        if mapped is None:
            out["residue_reason"] = "status-unmapped"
        else:
            out["residue_reason"] = None
        return out
    mapped = map_band(phrase)
    status_also = map_status(phrase)
    if mapped is not None:
        out["mapped"] = True
        out["band"] = mapped
        out["status"] = None
        out["residue_reason"] = None
        return out
    if status_also is not None and kind != "confidence":
        out["mapped"] = True
        out["band"] = None
        out["status"] = status_also
        out["residue_reason"] = None
        out["kind"] = "status"
        return out
    out["mapped"] = False
    out["band"] = None
    out["status"] = None
    if lock_key(phrase) in RESIDUE_LOCK:
        out["residue_reason"] = "hedge-locked"
    elif isinstance(row.get("phrase"), str) and _looks_numeric(phrase):
        out["residue_reason"] = "numeric-not-a-band"
    else:
        out["residue_reason"] = "no-lexical-alias"
    return out


def _looks_numeric(phrase: str) -> bool:
    s = phrase.strip()
    try:
        float(s)
        return True
    except ValueError:
        return False


def normalize(rows: Iterable[dict] | None = None) -> dict:
    expressions = [classify(r) for r in (rows if rows is not None else extract_all())]
    mapped = [e for e in expressions if e.get("mapped")]
    residue = [e for e in expressions if not e.get("mapped")]
    band_counts: dict[str, int] = {b: 0 for b in BANDS}
    status_counts: dict[str, int] = {s: 0 for s in STATUSES}
    for e in mapped:
        if e.get("band") in band_counts:
            band_counts[str(e["band"])] += 1
        if e.get("status") in status_counts:
            status_counts[str(e["status"])] += 1
    unique_mapped = sorted({e["phrase"] for e in mapped})
    unique_residue = sorted({e["phrase"] for e in residue})
    return {
        "expression_count": len(expressions),
        "mapped_count": len(mapped),
        "residue_count": len(residue),
        "unique_mapped_phrases": unique_mapped,
        "unique_residue_phrases": unique_residue,
        "band_counts": band_counts,
        "status_counts": status_counts,
        "expressions": expressions,
    }


def should_work_in_residue(result: dict) -> bool:
    for e in result.get("expressions") or []:
        if lock_key(e.get("phrase") or "") == "should work":
            if e.get("band") == "likely":
                return False
            return not e.get("mapped")
    return False


def greedy_wrong_map(phrase: str) -> str | None:
    """Detector control: a guesser that assigns likely to any hedge containing should/likely."""
    low = lock_key(phrase)
    if "should" in low or "likely" in low or "looks" in low:
        return "likely"
    return map_band(phrase)
