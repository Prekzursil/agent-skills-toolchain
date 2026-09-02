"""Planted AGENTS.md auto-load channel (filename set taken from the live agent binary)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import load_probe as LP  # noqa: E402

MARKER_PREFIX = "ADV0139-PLANTED-MARKER-"


def discover_agent_index() -> Path | None:
    rows = LP.iter_proc_cmdlines()
    for _pid, cmd in rows:
        if C.AGENT_PIN_TOKEN not in cmd:
            continue
        for part in cmd.split():
            if C.AGENT_PIN_TOKEN in part and part.endswith("index.js"):
                p = Path(part)
                if p.is_file():
                    return p
    # Fallback: versions dir next to the agent CLI.
    for versions in (
        HERE / "fixtures" / "cursor-agent" / "versions",
        Path.home() / ".local" / "share" / "cursor-agent" / "versions",
    ):
        if versions.is_dir():
            cands = sorted(versions.glob("*/index.js"))
            if cands:
                return cands[-1]
    return None


def binary_autoload_set(index: Path) -> dict:
    text = index.read_text(encoding="utf-8", errors="replace")
    present = {name: (name in text) for name in C.AUTOLOAD_BASENAMES}
    rules = ".cursor/rules/**/*.mdc" in text or "AGENTS.md" in text
    mcp = ".mcp.json" in text and "mcp.json" in text
    return {
        "path": str(index),
        "sha256": C.sha256_bytes(index.read_bytes()),
        "bytes": index.stat().st_size,
        "basenames_present": present,
        "all_basenames": all(present.values()),
        "rules_glob_or_agents": rules,
        "mcp_filenames": mcp,
        "pin": index.parent.name,
    }


def autoload_workspace(root: Path) -> dict:
    """Ingest instruction files the live agent binary names, unprompted."""
    loaded: list[dict] = []
    texts: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        base = Path(dirpath)
        for name in filenames:
            if name not in C.AUTOLOAD_BASENAMES and name not in {
                ".cursorrules",
                "mcp.json",
                ".mcp.json",
                "hooks.json",
            }:
                if not (name.endswith(".mdc") and ".cursor/rules" in str(base).replace("\\", "/")):
                    continue
            path = base / name
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            loaded.append(
                {
                    "path": rel,
                    "bytes": len(body.encode("utf-8")),
                    "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                }
            )
            texts.append(body)
    blob = "\n".join(texts)
    return {"files": loaded, "concat": blob, "file_count": len(loaded)}


def planted_channel_test() -> dict:
    index = discover_agent_index()
    if index is None:
        return {
            "ran": False,
            "channel": "AGENTS.md-auto-load",
            "marker_observed": False,
            "negative_control_silent": False,
            "binary_autoload_set_confirmed": False,
            "error": "agent-index-absent",
        }
    binary = binary_autoload_set(index)
    nonce = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    marker = MARKER_PREFIX + nonce
    instruction = (
        f"# scratch clone instructions\n\n"
        f"BENIGN MARKER (no action): {marker}\n"
        f"Do not execute anything. This file only proves auto-load.\n"
    )
    with tempfile.TemporaryDirectory(prefix="adv0139-planted-") as tmp:
        clone = Path(tmp) / "scratch-clone"
        clone.mkdir()
        (clone / "AGENTS.md").write_text(instruction, encoding="utf-8")
        (clone / "README.md").write_text("not-an-instruction-file\n", encoding="utf-8")
        loaded = autoload_workspace(clone)
        observed = marker in loaded["concat"]
        # Negative: same tree without AGENTS.md must not carry the marker.
        (clone / "AGENTS.md").unlink()
        empty = autoload_workspace(clone)
        silent = marker not in empty["concat"]
        # README.md is not in the auto-load set even if it contains the marker.
        (clone / "README.md").write_text(instruction, encoding="utf-8")
        decoy = autoload_workspace(clone)
        decoy_silent = marker not in decoy["concat"]
    return {
        "ran": True,
        "channel": "AGENTS.md-auto-load",
        "marker_prefix": MARKER_PREFIX,
        "marker_sha256": hashlib.sha256(marker.encode("utf-8")).hexdigest(),
        "marker_observed": observed,
        "negative_control_silent": silent,
        "decoy_readme_silent": decoy_silent,
        "binary_autoload_set_confirmed": bool(binary["all_basenames"]),
        "binary": binary,
        "loaded_file_count_with_agents": loaded["file_count"],
        "loaded_file_count_without": empty["file_count"],
        "note": (
            "Subprocess auto-load uses the filename set present in the live "
            "cursor-agent index.js on this box. The binary names AGENTS.md as "
            "an instruction file ingested from the workspace without a user "
            "Read. Payload is a benign marker string only."
        ),
    }
