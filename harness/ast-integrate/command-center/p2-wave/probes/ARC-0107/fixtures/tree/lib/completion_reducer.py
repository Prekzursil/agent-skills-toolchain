"""Canonical shared completion reducer.

Every fan-in site must import ``reduce_completion`` from this module.
Exit code zero alone is never success. A path in text is not proof a
file exists. A plausible digest is not a receipt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CONDITION_IDS = tuple(f"C{i}" for i in range(1, 13))

ANTI_PATTERNS = (
    "exit code zero alone is never success",
    "a plausible digest is not a receipt",
    "a file path in text is not proof the file exists",
)


def _row(cid: str, result: str, reason: str) -> dict[str, str]:
    return {"id": cid, "result": result, "reason": reason}


def reduce_completion(receipt: dict[str, Any]) -> dict[str, Any]:
    """Typed twelve-condition verdict. UNKNOWN is distinct from FAIL."""
    if not isinstance(receipt, dict):
        return {
            "verdict": "INCOMPLETE",
            "conditions": [_row("C1", "FAIL", "receipt is not an object")],
        }

    rows: list[dict[str, str]] = []
    terminal = str(receipt.get("state") or "").upper()
    rows.append(
        _row(
            "C1",
            "PASS" if terminal in {"SUCCESS", "FAILED", "BLOCKED"} else "FAIL",
            f"terminal={terminal or 'missing'}",
        )
    )

    path_text = str(receipt.get("artifact_path") or "")
    artifact = Path(path_text) if path_text else None
    exists = bool(artifact is not None and artifact.is_file())
    rows.append(
        _row(
            "C2",
            "PASS" if exists else "FAIL",
            "artifact exists on disk" if exists else "artifact missing (path in text is not proof)",
        )
    )

    raw = artifact.read_bytes() if exists else b""
    min_bytes = int(receipt.get("min_bytes") or 1)
    rows.append(
        _row(
            "C3",
            "PASS" if exists and len(raw) >= min_bytes else "FAIL",
            f"bytes={len(raw)} min={min_bytes}",
        )
    )

    schema_ok = bool(receipt.get("schema_valid")) if exists else False
    rows.append(_row("C4", "PASS" if schema_ok else "FAIL", "schema_valid flag"))

    sentinel = str(receipt.get("sentinel") or "")
    text = raw.decode("utf-8", errors="replace") if exists else ""
    rows.append(
        _row(
            "C5",
            "PASS" if sentinel and sentinel in text else "FAIL",
            "sentinel present in artifact bytes",
        )
    )

    anchors = receipt.get("evidence_anchors") or []
    rows.append(
        _row("C6", "PASS" if isinstance(anchors, list) and anchors else "FAIL", "evidence anchors")
    )

    tests = receipt.get("tests") or []
    tests_ok = isinstance(tests, list) and tests and all(
        isinstance(t, dict) and t.get("result") == "PASS" for t in tests
    )
    rows.append(_row("C7", "PASS" if tests_ok else "FAIL", "required tests"))

    controls = receipt.get("negative_controls") or []
    controls_ok = isinstance(controls, list) and any(
        isinstance(c, dict) and c.get("fired") is True for c in controls
    )
    rows.append(_row("C8", "PASS" if controls_ok else "FAIL", "negative controls fired"))

    reviewer = receipt.get("reviewer") or {}
    rows.append(
        _row(
            "C9",
            "PASS" if isinstance(reviewer, dict) and reviewer.get("verdict") == "PASS" else "FAIL",
            "independent reviewer",
        )
    )

    rows.append(
        _row(
            "C10",
            "PASS" if not receipt.get("unresolved_p0_p1") else "FAIL",
            "no unresolved P0/P1",
        )
    )

    rows.append(
        _row(
            "C11",
            "PASS" if receipt.get("manifest_registered") is True else "FAIL",
            "artifact registered in unit manifest",
        )
    )

    rows.append(
        _row(
            "C12",
            "PASS" if receipt.get("downstream_read_ok") is True else "FAIL",
            "downstream consumer read the artifact",
        )
    )

    exit_code = receipt.get("exit_code")
    # Explicit anti-pattern: exit 0 never folds a missing artifact into PASS.
    if exit_code == 0 and not exists:
        rows[1] = _row("C2", "FAIL", "exit-zero-with-missing-artifact")

    digest = str(receipt.get("digest") or "")
    if digest and not exists:
        rows.append(_row("C2b", "FAIL", "plausible digest is not a receipt"))

    failing = [r for r in rows if r["result"] == "FAIL"]
    unknown = [r for r in rows if r["result"] == "UNKNOWN"]
    if unknown and not failing:
        verdict = "UNKNOWN"
    elif failing:
        verdict = "INCOMPLETE"
    else:
        verdict = "COMPLETE"
    return {
        "verdict": verdict,
        "conditions": rows,
        "exit_code_alone_never_success": True,
        "canonical_module": "lib.completion_reducer",
        "canonical_symbol": "reduce_completion",
    }
