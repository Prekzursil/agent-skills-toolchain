"""Load first-order meta-review findings for SYN-0039.

Live SYN-0014..SYN-0027 artifacts are used when present. Absent artifacts
are not invented: the catalog declaration is reviewed as a stand-in and
labelled catalog-declared. Planted fixtures always join the corpus.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SUBJECT_IDS = [f"SYN-{n:04d}" for n in range(14, 28)]
PATH_RE = re.compile(
    r"(?:command-center|rules|tools)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+"
)
CLAIM_KEYS = (
    "claim",
    "statement",
    "finding",
    "question",
    "question_or_target",
    "title",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_by_id() -> dict[str, dict]:
    data = _read_json(CATALOG)
    out: dict[str, dict] = {}
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def _as_paths(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.extend(PATH_RE.findall(value.replace("\\", "/")))
        compact = value.replace("\\", "/").strip()
        if "/" in compact and " " not in compact and "." in compact.split("/")[-1]:
            found.append(compact)
    elif isinstance(value, list):
        for item in value:
            found.extend(_as_paths(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_as_paths(item))
    ordered: list[str] = []
    seen: set[str] = set()
    for path in found:
        rel = path.lstrip("./")
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def _claim_of(item: dict) -> str:
    for key in CLAIM_KEYS:
        val = item.get(key)
        if isinstance(val, str) and len(val.strip()) >= 8:
            return val.strip()
    return ""


def _finding(
    *,
    fid: str,
    source_unit: str,
    claim: str,
    cited_paths: list[str],
    evidence_text: str,
    remedy: str,
    kind: str,
    live_present: bool,
) -> dict[str, Any]:
    return {
        "id": fid,
        "source_unit": source_unit,
        "claim": claim,
        "cited_paths": cited_paths,
        "evidence_text": evidence_text,
        "remedy": remedy,
        "kind": kind,
        "live_present": live_present,
    }


def _extract_live(uid: str, doc: Any, output_rel: str) -> list[dict[str, Any]]:
    if not isinstance(doc, dict):
        return []
    found: list[dict[str, Any]] = []
    for key in ("findings", "meta_findings", "claims", "cases", "items", "lenses"):
        arr = doc.get(key)
        if not isinstance(arr, list):
            continue
        for i, item in enumerate(arr):
            if not isinstance(item, dict):
                continue
            claim = _claim_of(item)
            if not claim:
                continue
            paths = _as_paths(item.get("cited_paths") or item.get("anchors") or [])
            for field in ("path", "anchor", "source_path", "evidence_path"):
                if item.get(field):
                    paths.extend(_as_paths(item.get(field)))
            paths.extend(_as_paths(output_rel))
            found.append(
                _finding(
                    fid=f"{uid}::live::{item.get('id', i)}",
                    source_unit=uid,
                    claim=claim,
                    cited_paths=paths,
                    evidence_text=str(
                        item.get("evidence")
                        or item.get("evidence_text")
                        or item.get("evidence_requirement")
                        or ""
                    ),
                    remedy=str(
                        item.get("remedy")
                        or item.get("required_fix")
                        or item.get("rewrite")
                        or ""
                    ),
                    kind="live-artifact",
                    live_present=True,
                )
            )
    if found:
        return found
    claim = _claim_of(doc) or f"{uid} live artifact present but listed no findings"
    return [
        _finding(
            fid=f"{uid}::live::artifact",
            source_unit=uid,
            claim=claim,
            cited_paths=_as_paths(output_rel) + _as_paths(doc),
            evidence_text=str(doc.get("evidence_requirement") or ""),
            remedy=str(doc.get("remedy") or ""),
            kind="live-artifact",
            live_present=True,
        )
    ]


def _catalog_declared(unit: dict) -> dict[str, Any]:
    uid = unit["id"]
    claim = str(unit.get("question_or_target") or unit.get("title") or uid)
    evidence = str(unit.get("evidence_requirement") or "")
    tests = unit.get("tests_required") or []
    remedy_parts: list[str] = []
    if "Target:" in claim:
        remedy_parts.append("Target: " + claim.split("Target:", 1)[1].strip()[:400])
    if isinstance(tests, list):
        remedy_parts.extend(str(t) for t in tests if t)
    paths = _as_paths(unit.get("inputs"))
    paths.extend(_as_paths(unit.get("output_path")))
    paths.extend(_as_paths(evidence))
    return _finding(
        fid=f"{uid}::catalog-declared",
        source_unit=uid,
        claim=claim,
        cited_paths=paths,
        evidence_text=evidence,
        remedy=" | ".join(remedy_parts)[:800],
        kind="catalog-declared",
        live_present=False,
    )


def _candidate_live_paths(unit: dict) -> list[Path]:
    uid = unit["id"]
    rels: list[str] = []
    out = str(unit.get("output_path") or "").replace("\\", "/")
    if out:
        rels.append(out)
    rels.append(f"command-center/receipts/{uid}.json")
    rels.append(f"command-center/synthesis/{uid}.json")
    paths: list[Path] = []
    seen: set[Path] = set()
    for rel in rels:
        path = REPO / rel
        if path not in seen:
            seen.add(path)
            paths.append(path)
    synth = REPO / "command-center" / "synthesis"
    if synth.is_dir():
        for path in sorted(synth.glob(f"{uid}*")):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def _load_fixture(name: str) -> dict[str, Any]:
    doc = _read_json(HERE / "fixtures" / name)
    kind = str(doc["kind"])
    if kind == "planted-unanchored":
        mapped = "planted-unanchored"
    elif kind == "known-good":
        mapped = "known-good"
    else:
        mapped = kind
    return _finding(
        fid=str(doc["id"]),
        source_unit=str(doc.get("source_unit") or "SYN-FIXTURE"),
        claim=str(doc["claim"]),
        cited_paths=list(doc.get("cited_paths") or []),
        evidence_text=str(doc.get("evidence_text") or ""),
        remedy=str(doc.get("remedy") or ""),
        kind=mapped,
        live_present=False,
    )


def load_findings(*, include_fixtures: bool = True) -> dict[str, Any]:
    units = catalog_by_id()
    findings: list[dict[str, Any]] = []
    input_status: list[dict[str, Any]] = []
    for uid in SUBJECT_IDS:
        unit = units.get(uid)
        if unit is None:
            input_status.append(
                {"unit_id": uid, "live": False, "reason": "catalog-missing"}
            )
            continue
        live_doc = None
        live_rel = None
        for path in _candidate_live_paths(unit):
            if path.is_file() and path.stat().st_size > 0:
                try:
                    live_doc = _read_json(path)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    live_doc = None
                    continue
                live_rel = path.relative_to(REPO).as_posix()
                break
        if live_doc is not None and live_rel is not None:
            extracted = _extract_live(uid, live_doc, live_rel)
            findings.extend(extracted)
            input_status.append(
                {
                    "unit_id": uid,
                    "live": True,
                    "path": live_rel,
                    "n_findings": len(extracted),
                }
            )
        else:
            findings.append(_catalog_declared(unit))
            input_status.append(
                {
                    "unit_id": uid,
                    "live": False,
                    "path": str(unit.get("output_path") or ""),
                    "reason": "artifact-absent",
                    "n_findings": 1,
                }
            )
    if include_fixtures:
        findings.append(_load_fixture("planted_unanchored.json"))
        findings.append(_load_fixture("known_good.json"))
    return {
        "subject_ids": list(SUBJECT_IDS),
        "findings": findings,
        "input_status": input_status,
        "n_findings": len(findings),
        "n_live_units": sum(1 for row in input_status if row.get("live")),
        "n_absent_units": sum(1 for row in input_status if not row.get("live")),
    }
