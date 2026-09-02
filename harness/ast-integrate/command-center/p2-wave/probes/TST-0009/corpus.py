"""Harvest the existing claim/evidence corpus and resolve every anchor.

Primary store: command-center/CLAIM-REGISTRY.json (often absent on this tree).
When the registry is missing, the live corpus is every evidence item already
on disk under command-center/receipts/ and command-center/confirmation/.

Emit freezes that harvest to harvest-snapshot.json. Named probes re-resolve
the frozen records against the live worktree so remesure does not drift as
other units land new receipts.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from resolver import COMMAND, FILE_LINE, INFERRED, parse_spec, resolve

REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
RECEIPTS_REL = "command-center/receipts"
CONFIRM_REL = "command-center/confirmation"
SNAPSHOT_REL = "command-center/p2-wave/probes/TST-0009/harvest-snapshot.json"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _walk_claim_like(obj: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        cid = str(obj.get("id") or obj.get("claim_id") or obj.get("unit_id") or "")
        for key in ("evidence", "evidence_anchors", "anchors", "refs"):
            val = obj.get(key)
            if isinstance(val, list):
                for item in val:
                    yield cid, item
            elif isinstance(val, (dict, str)):
                yield cid, val
        claims = obj.get("claims") or obj.get("items") or obj.get("records")
        if isinstance(claims, list):
            for claim in claims:
                yield from _walk_claim_like(claim)
        elif isinstance(obj.get("claim"), (str, dict)) and not any(
            isinstance(obj.get(k), list) for k in ("evidence", "evidence_anchors", "anchors")
        ):
            yield cid, obj
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_claim_like(item)


def _file_line_from_item(item: dict) -> dict | None:
    line = item.get("line")
    path = item.get("path") or item.get("file") or item.get("relpath")
    if path is not None and line is not None:
        return {"kind": FILE_LINE, "path": str(path).replace("\\", "/"), "line": line}
    anchor = item.get("anchor")
    if isinstance(anchor, str):
        parsed = parse_spec(anchor)
        if parsed["kind"] == FILE_LINE and parsed.get("path") and parsed.get("line"):
            return {
                "kind": FILE_LINE,
                "path": parsed["path"],
                "line": parsed["line"],
            }
    return None


def _command_from_item(item: dict) -> dict | None:
    cmd = item.get("command") or item.get("cmd")
    kind = str(item.get("kind") or item.get("method") or "").lower()
    if cmd and (kind in {"command", "cmd", "shell"} or "command" in item or "cmd" in item):
        rec = item.get("recorded_exit")
        if rec is None:
            rec = item.get("exit_code")
        return {"kind": COMMAND, "command": str(cmd), "recorded_exit": rec}
    return None


def _inferred_from_item(item: dict) -> dict | None:
    kind = str(item.get("kind") or "").lower()
    src = item.get("source") or item.get("inferred_from") or item.get("inferredFrom")
    if kind.startswith("infer") or item.get("inferred") is True:
        return {"kind": INFERRED, "source": src or ""}
    for field in ("anchor", "detail", "claim", "ref"):
        val = item.get(field)
        if isinstance(val, str) and val.strip().lower().startswith("inferred from "):
            return val.strip()
    return None


def extract_specs(item: Any) -> list[Any]:
    specs: list[Any] = []
    seen: set[str] = set()

    def add(spec: Any) -> None:
        key = json.dumps(spec, sort_keys=True, default=str)
        if key in seen:
            return
        seen.add(key)
        specs.append(spec)

    if isinstance(item, str):
        add(item)
        return specs
    if not isinstance(item, dict):
        return specs

    fl = _file_line_from_item(item)
    if fl:
        add(fl)
    cmd = _command_from_item(item)
    if cmd:
        add(cmd)
    inf = _inferred_from_item(item)
    if inf is not None:
        add(inf)
    if not specs:
        kind = str(item.get("kind") or item.get("method") or "").lower()
        if kind in {"file:line", "command", "inferred"} or item.get("anchor"):
            add(item)

    for probe in item.get("probes") or []:
        if not isinstance(probe, dict):
            continue
        nested = _command_from_item(probe)
        if nested:
            add(nested)
        elif probe.get("command"):
            add(
                {
                    "kind": COMMAND,
                    "command": probe.get("command"),
                    "recorded_exit": probe.get("exit_code")
                    if probe.get("exit_code") is not None
                    else probe.get("recorded_exit"),
                }
            )
    return specs


def harvest_registry(repo: Path) -> dict[str, Any]:
    path = repo / REGISTRY_REL
    present = path.is_file() and path.stat().st_size > 0
    doc = _load_json(path) if present else None
    rows: list[dict[str, Any]] = []
    if present and doc is not None:
        for cid, item in _walk_claim_like(doc):
            for spec in extract_specs(item):
                rows.append(
                    {
                        "claim_id": cid,
                        "origin": REGISTRY_REL,
                        "spec": spec,
                    }
                )
    return {
        "path": REGISTRY_REL,
        "present": bool(present),
        "parseable": doc is not None if present else False,
        "anchor_records": rows,
        "record_count": len(rows),
    }


def harvest_json_dir(repo: Path, rel: str) -> list[dict[str, Any]]:
    root = repo / rel
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("*.json")):
        # This unit's own receipt is a consumer of the table, not an input.
        if path.name == "TST-0009.json":
            continue
        doc = _load_json(path)
        if not isinstance(doc, dict):
            continue
        origin = f"{rel}/{path.name}".replace("\\", "/")
        unit = str(doc.get("unit_id") or doc.get("id") or path.stem)
        evidence = doc.get("evidence")
        if not isinstance(evidence, list):
            continue
        for idx, item in enumerate(evidence):
            for spec in extract_specs(item):
                rows.append(
                    {
                        "claim_id": f"{unit}:evidence[{idx}]",
                        "origin": origin,
                        "spec": spec,
                    }
                )
    return rows


def harvest_live(repo: Path) -> dict[str, Any]:
    registry = harvest_registry(repo)
    receipts = harvest_json_dir(repo, RECEIPTS_REL)
    confirmation = harvest_json_dir(repo, CONFIRM_REL)
    if registry["present"] and registry["anchor_records"]:
        records = list(registry["anchor_records"])
        corpus_name = "claim-registry"
    else:
        records = receipts + confirmation
        corpus_name = "live-receipts-and-confirmation"
    return {
        "registry": {
            "path": registry["path"],
            "present": registry["present"],
            "parseable": registry["parseable"],
            "registry_anchor_count": registry["record_count"],
        },
        "corpus_name": corpus_name,
        "receipt_anchor_count": len(receipts),
        "confirmation_anchor_count": len(confirmation),
        "records": records,
        "snapshot": {
            "present": False,
            "path": SNAPSHOT_REL,
            "frozen_at": None,
            "record_count": len(records),
        },
    }


def write_snapshot(repo: Path, harvested: dict[str, Any]) -> dict[str, Any]:
    frozen_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap = {
        "unit_id": "TST-0009",
        "frozen_at": frozen_at,
        "corpus_name": harvested["corpus_name"],
        "registry": harvested["registry"],
        "receipt_anchor_count": harvested["receipt_anchor_count"],
        "confirmation_anchor_count": harvested["confirmation_anchor_count"],
        "record_count": len(harvested["records"]),
        "records": harvested["records"],
        "note": (
            "CLAIM-REGISTRY.json is absent on this worktree. This freeze is the "
            "live receipts+confirmation evidence harvest at emit time. Named "
            "probes re-resolve these records; they do not re-walk a growing tree."
        ),
    }
    path = repo / SNAPSHOT_REL
    path.write_text(
        json.dumps(snap, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    meta = {
        "present": True,
        "path": SNAPSHOT_REL,
        "frozen_at": frozen_at,
        "record_count": len(harvested["records"]),
    }
    harvested = dict(harvested)
    harvested["snapshot"] = meta
    return harvested


def load_snapshot(repo: Path) -> dict[str, Any] | None:
    path = repo / SNAPSHOT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    doc = _load_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        return None
    registry = doc.get("registry") if isinstance(doc.get("registry"), dict) else {
        "path": REGISTRY_REL,
        "present": False,
        "parseable": False,
        "registry_anchor_count": 0,
    }
    records = [r for r in doc["records"] if isinstance(r, dict) and "spec" in r]
    frozen_at = doc.get("frozen_at")
    return {
        "registry": registry,
        "corpus_name": str(doc.get("corpus_name") or "live-receipts-and-confirmation"),
        "receipt_anchor_count": int(doc.get("receipt_anchor_count") or 0),
        "confirmation_anchor_count": int(doc.get("confirmation_anchor_count") or 0),
        "records": records,
        "snapshot": {
            "present": True,
            "path": SNAPSHOT_REL,
            "frozen_at": frozen_at,
            "record_count": len(records),
        },
    }


def collect(repo: Path, *, freeze: bool = False) -> dict[str, Any]:
    if freeze:
        return write_snapshot(repo, harvest_live(repo))
    snapped = load_snapshot(repo)
    if snapped is not None:
        return snapped
    return harvest_live(repo)


def resolve_corpus(repo: Path, *, freeze: bool = False) -> dict[str, Any]:
    harvested = collect(repo, freeze=freeze)
    table: list[dict[str, Any]] = []
    by_kind: Counter[str] = Counter()
    by_outcome: Counter[str] = Counter()
    by_kind_outcome: Counter[str] = Counter()
    for rec in harvested["records"]:
        resolved = resolve(repo, rec["spec"])
        row = {
            "claim_id": rec["claim_id"],
            "origin": rec["origin"],
            "kind": resolved["kind"],
            "outcome": resolved["outcome"],
            "reason": resolved["reason"],
            "path": resolved.get("path"),
            "line": resolved.get("line"),
            "line_count": resolved.get("line_count"),
            "command": resolved.get("command"),
            "recorded_exit": resolved.get("recorded_exit"),
            "observed_exit": resolved.get("observed_exit"),
            "source": resolved.get("source"),
        }
        table.append(row)
        by_kind[row["kind"]] += 1
        by_outcome[row["outcome"]] += 1
        by_kind_outcome[f"{row['kind']}|{row['outcome']}"] += 1
    unresolved = [r for r in table if r["outcome"] != "resolved"]
    fail_to_resolve = [r for r in table if r["outcome"] == "unresolved"]
    return {
        "registry": harvested["registry"],
        "corpus_name": harvested["corpus_name"],
        "snapshot": harvested.get("snapshot") or {
            "present": False,
            "path": SNAPSHOT_REL,
            "frozen_at": None,
            "record_count": len(table),
        },
        "receipt_anchor_count": harvested["receipt_anchor_count"],
        "confirmation_anchor_count": harvested["confirmation_anchor_count"],
        "anchor_count": len(table),
        "resolved_count": by_outcome.get("resolved", 0),
        "unresolved_count": by_outcome.get("unresolved", 0),
        "not_reexecuted_count": by_outcome.get("not-reexecuted", 0),
        "fail_to_resolve_count": len(fail_to_resolve),
        "counts_by_kind": dict(sorted(by_kind.items())),
        "counts_by_outcome": dict(sorted(by_outcome.items())),
        "counts_by_kind_and_outcome": dict(sorted(by_kind_outcome.items())),
        "table": table,
        "unresolved": unresolved,
    }
