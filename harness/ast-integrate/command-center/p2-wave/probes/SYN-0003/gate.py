"""Coverage, restatement, and runnable-probe gates for SYN-0003."""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
PY_RE = re.compile(r"(command-center/\S+?\.py)")
COMPLETING = frozenset({"RIVAL", "SINGLE-HYPOTHESIS"})
THRESHOLD = 0.60
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "as",
        "by",
        "at",
        "be",
        "it",
        "that",
        "this",
        "with",
        "from",
        "not",
        "no",
        "was",
        "were",
        "are",
        "has",
        "have",
        "because",
        "than",
        "rather",
    }
)


def tokens(text: str) -> frozenset[str]:
    return frozenset(
        t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOP and len(t) > 1
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap(cause: str, rival: str) -> float:
    return round(jaccard(tokens(cause), tokens(rival)), 4)


def probe_path_from_command(cmd: str) -> str:
    m = PY_RE.search((cmd or "").replace("\\", "/"))
    return m.group(1) if m else ""


def runnable(cmd: str, repo: Path) -> tuple[bool, str, str]:
    rel = probe_path_from_command(cmd)
    if not rel:
        return False, "", "no-python-path-in-command"
    path = repo / rel
    if not path.is_file():
        return False, rel, "path-absent"
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return False, rel, f"unparseable:{type(exc).__name__}"
    return True, rel, "ok"


def coverage(cause_ids: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(
        str(r.get("cause_id") or "") for r in records if isinstance(r, dict)
    )
    missing: list[str] = []
    duplicate: list[str] = []
    unlabeled: list[str] = []
    non_disc_only: list[str] = []
    for cid in cause_ids:
        n = counts.get(cid, 0)
        if n == 0:
            missing.append(cid)
            continue
        if n != 1:
            duplicate.append(cid)
            continue
        rec = next(r for r in records if str(r.get("cause_id")) == cid)
        lab = str(rec.get("label") or "")
        if lab == "NON-DISCRIMINATING":
            non_disc_only.append(cid)
            missing.append(cid)
        elif lab not in COMPLETING:
            unlabeled.append(cid)
            missing.append(cid)
        elif lab == "SINGLE-HYPOTHESIS" and not str(
            rec.get("single_hypothesis_reason") or ""
        ).strip():
            unlabeled.append(cid)
            missing.append(cid)
    extra = [k for k in counts if k and k not in set(cause_ids)]
    rival_n = sum(1 for r in records if r.get("label") == "RIVAL")
    sh_n = sum(1 for r in records if r.get("label") == "SINGLE-HYPOTHESIS")
    nd_n = sum(1 for r in records if r.get("label") == "NON-DISCRIMINATING")
    ok = not missing and not duplicate and not unlabeled and not extra
    return {
        "cause_count": len(cause_ids),
        "rival_count": rival_n,
        "single_hypothesis_count": sh_n,
        "non_discriminating_count": nd_n,
        "missing_cause_ids": missing,
        "duplicate_cause_ids": duplicate,
        "unlabelled_cause_ids": unlabeled,
        "non_discriminating_only": non_disc_only,
        "extra_cause_ids": extra,
        "ok": ok,
    }


def restatement_hits(
    records: list[dict[str, Any]], threshold: float = THRESHOLD
) -> list[dict[str, Any]]:
    hits = []
    for rec in records:
        if rec.get("label") != "RIVAL":
            continue
        j = overlap(
            str(rec.get("cause_statement") or ""),
            str(rec.get("rival_statement") or ""),
        )
        if j >= threshold:
            hits.append(
                {
                    "cause_id": rec.get("cause_id"),
                    "token_overlap": j,
                    "threshold": threshold,
                }
            )
    return hits


def non_discriminating_hits(records: list[dict[str, Any]]) -> list[str]:
    bad = []
    for rec in records:
        if rec.get("label") != "RIVAL":
            continue
        shared = re.sub(
            r"\s+", " ", str(rec.get("shared_observation") or "")
        ).strip().lower()
        diff = re.sub(
            r"\s+", " ", str(rec.get("discriminating_observation") or "")
        ).strip().lower()
        if not diff or shared == diff:
            bad.append(str(rec.get("cause_id")))
    return bad


def unrunnable_hits(
    records: list[dict[str, Any]], repo: Path
) -> list[dict[str, Any]]:
    bad = []
    for rec in records:
        if rec.get("label") != "RIVAL":
            continue
        exp = rec.get("experiment") or {}
        cmd = str(exp.get("command") or "")
        ok, rel, why = runnable(cmd, repo)
        if not ok:
            bad.append(
                {
                    "cause_id": rec.get("cause_id"),
                    "command": cmd,
                    "probe_path": rel or exp.get("probe_path"),
                    "why": why,
                }
            )
    return bad
