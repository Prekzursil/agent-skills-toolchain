"""Miniature product with one fallback of each catalog kind, plus two controls."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import events as E  # noqa: E402

SRC = "command-center/p2-wave/probes/BLD-0026/fixtures/product.py"


def default_on_exception(path: Path) -> dict:
    """Kind: default-on-exception. Parse error -> empty object, work file kept."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        E.emit_loud(
            capability_lost="json-document-parse",
            fallback_kind="default-on-exception",
            source=f"{SRC}:default_on_exception",
            artifact_preserved=str(path),
            reason=type(exc).__name__,
        )
        return {}


def best_effort_parse(path: Path) -> dict:
    """Kind: best-effort-parse. Salvage first object from garbage; never delete the file."""
    raw = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
        if isinstance(doc, dict):
            return doc
        raise ValueError("not-an-object")
    except Exception as exc:
        recovered = {}
        match = re.search(r"\{[^{}]*\}", raw)
        if match:
            try:
                recovered = json.loads(match.group(0))
            except Exception:
                recovered = {"salvaged": False}
        E.emit_loud(
            capability_lost="strict-json-parse",
            fallback_kind="best-effort-parse",
            source=f"{SRC}:best_effort_parse",
            artifact_preserved=str(path),
            reason=type(exc).__name__,
        )
        return recovered if isinstance(recovered, dict) else {}


def capability_missing_shim(vendor: str, artifact: Path) -> str:
    """Kind: capability-missing-shim. Unknown vendor -> local echo, artifact kept."""
    known = {"local"}
    if vendor in known:
        return f"local:{artifact.name}"
    E.emit_loud(
        capability_lost=f"vendor:{vendor}",
        fallback_kind="capability-missing-shim",
        source=f"{SRC}:capability_missing_shim",
        artifact_preserved=str(artifact),
        reason="vendor-not-mounted",
    )
    return f"shim-local:{artifact.name}"


def cached_value_on_error(path: Path, cache: dict) -> str:
    """Kind: cached-value-on-error. Read fails -> last good cache, file still there."""
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("empty")
        cache["last"] = text
        return text
    except Exception as exc:
        E.emit_loud(
            capability_lost="fresh-read",
            fallback_kind="cached-value-on-error",
            source=f"{SRC}:cached_value_on_error",
            artifact_preserved=str(path),
            reason=type(exc).__name__,
        )
        return str(cache.get("last", ""))


def vendor_adapter_substitution(primary: str, artifact: Path) -> str:
    """Kind: vendor-adapter-substitution. Primary adapter fails -> secondary vendor."""

    def _primary() -> str:
        if primary != "local":
            raise RuntimeError(f"adapter-{primary}-unreachable")
        return f"primary:{primary}:{artifact.name}"

    try:
        return _primary()
    except Exception as exc:
        E.emit_loud(
            capability_lost=f"vendor-adapter:{primary}",
            fallback_kind="vendor-adapter-substitution",
            source=f"{SRC}:vendor_adapter_substitution",
            artifact_preserved=str(artifact),
            reason=type(exc).__name__,
        )
        return f"secondary:local:{artifact.name}"


def silent_debug_only(path: Path) -> dict:
    """CONTROL: fallback whose only trace is a debug log. Must classify SILENT."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        E.emit_debug(
            capability_lost="json-document-parse",
            fallback_kind="default-on-exception",
            source=f"{SRC}:silent_debug_only",
            artifact_preserved=str(path),
            reason=type(exc).__name__,
        )
        return {}


def no_fallback_strict(path: Path) -> dict:
    """CONTROL: no fallback. Parse errors propagate. Must not appear in the register."""
    return json.loads(path.read_text(encoding="utf-8"))


default_on_exception = default_on_exception
best_effort_parse = best_effort_parse
capability_missing_shim = capability_missing_shim
cached_value_on_error = cached_value_on_error
vendor_adapter_substitution = vendor_adapter_substitution
silent_debug_only = silent_debug_only
no_fallback_strict = no_fallback_strict
default_on_exception = default_on_exception
vendor_adapter_substitution = vendor_adapter_substitution
silent_debug_only = silent_debug_only
no_fallback_strict = no_fallback_strict
