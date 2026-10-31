"""Static scan: production call sites must not be the only redaction layer."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
OBS = HERE / "observability.py"
SINK = HERE / "sink_scrub.py"
MJS = HERE / "security.mjs"


def _calls_scrub(path: Path, func_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if isinstance(func, ast.Name) and func.id in {"scrub", "_emit"}:
                        return True
                    if isinstance(func, ast.Attribute) and func.attr in {"scrub", "_emit"}:
                        return True
    return False


def _call_site_ok(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # A new unscrubbed call site is allowed (probe1); production helpers must
    # go through the sink. Flag files that define their own scrub as defense.
    has_local_scrub = "def scrub(" in text and path.name not in {"sink_scrub.py"}
    return {
        "path": str(path),
        "ok": not has_local_scrub,
        "local_scrub": has_local_scrub,
    }


def run_scan(extra_call_sites: Iterable[Path] | None = None) -> dict:
    sink_ok = _calls_scrub(SINK, "_emit") or "scrub(" in SINK.read_text(encoding="utf-8")
    obs_text = OBS.read_text(encoding="utf-8")
    obs_uses_emit = "_emit(" in obs_text
    sites = [_call_site_ok(Path(p)) for p in extra_call_sites or []]
    mjs_ok = MJS.is_file()
    ok = bool(sink_ok and obs_uses_emit and all(s["ok"] for s in sites) and mjs_ok)
    return {
        "ok": ok,
        "sink": {"_emit_calls_scrub": bool(sink_ok)},
        "call_sites": sites,
        "security_mjs": {"ok": mjs_ok, "path": str(MJS)},
        "observability_uses_sink": obs_uses_emit,
    }
