"""Append-only fold: EVENTS.jsonl lines -> A5 ledger records.

The source file is never opened for write. Conservation is
  input_lines == output_records + classified_drops.
Each folded record carries the exact source line so the original JSONL
can be reconstituted (content-preserving in both directions).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
LEDGER_FIELDS = (
    "seq",
    "kind",
    "rail",
    "unit_id",
    "ts",
    "verb",
    "source",
    "payload",
    "prev_hash",
    "event_hash",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def event_hash(record: dict[str, Any]) -> str:
    body = {k: record[k] for k in record if k != "event_hash"}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def classify_line(line: str) -> tuple[str, dict[str, Any] | None, str]:
    """Return (classification, obj_or_none, reason)."""
    if line == "":
        return "blank", None, "empty-line"
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return "malformed-json", None, "json-decode-error"
    if not isinstance(obj, dict):
        return "malformed-json", None, "json-root-not-object"
    return "fold", obj, "parseable-object"


def _source_blob(path: str, line_no: int, line: str) -> dict[str, Any]:
    return {
        "path": path,
        "line_no": line_no,
        "sha256": sha256_text(line),
        "raw": line,
    }


def fold_lines(
    lines: list[str],
    source_rel: str,
    rail: str = "cc_close",
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    drops: list[dict[str, Any]] = []
    sample: list[dict[str, Any]] = []
    prev = GENESIS
    seq = 0
    for line_no, line in enumerate(lines, 1):
        classification, obj, reason = classify_line(line)
        src = _source_blob(source_rel, line_no, line)
        if classification != "fold" or obj is None:
            drops.append(
                {
                    "line_no": line_no,
                    "classification": classification,
                    "reason": reason,
                    "source": src,
                }
            )
            sample.append(
                {
                    "line_no": line_no,
                    "classification": classification,
                    "decision": "DROP",
                    "source_sha256": src["sha256"],
                    "source_bytes_preserved": True,
                    "unit_id": None,
                    "ledger_event_hash": None,
                    "rail": rail,
                    "reason": reason,
                }
            )
            continue
        seq += 1
        rec = {
            "seq": seq,
            "kind": "fold",
            "rail": rail,
            "unit_id": obj.get("id") or obj.get("unit_id"),
            "ts": obj.get("ts"),
            "verb": obj.get("verb") or obj.get("kind") or "event",
            "source": src,
            "payload": obj,
            "prev_hash": prev,
        }
        rec["event_hash"] = event_hash(rec)
        prev = rec["event_hash"]
        records.append(rec)
        sample.append(
            {
                "line_no": line_no,
                "classification": "fold",
                "decision": "FOLD",
                "source_sha256": src["sha256"],
                "source_bytes_preserved": True,
                "unit_id": rec["unit_id"],
                "ledger_event_hash": rec["event_hash"],
                "rail": rail,
                "reason": "mapped-to-ledger-record",
            }
        )
    input_n = len(lines)
    out_n = len(records)
    drop_n = len(drops)
    return {
        "input_events": input_n,
        "output_records": out_n,
        "classified_drops": drop_n,
        "conservation_holds": input_n == out_n + drop_n,
        "records": records,
        "drops": drops,
        "sample": sample,
        "chain_tip": prev,
    }


def reconstruct(result: dict[str, Any]) -> list[str]:
    """Reverse direction: original lines in line_no order from records+drops."""
    by_line: dict[int, str] = {}
    for rec in result["records"]:
        src = rec["source"]
        by_line[int(src["line_no"])] = src["raw"]
    for drop in result["drops"]:
        src = drop["source"]
        by_line[int(src["line_no"])] = src["raw"]
    return [by_line[i] for i in range(1, len(by_line) + 1)]


def both_directions(lines: list[str], result: dict[str, Any]) -> dict[str, Any]:
    forward_ok = all(
        rec["source"]["raw"] == lines[rec["source"]["line_no"] - 1]
        and rec["source"]["sha256"] == sha256_text(lines[rec["source"]["line_no"] - 1])
        for rec in result["records"]
    )
    reverse = reconstruct(result)
    reverse_ok = reverse == lines
    return {
        "forward_ok": forward_ok,
        "reverse_ok": reverse_ok,
        "both_directions": forward_ok and reverse_ok,
        "reconstructed_lines": len(reverse),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical(row) + "\n")


def fold_file(source: Path, ledger: Path, drops_path: Path, source_rel: str) -> dict[str, Any]:
    if source.resolve() == ledger.resolve() or source.resolve() == drops_path.resolve():
        return {
            "ok": False,
            "refused": True,
            "reason": "in-place-rewrite-forbidden",
            "input_events": 0,
            "output_records": 0,
            "classified_drops": 0,
            "conservation_holds": False,
        }
    text = source.read_text(encoding="utf-8")
    # splitlines() drops a trailing newline; keep physical lines including a
    # possible terminal empty line after a trailing \n\n.
    if text == "":
        lines: list[str] = []
    else:
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
    before = sha256_bytes(source.read_bytes())
    result = fold_lines(lines, source_rel)
    write_jsonl(ledger, result["records"])
    write_jsonl(drops_path, result["drops"])
    after = sha256_bytes(source.read_bytes())
    directions = both_directions(lines, result)
    result.update(
        {
            "ok": True,
            "refused": False,
            "reason": "folded-to-distinct-path",
            "source_sha256_before": before,
            "source_sha256_after": after,
            "source_unmodified": before == after,
            "ledger_path_distinct": source.resolve() != ledger.resolve(),
            "lines": lines,
            **directions,
        }
    )
    return result
