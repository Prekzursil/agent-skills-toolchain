#!/usr/bin/env python3
"""Independent-confirmation hook for the workflow certification path.

A confirmation is a receipt only when a confirmer who did not author the
workflow cites raw artifacts, every cited path exists (Test-Path) *before*
any digest is read, and the benchmark claim is recomputed from those files.

A confirmation that cites only the author's summary is rejected.
A digest is a claim, not a receipt (_USER-PROMPTS.md:10646).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RAW_ROLES = frozenset(
    {
        "per-case-row",
        "per_case_row",
        "raw-source",
        "raw-artifact",
        "raw-source-artifact",
        "case-row",
        "paired-row",
    }
)
SUMMARY_ROLES = frozenset(
    {"author-summary", "summary", "author_summary", "claim-summary"}
)
DIGEST_ROLES = frozenset({"digest", "claim-digest", "sha256", "checksum"})

VERDICT_ACCEPT = "ACCEPT"
VERDICT_REJECT = "REJECT"
REASON_SUMMARY_ONLY = "SUMMARY_ONLY"
REASON_DIGEST_IS_CLAIM = "DIGEST_IS_CLAIM"
REASON_PATH_ABSENT = "PATH_ABSENT"
REASON_NOT_INDEPENDENT = "AUTHOR_NOT_INDEPENDENT"
REASON_RECOMPUTE_MISMATCH = "RECOMPUTE_MISMATCH"
REASON_NO_CITATIONS = "NO_CITATIONS"
REASON_EMPTY_RAW = "EMPTY_RAW"


@dataclass
class GateResult:
    verdict: str
    reason: str
    trace: list[str] = field(default_factory=list)
    paths_existing: list[str] = field(default_factory=list)
    paths_missing: list[str] = field(default_factory=list)
    raw_citations: list[str] = field(default_factory=list)
    summary_citations: list[str] = field(default_factory=list)
    digest_read: bool = False
    digest_accepted: bool = False
    independent: bool = False
    recomputed: dict[str, Any] | None = None
    confirmer_id: str = ""
    author_id: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict == VERDICT_ACCEPT


def _norm_rel(rel: str) -> str:
    return str(rel or "").replace("\\", "/").lstrip("/")


def resolve_cited(root: Path, rel: str) -> Path:
    rel_n = _norm_rel(rel)
    if not rel_n:
        return root / "__empty_citation__"
    return root.joinpath(*rel_n.split("/"))


def test_path(root: Path, rel: str, trace: list[str]) -> bool:
    """Test-Path -PathType Leaf: file exists and is non-empty.

    This existence check MUST run before any digest is read.
    """
    rel_n = _norm_rel(rel)
    trace.append(f"test_path:{rel_n}")
    path = resolve_cited(root, rel_n)
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _is_raw_cite(cite: dict[str, Any]) -> bool:
    role = str(cite.get("role") or "").lower().replace(" ", "-")
    path = _norm_rel(str(cite.get("path") or "")).lower()
    role_ok = role in RAW_ROLES
    path_ok = (
        path.startswith("raw/")
        or "/raw/" in f"/{path}"
        or "per_case" in path
        or "case-" in path
    )
    return role_ok and path_ok


def _is_summary_cite(cite: dict[str, Any]) -> bool:
    role = str(cite.get("role") or "").lower().replace(" ", "-")
    path = _norm_rel(str(cite.get("path") or "")).lower()
    if role in SUMMARY_ROLES:
        return True
    return "summary" in path and not _is_raw_cite(cite)


def _is_digest_cite(cite: dict[str, Any]) -> bool:
    role = str(cite.get("role") or "").lower().replace(" ", "-")
    path = _norm_rel(str(cite.get("path") or "")).lower()
    return role in DIGEST_ROLES or path.endswith(".sha256") or path.endswith(".digest")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def recompute_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "mean_delta": None, "verdict": "INSUFFICIENT-EVIDENCE"}
    deltas = []
    for row in rows:
        if "delta" in row:
            deltas.append(float(row["delta"]))
        else:
            deltas.append(float(row["workflow_a"]) - float(row["workflow_b"]))
    n = len(deltas)
    mean = sum(deltas) / n
    verdict = "OUTPERFORMS" if mean > 0 else "NOT-BETTER"
    return {"n": n, "mean_delta": round(mean, 6), "verdict": verdict}


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "cases", "per_case_rows"):
            val = payload.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
        if "delta" in payload or ("workflow_a" in payload and "workflow_b" in payload):
            return [payload]
    return []


def _norm_verdict(value: Any) -> str:
    v = str(value or "").strip().upper().replace("_", "-")
    if v in {"OUTPERFORMS", "OUTPERFORM", "OUT-PERFORMS"}:
        return "OUTPERFORMS"
    if v in {"NOT-BETTER", "NOT_BETTER", "NOTBETTER"}:
        return "NOT-BETTER"
    return v


def _claims_match(recomputed: dict[str, Any], claimed: dict[str, Any]) -> bool:
    if int(recomputed.get("n") or -1) != int(claimed.get("n") or -2):
        return False
    rm = recomputed.get("mean_delta")
    cm = claimed.get("mean_delta")
    if cm is None:
        cm = claimed.get("mean_delta")
    if rm is None or cm is None:
        return False
    if abs(float(rm) - float(cm)) > 1e-9:
        return False
    claimed_verdict = claimed.get("verdict")
    if claimed_verdict is None:
        claimed_verdict = claimed.get("verdict")
    return _norm_verdict(recomputed.get("verdict")) == _norm_verdict(claimed_verdict)


def _confirmer_id(confirmation: dict[str, Any]) -> str:
    return str(
        confirmation.get("confirmer_id") or confirmation.get("confirmer_id") or ""
    ).strip()


def _cited_artifacts(confirmation: dict[str, Any]) -> list[Any]:
    cites = confirmation.get("cited_artifacts")
    if cites is None:
        cites = confirmation.get("cited_artifacts")
    if not isinstance(cites, list):
        return []
    return cites


def _independent(confirmation: dict[str, Any], workflow: dict[str, Any]) -> bool:
    confirmer = _confirmer_id(confirmation)
    author = str(workflow.get("author_id") or confirmation.get("author_id") or "").strip()
    if not confirmer or not author:
        return False
    if confirmer == author:
        return False
    authors: set[str] = set()
    for key in (
        "authoring_agents",
        "authoring_agents",
        "authors",
        "provenance_agents",
    ):
        val = workflow.get(key) or []
        if isinstance(val, list):
            authors.update(str(x) for x in val)
    if confirmer in authors:
        return False
    if confirmation.get("authored_workflow") is True:
        return False
    return True


def _reject(result: GateResult, reason: str) -> GateResult:
    result.verdict = VERDICT_REJECT
    result.reason = reason
    result.digest_accepted = False
    result.trace.append(f"verdict:{VERDICT_REJECT}:{reason}")
    return result


def admit(
    confirmation: dict[str, Any],
    workflow: dict[str, Any],
    root: Path,
) -> GateResult:
    """Run the independent-confirmation gate.

    Ordering is the contract: Test-Path every cited path, then (only if all
    exist and at least one is a raw source) recompute, then optionally read a
    digest. A digest is never accepted as a substitute for raw files.
    """
    result = GateResult(
        verdict=VERDICT_REJECT,
        reason=REASON_NO_CITATIONS,
        confirmer_id=_confirmer_id(confirmation),
        author_id=str(workflow.get("author_id") or ""),
    )
    trace = result.trace
    root = Path(root)

    trace.append("stage:independence_check")
    result.independent = _independent(confirmation, workflow)
    if not result.independent:
        return _reject(result, REASON_NOT_INDEPENDENT)

    cites = _cited_artifacts(confirmation)
    raw = [c for c in cites if isinstance(c, dict) and _is_raw_cite(c)]
    summaries = [c for c in cites if isinstance(c, dict) and _is_summary_cite(c)]
    digests = [c for c in cites if isinstance(c, dict) and _is_digest_cite(c)]
    result.raw_citations = [_norm_rel(str(c.get("path") or "")) for c in raw]
    result.summary_citations = [_norm_rel(str(c.get("path") or "")) for c in summaries]
    has_digest_field = bool(str(confirmation.get("digest") or "").strip())

    trace.append("stage:classify_citations")
    trace.append(
        "class:raw=%s summary=%s digest_cites=%s digest_field=%s"
        % (len(raw), len(summaries), len(digests), has_digest_field)
    )

    if not cites and not has_digest_field:
        return _reject(result, REASON_NO_CITATIONS)

    # Existence pass FIRST — before digest read, before parsing digest files.
    trace.append("stage:test_path")
    missing: list[str] = []
    existing: list[str] = []
    for cite in cites:
        if not isinstance(cite, dict):
            continue
        rel = _norm_rel(str(cite.get("path") or ""))
        if not rel:
            missing.append("(empty-path)")
            continue
        if test_path(root, rel, trace):
            existing.append(rel)
        else:
            missing.append(rel)
    result.paths_existing = existing
    result.paths_missing = missing
    if missing:
        return _reject(result, REASON_PATH_ABSENT)

    if not raw:
        if summaries:
            return _reject(result, REASON_SUMMARY_ONLY)
        if has_digest_field or digests:
            return _reject(result, REASON_DIGEST_IS_CLAIM)
        return _reject(result, REASON_SUMMARY_ONLY)

    trace.append("stage:recompute_from_raw")
    rows: list[dict[str, Any]] = []
    for cite in raw:
        rel = _norm_rel(str(cite.get("path") or ""))
        payload = _load_json(resolve_cited(root, rel))
        rows.extend(_rows_from_payload(payload))
    if not rows:
        return _reject(result, REASON_EMPTY_RAW)
    recomputed = recompute_from_rows(rows)
    result.recomputed = recomputed
    claimed = confirmation.get("claim") or confirmation.get("claim") or {}
    if not isinstance(claimed, dict) or not _claims_match(recomputed, claimed):
        return _reject(result, REASON_RECOMPUTE_MISMATCH)

    # Digest may be read only after Test-Path passed for every cited path.
    # It may corroborate; it is never the receipt.
    trace.append("stage:digest_read_allowed")
    if has_digest_field or digests:
        if has_digest_field:
            trace.append("digest_read:confirmation.digest")
            result.digest_read = True
        for cite in digests:
            rel = _norm_rel(str(cite.get("path") or ""))
            path = resolve_cited(root, rel)
            trace.append(f"digest_read:{rel}")
            result.digest_read = True
            _ = _file_digest(path)
        result.digest_accepted = False
        trace.append("digest:claim-not-receipt")

    result.verdict = VERDICT_ACCEPT
    result.reason = "RAW_RECOMPUTE_MATCH"
    trace.append(f"verdict:{VERDICT_ACCEPT}:{result.reason}")
    return result


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
