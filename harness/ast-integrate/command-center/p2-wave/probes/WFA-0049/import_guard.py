"""Refuse a LangGraph runtime import or a vendored copy in this unit tree."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORBIDDEN_NAMES = ("langgraph", "langgraph.graph", "langgraph.checkpoint")


def langgraph_importable() -> tuple[bool, str]:
    if "langgraph" in sys.modules:
        return True, f"sys.modules:{sys.modules['langgraph']}"
    spec = importlib.util.find_spec("langgraph")
    if spec is not None:
        return True, f"find_spec:{spec.origin}"
    return False, "ModuleNotFoundError"


def vendored_copy(root: Path | None = None) -> list[str]:
    root = root or HERE
    hits: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if name in {"langgraph.py", "langgraph.pth"} or p.parent.name.lower() == "langgraph":
            if p.suffix in {".py", ".pyc", ".so", ".pth"}:
                hits.append(str(p.relative_to(root)))
    return hits


def assert_no_runtime() -> dict:
    imported, why = langgraph_importable()
    vendor = vendored_copy()
    ok = (not imported) and (not vendor)
    return {
        "ok": ok,
        "importable": imported,
        "import_detail": why,
        "vendored": vendor,
    }
