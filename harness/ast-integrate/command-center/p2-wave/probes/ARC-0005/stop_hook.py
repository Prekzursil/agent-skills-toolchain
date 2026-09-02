"""Stop-hook surface for repo-vs-live config drift.

Catalog latency test: wall-clock from a planted edit to the first surfaced
warning through this Stop-hook path. Estate `hooks/git-hygiene/check.py` is
absent on this worktree; this module is the executable Stop-hook used by the
probe (invoke on Stop, write a warning file if drift fired).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SURFACE = HERE / "fixtures" / "stop-surface" / "WARNING.txt"

sys.path.insert(0, str(HERE))
from detector import detect  # noqa: E402
from trees import CTRL_LIVE, CTRL_REPO  # noqa: E402


def surface_warning(payload: dict) -> Path:
    SURFACE.parent.mkdir(parents=True, exist_ok=True)
    if payload.get("fired"):
        text = (
            "STOP-HOOK DRIFT WARNING\n"
            f"ts={time.time_ns()}\n"
            f"drifted_count={payload.get('drifted_count')}\n"
            f"first_paths={payload.get('first_paths')}\n"
        )
        SURFACE.write_text(text, encoding="utf-8")
    elif SURFACE.exists():
        SURFACE.unlink()
    return SURFACE


def run(repo: Path | None = None, live: Path | None = None) -> dict:
    repo = repo or CTRL_REPO
    live = live or CTRL_LIVE
    result = detect(repo, live)
    path = surface_warning(result)
    result["warning_path"] = str(path)
    result["warning_present"] = path.is_file()
    return result


def main() -> int:
    doc = run()
    print(json.dumps(doc, sort_keys=True))
    print("STOP-HOOK fired" if doc["fired"] else "STOP-HOOK silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
