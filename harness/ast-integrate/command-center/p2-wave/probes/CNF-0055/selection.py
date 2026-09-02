#!/usr/bin/env python3
"""Load fixtures, apply the planted after-mutation, and diff top-k selections."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from router import route_task

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
INDEX_PATH = FIX / "capability-index.json"
CORPUS_PATH = FIX / "corpus.json"
MUTATION_PATH = FIX / "after-mutation.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_obj(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_index() -> dict[str, Any]:
    return load_json(INDEX_PATH)


def load_corpus() -> dict[str, Any]:
    return load_json(CORPUS_PATH)


def load_mutation() -> dict[str, Any]:
    return load_json(MUTATION_PATH)


def apply_after_mutation(index: dict[str, Any], mutation: dict[str, Any] | None = None) -> dict[str, Any]:
    mutation = mutation or load_mutation()
    after = copy.deepcopy(index)
    cap_id = mutation["capability_id"]
    action = mutation.get("action")
    found = False
    kept: list[dict[str, Any]] = []
    for cap in after.get("capabilities") or []:
        if cap.get("capability_id") != cap_id:
            kept.append(cap)
            continue
        found = True
        if action == "strip_triggers" and mutation.get("keep_in_index", True):
            cap = copy.deepcopy(cap)
            cap["triggers"] = {
                "keywords": [],
                "globs": [],
                "cwd_prefixes": [],
                "verbs": [],
            }
            if mutation.get("replacement_description"):
                cap["description"] = mutation["replacement_description"]
            kept.append(cap)
        elif action == "drop":
            continue
        else:
            kept.append(cap)
    if not found:
        raise SystemExit(f"mutation target {cap_id} missing from index")
    after["capabilities"] = kept
    after["mutation"] = {
        "id": mutation.get("id"),
        "capability_id": cap_id,
        "action": action,
    }
    return after


def route_corpus(index: dict[str, Any], corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    corpus = corpus or load_corpus()
    k = int(corpus.get("k") or index.get("k") or 3)
    out = []
    for task in corpus["tasks"]:
        row = route_task(task, index, k=k)
        out.append(row)
    return out


def selected_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        ids.update(row.get("topk_ids") or [])
    return ids


def indexed_ids(index: dict[str, Any]) -> list[str]:
    return [c["capability_id"] for c in index.get("capabilities") or []]


def unreachable_in_state(index: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = selected_ids(rows)
    out = []
    for cap_id in indexed_ids(index):
        if cap_id in selected:
            continue
        out.append(
            {
                "capability_id": cap_id,
                "classification": "routing-defect",
                "not": "corpus-gap",
                "reason": (
                    "indexed capability was never selected for any corpus task; "
                    "that is a routing defect, not a corpus gap"
                ),
            }
        )
    return out


def topk_tuple(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(row.get("topk_ids") or [])


def changed_selections(
    before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    after_by = {r["task_id"]: r for r in after_rows}
    changed = []
    for before in before_rows:
        tid = before["task_id"]
        after = after_by[tid]
        if topk_tuple(before) != topk_tuple(after) or before["verdict"] != after["verdict"]:
            changed.append(
                {
                    "id": tid,
                    "task_id": tid,
                    "before_verdict": before["verdict"],
                    "after_verdict": after["verdict"],
                    "before_topk": before.get("topk") or [],
                    "after_topk": after.get("topk") or [],
                    "before_ids": list(before.get("topk_ids") or []),
                    "after_ids": list(after.get("topk_ids") or []),
                }
            )
    return changed


def measure() -> dict[str, Any]:
    index = load_index()
    corpus = load_corpus()
    mutation = load_mutation()
    after_index = apply_after_mutation(index, mutation)
    before_rows = route_corpus(index, corpus)
    after_rows = route_corpus(after_index, corpus)
    # Determinism: routing the before index twice must be identical.
    again = route_corpus(index, corpus)
    if json.dumps(before_rows, sort_keys=True) != json.dumps(again, sort_keys=True):
        raise SystemExit("router is not deterministic on the before index")
    changed = changed_selections(before_rows, after_rows)
    before_selected = selected_ids(before_rows)
    after_selected = selected_ids(after_rows)
    previously_now_unreach = sorted(before_selected - after_selected)
    before_unreach = unreachable_in_state(index, before_rows)
    after_unreach = unreachable_in_state(after_index, after_rows)
    control = next(t for t in corpus["tasks"] if t.get("is_control"))
    control_row = next(r for r in before_rows if r["task_id"] == control["id"])
    control_ok = (
        control["expected_capability"] in (control_row.get("topk_ids") or [])
        and (control_row.get("topk_ids") or [None])[0] == control["expected_capability"]
    )
    labelled = [t for t in corpus["tasks"] if t.get("expected_capability")]
    before_by = {r["task_id"]: r for r in before_rows}
    labelled_hits = 0
    for task in labelled:
        row = before_by[task["id"]]
        expected = task["expected_capability"]
        if expected in (row.get("topk_ids") or []) and (row.get("topk_ids") or [None])[0] == expected:
            labelled_hits += 1
    nofit = next(t for t in corpus["tasks"] if t.get("expected_verdict") == "NO-CAPABILITY-FITS")
    nofit_row = before_by[nofit["id"]]
    nofit_ok = nofit_row["verdict"] == "NO-CAPABILITY-FITS" and not nofit_row.get("topk_ids")
    return {
        "k": int(corpus.get("k") or index.get("k") or 3),
        "score_threshold": float(index.get("score_threshold") or 1.0),
        "index_sha256": sha256_bytes(INDEX_PATH.read_bytes()),
        "after_index_sha256": sha256_obj(after_index),
        "corpus_sha256": sha256_bytes(CORPUS_PATH.read_bytes()),
        "mutation": mutation,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "changed": changed,
        "changed_count": len(changed),
        "unchanged_count": len(before_rows) - len(changed),
        "before_unreachable": before_unreach,
        "after_unreachable": after_unreach,
        "previously_selected_now_unreachable": previously_now_unreach,
        "control_task_id": control["id"],
        "control_expected": control["expected_capability"],
        "control_topk": control_row.get("topk") or [],
        "control_ok": control_ok,
        "labelled_count": len(labelled),
        "labelled_top1_hits": labelled_hits,
        "nofit_ok": nofit_ok,
        "corpus_discriminating": bool(control_ok and labelled_hits == len(labelled) and nofit_ok),
        "indexed_capability_ids": indexed_ids(index),
        "after_indexed_capability_ids": indexed_ids(after_index),
    }


def artifact_field(doc: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a payload field from a receipt-shaped or legacy top-level artifact."""
    if not isinstance(doc, dict):
        return default
    for container in (doc, doc.get("report"), doc.get("extensions")):
        if isinstance(container, dict) and key in container:
            val = container[key]
            if val is not None:
                return val
    return default
