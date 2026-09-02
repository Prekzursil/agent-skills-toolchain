"""Two mechanically different extractors for sampled/representative claims.

Line regex walks catalog text (anchors at path:line). JSON walk reads
work_unit string fields. Coverage requires every walk hit to appear in the
audit (located) or the unlocated list.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

LINE_RE = re.compile(
    r"stratified sample|representative subset|representative sample|"
    r"sampled measurement|sampled error rate|convenience sample|"
    r"sample of \d+|28 of 60|\d+ of \d+ CI-declared",
    re.IGNORECASE,
)

WALK_RE = re.compile(
    r"stratified sample|representative subset|representative sample|"
    r"sampled measurement|sampled error|convenience sample|"
    r"sample of \d+|28 of 60|\d+ of \d+ CI",
    re.IGNORECASE,
)

SKIP_KEYS = {
    "failure_classification",
    "assigned_model_vendor_role",
    "tool_permissions",
    "completion_sentinel",
    "_source_slice_file",
    "output_schema",
    "output_path",
    "retry_policy",
    "execution_substrate",
}

ID_RE = re.compile(r'"id": "(?P<uid>[A-Z]{2,5}-\d{4})"')


def _snippet(text: str, start: int, end: int, width: int = 160) -> str:
    lo = max(0, start - 40)
    hi = min(len(text), end + width)
    return " ".join(text[lo:hi].split())


def scan_lines(path: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if not path.is_file():
        return hits
    lines = path.read_text(encoding="utf-8").splitlines()
    last_uid = None
    rel = path.relative_to(REPO).as_posix()
    for i, line in enumerate(lines, 1):
        m_id = ID_RE.search(line)
        if m_id:
            last_uid = m_id.group("uid")
        if "sampling-error" in line or "sampling-statistician" in line:
            continue
        for m in LINE_RE.finditer(line):
            hits.append(
                {
                    "path": rel,
                    "line": i,
                    "unit_id": last_uid,
                    "match": m.group(0),
                    "snippet": _snippet(line, m.start(), m.end()),
                    "extractor": "line-regex",
                }
            )
    return hits


def _walk_strings(obj: Any, skip: Iterable[str]) -> Iterable[str]:
    skip_set = set(skip)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_set:
                continue
            yield from _walk_strings(v, skip)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item, skip)
    elif isinstance(obj, str):
        yield obj


def scan_catalog_units() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if not CATALOG.is_file():
        return hits
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    rel = CATALOG.relative_to(REPO).as_posix()
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = unit.get("id")
        blob = "\n".join(_walk_strings(unit, SKIP_KEYS))
        seen: set[str] = set()
        for m in WALK_RE.finditer(blob):
            key = m.group(0).lower()
            span = blob[max(0, m.start() - 20) : m.end() + 120]
            fingerprint = f"{uid}:{key}:{span[:80]}"
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            hits.append(
                {
                    "path": rel,
                    "line": None,
                    "unit_id": uid,
                    "match": m.group(0),
                    "snippet": " ".join(span.split()),
                    "extractor": "json-walk",
                }
            )
    return hits


def coverage_key(hit: dict[str, Any]) -> str:
    uid = hit.get("unit_id") or "NO-UNIT"
    match = str(hit.get("match") or "").lower()
    path = str(hit.get("path") or "")
    return f"{path}|{uid}|{match}"


def extra_corpus_files() -> list[Path]:
    extras = [
        REPO / "command-center" / "BASELINE-SNAPSHOT.json",
        REPO / "command-center" / "CLAIM-REGISTRY.json",
    ]
    receipts = REPO / "command-center" / "receipts"
    if receipts.is_dir():
        extras.extend(sorted(receipts.glob("*.json")))
    confirmation = REPO / "command-center" / "confirmation"
    if confirmation.is_dir():
        extras.extend(sorted(confirmation.rglob("*.json")))
    audit = REPO / "command-center" / "audit"
    if audit.is_dir():
        extras.extend(sorted(audit.rglob("*.json")))
    return [p for p in extras if p.is_file() and p.name != "BLD-0062.json"]


def scan_all() -> dict[str, list[dict[str, Any]]]:
    line_hits = scan_lines(CATALOG)
    for extra in extra_corpus_files():
        line_hits.extend(scan_lines(extra))
    walk_hits = scan_catalog_units()
    return {"line": line_hits, "walk": walk_hits}
