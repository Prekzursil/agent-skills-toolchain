"""Completion-predicate condition 12: existence is not readability.

A downstream consumer must open the artifact, parse it, and extract a
required field the consumer can actually use. ``os.path.exists`` (and a
parse-plus-key-presence check) are not that consumer.

Codes:
  READABLE                 required field is a non-empty string
  ABSENT                   open/read failed (missing path, permission, ...)
  UNPARSEABLE              bytes exist but are not UTF-8 JSON object
  MISSING_REQUIRED_FIELD   JSON object lacks the required key
  REQUIRED_FIELD_UNUSABLE  key is present but the value is not a usable string
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_FIELD = "sentinel"

CODES = (
    "READABLE",
    "ABSENT",
    "UNPARSEABLE",
    "MISSING_REQUIRED_FIELD",
    "REQUIRED_FIELD_UNUSABLE",
)


@dataclass(frozen=True)
class ConsumeResult:
    ok: bool
    code: str
    path: str
    extracted: str | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "detail": self.detail,
            "extracted": self.extracted,
            "path": self.path,
        }


def _result(
    path: Path,
    *,
    ok: bool,
    code: str,
    extracted: str | None = None,
    detail: str = "",
) -> ConsumeResult:
    return ConsumeResult(
        ok=ok,
        code=code,
        path=str(path),
        extracted=extracted,
        detail=detail,
    )


def _usable_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def consume(path: Path, required_field: str = REQUIRED_FIELD) -> ConsumeResult:
    """Open, parse, and extract ``required_field``. Do not stat-and-return."""
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as exc:
        return _result(
            target,
            ok=False,
            code="ABSENT",
            detail=f"{type(exc).__name__}: {exc}",
        )
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _result(target, ok=False, code="UNPARSEABLE", detail=str(exc))
    if not isinstance(doc, dict):
        return _result(
            target,
            ok=False,
            code="UNPARSEABLE",
            detail=f"root is {type(doc).__name__}, want object",
        )
    if required_field not in doc:
        return _result(
            target,
            ok=False,
            code="MISSING_REQUIRED_FIELD",
            detail=required_field,
        )
    value = doc[required_field]
    if not _usable_string(value):
        return _result(
            target,
            ok=False,
            code="REQUIRED_FIELD_UNUSABLE",
            detail=(
                f"{required_field} type={type(value).__name__} usable=false"
            ),
        )
    return _result(target, ok=True, code="READABLE", extracted=value, detail="")


def condition_12(path: Path, required_field: str = REQUIRED_FIELD) -> ConsumeResult:
    """Reducer-facing name for condition 12. Delegates to consume()."""
    return consume(path, required_field=required_field)


def mutant_exists_only(path: Path) -> bool:
    """Catalog mutation: reduce the probe to ``os.path.exists``.

    This mutant greens a file that exists, parses, and lacks the required
    field — which is exactly why the three-fixture battery requires that
    third fixture to FAIL under consume().
    """
    return os.path.exists(path)


def decorative_parse_and_key(
    path: Path, required_field: str = REQUIRED_FIELD
) -> bool:
    """Parse plus key-presence. Passes when the value is an unusable object.

    The adversarial fourth fixture is built to make this return True while
    consume() returns REQUIRED_FIELD_UNUSABLE.
    """
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and required_field in doc
