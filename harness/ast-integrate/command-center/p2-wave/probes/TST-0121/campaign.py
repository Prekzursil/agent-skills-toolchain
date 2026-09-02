"""Differential campaign: feed generated documents to both parsers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from generate import campaign_documents
from parsers import classify, is_disagreement

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "disagreements"
INDEX_REL = "command-center/p2-wave/probes/TST-0121/fixtures/INDEX.json"
DEFAULT_SEED = 1212026
DEFAULT_COUNT = 48


def finding_id(kind: str, text: str) -> str:
    digest = hashlib.sha256(f"{kind}\n{text}".encode("utf-8")).hexdigest()[:16]
    return f"D-{digest}"


def run_campaign(
    seed: int = DEFAULT_SEED, generated_count: int = DEFAULT_COUNT
) -> dict[str, Any]:
    docs = campaign_documents(seed, generated_count)
    findings: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    agreeing = 0
    both_reject = 0
    for doc in docs:
        row = classify(doc["input"])
        row["index"] = doc["index"]
        row["origin"] = doc["origin"]
        row["mutation"] = doc["mutation"]
        if is_disagreement(row):
            fid = finding_id(row["kind"], doc["input"])
            row["id"] = fid
            row["fixture"] = f"fixtures/disagreements/{fid}.json"
            prev = by_id.get(fid)
            # One fixture per unique (kind, input). Prefer the planted row.
            if prev is None or (
                row["origin"] == "planted" and prev["origin"] != "planted"
            ):
                by_id[fid] = row
        else:
            agreeing += 1
            if (not row["strict"]["accepted"]) and (not row["lenient"]["accepted"]):
                both_reject += 1
    findings = sorted(by_id.values(), key=lambda r: r["id"])
    planted_found = [
        r
        for r in findings
        if r["origin"] == "planted"
    ]
    return {
        "seed": seed,
        "generated_count": generated_count,
        "document_count": len(docs),
        "finding_count": len(findings),
        "agreeing_count": agreeing,
        "both_reject_count": both_reject,
        "findings": findings,
        "planted_found_count": len(planted_found),
        "planted_ids": [r["id"] for r in planted_found],
        "finding_ids": [r["id"] for r in findings],
    }


def fixture_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "origin": row["origin"],
        "mutation": row["mutation"],
        "index": row["index"],
        "input": row["input"],
        "strict": row["strict"],
        "lenient": row["lenient"],
        "interpretations_side_by_side": {
            "strict": row["strict"],
            "lenient": row["lenient"],
        },
    }


def persist_fixtures(
    result: dict[str, Any], root: Path | None = None
) -> dict[str, Any]:
    base = root or HERE
    dest = base / "fixtures" / "disagreements"
    dest.mkdir(parents=True, exist_ok=True)
    index_rows: list[dict[str, Any]] = []
    for row in result["findings"]:
        payload = fixture_payload(row)
        path = dest / f"{row['id']}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        rel = f"command-center/p2-wave/probes/TST-0121/fixtures/disagreements/{row['id']}.json"
        index_rows.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "origin": row["origin"],
                "path": rel,
            }
        )
    index = {
        "seed": result["seed"],
        "generated_count": result["generated_count"],
        "finding_count": result["finding_count"],
        "finding_ids": result["finding_ids"],
        "fixtures": index_rows,
    }
    index_path = base / "fixtures" / "INDEX.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result = dict(result)
    result["index_path"] = INDEX_REL
    result["fixture_count_on_disk"] = len(index_rows)
    return result


def load_index(root: Path | None = None) -> dict[str, Any]:
    base = root or HERE
    path = base / "fixtures" / "INDEX.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def missing_fixtures(
    findings: list[dict[str, Any]], root: Path | None = None
) -> list[str]:
    base = root or HERE
    dest = base / "fixtures" / "disagreements"
    missing: list[str] = []
    for row in findings:
        if not (dest / f"{row['id']}.json").is_file():
            missing.append(row["id"])
    return missing
