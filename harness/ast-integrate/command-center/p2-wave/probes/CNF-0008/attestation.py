#!/usr/bin/env python3
"""Execution attestation: a claimed probe run is attested only by ledger or file+mtime.

A confirmation receipt is attested when at least one of:
  * a ledger row whose command matches the claimed source_probe, or
  * a produced file path that exists, is non-empty, and yields an mtime.

Receipts with neither are unattested. CONFIRMED with no execution record is
downgraded to NOT-CHECKED. Empty source_probe is unattested, never a free pass.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLOSED_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
DOWNGRADE = "NOT-CHECKED"


def iso_mtime(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def load_ledger_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    if path.is_file():
        if path.suffix == ".jsonl":
            return load_jsonl(path)
        if path.suffix == ".json":
            doc = load_json(path)
            if isinstance(doc, list):
                return [x for x in doc if isinstance(x, dict)]
            if isinstance(doc, dict):
                return [doc]
            return []
        return []
    rows: list[dict] = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and child.suffix in {".jsonl", ".json"}:
            rows.extend(load_ledger_dir(child))
    return rows


def fingerprint(probe: Any) -> tuple[str, str, str, str]:
    if not isinstance(probe, dict):
        return ("", "", "", "")
    return (
        str(probe.get("tool") or ""),
        str(probe.get("shell") or ""),
        str(probe.get("data_field") or probe.get("field") or ""),
        str(probe.get("measurement_kind") or probe.get("kind") or ""),
    )


def probe_command(receipt: dict) -> str:
    sp = receipt.get("source_probe")
    if isinstance(sp, str):
        return sp.strip()
    if isinstance(sp, dict):
        return str(sp.get("command") or sp.get("id") or "").strip()
    return str(receipt.get("probe_command") or "").strip()


def ledger_command(row: dict) -> str:
    return str(
        row.get("command")
        or row.get("cmd")
        or row.get("input")
        or ((row.get("tool_input") or {}) if isinstance(row.get("tool_input"), dict) else {}).get(
            "command", ""
        )
        or ""
    ).strip()


def ledger_id(row: dict) -> str:
    return str(row.get("id") or row.get("row_id") or row.get("event_id") or "").strip()


def source_probe_empty(receipt: dict) -> bool:
    sp = receipt.get("source_probe")
    if sp is None:
        return True
    if isinstance(sp, str):
        return not sp.strip()
    if isinstance(sp, dict):
        return not any(
            str(sp.get(k) or "").strip()
            for k in ("command", "id", "tool", "shell", "data_field", "measurement_kind")
        )
    return True


def probe_matches_ledger(receipt: dict, row: dict) -> bool:
    cmd = probe_command(receipt)
    lcmd = ledger_command(row)
    if not cmd or not lcmd:
        return False
    if cmd == lcmd or cmd in lcmd or lcmd in cmd:
        return True
    sp = receipt.get("source_probe")
    if isinstance(sp, dict):
        pid = str(sp.get("id") or "").strip()
        if pid and pid in lcmd:
            return True
    return False


def produced_paths(receipt: dict) -> list[str]:
    out: list[str] = []
    for key in ("produced_path", "output_path", "probe_output_path"):
        val = receipt.get(key)
        if isinstance(val, str) and val.strip():
            out.append(val.strip())
    produced = receipt.get("produced") or receipt.get("produced_files")
    if isinstance(produced, list):
        for item in produced:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                p = item.get("path")
                if isinstance(p, str) and p.strip():
                    out.append(p.strip())
    return out


def file_attestation(path_str: str, roots: list[Path]) -> dict | None:
    candidates = [Path(path_str)]
    if not Path(path_str).is_absolute():
        candidates.extend(root / path_str for root in roots)
    for cand in candidates:
        try:
            if cand.is_file() and cand.stat().st_size > 0:
                return {
                    "path": str(cand),
                    "mtime": iso_mtime(cand),
                    "bytes": cand.stat().st_size,
                }
        except OSError:
            continue
    return None


def classify_one(
    receipt: dict,
    ledger_rows: list[dict],
    file_roots: list[Path] | None = None,
) -> dict:
    rid = str(receipt.get("id") or receipt.get("receipt_id") or "").strip()
    original = str(receipt.get("verdict") or "").upper()
    roots = file_roots or []

    claimed_ledger = str(
        receipt.get("ledger_row_id") or receipt.get("ledger_id") or ""
    ).strip()
    empty_probe = source_probe_empty(receipt)

    ledger_hit: dict | None = None
    if not empty_probe:
        by_id = {ledger_id(r): r for r in ledger_rows if ledger_id(r)}
        if claimed_ledger and claimed_ledger in by_id:
            row = by_id[claimed_ledger]
            if probe_matches_ledger(receipt, row):
                ledger_hit = row
        if ledger_hit is None:
            for row in ledger_rows:
                if probe_matches_ledger(receipt, row):
                    ledger_hit = row
                    break

    file_hit: dict | None = None
    claimed_paths = produced_paths(receipt)
    for p in claimed_paths:
        hit = file_attestation(p, roots)
        if hit:
            file_hit = hit
            break

    attested = ledger_hit is not None or file_hit is not None
    if empty_probe and ledger_hit is None:
        attested = file_hit is not None
        if not attested:
            reason = "empty-source-probe"
        else:
            reason = "file-mtime-only"
    elif attested and ledger_hit is not None and file_hit is not None:
        reason = "ledger-and-file"
    elif attested and ledger_hit is not None:
        reason = "ledger-only"
    elif attested:
        reason = "file-mtime-only"
    else:
        reason = "no-ledger-no-file"

    attested_verdict = original
    if not attested and original == "CONFIRMED":
        attested_verdict = DOWNGRADE

    return {
        "id": rid or "(missing-id)",
        "claim_id": str(receipt.get("claim_id") or ""),
        "original_verdict": original,
        "attested_verdict": attested_verdict,
        "unattested": not attested,
        "downgraded": (not attested) and original == "CONFIRMED",
        "reason": reason,
        "empty_source_probe": empty_probe,
        "ledger_row_id": ledger_id(ledger_hit) if ledger_hit else None,
        "produced_path": (file_hit or {}).get("path"),
        "produced_mtime": (file_hit or {}).get("mtime"),
        "produced_bytes": (file_hit or {}).get("bytes"),
        "claimed_ledger_row_id": claimed_ledger or None,
        "claimed_produced_paths": claimed_paths,
        "source_probe_command": probe_command(receipt),
        "source_probe_fingerprint": list(fingerprint(receipt.get("source_probe"))),
    }


def classify_receipts(
    receipts: list[dict],
    ledger_rows: list[dict],
    file_roots: list[Path] | None = None,
) -> dict:
    rows = [classify_one(r, ledger_rows, file_roots) for r in receipts]
    unattested = [r for r in rows if r["unattested"]]
    n = len(rows)
    u = len(unattested)
    return {
        "receipt_count": n,
        "unattested_count": u,
        "attested_count": n - u,
        "fraction_unattested": None if n == 0 else u / n,
        "fraction_unattested_display": "0 of 0" if n == 0 else f"{u} of {n}",
        "unattested_ids": [r["id"] for r in unattested],
        "rows": rows,
    }


def opposite_controls(planted: dict, genuine: dict) -> bool:
    return planted.get("unattested") is True and genuine.get("unattested") is False


def artifact_controls(doc: Any) -> dict:
    """Read planted/genuine controls from a receipt-shaped or legacy artifact."""
    if not isinstance(doc, dict):
        return {}
    ctrl = doc.get("controls")
    if isinstance(ctrl, dict) and (
        "planted" in ctrl or "genuine" in ctrl or "classified_oppositely" in ctrl
    ):
        return ctrl
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("controls"), dict):
        return report["controls"]
    return ctrl if isinstance(ctrl, dict) else {}
