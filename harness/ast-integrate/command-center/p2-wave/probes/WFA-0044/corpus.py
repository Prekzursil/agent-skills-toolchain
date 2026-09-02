"""Locate the 10-file saved-workflow corpus.

Prefers live ~/.claude/workflows when it holds .js/.mjs files. This Linux
worktree does not ship those bodies; the in-tree dialect stand-ins then
carry the round-trip proof. Live absence is recorded, not filled with a
claimed Windows harvest.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_DIR = HERE / "fixtures" / "saved-workflows"
LIVE_CANDIDATES = (
    Path.home() / ".claude" / "workflows",
    Path.home() / ".claude" / "workflows",
    Path("/home/Prekzursil/.claude/workflows"),
    REPO / "workflows",
)


def list_workflow_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files = [
        p
        for p in sorted(directory.iterdir())
        if p.is_file() and p.suffix.lower() in {".js", ".mjs"}
    ]
    return files


def discover() -> dict:
    live_hits = []
    for path in LIVE_CANDIDATES:
        files = list_workflow_files(path)
        live_hits.append(
            {
                "path": str(path),
                "present": path.is_dir(),
                "n_js_mjs": len(files),
                "names": [p.name for p in files],
            }
        )
    live_usable = next((h for h in live_hits if h["n_js_mjs"] >= 10), None)
    fixture_files = list_workflow_files(FIXTURE_DIR)
    if live_usable:
        chosen_dir = Path(live_usable["path"])
        source = "live"
        files = list_workflow_files(chosen_dir)[:10]
    else:
        chosen_dir = FIXTURE_DIR
        source = "dialect-standin"
        files = fixture_files
    return {
        "source": source,
        "directory": str(chosen_dir.relative_to(REPO) if chosen_dir.is_relative_to(REPO) else chosen_dir),
        "absolute": str(chosen_dir),
        "live_hits": live_hits,
        "files": [str(p.relative_to(REPO) if p.is_relative_to(REPO) else p) for p in files],
        "names": [p.name for p in files],
        "n": len(files),
        "harvest_named": [
            "agentic-repair-reliability.js",
            "bc-stage-compendium-enrichment.js",
            "codex-auth-research-fanout.mjs",
            "design-gate.mjs",
            "harness-self-improve-sweep.js",
            "plan-gate.mjs",
        ],
        "note": (
            "WFA-0007/WFA-0042 harvest sampled five wf-saved-* ids; catalog "
            "WFA-0045 names plan-gate.mjs and design-gate.mjs. Remaining live "
            "filenames are UNKNOWN because 08-WORKFLOW-CANDIDATE-REGISTRY.json "
            "and live ~/.claude/workflows are absent on this worktree."
        ),
    }


def load_texts() -> list[dict]:
    info = discover()
    rows = []
    for rel, name in zip(info["files"], info["names"]):
        path = REPO / rel if not Path(rel).is_absolute() else Path(rel)
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "name": name,
                "path": rel.replace("\\", "/"),
                "text": text,
                "bytes": len(text.encode("utf-8")),
            }
        )
    info["rows"] = rows
    return rows
