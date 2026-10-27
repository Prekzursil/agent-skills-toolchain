#!/usr/bin/env python3
"""BLD-0031 confidence-band / evidence-tag classifier.

Two mechanically different scorers:

* lexicon — Sherman-Kent band tokens plus the catalog bare-hedge list
  (should work / looks fine / likely fine).
* modality — grammatical modals, future/uncertain register, and numeric
  (N-M%) ranges. Does not key off the hyphenated Sherman-Kent lexicon.

A band attached to a PAST measured fact is CATEGORY-ERROR, not COMPLIANT.
The citation idiom ``measured at path:line`` is an evidence tag, not a past fact.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SHERMAN_KENT = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)

CALIBRATED_BAND_RE = re.compile(
    r"\b(almost[-\s]certain|likely|roughly[-\s]even|unlikely|remote)\b"
    r"(?:\s*\(\s*(\d+)\s*[-–]\s*(\d+)\s*%\s*\))?",
    re.I,
)
RANGE_ONLY_RE = re.compile(r"\(\s*\d+\s*[-–]\s*\d+\s*%\s*\)")
BARE_HEDGE_RE = re.compile(r"\bshould work\b|\blooks fine\b|\blikely fine\b", re.I)
EVIDENCE_RE = re.compile(
    r"measured at\s+[A-Za-z0-9_./\\-]+(?:\.[A-Za-z0-9]+)?:\d+"
    r"|[A-Za-z0-9_./\\-]+\.(?:md|json|py|txt|yml|yaml):\d+"
    r"|sha256:[a-fA-F0-9]{64}",
    re.I,
)
MODAL_RE = re.compile(
    r"\b(should|will|would|may|might|could|expect(?:ed)? to|going to)\b",
    re.I,
)
HEDGE_WORD_RE = re.compile(r"\b(looks|seems|probably|appears)\b", re.I)
PAST_MEASURE_RE = re.compile(
    r"\b(measured|was measured|were measured|had measured)\b",
    re.I,
)
IMPERATIVE_RE = re.compile(
    r"^\s*(do not|don't|never|run |write |create |add |see |use |note:)\b",
    re.I,
)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
FLAGGED = frozenset(
    {"MISSING-BAND", "BARE-HEDGE", "BANDED-NO-EVIDENCE", "CATEGORY-ERROR"}
)
SKIP_NAMES = frozenset(
    {
        "WORK-UNIT-CATALOG.json",
        "SUBAGENT-RETURN.json",
        "UNIT-ARTIFACT-MANIFEST.json",
        "BLD-0031.json",
    }
)


def _canon_band(token: str) -> str:
    return re.sub(r"\s+", "-", token.strip().lower())


def evidence_span(text: str) -> str | None:
    m = EVIDENCE_RE.search(text)
    return m.group(0) if m else None


def strip_evidence(text: str) -> str:
    return EVIDENCE_RE.sub(" ", text)


def band_info(text: str) -> dict | None:
    m = CALIBRATED_BAND_RE.search(text)
    if not m:
        return None
    token = _canon_band(m.group(1))
    lo = int(m.group(2)) if m.group(2) else None
    hi = int(m.group(3)) if m.group(3) else None
    calibrated = lo is not None and hi is not None
    if token in {"almost-certain", "roughly-even"}:
        calibrated = True
    if lo is not None and hi is not None:
        calibrated = True
    return {
        "band": token,
        "lo": lo,
        "hi": hi,
        "calibrated": calibrated,
        "raw": m.group(0),
    }


def is_past_measured_fact(text: str) -> bool:
    stripped = strip_evidence(text)
    if not PAST_MEASURE_RE.search(stripped):
        return False
    if re.search(r"\bmeasured at\b", text, re.I) and not re.search(
        r"\bmeasured\b(?!\s+at\b)", stripped, re.I
    ):
        return False
    return True


def is_forward_or_uncertain(text: str, info: dict | None) -> bool:
    if BARE_HEDGE_RE.search(text):
        return True
    if MODAL_RE.search(text) or HEDGE_WORD_RE.search(text):
        return True
    if info and info.get("calibrated"):
        return True
    if info and info.get("band") == "likely":
        return True
    return False


def classify_lexicon(text: str) -> dict:
    """Primary scorer: Sherman-Kent lexicon + catalog bare hedges."""
    raw = " ".join(text.split())
    if len(raw) < 12 or IMPERATIVE_RE.match(raw):
        return {"class": "NOT-CLAIM", "method": "lexicon", "quote": raw}
    info = band_info(raw)
    ev = evidence_span(raw)
    if info and info.get("calibrated") and is_past_measured_fact(raw):
        klass = "CATEGORY-ERROR"
    elif info and info.get("calibrated") and ev:
        klass = "COMPLIANT"
    elif info and info.get("calibrated") and not ev:
        klass = "BANDED-NO-EVIDENCE"
    elif BARE_HEDGE_RE.search(raw):
        klass = "MISSING-BAND"
    elif is_forward_or_uncertain(raw, info) and not (info and info.get("calibrated")):
        klass = "MISSING-BAND"
    else:
        klass = "NOT-CLAIM"
    return {
        "class": klass,
        "method": "lexicon",
        "quote": raw,
        "band": None if not info else info.get("band"),
        "calibrated": bool(info and info.get("calibrated")),
        "evidence_tag": ev,
        "bare_hedge": bool(BARE_HEDGE_RE.search(raw)),
    }


def classify_modality(text: str) -> dict:
    """Independent scorer: modality + numeric ranges, not the Sherman-Kent list."""
    raw = " ".join(text.split())
    if len(raw) < 12 or IMPERATIVE_RE.match(raw):
        return {"class": "NOT-CLAIM", "method": "modality", "quote": raw}
    has_range = bool(RANGE_ONLY_RE.search(raw))
    ev = evidence_span(raw)
    past = is_past_measured_fact(raw)
    modal = bool(MODAL_RE.search(raw) or BARE_HEDGE_RE.search(raw) or HEDGE_WORD_RE.search(raw))
    if past and has_range:
        klass = "CATEGORY-ERROR"
    elif has_range and ev and not past:
        klass = "COMPLIANT"
    elif has_range and not ev:
        klass = "BANDED-NO-EVIDENCE"
    elif modal and not has_range:
        klass = "MISSING-BAND"
    else:
        klass = "NOT-CLAIM"
    return {
        "class": klass,
        "method": "modality",
        "quote": raw,
        "has_range": has_range,
        "evidence_tag": ev,
        "modal": modal,
    }


def split_sentences(para: str) -> list[str]:
    para = " ".join(para.split())
    if not para:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9*])", para)
    return [p.strip() for p in parts if p.strip()]


def units_from_markdown(text: str) -> list[tuple[int, str]]:
    text = CODE_FENCE_RE.sub("\n", text)
    out: list[tuple[int, str]] = []
    offset = 0
    for block in re.split(r"\n\s*\n", text):
        line_no = text[:offset].count("\n") + 1
        offset += len(block) + 2
        block = block.strip()
        if not block or block.startswith("<!--"):
            # keep the sentence AFTER an HTML control marker in the same block
            lines = [ln for ln in block.splitlines() if not ln.strip().startswith("<!--")]
            block = "\n".join(lines).strip()
            if not block:
                continue
        compact = " ".join(block.split())
        if CALIBRATED_BAND_RE.search(compact[:120]) or compact.startswith("**"):
            out.append((line_no, compact))
        else:
            for sent in split_sentences(block):
                out.append((line_no, sent))
    return out


def units_from_json(text: str) -> list[tuple[int, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return units_from_markdown(text)
    blobs: list[str] = []

    def walk(obj) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str) and len(obj) >= 40:
            blobs.append(obj)

    walk(data)
    out: list[tuple[int, str]] = []
    for blob in blobs:
        for sent in split_sentences(blob):
            # line is approximate: first occurrence in the file
            idx = text.find(sent[:40] if len(sent) > 40 else sent)
            line = text[:idx].count("\n") + 1 if idx >= 0 else 1
            out.append((line, sent))
    return out


def iter_corpus(repo: Path) -> Iterable[Path]:
    wave = repo / "command-center" / "p2-wave"
    for p in sorted(wave.glob("*.md")):
        yield p
    phase3 = repo / "command-center" / "phase3"
    if phase3.is_dir():
        for p in sorted(phase3.rglob("*.json")):
            if p.name not in SKIP_NAMES:
                yield p
    receipts = repo / "command-center" / "receipts"
    if receipts.is_dir():
        for p in sorted(receipts.glob("*.json")):
            if p.name not in SKIP_NAMES:
                yield p
    fixtures = Path(__file__).resolve().parent / "fixtures"
    for p in sorted(fixtures.glob("*.md")):
        yield p


def rel_to(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def scan_file(repo: Path, path: Path, method: str = "lexicon") -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        units = units_from_json(text)
    else:
        units = units_from_markdown(text)
    classify = classify_lexicon if method == "lexicon" else classify_modality
    rel = rel_to(repo, path)
    rows = []
    for line, unit in units:
        rec = classify(unit)
        rec["path"] = rel
        rec["line"] = int(line)
        rows.append(rec)
    return rows


def scan_corpus(repo: Path | None = None, method: str = "lexicon") -> list[dict]:
    root = repo or REPO
    rows: list[dict] = []
    seen = set()
    for path in iter_corpus(root):
        key = str(path.resolve())
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        rows.extend(scan_file(root, path, method=method))
    return rows


def load_sample20(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^S(\d{2})\s+(\S+)\s+\|\s+(.+)$", line.strip())
        if not m:
            continue
        rows.append(
            {
                "id": f"S{m.group(1)}",
                "expected": m.group(2),
                "text": m.group(3).strip(),
                "line": i,
            }
        )
    return rows


def control_sentences(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    blocks = re.split(r"<!--\s*BLD-0031:(CONTROL-[A-Z-]+)\s*-->", text)
    # split keeps markers: [pre, name, body, name, body, ...]
    for i in range(1, len(blocks), 2):
        name = blocks[i]
        body = blocks[i + 1]
        sent = " ".join(
            ln.strip()
            for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
        out[name] = sent
    return out


def flagged(rec: dict) -> bool:
    return rec.get("class") in FLAGGED
