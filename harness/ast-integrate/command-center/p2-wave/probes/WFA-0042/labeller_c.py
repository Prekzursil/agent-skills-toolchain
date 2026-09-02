"""Labeller C — third reader. Blind of A and B (does not import them).

Narrower than A (top-level JSON keys only, not a deep walk) and different
from B (no SPDX-anywhere, no role-token spray). Used only on the frozen
first-five subset.
"""
from __future__ import annotations

import re
from typing import Any

from dimensions import DIMENSIONS, empty_cell, evidenced, honest_null

TOP_LICENSE = re.compile(
    r'(?m)^(?:  ){0,2}"license"\s*:\s*"([^"]+)"'
    r"|^(?:license|licence)\s*:\s*(\S+)",
)
SHA256_KEY = re.compile(
    r'(?i)"(?:sha256|fingerprint|registry_entry_sha256)"\s*:\s*"([0-9a-f]{16,})"'
)
STAGES_KEY = re.compile(r'(?m)^\s{0,4}"stages"\s*:')
STOPPING_KEY = re.compile(r'(?m)^\s{0,4}"stopping(?:_point)?"\s*:')
ON_ERROR = re.compile(r'"on_error"\s*:\s*"([^"]+)"')
FRONTMATTER_NAME = re.compile(r"(?m)^name:\s*(\S+)")


def _first_group(match: re.Match[str] | None) -> str:
    if not match:
        return ""
    for g in match.groups():
        if g:
            return g
    return match.group(0)


def label_source(src: dict[str, Any]) -> dict[str, dict[str, Any]]:
    text = src["text"]
    out: dict[str, dict[str, Any]] = {}

    lic = TOP_LICENSE.search(text)
    if lic:
        out["license"] = evidenced(_first_group(lic), anchor=f"{src['path']}:top-license")
    else:
        out["license"] = empty_cell(note="no top-level license key")

    out["maintenance"] = evidenced(
        "present-on-tree", anchor=src["path"], note="live nonempty file"
    )

    sha = SHA256_KEY.search(text)
    if sha:
        out["provenance"] = evidenced(sha.group(1)[:16], anchor=f"{src['path']}:hash-key")
    else:
        out["provenance"] = empty_cell(note="no sha256/fingerprint key")

    if FRONTMATTER_NAME.search(text) or re.search(r"^##\s+Role\s+`", text, re.M):
        out["roles"] = evidenced("named-role-or-skill", anchor=src["path"])
    else:
        out["roles"] = empty_cell(note="no Role heading or frontmatter name")

    if STAGES_KEY.search(text):
        out["stages"] = evidenced("stages-key", anchor=f"{src['path']}:stages")
    else:
        out["stages"] = empty_cell(note="no top-level stages key")

    if STOPPING_KEY.search(text):
        out["stop_rules"] = evidenced("stopping-key", anchor=src["path"])
    else:
        out["stop_rules"] = empty_cell(note="no stopping key")

    if re.search(r'"(?:tools|allowed-tools|permissions)"\s*:', text):
        out["tools"] = evidenced("tools-key", anchor=src["path"])
    else:
        out["tools"] = empty_cell(note="no tools key")

    out["task_fit"] = evidenced(src["family"], anchor=src["path"], note="sampling family")

    err = ON_ERROR.search(text)
    if err:
        out["failure_behaviour"] = evidenced(err.group(1), anchor=src["path"])
    else:
        out["failure_behaviour"] = empty_cell(note="no on_error key")

    if re.search(r"(?i)benchmark|reproduction_status|claimed_delta", text):
        out["benchmark_evidence"] = evidenced("bench-mention", anchor=src["path"])
    else:
        out["benchmark_evidence"] = honest_null(note="no benchmark mention")

    missing = [d for d in DIMENSIONS if d not in out]
    if missing:
        raise RuntimeError(f"labeller C missed {missing}")
    return out
