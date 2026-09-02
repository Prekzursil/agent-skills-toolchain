"""Independent gold labels for TST-0006.

The linter scans path-shaped tokens in payload text. Gold labels come from a
*different* signal: JSON keys whose *name* declares a filesystem path, plus
fenced-code regions treated as illustrative MENTION.

A human reviewed the protocol and recorded overrides in labels.json.
This is not 'the linter scoring itself'.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from path_linter import (
    UNVERIFIED,
    VERIFIED,
    DOCUMENTARY_KEYS,
    extract_path_tokens,
    looks_like_path,
    normalize_token,
    split_fenced,
    stat_cited_path,
)

# Keys whose value is a cited filesystem path (USE), not an example.
_PATH_KEY_EXACT = {
    "path",
    "paths",
    "file",
    "filepath",
    "file_path",
    "output_path",
    "output_schema",
    "receipt_path",
    "manifest_path",
    "artifact_path",
    "schema_path",
    "live_path",
    "absent_paths",
    "present_paths",
    "missing_paths",
    "sidecar",
    "sidecars",
}

_PATH_KEY_SUFFIX = ("_path", "_paths", "_file", "_files", "_schema")

# Keys that hold documentary / example prose. Fences inside them are MENTION.
# Unfenced tokens in these keys are NOT gold-USE (catalog quotes, questions).
_PROSE_KEYS = {
    "question_or_target",
    "question",
    "example",
    "snippet",
    "original_preview",
    "notes",
    "doc",
    "documentation",
    "prompt",
    "body",
    "markdown",
}

# Keys that hold the agent's own cited-path prose (receipts, error tails).
_CITE_PROSE_KEYS = {
    "stdout_head",
    "stderr_head",
    "raw_output",
    "failure_reason",
    "answer",
    "basis",
}


def _is_path_key(key: str) -> bool:
    k = key.lower()
    if k in _PATH_KEY_EXACT:
        return True
    return any(k.endswith(suf) for suf in _PATH_KEY_SUFFIX)


def _as_path_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        token = normalize_token(value)
        if looks_like_path(token):
            out.append(token)
        else:
            # A path-key sometimes holds a list serialized in one string.
            out.extend(extract_path_tokens(value))
    elif isinstance(value, list):
        for item in value:
            out.extend(_as_path_strings(item))
    elif isinstance(value, dict):
        nested = value.get("path")
        if isinstance(nested, str):
            out.extend(_as_path_strings(nested))
    return out


def _walk_gold(obj: Any, use: set[str], mention: set[str], key: str | None = None) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk_gold(v, use, mention, key=str(k))
        return
    if isinstance(obj, list):
        if key is not None and _is_path_key(key):
            for item in obj:
                for token in _as_path_strings(item):
                    use.add(token)
            return
        for item in obj:
            _walk_gold(item, use, mention, key=key)
        return
    if isinstance(obj, str):
        token = normalize_token(obj)
        whole = looks_like_path(token) and len(obj) < 400 and "\n" not in obj
        if key is not None and _is_path_key(key):
            for item in _as_path_strings(obj):
                use.add(item)
            return
        outside, inside = split_fenced(obj)
        if inside:
            for item in extract_path_tokens(inside):
                mention.add(item)
        if key is not None and key.lower() in DOCUMENTARY_KEYS:
            for item in extract_path_tokens(outside):
                mention.add(item)
            return
        if key is not None and key.lower() in _CITE_PROSE_KEYS:
            for item in extract_path_tokens(outside):
                use.add(item)
            return
        if whole and not (key and key.lower() in DOCUMENTARY_KEYS):
            use.add(token)
        return


def label_payload_text(text: str, root: Path) -> dict[str, Any]:
    use: set[str] = set()
    mention: set[str] = set()
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        outside, inside = split_fenced(text)
        use.update(extract_path_tokens(outside))
        mention.update(extract_path_tokens(inside))
        # For non-JSON, gold USE is "paths outside fences" — still independent
        # of the linter's JSON-string walk, but overlapping on markdown.
    else:
        _walk_gold(doc, use, mention)
    mention -= use
    absent_use: list[str] = []
    present_use: list[str] = []
    for token in sorted(use):
        _, exists = stat_cited_path(root, token)
        if exists:
            present_use.append(token)
        else:
            absent_use.append(token)
    mention_list = sorted(mention)
    status = UNVERIFIED if absent_use else VERIFIED
    return {
        "gold_status": status,
        "use_paths": sorted(use),
        "mention_paths": mention_list,
        "absent_use_paths": absent_use,
        "present_use_paths": present_use,
        "should_flag": sorted(absent_use),
    }


def label_file(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    row = label_payload_text(text, root)
    row["path"] = path.as_posix()
    return row


_OVERRIDE_NOTE = re.compile(r".")  # placeholder; overrides live in labels.json
