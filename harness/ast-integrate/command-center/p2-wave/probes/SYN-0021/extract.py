"""Extract completion CLAIMs vs completion REQUIREMENTs (use-versus-mention)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID_RE = re.compile(r"\b([A-Z]{2,5}-\d{4})\b")
CLAIM_RE = re.compile(
    r"\b(is|are|was|were|has been|have been)\s+"
    r"(complete|done|shipped|closed|verified|delivered)\b",
    re.I,
)
REQUIREMENT_MARKERS = (
    "emitted only when",
    "is complete only when",
    "are complete only when",
    "must be complete",
    "must be done",
    "completion is required",
    "completion_sentinel",
    "a work unit is complete only",
    "a unit is complete only",
    "the shared 12-condition predicate",
)
SKIP_NAME = {
    "WORK-UNIT-CATALOG.json",
    "completion-census.schema.json",
    "SYN-0021.completion-census.json",
    "extract.py",
    "shared_judge.py",
    "census.py",
    "emit_census.py",
    "probe1_planted_and_mention.py",
    "probe2_shared_reducer.py",
    "write_receipts.py",
}
SKIP_DIR_PARTS = {"__pycache__", ".git"}


def classify_line(text: str) -> str:
    """Return CLAIM, REQUIREMENT, or NEITHER."""
    low = text.lower()
    if any(m in low for m in REQUIREMENT_MARKERS):
        return "REQUIREMENT"
    if re.search(r"\bonly when\b", low) and re.search(r"complete", low):
        return "REQUIREMENT"
    if CLAIM_RE.search(text):
        return "CLAIM"
    return "NEITHER"


def subject_of(text: str, fallback: str) -> str:
    found = UID_RE.findall(text)
    return found[0] if found else fallback


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def iter_scan_paths(repo: Path) -> Iterator[Path]:
    yield from sorted((HERE / "fixtures").glob("*"))
    probes = repo / "command-center/p2-wave/probes"
    if probes.is_dir():
        for p in sorted(probes.glob("*/SUBAGENT-RETURN.json")):
            if "SYN-0021" in p.parts:
                continue
            yield p
    receipts = repo / "command-center/receipts"
    if receipts.is_dir():
        yield from sorted(receipts.glob("*.json"))
    synthesis = repo / "command-center/synthesis"
    if synthesis.is_dir():
        for p in sorted(synthesis.glob("*.json")):
            if p.name == "SYN-0021.completion-census.json":
                continue
            yield p
    status = repo / "command-center/STATUS.md"
    if status.is_file():
        yield status
    events = repo / "command-center/events/EVENTS.jsonl"
    if events.is_file():
        yield events


def extract_markdown(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    rel = _rel(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return claims, mentions
    for i, line in enumerate(lines, 1):
        kind = classify_line(line)
        if kind == "NEITHER":
            continue
        row = {
            "id": f"{path.stem}:{i}",
            "text": line.strip(),
            "anchor": f"{rel}:{i}",
            "subject": subject_of(line, path.stem.upper()),
            "kind": kind,
            "source_kind": "markdown",
            "path": rel,
        }
        if kind == "CLAIM":
            claims.append(row)
        else:
            mentions.append(row)
    return claims, mentions


def is_native_receipt(doc: Any) -> bool:
    return (
        isinstance(doc, dict)
        and "min_bytes_threshold" in doc
        and isinstance(doc.get("artifacts"), list)
        and isinstance(doc.get("unit_id"), str)
    )


def extract_json(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    rel = _rel(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return claims, mentions
    if not isinstance(doc, dict):
        return claims, mentions

    if is_native_receipt(doc):
        uid = str(doc.get("unit_id"))
        state = str(doc.get("state") or "")
        text = (
            f"{uid} receipt asserts state={state} "
            f"with primary artifact claimed present."
        )
        line = 1
        raw = path.read_text(encoding="utf-8")
        idx = raw.find('"state"')
        if idx >= 0:
            line = raw[:idx].count("\n") + 1
        claims.append(
            {
                "id": f"receipt:{uid}",
                "text": text,
                "anchor": f"{rel}:{line}",
                "subject": uid,
                "kind": "CLAIM",
                "source_kind": "native-receipt",
                "path": rel,
                "receipt": doc,
            }
        )
        return claims, mentions

    uid = str(doc.get("unit_id") or doc.get("id") or "")
    state = str(doc.get("state") or "").upper()
    status = str(doc.get("status") or "").upper()
    sentinel = str(doc.get("sentinel") or "")
    completionish = (
        state in {"SUCCESS"}
        or status in {"DELIVERED"}
        or sentinel.startswith("SUCCESS:")
    )
    if uid and completionish:
        line = 1
        raw = path.read_text(encoding="utf-8")
        for key in ('"state"', '"status"', '"sentinel"'):
            idx = raw.find(key)
            if idx >= 0:
                line = raw[:idx].count("\n") + 1
                break
        text = (
            f"{uid} asserts completion "
            f"state={doc.get('state')!r} status={doc.get('status')!r}."
        )
        claims.append(
            {
                "id": f"return:{uid}:{path.name}",
                "text": text,
                "anchor": f"{rel}:{line}",
                "subject": uid,
                "kind": "CLAIM",
                "source_kind": "unit-return",
                "path": rel,
                "return_doc": doc,
            }
        )
    return claims, mentions


def census_body(doc: dict[str, Any]) -> dict[str, Any]:
    """Receipt envelope puts the census payload under report; probes accept both."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("claims") is not None or report.get("split") is not None
    ):
        return report
    return doc


def collect(repo: Path | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = repo or REPO
    claims: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []
    for path in iter_scan_paths(root):
        if path.name in SKIP_NAME or not path.is_file():
            continue
        if any(part in SKIP_DIR_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in {".md", ".txt", ".jsonl"}:
            c, m = extract_markdown(path)
        elif path.suffix.lower() == ".json":
            c, m = extract_json(path)
        else:
            continue
        claims.extend(c)
        mentions.extend(m)
    return claims, mentions
