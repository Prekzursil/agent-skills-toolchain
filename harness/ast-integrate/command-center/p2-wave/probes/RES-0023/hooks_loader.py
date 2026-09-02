"""Deserialize a Codex hooks.json the way HooksFile does.

The allowed top-level keys and the deny_unknown_fields flag are read from a
captured copy of openai/codex `hook_config.rs`, not invented here. A stray
top-level key (including `$schema`) therefore fails the same way serde would:
the file does not load, so every hook in it is dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
HOOK_CONFIG_SHA12 = "61c9f01b2ddc"
HOOK_CONFIG_CAPTURE = CAPTURES / f"{HOOK_CONFIG_SHA12}.bin"


class HooksLoadError(ValueError):
    pass


def _struct_block(src: str, name: str) -> str:
    marker = f"pub struct {name}"
    start = src.find(marker)
    if start < 0:
        raise HooksLoadError(f"struct {name} missing from captured hook_config.rs")
    brace = src.find("{", start)
    depth = 0
    for i, ch in enumerate(src[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise HooksLoadError(f"struct {name} unterminated")


def parse_hooks_file_contract(src: str) -> dict[str, Any]:
    attrs_and_struct = src
    idx = attrs_and_struct.find("pub struct HooksFile")
    preamble = attrs_and_struct[max(0, idx - 400) : idx]
    deny = "#[serde(deny_unknown_fields)]" in preamble.split("pub struct ")[-1] or (
        "#[serde(deny_unknown_fields)]" in preamble
        and "pub struct HooksFile" in src[idx : idx + 40]
    )
    # The attribute immediately above the struct is the one that applies.
    window = src[max(0, idx - 180) : idx]
    deny = "#[serde(deny_unknown_fields)]" in window
    block = _struct_block(src, "HooksFile")
    fields: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("pub "):
            continue
        rest = line[4:]
        if ":" not in rest:
            continue
        name = rest.split(":", 1)[0].strip()
        if name.isidentifier():
            fields.append(name)
    if "hooks" not in fields:
        raise HooksLoadError("HooksFile.hooks field missing from captured source")
    return {
        "deny_unknown_fields": deny,
        "fields": fields,
        "source_line": _line_of(src, "#[serde(deny_unknown_fields)]"),
        "struct_line": _line_of(src, "pub struct HooksFile"),
    }


def _line_of(src: str, needle: str) -> int:
    for i, line in enumerate(src.splitlines(), 1):
        if needle in line:
            return i
    return -1


def load_contract(path: Path | None = None) -> dict[str, Any]:
    src_path = path or HOOK_CONFIG_CAPTURE
    src = src_path.read_text(encoding="utf-8")
    contract = parse_hooks_file_contract(src)
    contract["capture_path"] = str(
        src_path.relative_to(HERE.parents[3]) if HERE.parents[3] in src_path.parents else src_path
    )
    contract["source_sha256"] = _sha256(src_path)
    return contract


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_handlers(doc: dict[str, Any]) -> int:
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    n = 0
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if isinstance(handlers, list):
                n += len(handlers)
    return n


def load_hooks_file(raw: str | dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {ok, handlers, error, extra_keys} for one hooks.json body."""
    contract = contract or load_contract()
    if isinstance(raw, str):
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "handlers": 0,
                "error": f"invalid JSON: {exc}",
                "extra_keys": [],
                "loaded": False,
            }
    else:
        doc = raw
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "handlers": 0,
            "error": "top-level value is not an object",
            "extra_keys": [],
            "loaded": False,
        }
    allowed = set(contract["fields"])
    extra = sorted(k for k in doc.keys() if k not in allowed)
    if extra and contract["deny_unknown_fields"]:
        expected = ", ".join(f"`{k}`" for k in contract["fields"])
        unknown = extra[0]
        err = f"unknown field `{unknown}`, expected {expected}"
        return {
            "ok": False,
            "handlers": 0,
            "error": err,
            "extra_keys": extra,
            "loaded": False,
        }
    n = count_handlers(doc)
    return {
        "ok": True,
        "handlers": n,
        "error": None,
        "extra_keys": extra,
        "loaded": n > 0,
        "doc": doc,
    }


_FIELD_RE = re.compile(r"pub ([a-zA-Z0-9_]+):")
