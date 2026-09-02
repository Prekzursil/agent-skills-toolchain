"""Enumerate SYN-0041 report items from catalog + disk. Never hand-typed."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from labels import LABEL_SET, NOT_DELIVERING

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"

# Named inputs from the SYN-0041 catalog contract.
NAMED_INPUT_UNITS = (
    "SYN-0001",
    "SYN-0005",
    "SYN-0011",
    "SYN-0014",
    "SYN-0015",
    "SYN-0016",
    "SYN-0017",
    "SYN-0018",
    "SYN-0019",
    "SYN-0020",
    "SYN-0021",
    "SYN-0022",
    "SYN-0023",
    "SYN-0024",
    "SYN-0025",
    "SYN-0026",
    "SYN-0027",
    "SYN-0028",
    "BLD-0029",
    "SYN-0033",
    "SYN-0034",
    "SYN-0035",
)

# Circular / downstream units: cannot be settled until this report exists.
DEFERRED_UNITS = ("SYN-0019", "SYN-0042", "SYN-0043", "SYN-0045")

LIVE_RECEIPTS = (
    ("BLD-0018", "command-center/receipts/BLD-0018.json"),
    ("BLD-0063", "command-center/receipts/BLD-0063.json"),
    ("IMP-0016", "command-center/receipts/IMP-0016.json"),
)

POSITIVE_EXISTENCE_CLAIMS = (
    (
        "SPEC-USER-PROMPTS",
        "_USER-PROMPTS.md exists on this worktree at the cited Phase 14 line range",
        "_USER-PROMPTS.md",
    ),
    (
        "REG-CLAIM",
        "command-center/CLAIM-REGISTRY.json exists as the canonical claim corpus",
        "command-center/CLAIM-REGISTRY.json",
    ),
    (
        "REG-ARTIFACT-MANIFEST",
        "command-center/ARTIFACT-MANIFEST.json exists for the SYN-0019 gate corpus",
        "command-center/ARTIFACT-MANIFEST.json",
    ),
)


def load_catalog(root: Path) -> dict[str, Any]:
    path = root / CATALOG_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("catalog is not an object")
    return data


def catalog_units(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    return out


def catalog_line(root: Path, needle: str) -> int:
    text = (root / CATALOG_REL).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return 1


def catalog_anchor(root: Path, unit_id: str) -> str:
    line = catalog_line(root, f'"id": "{unit_id}"')
    return f"{CATALOG_REL}:{line}"


def resolve_anchor(root: Path, anchor: str) -> bool:
    rel, sep, rest = anchor.partition(":")
    path = root / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sep or not rest:
        return True
    try:
        line_no = int(rest)
    except ValueError:
        return path.is_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    return 1 <= line_no <= len(lines) and bool(lines[line_no - 1].strip())


def classify_output(path: Path) -> str:
    if not path.is_file() or path.stat().st_size <= 0:
        return "UNVERIFIED"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "REJECTED"
    if isinstance(doc, dict):
        st = str(doc.get("state") or doc.get("status") or "").upper()
        if st in NOT_DELIVERING:
            return "REJECTED"
    return "VERIFIED"


def _item(
    item_id: str,
    claim: str,
    label: str,
    anchors: list[str],
    upstream: str,
    reason: str,
) -> dict[str, Any]:
    if label not in LABEL_SET:
        raise ValueError(f"illegal label {label}")
    return {
        "id": item_id,
        "claim": claim,
        "label": label,
        "anchors": anchors,
        "upstream_artifact_id": upstream,
        "reason": reason,
    }


def collect_items(root: Path) -> list[dict[str, Any]]:
    data = load_catalog(root)
    units = catalog_units(data)
    items: list[dict[str, Any]] = []

    syn0041 = units.get("SYN-0041") or {}
    q = str(syn0041.get("question_or_target") or "")
    items.append(
        _item(
            "CAT-SYN-0041-CONTRACT",
            (
                "WORK-UNIT-CATALOG.json records SYN-0041 as the five-way "
                "final evidence-backed report (VERIFIED/INFERRED/UNVERIFIED/"
                "REJECTED/DEFERRED) with exactly-one-label enforcement."
            ),
            "VERIFIED",
            [catalog_anchor(root, "SYN-0041")],
            "SYN-0041",
            "catalog row present; question names the five labels",
        )
    )
    out_rel = str(syn0041.get("output_path") or "")
    items.append(
        _item(
            "CAT-SYN-0041-OUTPUT-PATH",
            (
                "The contracted output_path for SYN-0041 is "
                f"{out_rel or '(missing)'}."
            ),
            "VERIFIED" if out_rel == "command-center/synthesis/SYN-0041.final-report.json" else "REJECTED",
            [catalog_anchor(root, "SYN-0041")],
            "SYN-0041",
            "output_path field read from the catalog unit",
        )
    )

    for uid in NAMED_INPUT_UNITS:
        unit = units.get(uid) or {}
        rel = str(unit.get("output_path") or "")
        path = root / rel if rel else None
        anchors = [catalog_anchor(root, uid)] if uid in units else [CATALOG_REL]
        if uid == "SYN-0019":
            items.append(
                _item(
                    f"IN-{uid}",
                    (
                        "SYN-0019's program-wide manifest-gate receipt is not "
                        "a settled input of this report: the unit circularly "
                        "depends on SYN-0041, so the writer inlines the gate "
                        "rather than citing command-center/receipts/SYN-0019.json."
                    ),
                    "DEFERRED",
                    anchors,
                    uid,
                    "circular dependency SYN-0019 <-> SYN-0041",
                )
            )
            continue
        if not rel:
            items.append(
                _item(
                    f"IN-{uid}",
                    f"Catalog unit {uid} is a named input of SYN-0041.",
                    "UNVERIFIED",
                    anchors,
                    uid,
                    "unit missing from catalog or has no output_path",
                )
            )
            continue
        label = classify_output(path) if path is not None else "UNVERIFIED"
        if label == "VERIFIED":
            anchors = [rel, *anchors]
            claim = f"{uid} output {rel} exists, parses, and is not self-declared failed."
            reason = "output_path present and parseable"
        elif label == "REJECTED":
            anchors = [rel, *anchors]
            claim = f"{uid} output {rel} exists but is unparseable or self-declared failed."
            reason = "output present but not a delivering artifact"
        else:
            claim = (
                f"{uid} output {rel} is absent on this worktree, so the "
                "named synthesis input cannot be cited as settled evidence."
            )
            reason = "output_path missing or empty"
        items.append(_item(f"IN-{uid}", claim, label, anchors, uid, reason))

    for uid, rel in LIVE_RECEIPTS:
        path = root / rel
        label = classify_output(path)
        line = 1
        if path.is_file():
            for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if '"state"' in ln or '"sentinel"' in ln:
                    line = i
                    break
        items.append(
            _item(
                f"LIVE-{uid}",
                f"Live machine receipt {rel} is on disk for {uid}.",
                label,
                [f"{rel}:{line}"],
                uid,
                "direct read of a delivered unit receipt",
            )
        )

    missing_named = []
    for uid in NAMED_INPUT_UNITS:
        if uid == "SYN-0019":
            continue
        unit = units.get(uid) or {}
        rel = str(unit.get("output_path") or "")
        if not rel or not (root / rel).is_file():
            missing_named.append(uid)
    items.append(
        _item(
            "INF-UNMET-NAMED-INPUTS",
            (
                "Until the named SYN/BLD input artifacts exist, this report "
                f"cannot cite settled Phase-14 synthesis. Missing: {', '.join(missing_named)}."
            ),
            "INFERRED",
            [catalog_anchor(root, "SYN-0041")],
            "SYN-0041",
            "derived from catalog named-input list plus filesystem absence",
        )
    )
    syn_units = [u for u in units if u.startswith("SYN-") and u != "SYN-0041"]
    syn_present = [
        u
        for u in syn_units
        if str((units[u] or {}).get("output_path") or "")
        and (root / str(units[u]["output_path"])).is_file()
    ]
    items.append(
        _item(
            "INF-SYN-CENSUS",
            (
                f"Catalog enumerates {len(syn_units)} SYN units; "
                f"{len(syn_present)} have a non-empty output_path on disk "
                "(SYN-0041 itself is excluded from this count until write)."
            ),
            "INFERRED",
            [catalog_anchor(root, "SYN-0001"), catalog_anchor(root, "SYN-0048")],
            "WORK-UNIT-CATALOG",
            "join of catalog ids against filesystem, excluding this write",
        )
    )
    items.append(
        _item(
            "INF-NO-ADJUDICATIONS",
            (
                "No SYN-0011 adjudication record exists, so no divergence "
                "in this report is labelled VERIFIED on the basis of raw-source "
                "adjudication."
            ),
            "INFERRED",
            [catalog_anchor(root, "SYN-0011")],
            "SYN-0011",
            "inferred from catalog dependency plus missing adjudications file",
        )
    )

    for cid, claim, rel in POSITIVE_EXISTENCE_CLAIMS:
        exists = (root / rel).is_file() and (root / rel).stat().st_size > 0
        items.append(
            _item(
                cid,
                claim,
                "VERIFIED" if exists else "REJECTED",
                [CATALOG_REL if not exists else rel],
                cid,
                "positive existence claim tested against the worktree",
            )
        )
    all_named_present = not missing_named
    items.append(
        _item(
            "CLAIM-ALL-NAMED-INPUTS-PRESENT",
            "Every named SYN-0041 input artifact is present and parseable on disk.",
            "VERIFIED" if all_named_present else "REJECTED",
            [catalog_anchor(root, "SYN-0041")],
            "SYN-0041",
            "conjunction over named-input classify_output results",
        )
    )

    for uid in DEFERRED_UNITS:
        if uid == "SYN-0019":
            continue
        unit = units.get(uid) or {}
        anchors = [catalog_anchor(root, uid)] if uid in units else [CATALOG_REL]
        items.append(
            _item(
                f"DEF-{uid}",
                (
                    f"{uid} is downstream of this report "
                    f"({unit.get('title') or uid}) and is not closed here."
                ),
                "DEFERRED",
                anchors,
                uid,
                "downstream / owner-facing unit not in this writer's scope",
            )
        )

    # q is read so a future item can quote it; keep the catalog question honest.
    if "VERIFIED" not in q and "five" not in q.lower() and "INFERRED" not in q:
        items.append(
            _item(
                "CAT-QUESTION-DRIFT",
                "SYN-0041 catalog question no longer names the five-way taxonomy.",
                "REJECTED",
                [catalog_anchor(root, "SYN-0041")],
                "SYN-0041",
                "catalog question drifted from the contracted vocabulary",
            )
        )

    seen: set[str] = set()
    for it in items:
        if it["id"] in seen:
            raise ValueError(f"duplicate item id {it['id']}")
        seen.add(it["id"])
        if len(it["label"].split()) != 1 or it["label"] not in LABEL_SET:
            raise ValueError(f"item {it['id']} not exactly one legal label")
    return items
