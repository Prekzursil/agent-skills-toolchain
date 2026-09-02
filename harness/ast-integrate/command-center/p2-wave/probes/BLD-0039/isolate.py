"""Isolated copies for BLD-0039. Mutations never touch the shared tree."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
VALIDATE_PY = CC_TOOLS / "validate.py"
CATALOG_PATH = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P2LIB = REPO / "command-center" / "p2-wave" / "_p2lib.py"

# Gate sources this unit is allowed to mutate only as copies.
SHARED_GATE_PATHS = (
    "tools/command-center/validate.py",
    "tools/command-center/seed.py",
    "tools/command-center/catalog.py",
    "tools/command-center/register_parse.py",
    "command-center/p2-wave/_p2lib.py",
    "command-center/WORK-UNIT-CATALOG.json",
)

_FIXTURE_KEYS = (
    "defaults",
    "items",
    "owner_questions",
    "provenance",
    "schema_version",
    "terminal_dispositions",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "ABSENT"


def fingerprint_shared(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    rows = []
    digest = hashlib.sha256()
    for rel in SHARED_GATE_PATHS:
        path = root / rel
        raw = path.read_bytes() if path.is_file() else b""
        h = sha256_bytes(raw)
        digest.update(rel.encode())
        digest.update(h.encode())
        rows.append(
            {
                "path": rel,
                "sha256": h,
                "bytes": len(raw),
                "present": path.is_file(),
            }
        )
    return {
        "aggregate_sha256": digest.hexdigest(),
        "files": rows,
    }


def find_item(catalog: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in catalog["items"]:
        if item.get("id") == item_id:
            return item
    raise KeyError(item_id)


def slim_catalog() -> dict[str, Any]:
    """Register items only — drop the 2007-row work_units blob."""
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    out = {k: copy.deepcopy(raw[k]) for k in _FIXTURE_KEYS if k in raw}
    return out


def synthetic_register_text(catalog: dict[str, Any]) -> str:
    sections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog["items"]:
        sections[str(item.get("section") or "OUTSTANDING")].append(item)
    order = (
        ("## 1. OUTSTANDING", "OUTSTANDING"),
        ("## 2. DELIBERATELY-SKIPPED", "DELIBERATELY-SKIPPED"),
        ("## 3. SUPERSEDED", "SUPERSEDED"),
        ("## 4. SETTLED", "SETTLED"),
    )
    lines = ["# Register (isolated BLD-0039 fixture)", ""]
    for heading, key in order:
        lines.extend([heading, "", "| id | title |", "| --- | --- |"])
        for item in sections.get(key, []):
            title = str(item.get("title") or "").replace("|", "/")
            lines.append(f"| {item['id']} | {title} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def bind_register(catalog: dict[str, Any], text: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    catalog["provenance"] = {
        "overlay": "command-center/sources/overlay.json",
        "register": "command-center/sources/REGISTER.md",
        "register_bytes": len(raw),
        "register_sha256": hashlib.sha256(raw).hexdigest(),
        "seeded_by": "command-center/p2-wave/probes/BLD-0039/isolate.py",
    }
    return catalog


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def materialise_clean(tmp: Path) -> dict[str, Any]:
    """Write a clean catalog+register+graph under tmp. Shared tree untouched."""
    sys.path.insert(0, str(CC_TOOLS))
    import catalog as cat  # noqa: WPS433

    catalog = slim_catalog()
    register_text = synthetic_register_text(catalog)
    bind_register(catalog, register_text)
    graph = cat.build_graph(catalog)
    cat_path = tmp / "catalog.json"
    graph_path = tmp / "graph.json"
    reg_path = tmp / "REGISTER.md"
    write_json(cat_path, catalog)
    write_json(graph_path, graph)
    reg_path.write_text(register_text, encoding="utf-8", newline="\n")
    return {
        "catalog": catalog,
        "graph": graph,
        "register_text": register_text,
        "catalog_path": cat_path,
        "graph_path": graph_path,
        "register_path": reg_path,
    }


def run_validate_cli(
    catalog_path: Path,
    graph_path: Path,
    register_path: Path | None,
    *,
    require_complete: bool = False,
    timeout: int = 60,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str(VALIDATE_PY),
        "--catalog",
        str(catalog_path),
        "--graph",
        str(graph_path),
    ]
    if register_path is not None:
        cmd.extend(["--register", str(register_path)])
    if require_complete:
        cmd.append("--require-complete")
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "command": cmd,
            "stdout": "",
            "stderr": "TIMEOUT",
            "output": "TIMEOUT",
        }
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "command": cmd,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "output": out,
    }


def load_validate():
    sys.path.insert(0, str(CC_TOOLS))
    import validate as val  # noqa: WPS433

    return val
