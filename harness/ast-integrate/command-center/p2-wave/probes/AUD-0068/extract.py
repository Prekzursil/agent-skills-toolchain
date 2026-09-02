"""Map each heading and verdict-tagged sentence to a claim record or NOT-A-CLAIM."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from contract import (
    CONTRACT_29,
    FIXTURE_CORPUS,
    P2,
    PLANTED_TOKEN,
    REPO,
    SCHEMA_STATUS,
    STRUCTURAL_HEADINGS,
    UNIT,
    find_live,
    live_roots_present,
)
from spans import enumerate_file

CLAIM_ID_SAFE = re.compile(r"[^A-Za-z0-9._:-]+")


def coverage_key(span: dict[str, Any]) -> str:
    return f"{span['path']}:{span['line']}:{span['kind']}"


def _stem_id(name: str) -> str:
    return CLAIM_ID_SAFE.sub("-", name).strip("-")


def _is_structural_heading(text: str, filename: str) -> tuple[bool, str]:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    if norm in STRUCTURAL_HEADINGS:
        return True, f"structural-heading:{norm.replace(' ', '-')}"
    fname = filename.lower()
    if norm == fname or norm == Path(filename).stem.lower():
        return True, "structural-heading:document-title"
    if norm.rstrip(".") == fname:
        return True, "structural-heading:document-title"
    return False, ""


def classify_span(span: dict[str, Any], filename: str) -> dict[str, Any]:
    if span["kind"] == "heading":
        structural, reason = _is_structural_heading(span["text"], filename)
        if structural:
            return {"decision": "NOT-A-CLAIM", "reason": reason}
        return {"decision": "CLAIM", "reason": "material-heading"}
    tags = list(span.get("tags") or [])
    distinct = {t.upper() for t in tags}
    if len(distinct) >= 3:
        return {"decision": "NOT-A-CLAIM", "reason": "vocab-mention"}
    if not tags:
        return {"decision": "NOT-A-CLAIM", "reason": "verdict-token-absent"}
    return {
        "decision": "CLAIM",
        "reason": "verdict-tagged-sentence",
        "tag": tags[0].upper(),
    }


def _mechanism(span: dict[str, Any], following: str) -> str:
    if span["kind"] == "heading":
        body = following.strip() or span["text"]
        mech = f"Material heading {span['text']} asserts: {body}"
    else:
        mech = span["text"].strip()
    if len(mech) < 16:
        mech = (mech + " — extracted as a Prompt-One corpus claim span.").strip()
    return mech[:2000]


def _following_line(path: Path, line_no: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split(
        "\n"
    )
    for i in range(line_no, min(len(lines), line_no + 6)):
        raw = lines[i].strip()
        if not raw or raw.startswith("#") or raw.startswith("- "):
            continue
        if raw.startswith("{") or raw.startswith("}"):
            continue
        return raw
    return ""


def _confidence(tag: str | None) -> str:
    if tag in {"CONFIRMED", "REFUTED", "VERIFIED"}:
        return "high"
    if tag in {"PARTIAL", "CONTESTED"}:
        return "medium"
    if tag in {"NOT-CHECKED", "UNVERIFIED", "BLOCKED"}:
        return "unknown"
    return "medium"


def _impact(tag: str | None) -> str:
    if tag in {"CONFIRMED", "REFUTED", "VERIFIED"}:
        return "correctness"
    if tag in {"NOT-CHECKED", "UNVERIFIED"}:
        return "observability"
    return "none"


def make_record(span: dict[str, Any], cls: dict[str, Any], src_path: Path) -> dict[str, Any]:
    filename = Path(span["path"]).name
    tag = cls.get("tag")
    status = SCHEMA_STATUS.get(tag or "", "UNVERIFIED")
    cid = f"{UNIT}-{_stem_id(filename)}-{span['kind'][0].upper()}-{span['line']}"
    following = _following_line(src_path, span["line"]) if span["kind"] == "heading" else ""
    rec = {
        "claim_id": cid,
        "canonical_mechanism": _mechanism(span, following),
        "duplicate_of": [],
        "support": [],
        "contradiction": [],
        "source_lineage": [
            {
                "path": span["path"],
                "line": int(span["line"]),
                "snippet": span["snippet"],
            }
        ],
        "confidence": _confidence(tag),
        "verification_status": status,
        "implementation_impact": _impact(tag),
        "settling_probe": {"id": f"{cid}-reverse-trace", "command": P2},
        "schema_version": "0.1.0-provisional",
        "extension_points": {
            "span_kind": span["kind"],
            "classify_reason": cls["reason"],
            "source_tag": tag,
            "covers": [span["kind"]],
        },
    }
    return rec


def make_not_a_claim(span: dict[str, Any], cls: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "NOT-A-CLAIM",
        "reason": cls["reason"],
        "path": span["path"],
        "line": int(span["line"]),
        "kind": span["kind"],
        "snippet": span["snippet"],
        "covers": [span["kind"]],
    }


def extract_path(path: Path, rel: str) -> dict[str, Any]:
    spans = enumerate_file(path, rel)
    filename = path.name
    records: list[dict[str, Any]] = []
    not_a_claim: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for span in spans:
        cls = classify_span(span, filename)
        key = coverage_key(span)
        if cls["decision"] == "CLAIM":
            rec = make_record(span, cls, path)
            records.append(rec)
            index[key] = {
                "decision": "CLAIM",
                "claim_id": rec["claim_id"],
                "reason": cls["reason"],
            }
        else:
            nac = make_not_a_claim(span, cls)
            not_a_claim.append(nac)
            index[key] = {
                "decision": "NOT-A-CLAIM",
                "reason": cls["reason"],
            }
    return {
        "spans": spans,
        "records": records,
        "not_a_claim": not_a_claim,
        "coverage_index": index,
        "rel": rel,
        "path": str(path),
        "empty": len(spans) == 0,
    }


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_corpus() -> dict[str, Any]:
    live = live_roots_present()
    files: list[dict[str, Any]] = []
    unread: list[str] = []
    for name in CONTRACT_29:
        live_path = find_live(name)
        if live_path is not None:
            files.append(
                {
                    "name": name,
                    "tree": "live",
                    "path": repo_rel(live_path),
                    "abs": str(live_path.resolve()),
                }
            )
        else:
            unread.append(name)
            fx = FIXTURE_CORPUS / name
            files.append(
                {
                    "name": name,
                    "tree": "fixture",
                    "path": repo_rel(fx) if fx.is_file() else f"MISSING:{name}",
                    "abs": str(fx),
                    "present": fx.is_file(),
                }
            )
    return {
        "live_roots": live,
        "live_present": bool(live),
        "files": files,
        "live_unread": unread,
        "contract_n": len(CONTRACT_29),
        "fixture_substituted_n": sum(1 for f in files if f["tree"] == "fixture"),
        "live_read_n": sum(1 for f in files if f["tree"] == "live"),
    }


def extract_corpus(files: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    not_a_claim: list[dict[str, Any]] = []
    coverage_index: dict[str, dict[str, Any]] = {}
    per_file: list[dict[str, Any]] = []
    dropped_empty: list[str] = []
    for item in files:
        path = Path(item["abs"])
        rel = item["path"]
        if not path.is_file():
            dropped_empty.append(item["name"])
            per_file.append(
                {
                    "name": item["name"],
                    "tree": item["tree"],
                    "path": rel,
                    "span_n": 0,
                    "record_n": 0,
                    "not_a_claim_n": 0,
                    "missing": True,
                }
            )
            continue
        result = extract_path(path, rel)
        if result["empty"]:
            dropped_empty.append(item["name"])
            nac = {
                "decision": "NOT-A-CLAIM",
                "reason": "empty-source-no-heading-or-verdict-span",
                "path": rel,
                "line": 1,
                "kind": "file",
                "snippet": path.name,
                "covers": ["file"],
            }
            not_a_claim.append(nac)
        records.extend(result["records"])
        not_a_claim.extend(result["not_a_claim"])
        coverage_index.update(result["coverage_index"])
        per_file.append(
            {
                "name": item["name"],
                "tree": item["tree"],
                "path": rel,
                "span_n": len(result["spans"]),
                "record_n": len(result["records"]),
                "not_a_claim_n": len(result["not_a_claim"]),
                "missing": False,
            }
        )
    planted_in_corpus = False
    for rec in records:
        blob = " ".join(
            [
                str(rec.get("canonical_mechanism") or ""),
                str((rec.get("source_lineage") or [{}])[0].get("snippet") or ""),
            ]
        )
        if PLANTED_TOKEN in blob:
            planted_in_corpus = True
            break
    return {
        "records": records,
        "not_a_claim": not_a_claim,
        "coverage_index": coverage_index,
        "per_file": per_file,
        "dropped_empty": dropped_empty,
        "planted_in_unmodified_corpus": planted_in_corpus,
        "span_n": sum(p["span_n"] for p in per_file),
        "record_n": len(records),
        "not_a_claim_n": len(not_a_claim),
    }
