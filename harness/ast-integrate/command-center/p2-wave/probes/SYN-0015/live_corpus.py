"""Walk declared Phase-14 synthesis outputs. A subset scan is not 'every'."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import scanner as S

LIVE_SYNTHESIS_DIR = "command-center/synthesis"
LIVE_ADJUDICATIONS = "command-center/synthesis/SYN-0011.adjudications.json"
FANOUT = "rules/common/fan-out-contract.md"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SELF_ID = "SYN-0015"
CONTRACT_TAIL = re.compile(
    r"\s*(?:SUCCESS|FAILED):[A-Z]{2,5}-\d{4} emitted only when[\s\S]*$",
    re.I,
)


def strip_contract_tail(text: str) -> str:
    return CONTRACT_TAIL.sub("", text).strip()


def phase14_syn_units(repo: Path) -> list[dict[str, Any]]:
    catalog = repo / CATALOG
    data = json.loads(catalog.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if not uid.startswith("SYN-"):
            continue
        if str(unit.get("phase")) != "14":
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        path = repo / rel if rel else None
        present = bool(rel) and path is not None and path.is_file() and path.stat().st_size > 0
        rows.append({"id": uid, "output_path": rel, "present": present})
    return rows


def declared_inputs(repo: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in (LIVE_SYNTHESIS_DIR, LIVE_ADJUDICATIONS, FANOUT, CATALOG):
        p = repo / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file() or p.is_dir(),
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
            }
        )
    return rows


def _extract_json_text(doc: Any) -> str:
    """Synthesis prose only: top-level answer/text, not nested claim lists."""
    if not isinstance(doc, dict):
        return ""
    chunks: list[str] = []
    for key in ("answer", "text", "synthesis", "prose", "body"):
        val = doc.get(key)
        if isinstance(val, str) and len(val.strip()) >= 8:
            chunks.append(strip_contract_tail(val.strip()))
    return "\n".join(c for c in chunks if c)


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _scan_targets(repo: Path, units: list[dict[str, Any]]) -> list[Path]:
    seen: set[str] = set()
    files: list[Path] = []

    def add(path: Path) -> None:
        if not path.is_file():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        files.append(path)

    for row in units:
        if row["id"] == SELF_ID:
            continue
        if not row["present"]:
            continue
        add(repo / row["output_path"])
    root = repo / LIVE_SYNTHESIS_DIR
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".md", ".json"}:
                if p.name.startswith("SYN-0015"):
                    continue
                add(p)
    return files


def scan_live(repo: Path) -> dict[str, Any]:
    units = phase14_syn_units(repo)
    catalog_n = len(units)
    present_ids = [r["id"] for r in units if r["present"]]
    absent_ids = [r["id"] for r in units if not r["present"]]
    files = _scan_targets(repo, units)
    all_findings: list[dict[str, Any]] = []
    overclaims: list[dict[str, Any]] = []
    unbound: list[dict[str, Any]] = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                text = strip_contract_tail(raw)
            else:
                text = _extract_json_text(doc)
        else:
            text = strip_contract_tail(raw)
        receipt = S.bind_receipt(path, text)
        findings = S.scan_text(
            text, receipt, strip_mentions=True, source_path=_rel(repo, path)
        )
        for row in findings:
            row["corpus"] = "live-phase14"
            all_findings.append(row)
            if row.get("kind") == "overclaim":
                overclaims.append(row)
            elif row.get("kind") == "unbound":
                unbound.append(row)

    n_files = len(files)
    n_absent = len(absent_ids)
    if catalog_n == 0:
        coverage_verdict = "NOT-CHECKED"
    elif n_absent > 0 or n_files == 0:
        coverage_verdict = "PARTIAL" if n_files else "NOT-CHECKED"
    else:
        coverage_verdict = "CONFIRMED"

    if overclaims:
        overclaim_verdict = "REFUTED"
    elif unbound:
        overclaim_verdict = "PARTIAL"
    elif n_files == 0:
        overclaim_verdict = "NOT-CHECKED"
    else:
        overclaim_verdict = "CONFIRMED"

    if coverage_verdict != "CONFIRMED":
        verdict = "PARTIAL" if n_files else "NOT-CHECKED"
        if overclaims:
            verdict = "PARTIAL"
    else:
        verdict = overclaim_verdict

    return {
        "declared_inputs": declared_inputs(repo),
        "catalog_phase14_syn_units": catalog_n,
        "present_output_ids": present_ids,
        "absent_output_ids": absent_ids,
        "present_outputs": len(present_ids),
        "absent_outputs": n_absent,
        "scanned_excluding_self": n_files,
        "files_scanned": n_files,
        "file_paths": [_rel(repo, p) for p in files],
        "quantified_use_sentences": len(all_findings),
        "overclaims": len(overclaims),
        "unbound": len(unbound),
        "overclaim_rows": overclaims,
        "unbound_rows": unbound,
        "coverage_verdict": coverage_verdict,
        "overclaim_verdict": overclaim_verdict,
        "verdict": verdict,
    }
