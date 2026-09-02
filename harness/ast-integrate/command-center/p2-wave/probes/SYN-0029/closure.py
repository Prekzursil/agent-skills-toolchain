#!/usr/bin/env python3
"""Join a requirement register to a five-way labelled report.

Exactly one of VERIFIED | INFERRED | UNVERIFIED | REJECTED | DEFERRED is
taken from the report. A register row with no report label is DISAPPEARED
(unlabelled). A double-labelled row fails; it is not collapsed by vote.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

FIVE = (
    "VERIFIED",
    "INFERRED",
    "UNVERIFIED",
    "REJECTED",
    "DEFERRED",
)
FIVE_SET = frozenset(FIVE)
DISAPPEARED = "DISAPPEARED"
ABSENCE_LABELS = frozenset({DISAPPEARED})


def _as_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def item_ids(item: dict) -> list[str]:
    found: list[str] = []
    for key in ("requirement_id", "id", "req_id", "floor_id"):
        got = _as_id(item.get(key))
        if got and got not in found:
            found.append(got)
    return found


def labels_of(item: dict) -> list[str]:
    raw: list[str] = []
    lab = item.get("label")
    if isinstance(lab, str) and lab.strip():
        raw.append(lab.strip())
    labs = item.get("labels")
    if isinstance(labs, list):
        for x in labs:
            if isinstance(x, str) and x.strip():
                raw.append(x.strip())
    disposition = item.get("disposition")
    if isinstance(disposition, str) and disposition.strip():
        raw.append(disposition.strip())
    # Preserve duplicates across fields so VERIFIED+INFERRED is visible;
    # collapse only exact repeats of the same token.
    unique: list[str] = []
    for tok in raw:
        if tok not in unique:
            unique.append(tok)
    return unique


def report_ids_digest(items: list[dict]) -> str:
    ids: list[str] = []
    for item in items:
        ids.extend(item_ids(item))
    blob = "\n".join(sorted(set(ids))).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def index_report(items: list[dict]) -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        keys = item_ids(item)
        if not keys:
            continue
        for key in keys:
            by_id.setdefault(key, []).append(item)
    return by_id


def close(register: list[dict], report_items: list[dict], report_meta: dict) -> dict:
    """Return a closure document fragment. Never retries; first observation is the verdict."""
    rows: list[dict] = []
    double_labelled: list[dict] = []
    illegal_labels: list[dict] = []
    register_dupes: list[str] = []
    seen_reg: set[str] = set()
    by_id = index_report(report_items)
    ids_sha = report_ids_digest(report_items)
    report_path = str(report_meta.get("path") or "report")
    report_present = bool(report_meta.get("present"))
    report_item_count = len(report_items)

    for rec in register:
        if not isinstance(rec, dict):
            continue
        rid = _as_id(rec.get("requirement_id") or rec.get("id"))
        if not rid:
            continue
        if rid in seen_reg:
            register_dupes.append(rid)
            continue
        seen_reg.add(rid)
        text = str(rec.get("text") or "").strip()
        spec_anchor = str(rec.get("spec_anchor") or "").strip()
        bound = rec.get("bound_unit_ids")
        if not isinstance(bound, list):
            bound = []
        bound_ids = [str(x) for x in bound if isinstance(x, str) and x.strip()]
        hits = by_id.get(rid, [])
        label_tokens: list[str] = []
        for hit in hits:
            label_tokens.extend(labels_of(hit))
        unique_labels: list[str] = []
        for tok in label_tokens:
            if tok not in unique_labels:
                unique_labels.append(tok)

        kind = str(rec.get("kind") or "requirement")
        base = {
            "requirement_id": rid,
            "text": text,
            "spec_anchor": spec_anchor,
            "bound_unit_ids": bound_ids,
            "kind": kind,
        }

        if len(unique_labels) > 1:
            double_labelled.append({"requirement_id": rid, "labels": unique_labels})
            rows.append(
                {
                    **base,
                    "label": DISAPPEARED,
                    "unlabelled": True,
                    "report_anchor": (
                        f"{report_path} double-labelled {rid} labels={unique_labels} "
                        f"(exactly-one failed; not collapsed by vote)"
                    ),
                }
            )
            continue

        if len(unique_labels) == 1:
            lab = unique_labels[0]
            if lab not in FIVE_SET:
                illegal_labels.append({"requirement_id": rid, "label": lab})
                rows.append(
                    {
                        **base,
                        "label": DISAPPEARED,
                        "unlabelled": True,
                        "report_anchor": (
                            f"{report_path} illegal label {lab!r} on {rid}; "
                            f"vocabulary is {list(FIVE)}"
                        ),
                    }
                )
                continue
            hit = hits[0]
            anchor = hit.get("report_anchor") or hit.get("anchor")
            if not isinstance(anchor, str) or not anchor.strip():
                anchors = hit.get("anchors")
                if isinstance(anchors, list) and anchors:
                    first = anchors[0]
                    if isinstance(first, str):
                        anchor = first
                    elif isinstance(first, dict):
                        anchor = str(first.get("path") or first.get("anchor") or "")
            if not isinstance(anchor, str) or not anchor.strip():
                anchor = f"{report_path} item id={rid} label={lab}"
            rows.append(
                {
                    **base,
                    "label": lab,
                    "unlabelled": False,
                    "report_anchor": str(anchor).strip(),
                }
            )
            continue

        absence = (
            f"{report_path} ABSENT-LABEL id={rid} report_present={str(report_present).lower()} "
            f"report_item_count={report_item_count} report_item_ids_sha256={ids_sha}"
        )
        rows.append(
            {
                **base,
                "label": DISAPPEARED,
                "unlabelled": True,
                "report_anchor": absence,
            }
        )

    counts = Counter(r["label"] for r in rows)
    label_counts = {name: int(counts.get(name, 0)) for name in (*FIVE, DISAPPEARED)}
    unlabelled = sum(1 for r in rows if r.get("unlabelled") is True)
    labelled = len(rows) - unlabelled
    exactly_one = (
        not double_labelled
        and not illegal_labels
        and not register_dupes
        and all(r.get("label") in FIVE_SET or r.get("label") == DISAPPEARED for r in rows)
        and all(isinstance(r.get("report_anchor"), str) and r["report_anchor"] for r in rows)
    )
    return {
        "rows": rows,
        "register_size": len(rows),
        "unlabelled_count": unlabelled,
        "labelled_count": labelled,
        "label_counts": label_counts,
        "double_labelled": double_labelled,
        "illegal_labels": illegal_labels,
        "register_dupes": register_dupes,
        "exactly_one_label_per_requirement": exactly_one and not double_labelled,
        "vocabulary_ok": not illegal_labels,
        "report_item_ids_sha256": ids_sha,
        "report_present": report_present,
        "report_path": report_path,
        "report_item_count": report_item_count,
    }


def planted_omission(register: list[dict], report_items: list[dict], drop_id: str, report_meta: dict) -> dict:
    remaining = [
        item
        for item in report_items
        if drop_id not in item_ids(item if isinstance(item, dict) else {})
    ]
    result = close(register, remaining, report_meta)
    disappeared = [r for r in result["rows"] if r["requirement_id"] == drop_id]
    fired = (
        len(disappeared) == 1
        and disappeared[0]["label"] == DISAPPEARED
        and disappeared[0]["unlabelled"] is True
    )
    result["planted_id"] = drop_id
    result["planted_omission_fired"] = fired
    return result


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
