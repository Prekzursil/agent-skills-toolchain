#!/usr/bin/env python3
"""Bidirectional contradiction accounting for ADV-0109.

Probe 1 direction: start from recorded contradiction pairs, classify each
as represented / resolved-with-reason / silently-dropped against the
synthesis text.

Probe 2 direction: start from agreement/convergence claims in the
synthesis, then ask whether unresolved contradiction pairs remain
(manufactured consensus).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "cases.json"
OUT_REL = "command-center/adversarial/ADV-0109-dissent-omission-differential.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0109 emitted ONLY when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, records BOTH named probes verbatim with their raw output, "
    "carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per "
    "enumerated target, and records the result of every listed control/negative test. Any "
    "missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0109 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0109/probe1_omitted_dissent.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0109/probe2_manufactured_consensus.py"
)
# Aliases used by emit_artifact.py / write_receipts.py
SCHEMA_REL = SCHEMA_REL
P1_CMD = P1_CMD
P2_CMD = P2_CMD
COMPLETION_SENTINEL = COMPLETION_SENTINEL

CONFLICT_MARKERS = (
    "disagreement",
    "dissent",
    "contradict",
    "versus",
    "conflict",
    "split",
    "minority",
    "opposed",
    "counterclaim",
    "disagree",
)
REASON_MARKERS = (
    "because",
    "we adopt",
    "resolved",
    "superseded",
    "disposal",
    "overruled",
    "settled by",
    "evidence shows",
)
AGREE_RE = re.compile(
    r"\b("
    r"all participants agree|"
    r"everyone agreed|"
    r"consensus is unanimous|"
    r"unanimous|"
    r"no remaining disagreement|"
    r"full convergence|"
    r"there is no remaining disagreement"
    r")\b",
    re.IGNORECASE,
)

LIVE_PATHS = (
    "command-center/CLAIM-REGISTRY.json",
    "command-center/synthesis",
    "command-center/adversarial",
)


def load_cases(path: Path | None = None) -> dict:
    target = path or FIXTURE
    return json.loads(target.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", (text or "").lower()) + " "


def claim_present(claim: dict, synthesis_text: str) -> bool:
    blob = _norm(synthesis_text)
    cid = str(claim.get("id") or "").lower()
    if cid and cid in blob:
        return True
    markers = [str(m).lower() for m in (claim.get("markers") or []) if str(m).strip()]
    if markers:
        return all(m in blob for m in markers)
    words = re.findall(r"[a-z0-9]{4,}", str(claim.get("text") or "").lower())
    if not words:
        return False
    hit = sum(1 for w in words if w in blob)
    return hit / len(words) >= 0.6


def has_marker(text: str, markers: tuple[str, ...]) -> bool:
    blob = _norm(text)
    return any(m in blob for m in markers)


def claim_by_id(claims: list[dict], cid: str) -> dict:
    for row in claims:
        if row.get("id") == cid:
            return row
    raise KeyError(cid)


def classify_pair(pair: dict, claims: list[dict], synthesis_text: str) -> dict:
    a = claim_by_id(claims, pair["claim_a"])
    b = claim_by_id(claims, pair["claim_b"])
    a_ok = claim_present(a, synthesis_text)
    b_ok = claim_present(b, synthesis_text)
    conflict = has_marker(synthesis_text, CONFLICT_MARKERS)
    reason = has_marker(synthesis_text, REASON_MARKERS)
    if a_ok and b_ok and reason:
        label = "resolved-with-reason"
    elif a_ok and b_ok and conflict:
        label = "represented"
    else:
        label = "silently-dropped"
    return {
        "pair_id": pair["id"],
        "claim_a": pair["claim_a"],
        "claim_b": pair["claim_b"],
        "a_present": a_ok,
        "b_present": b_ok,
        "conflict_acknowledged": conflict,
        "reason_stated": reason,
        "class": label,
    }


def agreement_spans(synthesis_text: str) -> list[str]:
    return [m.group(0) for m in AGREE_RE.finditer(synthesis_text or "")]


def classify_synthesis(row: dict) -> dict:
    text = str(row.get("synthesis_text") or "")
    claims = list((row.get("raw_inputs") or {}).get("claims") or [])
    pairs = list((row.get("raw_inputs") or {}).get("contradiction_pairs") or [])
    classified = [classify_pair(p, claims, text) for p in pairs]
    counts = {
        "represented": 0,
        "resolved-with-reason": 0,
        "silently-dropped": 0,
    }
    for item in classified:
        counts[item["class"]] += 1
    unresolved = [
        item
        for item in classified
        if item["class"] in {"silently-dropped", "represented"}
    ]
    spans = agreement_spans(text)
    manufactured = bool(spans) and bool(unresolved)
    return {
        "id": row["id"],
        "role": row.get("role"),
        "pair_count": len(classified),
        "pairs": classified,
        "counts": counts,
        "agreement_spans": spans,
        "unresolved_pair_ids": [u["pair_id"] for u in unresolved],
        "manufactured_consensus": manufactured,
        "expect_probe1": dict(row.get("expect_probe1") or {}),
        "expect_probe2_manufactured": bool(row.get("expect_probe2_manufactured")),
    }


def classify_all(doc: dict | None = None) -> dict:
    data = doc if doc is not None else load_cases()
    rows = [classify_synthesis(s) for s in data.get("syntheses") or []]
    totals = {
        "represented": 0,
        "resolved-with-reason": 0,
        "silently-dropped": 0,
        "pair_count": 0,
        "manufactured_true": 0,
        "manufactured_false": 0,
    }
    mismatches = []
    for row in rows:
        for key in ("represented", "resolved-with-reason", "silently-dropped"):
            totals[key] += row["counts"][key]
        totals["pair_count"] += row["pair_count"]
        if row["manufactured_consensus"]:
            totals["manufactured_true"] += 1
        else:
            totals["manufactured_false"] += 1
        for pair in row["pairs"]:
            want = row["expect_probe1"].get(pair["pair_id"])
            if want and want != pair["class"]:
                mismatches.append(
                    {
                        "synthesis": row["id"],
                        "pair_id": pair["pair_id"],
                        "want": want,
                        "got": pair["class"],
                    }
                )
        if row["manufactured_consensus"] != row["expect_probe2_manufactured"]:
            mismatches.append(
                {
                    "synthesis": row["id"],
                    "axis": "manufactured_consensus",
                    "want": row["expect_probe2_manufactured"],
                    "got": row["manufactured_consensus"],
                }
            )
    dropped = totals["silently-dropped"]
    denom = totals["pair_count"]
    return {
        "rows": rows,
        "totals": totals,
        "ratio": {
            "silently_dropped": dropped,
            "represented": totals["represented"],
            "resolved_with_reason": totals["resolved-with-reason"],
            "denominator": denom,
            "drop_rate": (dropped / denom) if denom else None,
        },
        "mismatches": mismatches,
        "expect_match": not mismatches,
    }


def control_represented(result: dict) -> dict:
    row = next(r for r in result["rows"] if r["id"] == "SYN-REPRESENTED")
    got = row["pairs"][0]["class"] if row["pairs"] else None
    return {
        "id": "control-represented",
        "pass": got == "represented",
        "got": got,
        "want": "represented",
    }


def control_planted_drop(result: dict) -> dict:
    row = next(r for r in result["rows"] if r["id"] == "SYN-DROP")
    got = row["pairs"][0]["class"] if row["pairs"] else None
    return {
        "id": "control-planted-silent-drop",
        "pass": got == "silently-dropped",
        "got": got,
        "want": "silently-dropped",
    }


def mutant_strip_conflict_markers(doc: dict) -> dict:
    """Both-states mutant: wipe conflict language from the represented case.

    The represented pair should then classify as silently-dropped, proving
    the detector is not glued to the pair id.
    """
    clone = json.loads(json.dumps(doc))
    for row in clone["syntheses"]:
        if row["id"] == "SYN-REPRESENTED":
            text = row["synthesis_text"]
            for marker in CONFLICT_MARKERS:
                text = re.sub(re.escape(marker), "noted", text, flags=re.I)
            row["synthesis_text"] = text
    return clone


def mutant_strip_drop_pair(doc: dict) -> dict:
    """Both-states mutant: remove the planted contradiction from SYN-DROP.

    The silent-drop detector must go silent (no P-MINORITY pair left).
    """
    clone = json.loads(json.dumps(doc))
    for row in clone["syntheses"]:
        if row["id"] == "SYN-DROP":
            row["raw_inputs"]["contradiction_pairs"] = []
            row["expect_probe1"] = {}
    return clone


def live_inventory(repo: Path | None = None) -> dict:
    root = repo or REPO
    found: list[dict[str, Any]] = []
    for rel in LIVE_PATHS:
        path = root / rel
        found.append(
            {
                "path": rel,
                "exists": path.exists(),
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    extra = []
    for pattern in (
        "command-center/**/*synthesis*.json",
        "command-center/**/CLAIM-REGISTRY.json",
        "command-center/adversarial/*.json",
    ):
        for hit in sorted(root.glob(pattern)):
            rel = hit.relative_to(root).as_posix()
            if rel.endswith("ADV-0109-dissent-omission-differential.json"):
                continue
            extra.append(
                {
                    "path": rel,
                    "exists": True,
                    "bytes": hit.stat().st_size if hit.is_file() else None,
                }
            )
    live_pairs = 0
    claim_reg = root / "command-center/CLAIM-REGISTRY.json"
    if claim_reg.is_file():
        try:
            reg = json.loads(claim_reg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reg = None
        if isinstance(reg, dict):
            live_pairs = len(reg.get("contradiction_edges") or [])
    return {
        "checked": found,
        "extra_hits": extra,
        "live_contradiction_edges": live_pairs,
        "live_corpus_present": bool(extra) or any(x["exists"] for x in found if x["path"].endswith(".json")),
    }


def main() -> int:
    result = classify_all()
    print(json.dumps({"totals": result["totals"], "ratio": result["ratio"], "mismatches": result["mismatches"]}, sort_keys=True))
    return 0 if result["expect_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
