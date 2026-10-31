"""Interpreter discovery that fails loudly instead of silently substituting."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
DECL_PATH = HERE / "interpreters.json"
VERDICTS_OK = frozenset({"OK"})
VERDICTS_FAIL = frozenset({"MISSING", "BELOW_FLOOR", "AMBIGUOUS", "UNPARSABLE"})
_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def load_declarations(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DECL_PATH
    doc = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("interpreters.json is not an object")
    doc.setdefault("declaration_source", str(target.as_posix()))
    return doc


def _normalize_decl(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("interpreter declaration must be an object")
    name = str(raw.get("name") or raw.get("id") or "")
    return {
        "id": str(raw.get("id") or name),
        "name": name,
        "floor": str(raw.get("floor") or "0.0.0"),
        "version_argv": list(raw.get("version_argv") or ["--version"]),
    }


def candidate_names(declared_name: str) -> set[str]:
    """Exact basename only. Do not search alias tables."""
    return {str(declared_name)}


def which_all(declared_name: str, path_var: str | None = None) -> list[str]:
    """Locate binaries whose basename equals declared_name. No aliases."""
    want = str(declared_name)
    env_path = path_var if path_var is not None else os.environ.get("PATH", "")
    found: list[str] = []
    seen: set[str] = set()
    for chunk in env_path.split(os.pathsep):
        if not chunk:
            continue
        directory = Path(chunk)
        try:
            if not directory.is_dir():
                continue
            for child in directory.iterdir():
                if child.name != want:
                    continue
                if not child.is_file():
                    continue
                resolved = str(child)
                if resolved in seen:
                    continue
                if os.access(child, os.X_OK) or os.name == "nt":
                    seen.add(resolved)
                    found.append(resolved)
        except OSError:
            continue
    located = shutil.which(want, path=env_path)
    if located and located not in seen:
        found.insert(0, located)
    return found


def parse_version_probe(raw: str | None) -> tuple[int, int, int] | None:
    if not raw:
        return None
    match = _VERSION_RE.search(str(raw))
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def parse_version_independent(raw: str | None) -> tuple[int, int, int] | None:
    if not raw:
        return None
    digits: list[int] = []
    token = ""
    for ch in str(raw):
        if ch.isdigit():
            token += ch
        elif token:
            digits.append(int(token))
            token = ""
            if len(digits) >= 3:
                break
    if token and len(digits) < 3:
        digits.append(int(token))
    if len(digits) < 2:
        return None
    while len(digits) < 3:
        digits.append(0)
    return (digits[0], digits[1], digits[2])


def capture_version_independent(binary: str | Path, version_argv: Iterable[str] | None = None) -> str:
    argv = [str(binary), *(list(version_argv) if version_argv else ["--version"])]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def _parse_floor(floor: str) -> tuple[int, int, int]:
    parsed = parse_version_probe(floor)
    return parsed or (0, 0, 0)


def _remediation(code: str, declared: str, floor: str) -> dict[str, str]:
    return {
        "code": code,
        "declared_name": declared,
        "floor": floor,
        "message": f"{code}: install {declared} at or above {floor}",
    }


def probe_one(decl: dict[str, Any], path_var: str | None = None) -> dict[str, Any]:
    name = decl["name"]
    floor = decl["floor"]
    matches = which_all(name, path_var)
    row: dict[str, Any] = {
        "id": decl["id"],
        "declared_name": name,
        "floor": floor,
        "all_paths": matches,
        "resolved_path": matches[0] if matches else None,
        "raw_version": "",
        "parsed_probe": None,
        "parsed_independent": None,
        "parsers_agree": True,
        "silent_fallback": False,
        "verdict": "MISSING",
        "remediation": _remediation(f"INSTALL_{name.upper()}_AT_OR_ABOVE_{floor}", name, floor),
    }
    if not matches:
        return row
    if len(matches) > 1:
        row["verdict"] = "AMBIGUOUS"
        row["remediation"] = _remediation("AMBIGUOUS_INSTALL", name, floor)
        return row
    raw = capture_version_independent(matches[0], decl.get("version_argv"))
    probe_v = parse_version_probe(raw)
    indep_v = parse_version_independent(raw)
    row["raw_version"] = raw
    row["parsed_probe"] = list(probe_v) if probe_v else None
    row["parsed_independent"] = list(indep_v) if indep_v else None
    row["parsers_agree"] = probe_v == indep_v
    if probe_v is None:
        row["verdict"] = "UNPARSABLE"
        row["remediation"] = _remediation("UNPARSABLE_VERSION", name, floor)
        return row
    if probe_v < _parse_floor(floor):
        row["verdict"] = "BELOW_FLOOR"
        row["remediation"] = _remediation(f"INSTALL_{name.upper()}_AT_OR_ABOVE_{floor}", name, floor)
        return row
    row["verdict"] = "OK"
    row["remediation"] = None
    return row


def probe_all(decls: dict[str, Any] | None = None, path_var: str | None = None) -> dict[str, Any]:
    doc = decls if isinstance(decls, dict) else load_declarations()
    rows = [probe_one(_normalize_decl(raw), path_var) for raw in doc.get("interpreters") or []]
    return {
        "declaration_source": doc.get("declaration_source") or str(DECL_PATH.as_posix()),
        "results": rows,
        "ok_count": sum(1 for r in rows if r["verdict"] == "OK"),
        "fail_count": sum(1 for r in rows if r["verdict"] != "OK"),
        "silent_fallback": any(r.get("silent_fallback") for r in rows),
    }
