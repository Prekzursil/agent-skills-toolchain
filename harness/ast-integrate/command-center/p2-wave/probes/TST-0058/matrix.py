#!/usr/bin/env python3
"""Accept/reject agreement matrix: strict vs aligned-lenient (TST-0058)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.json_ingest import (  # noqa: E402
    ParseResult,
    decisions_agree,
    jsonc_loads,
    lenient_loads,
    strict_loads,
    values_agree,
)

import corpus as C  # noqa: E402

Loader = Callable[[str], ParseResult]


def _sha(value: Any) -> str | None:
    if value is None:
        return None
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def row_for(path: Path, kind: str, left: Loader, right: Loader) -> dict[str, Any]:
    rel = path.relative_to(REPO).as_posix() if path.is_absolute() else str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "path": rel,
            "kind": kind,
            "strict": "reject",
            "lenient": "reject",
            "agree": True,
            "read_error": type(exc).__name__,
        }
    a = left(text)
    b = right(text)
    left_name = getattr(left, "__name__", "left").replace("_loads", "")
    right_name = getattr(right, "__name__", "right").replace("_loads", "")
    # Canonical column names when comparing production pair.
    if left is strict_loads and right is lenient_loads:
        left_name, right_name = "strict", "lenient"
    agree = decisions_agree(a, b)
    item: dict[str, Any] = {
        "path": rel,
        "kind": kind,
        left_name: a.decision(),
        right_name: b.decision(),
        "agree": agree,
        "values_agree": values_agree(a, b) if agree and a.accepted else True,
        "features_lenient": list(b.features) if right is lenient_loads else list(b.features),
        "features_left": list(a.features),
        "strict_error": a.error if not a.accepted else None,
        "lenient_error": b.error if not b.accepted else None,
        "strict_pos": (
            f"{a.line}:{a.column}" if a.line is not None else None
        ),
        "value_sha256": _sha(a.value) if a.accepted else None,
    }
    if left is not strict_loads or right is not lenient_loads:
        item[f"{left_name}_error"] = a.error if not a.accepted else None
        item[f"{right_name}_error"] = b.error if not b.accepted else None
    return item


def production_matrix(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    info = C.require_corpus(root)
    rows: list[dict[str, Any]] = []
    for rel in info["real_paths"]:
        rows.append(row_for(root / rel, "real", strict_loads, lenient_loads))
    for rel in info["adversarial_paths"]:
        rows.append(row_for(root / rel, "adversarial", strict_loads, lenient_loads))
    disagreements = [r for r in rows if not r["agree"] or r.get("values_agree") is False]
    real_rows = [r for r in rows if r["kind"] == "real"]
    adv_rows = [r for r in rows if r["kind"] == "adversarial"]
    both_reject_adv = [
        r
        for r in adv_rows
        if r.get("strict") == "reject" and r.get("lenient") == "reject"
    ]
    both_accept_real = [
        r
        for r in real_rows
        if r.get("strict") == "accept" and r.get("lenient") == "accept"
    ]
    return {
        "unit_id": "TST-0058",
        "left": "strict_loads (shipped client, json.loads)",
        "right": "lenient_loads (aligned dev-tool ingest; JSON5-isms refused)",
        "real_count": len(real_rows),
        "adversarial_count": len(adv_rows),
        "row_count": len(rows),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "real_both_accept": len(both_accept_real),
        "adversarial_both_reject": len(both_reject_adv),
        "corpus_ok": info["ok"],
        "rows": rows,
    }


def control_matrix(repo: Path | None = None) -> dict[str, Any]:
    """Same corpus through (strict, jsonc). Must DISAGREE on adversarial docs."""
    root = repo or REPO
    info = C.require_corpus(root)
    rows: list[dict[str, Any]] = []
    for rel in info["adversarial_paths"]:
        rows.append(row_for(root / rel, "adversarial", strict_loads, jsonc_loads))
    disagreements = [r for r in rows if not r["agree"]]
    jsonc_accepts = [r for r in rows if r.get("jsonc") == "accept"]
    strict_rejects = [r for r in rows if r.get("strict") == "reject"]
    planted = [
        r
        for r in rows
        if r.get("strict") == "reject" and r.get("jsonc") == "accept"
    ]
    return {
        "unit_id": "TST-0058",
        "left": "strict_loads",
        "right": "jsonc_loads (unaligned diagnostic parser)",
        "adversarial_count": len(rows),
        "jsonc_accept_count": len(jsonc_accepts),
        "strict_reject_count": len(strict_rejects),
        "planted_divergence_count": len(planted),
        "disagreement_count": len(disagreements),
        "rows": rows,
    }


def test_no_document_is_accepted_by_one_path_and_rejected_by_the_other(
    matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    m = matrix or production_matrix()
    ok = (
        m["corpus_ok"]
        and m["real_count"] >= C.MIN_REAL
        and m["adversarial_count"] >= 10
        and m["disagreement_count"] == 0
        and m["real_both_accept"] == m["real_count"]
    )
    return {
        "id": "test_no_document_is_accepted_by_one_path_and_rejected_by_the_other",
        "result": "PASS" if ok else "FAIL",
        "ok": ok,
        "real_count": m["real_count"],
        "adversarial_count": m["adversarial_count"],
        "disagreement_count": m["disagreement_count"],
        "real_both_accept": m["real_both_accept"],
        "disagreements": m["disagreements"][:12],
    }


def test_the_adversarial_documents_are_rejected_by_both(
    matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    m = matrix or production_matrix()
    ok = (
        m["adversarial_count"] >= 10
        and m["adversarial_both_reject"] == m["adversarial_count"]
        and m["disagreement_count"] == 0
    )
    return {
        "id": "test_the_adversarial_documents_are_rejected_by_both",
        "result": "PASS" if ok else "FAIL",
        "ok": ok,
        "adversarial_count": m["adversarial_count"],
        "adversarial_both_reject": m["adversarial_both_reject"],
        "disagreements": m["disagreements"][:12],
    }
