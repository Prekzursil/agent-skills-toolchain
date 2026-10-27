"""Three ordered checks: background receipt, Test-Path, parseable."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHECK_BACKGROUND = "background_receipt"
CHECK_TEST_PATH = "test_path"
CHECK_PARSEABLE = "parseable"
BACKGROUND_MARKERS = (
    "started in the background",
    "check /codex:status",
)


def _posix(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("/")


def _text_blob(result: dict[str, Any]) -> str:
    parts = [
        str(result.get("result_text") or ""),
        str(result.get("text") or ""),
        str(result.get("kind") or ""),
        str(result.get("result_id") or ""),
    ]
    digest = result.get("digest")
    if isinstance(digest, dict):
        parts.append(json.dumps(digest, sort_keys=True))
    elif digest is not None:
        parts.append(str(digest))
    return "\n".join(parts).lower()


def _is_background(result: dict[str, Any]) -> bool:
    blob = _text_blob(result)
    return any(marker in blob for marker in BACKGROUND_MARKERS)


def _contracted_path(root: Path, result: dict[str, Any]) -> Path:
    rel = _posix(
        str(
            result.get("contracted_output_path")
            or result.get("output_path")
            or ""
        )
    )
    return Path(root) / rel


def evaluate_result(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Run (a) background, (b) Test-Path, (c) parseable. Skip later checks on fail."""
    checks: list[dict[str, Any]] = []
    file_opened = False
    rejected_by: str | None = None

    bg_fail = _is_background(result)
    checks.append(
        {
            "name": CHECK_BACKGROUND,
            "passed": not bg_fail,
            "skipped": False,
            "detail": "background-receipt markers in result_text"
            if bg_fail
            else "no background markers",
        }
    )
    if bg_fail:
        rejected_by = CHECK_BACKGROUND
        checks.append(
            {
                "name": CHECK_TEST_PATH,
                "passed": False,
                "skipped": True,
                "detail": "skipped after background_receipt",
            }
        )
        checks.append(
            {
                "name": CHECK_PARSEABLE,
                "passed": False,
                "skipped": True,
                "detail": "skipped after background_receipt",
            }
        )
        return {
            "passed": False,
            "rejected_by": rejected_by,
            "file_opened": False,
            "checks": checks,
        }

    path = _contracted_path(root, result)
    exists = path.is_file()
    checks.append(
        {
            "name": CHECK_TEST_PATH,
            "passed": exists,
            "skipped": False,
            "detail": str(path.as_posix()),
        }
    )
    if not exists:
        rejected_by = CHECK_TEST_PATH
        checks.append(
            {
                "name": CHECK_PARSEABLE,
                "passed": False,
                "skipped": True,
                "detail": "skipped after test_path",
            }
        )
        return {
            "passed": False,
            "rejected_by": rejected_by,
            "file_opened": False,
            "checks": checks,
        }

    file_opened = True
    raw = path.read_bytes()
    parse_ok = bool(raw.strip())
    if parse_ok:
        try:
            json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parse_ok = False
    checks.append(
        {
            "name": CHECK_PARSEABLE,
            "passed": parse_ok,
            "skipped": False,
            "detail": "non-empty json" if parse_ok else "empty-or-unparsable",
        }
    )
    if not parse_ok:
        rejected_by = CHECK_PARSEABLE
    return {
        "passed": rejected_by is None,
        "rejected_by": rejected_by,
        "file_opened": file_opened,
        "checks": checks,
    }
