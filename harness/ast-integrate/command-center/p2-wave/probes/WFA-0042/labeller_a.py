"""Labeller A — declared-structure read.

Only structured keys / YAML frontmatter / SPDX-License-Identifier count as
EVIDENCED. Prose mentions are ignored. Absence of a benchmark key is
HONEST-NULL (the catalog near-zero prior), not EMPTY and not a manufactured
score. Independent of labeller_b / labeller_c.
"""
from __future__ import annotations

import re
from typing import Any

from dimensions import DIMENSIONS, empty_cell, evidenced, honest_null

SPDX_LINE = re.compile(
    r"(?im)^(?:#\s*)?SPDX-License-Identifier:\s*([A-Za-z0-9.\-+]+)"
)
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
ROLE_HEADING = re.compile(r"^##\s+Role\s+`([^`]+)`\s*$", re.M | re.I)

LICENSE_KEYS = ("license", "licence", "spdx", "license_id")
MAINT_KEYS = ("maintenance", "maintenance_state", "lifecycle")
PROV_KEYS = (
    "provenance",
    "sha256",
    "fingerprint",
    "registry_entry_sha256",
    "source_anchor",
)
ROLE_KEYS = ("roles", "role", "participants")
STAGE_KEYS = ("stages", "phase", "phases")
STOP_KEYS = ("stopping", "stop_rule", "stop_rules", "stopping_point", "stop")
TOOL_KEYS = (
    "tools",
    "allowed-tools",
    "allowed_tools",
    "tool_permissions",
    "permissions",
    "tool_access",
)
FAIL_KEYS = ("on_error", "failure_behaviour", "failure", "timeout_seconds")
BENCH_KEYS = (
    "benchmark",
    "benchmark_evidence",
    "claimed_delta",
    "reproduction_status",
    "independently_reproduced",
)


def _frontmatter_map(text: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1] in " \t#-":
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        if key:
            out[key] = val.strip().strip('"').strip("'")
    return out


def _find_key(obj: Any, names: tuple[str, ...], prefix: str = "$") -> tuple[str, Any] | None:
    want = {n.lower() for n in names}
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in want:
                return path, val
            found = _find_key(val, names, path)
            if found:
                return found
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:40]):
            found = _find_key(item, names, f"{prefix}[{i}]")
            if found:
                return found
    return None


def _stringify(val: Any, limit: int = 160) -> str:
    if val is None:
        return ""
    if isinstance(val, (str, int, float, bool)):
        text = str(val).strip()
        return text[:limit]
    if isinstance(val, list):
        parts = []
        for item in val[:12]:
            if isinstance(item, dict):
                ident = item.get("id") or item.get("name") or item.get("kind")
                if ident:
                    parts.append(str(ident))
            elif isinstance(item, (str, int)):
                parts.append(str(item))
        return ",".join(parts)[:limit]
    if isinstance(val, dict):
        if "id" in val:
            return str(val["id"])[:limit]
        return ",".join(str(k) for k in list(val.keys())[:8])[:limit]
    return str(type(val).__name__)


def _from_key(src: dict[str, Any], names: tuple[str, ...], *, empty_is_null: bool = False) -> dict[str, Any]:
    found = None
    if src.get("json_ok"):
        found = _find_key(src["json"], names)
    if found is None:
        fm = _frontmatter_map(src["text"])
        for name in names:
            if name in fm and fm[name]:
                found = (f"frontmatter.{name}", fm[name])
                break
    if found is None:
        if empty_is_null:
            return honest_null(note=f"no {'/'.join(names)} key")
        return empty_cell(note=f"no {'/'.join(names)} key")
    path, val = found
    text = _stringify(val)
    if text == "" or str(val).strip().lower() in {"null", "none", "[]", "{}"}:
        return honest_null(note=f"{path} present but empty",)
    return evidenced(text, anchor=f"{src['path']}:{path}")


def label_source(src: dict[str, Any]) -> dict[str, dict[str, Any]]:
    text = src["text"]
    out: dict[str, dict[str, Any]] = {}

    spdx = SPDX_LINE.search(text)
    lic = _from_key(src, LICENSE_KEYS)
    if lic["cell_state"] != "EVIDENCED" and spdx:
        lic = evidenced(spdx.group(1), anchor=f"{src['path']}:SPDX-License-Identifier")
    out["license"] = lic

    maint = _from_key(src, MAINT_KEYS)
    if maint["cell_state"] != "EVIDENCED":
        maint = evidenced("present-on-tree", anchor=src["path"], note="live nonempty file")
    out["maintenance"] = maint

    out["provenance"] = _from_key(src, PROV_KEYS)
    roles = _from_key(src, ROLE_KEYS)
    if roles["cell_state"] != "EVIDENCED":
        headed = ROLE_HEADING.findall(text)
        if headed:
            roles = evidenced(",".join(headed[:8]), anchor=f"{src['path']}:Role-heading")
    out["roles"] = roles
    out["stages"] = _from_key(src, STAGE_KEYS)
    out["stop_rules"] = _from_key(src, STOP_KEYS)
    out["tools"] = _from_key(src, TOOL_KEYS)
    out["task_fit"] = evidenced(src["family"], anchor=src["path"], note="sampling family")
    out["failure_behaviour"] = _from_key(src, FAIL_KEYS)
    out["benchmark_evidence"] = _from_key(src, BENCH_KEYS, empty_is_null=True)

    missing = [d for d in DIMENSIONS if d not in out]
    if missing:
        raise RuntimeError(f"labeller A missed {missing}")
    return out
