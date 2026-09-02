"""Harvest live telemetry emitters and payloads from the worktree.

Product telemetry is distinct from unit-probe test doubles. Hits under
command-center/p2-wave/probes/ are excluded so the suite cannot grade
fixtures, scratch copies, or vendored probe deps (AUD-0090 OpenTelemetry)
as production emissions. Directories named deps/vendor/scratch are pruned
during the walk rather than scanned then discarded.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from paths import CONTRACT_LIVE_REL, REPO

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "deps",
    "vendor",
    "scratch",
    "site-packages",
    "dist",
    "build",
    "target",
}
SOURCE_SUFFIXES = {".py", ".mjs", ".js", ".ts", ".go", ".rs"}
HIT_RE = re.compile(
    r"\b("
    r"emit_telemetry|record_telemetry|telemetry_payload|"
    r"OTEL_EXPORTER_OTLP|DISABLE_TELEMETRY|"
    r"posthog\.|sentry_sdk|OpenTelemetry"
    r")\b"
)
FILE_NAME_RE = re.compile(r"(?i)telemetry")


def _rel(path: Path, base: Path) -> str | None:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return None


def _excluded(rel_path: str) -> bool:
    if rel_path.startswith("command-center/p2-wave/probes/"):
        return True
    if rel_path == "command-center/WORK-UNIT-CATALOG.json":
        return True
    return False


SEARCH_ROOTS = ("tools", "command-center", "hooks", "platform", "src", "lib")


def _iter_source(base: Path):
    roots = [base / name for name in SEARCH_ROOTS if (base / name).is_dir()]
    if not roots:
        roots = [base]
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                yield Path(dirpath) / name


def harvest_live(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else REPO
    emitter_files: list[str] = []
    static_hits: list[dict[str, str]] = []
    for path in _iter_source(base):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel_path = _rel(path, base)
        if rel_path is None or _excluded(rel_path):
            continue
        name_hit = bool(FILE_NAME_RE.search(path.name) and path.suffix in SOURCE_SUFFIXES)
        ident_hit = False
        if path.suffix in SOURCE_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            ident_hit = bool(HIT_RE.search(text))
        if name_hit or ident_hit:
            emitter_files.append(rel_path)
            kind = "filename" if name_hit else "identifier"
            if ident_hit:
                kind = "identifier"
            static_hits.append({"path": rel_path, "kind": kind})

    emitter_files = sorted(set(emitter_files))
    payloads: list[dict[str, Any]] = []
    runtime_notes = [
        f"static-hit-no-runtime-capture:{rel_path}" for rel_path in emitter_files
    ]
    return {
        "contract_path": CONTRACT_LIVE_REL,
        "contract_present": (base / CONTRACT_LIVE_REL).is_file(),
        "emitter_files": emitter_files,
        "static_hits": static_hits,
        "payloads": payloads,
        "payload_count": len(payloads),
        "runtime_notes": runtime_notes,
        "empty_live_is_not_a_pass": True,
    }


def harvest_scratch(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    captured = [{"source": "scratch-emitter", "payload": item} for item in payloads]
    return {
        "emitter_files": ["scratch-emitter"],
        "payloads": captured,
        "payload_count": len(captured),
        "empty_live_is_not_a_pass": True,
    }


def canonical_live(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_present": bool(report.get("contract_present")),
        "emitter_files": list(report.get("emitter_files") or []),
        "payload_count": int(report.get("payload_count") or 0),
        "static_hit_paths": sorted(
            {
                h.get("path")
                for h in (report.get("static_hits") or [])
                if isinstance(h, dict) and h.get("path")
            }
        ),
        "empty_live_is_not_a_pass": True,
    }


def main() -> int:
    public = canonical_live(harvest_live())
    print(json.dumps(public, sort_keys=True))
    print(
        f"payloads={public['payload_count']} files={len(public['emitter_files'])} "
        f"contract_present={public['contract_present']}"
    )
    print("SUCCESS:TST-0050-harvest live census complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
