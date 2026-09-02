#!/usr/bin/env python3
"""Edit-time guard: the repo is the source of truth; the live tree is a deploy target.

A Write/Edit targeting a live path that has a provenance record pointing at a
repo counterpart FIREs an advisory naming that repo path. A live-only scratch
path (no provenance row) stays SILENT. Editing the repo counterpart itself is
SILENT. The trigger is the provenance record, not the live-path prefix.

Internal errors fail open: permit the tool, exit 0, never block (exit 2).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WRITE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})


def load_provenance(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("provenance must be an object")
    return raw


def _rel_to(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _allow(
    reason: str,
    *,
    fired: bool = False,
    write_rel: str | None = None,
    repo_counterpart: str | None = None,
    advisory: str | None = None,
    fail_open: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "fired": fired,
        "silent": not fired,
        "permit": True,
        "exit_code": 0,
        "reason": reason,
        "write_rel": write_rel,
        "repo_counterpart": repo_counterpart,
        "advisory": advisory,
        "fail_open": fail_open,
    }
    if extra:
        out.update(extra)
    return out


def inspect_write(
    *,
    write_path: str | Path,
    live_root: str | Path,
    repo_root: str | Path,
    provenance: dict[str, Any],
    fail_open: bool = True,
) -> dict[str, Any]:
    """Classify a write. Never raises when fail_open is True."""
    try:
        return _inspect(
            write_path=Path(write_path),
            live_root=Path(live_root),
            repo_root=Path(repo_root),
            provenance=provenance,
        )
    except Exception as exc:
        if fail_open:
            return _allow(
                "fail-open-internal-error",
                fail_open=True,
                extra={"error": type(exc).__name__, "error_detail": str(exc)[:240]},
            )
        raise


def _inspect(
    *,
    write_path: Path,
    live_root: Path,
    repo_root: Path,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    wp = write_path.resolve()
    live_rel = _rel_to(wp, Path(live_root))
    repo_rel = _rel_to(wp, Path(repo_root))

    if live_rel is None and repo_rel is not None:
        return _allow(
            "repo-source-of-truth",
            write_rel=repo_rel,
            extra={"tree": "repo"},
        )

    if live_rel is None:
        return _allow(
            "outside-estate",
            extra={"tree": "outside", "write_path": str(wp)},
        )

    rec = provenance.get(live_rel)
    if not isinstance(rec, dict):
        return _allow(
            "live-only-no-provenance",
            write_rel=live_rel,
            extra={"tree": "live"},
        )

    counterpart = rec.get("repo_rel")
    if not isinstance(counterpart, str) or not counterpart.strip():
        return _allow(
            "live-only-no-provenance",
            write_rel=live_rel,
            extra={"tree": "live", "note": "provenance-row-lacks-repo_rel"},
        )
    counterpart = counterpart.replace("\\", "/").strip()
    counterpart_path = Path(repo_root).resolve() / counterpart
    if not counterpart_path.is_file():
        return _allow(
            "deployed-but-repo-counterpart-absent",
            write_rel=live_rel,
            extra={"tree": "live", "missing_repo_rel": counterpart},
        )

    advisory = (
        f"Write targets deployed copy {live_rel} which has repo counterpart "
        f"{counterpart}. Edit the repository source of truth; the live tree "
        f"is a deploy target and will be overwritten on the next deploy."
    )
    return _allow(
        "deployed-copy-has-repo-counterpart",
        fired=True,
        write_rel=live_rel,
        repo_counterpart=counterpart,
        advisory=advisory,
        extra={
            "tree": "live",
            "repo_counterpart_path": str(counterpart_path),
            "plugin_version": rec.get("plugin_version"),
        },
    )


def pre_tool_use(event: dict[str, Any], estate: dict[str, Any]) -> dict[str, Any]:
    """PreToolUse face: inject an advisory, never block."""
    tool = str(event.get("tool") or event.get("tool_name") or "")
    path = event.get("path") or event.get("file_path")
    if tool not in WRITE_TOOLS:
        return _allow("not-a-write-tool", extra={"tool": tool})
    if not isinstance(path, str) or not path:
        return _allow("missing-path", extra={"tool": tool})
    decision = inspect_write(
        write_path=path,
        live_root=estate["live_root"],
        repo_root=estate["repo_root"],
        provenance=estate["provenance"],
        fail_open=bool(estate.get("fail_open", True)),
    )
    decision["tool"] = tool
    decision["write_path"] = path
    return decision
