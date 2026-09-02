"""Inventory live monitors, harvesters, reducers, and completion-predicate files."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "BLD-0027",
}

NAME_HINTS = ("monitor", "harvester", "harvest", "reducer", "liveness", "stall")
CONTENT_HINTS = (
    "class Monitor",
    "def harvest",
    "fan-in",
    "fan_in",
    "stall_window",
    "mtime stall",
    "SEVERED",
)

REQUIRED_SURFACES = (
    "platform/lib/completion_predicate.py",
    "rules/common/bash-hud-and-terminal-emit.md",
)


def _skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def inventory(repo: Path | None = None) -> dict:
    root = repo or REPO
    hits: list[dict] = []
    for path in root.rglob("*"):
        if not path.is_file() or _skip(path):
            continue
        rel = path.relative_to(root).as_posix()
        name = path.name.lower()
        name_hit = any(h in name for h in NAME_HINTS)
        content_hit = False
        snippet = ""
        if path.suffix.lower() in {".py", ".md", ".json"} and path.stat().st_size < 400_000:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            for hint in CONTENT_HINTS:
                if hint in text:
                    content_hit = True
                    idx = text.find(hint)
                    snippet = text[max(0, idx - 20) : idx + 40].replace("\n", " ")
                    break
        if name_hit or content_hit:
            hits.append(
                {
                    "path": rel,
                    "name_hit": name_hit,
                    "content_hit": content_hit,
                    "snippet": snippet[:80],
                    "bytes": path.stat().st_size,
                }
            )
    required = []
    for rel in REQUIRED_SURFACES:
        p = root / rel
        required.append({"path": rel, "exists": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0})
    adapter = root / "command-center" / "adapters" / "codex.py"
    return {
        "required_surfaces": required,
        "required_missing": [r["path"] for r in required if not r["exists"]],
        "named_hits": hits,
        "codex_adapter_present": adapter.is_file(),
        "codex_adapter_path": "command-center/adapters/codex.py" if adapter.is_file() else None,
        "runner_monitors_present": any("monitor" in h["path"].lower() and "p2-wave/probes" not in h["path"] for h in hits),
    }


def main() -> int:
    inv = inventory()
    print(
        "required_missing={0} named_hits={1} codex={2} runner_monitors={3}".format(
            inv["required_missing"],
            len(inv["named_hits"]),
            inv["codex_adapter_present"],
            inv["runner_monitors_present"],
        )
    )
    for row in inv["required_surfaces"]:
        print(f"required {row['path']} exists={row['exists']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
