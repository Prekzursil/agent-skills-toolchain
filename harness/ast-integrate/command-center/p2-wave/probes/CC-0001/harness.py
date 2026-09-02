"""Isolated validate.py CLI so mutation exit codes are about V-FIELDS/V-DEFAULTS.

This worktree extract has no REGISTER.md and no DEPENDENCY-GRAPH.json, so a
bare `python tools/command-center/validate.py` exits 1 before the completeness
gate runs. Probes therefore write a temp catalog + matching graph + matching
register digest and invoke the CLI with those paths.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import blobread  # noqa: E402
import catalog as cat  # noqa: E402

VALIDATE = CC / "validate.py"
NINE = cat.OVERRIDEABLE_FIELDS


def per_field_override_census(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog if catalog is not None else cat.load()
    defaults = cat.catalog_defaults(catalog) or {}
    rows: dict[str, dict[str, int]] = {}
    n = len(cat.items(catalog))
    for field in NINE:
        item_n = default_n = unset_n = 0
        for unit in cat.items(catalog):
            token = cat.resolve_contract_field(unit, defaults, field)["provenance"]
            if token == "item":
                item_n += 1
            elif token == "default":
                default_n += 1
            else:
                unset_n += 1
        rows[field] = {
            "item": item_n,
            "default": default_n,
            "unset": unset_n,
            "n": n,
            "item_over_n": f"{item_n}/{n}",
        }
    return {"items": n, "fields": rows}


def _write_isolated(catalog: dict[str, Any], tmp: Path) -> dict[str, Path]:
    reg = tmp / "REGISTER.md"
    reg.write_bytes(b"CC-0001 isolated register\n")
    digest = hashlib.sha256(blobread.content_bytes(reg)).hexdigest()
    doc = copy.deepcopy(catalog)
    prov = dict(doc.get("provenance") or {})
    prov["register"] = "REGISTER.md"
    prov["register_sha256"] = digest
    doc["provenance"] = prov
    cat_path = tmp / "WORK-UNIT-CATALOG.json"
    graph_path = tmp / "DEPENDENCY-GRAPH.json"
    cat.save(doc, cat_path)
    cat.save(cat.build_graph(doc), graph_path)
    return {"catalog": cat_path, "graph": graph_path, "register": reg}


def run_validate_cli(
    catalog: dict[str, Any],
    *,
    require_complete: bool,
    extra: list[str] | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="cc0001-") as raw:
        tmp = Path(raw)
        paths = _write_isolated(catalog, tmp)
        cmd = [
            sys.executable,
            "-B",
            str(VALIDATE),
            "--catalog",
            str(paths["catalog"]),
            "--graph",
            str(paths["graph"]),
            "--register",
            str(paths["register"]),
        ]
        if require_complete:
            cmd.append("--require-complete")
        else:
            cmd.append("--no-require-complete")
        if extra:
            cmd.extend(extra)
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {
            "exit_code": proc.returncode,
            "command": " ".join(cmd),
            "require_complete": require_complete,
            "output_tail": "\n".join(text.splitlines()[-12:]),
            "v_fields": "V-FIELDS" in text,
            "v_defaults": "V-DEFAULTS" in text,
            "success_marker": "SUCCESS:cc-validate" in text,
            "failed_marker": "FAILED:cc-validate" in text,
        }


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise RuntimeError(f"{path}: needle not found: {needle!r}")
