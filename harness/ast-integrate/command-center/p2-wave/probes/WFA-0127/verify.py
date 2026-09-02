"""Provenance dereference: file:line content must contain claimed tokens.

exists-only is the known-bad control (WFA-0019): a fabricated src that
points at a real file whose cited line does not contain the mechanism
must fail content mode and would wrongly pass exists-only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_src(src: str) -> tuple[str, int] | None:
    if not src or ":" not in src:
        return None
    path, _, line_s = src.rpartition(":")
    if not path or not line_s.isdigit():
        return None
    return path, int(line_s)


def read_line(root: Path, src: str) -> dict[str, Any]:
    parsed = parse_src(src)
    if parsed is None:
        return {
            "ok": False,
            "reason": "malformed-src",
            "src": src,
            "exists": False,
            "line_content": "",
        }
    rel, lineno = parsed
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return {
            "ok": False,
            "reason": "path-escape",
            "src": src,
            "exists": False,
            "line_content": "",
        }
    if not path.is_file():
        return {
            "ok": False,
            "reason": "missing-file",
            "src": src,
            "exists": False,
            "line_content": "",
        }
    lines = path.read_text(encoding="utf-8").splitlines()
    if lineno < 1 or lineno > len(lines):
        return {
            "ok": False,
            "reason": "line-out-of-range",
            "src": src,
            "exists": True,
            "line_content": "",
        }
    return {
        "ok": True,
        "reason": "read",
        "src": src,
        "exists": True,
        "line_content": lines[lineno - 1],
        "lineno": lineno,
        "path": str(path),
    }


def content_contains(line: str, tokens: list[str]) -> tuple[bool, list[str]]:
    missing = [t for t in tokens if t and t not in line]
    return (not missing, missing)


def verify_candidate(candidate: dict[str, Any], anchor_root: Path) -> dict[str, Any]:
    prov = candidate.get("provenance") or {}
    src = str(prov.get("src") or "")
    mechanisms = [str(m) for m in (candidate.get("mechanisms") or [])]
    claimed = list(mechanisms)
    extra = str(prov.get("prov") or "").strip()
    if extra and extra not in claimed:
        claimed.append(extra)
    deref = read_line(anchor_root, src)
    exists_only_ok = bool(deref.get("exists"))
    if not deref.get("ok"):
        return {
            "verdict": "UNKNOWN-NEEDS-PROBE",
            "reason": f"provenance-{deref.get('reason')}",
            "src": src,
            "exists_only_ok": exists_only_ok,
            "content_ok": False,
            "line_content": deref.get("line_content") or "",
            "missing_tokens": claimed,
        }
    ok, missing = content_contains(str(deref["line_content"]), mechanisms)
    if not ok:
        return {
            "verdict": "UNKNOWN-NEEDS-PROBE",
            "reason": "provenance-token-absent",
            "src": src,
            "exists_only_ok": True,
            "content_ok": False,
            "line_content": deref["line_content"],
            "missing_tokens": missing,
        }
    return {
        "verdict": "VERIFIED",
        "reason": "provenance-content-match",
        "src": src,
        "exists_only_ok": True,
        "content_ok": True,
        "line_content": deref["line_content"],
        "missing_tokens": [],
    }
