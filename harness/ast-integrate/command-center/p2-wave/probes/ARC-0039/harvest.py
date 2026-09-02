#!/usr/bin/env python3
"""Freeze retrieved vendor notes and compact GitHub release metadata for ARC-0039."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

ANTHROPIC_SRC = Path(
    "/root/.cursor/projects/opt-p2-ast-integrate/agent-tools/"
    "a055d341-04c3-4941-97bb-721ba3b1f0e4.txt"
)
OPENAI_SRC = Path(
    "/root/.cursor/projects/opt-p2-ast-integrate/agent-tools/"
    "83bc95a8-ac50-4edd-8c43-b42f807c67ce.txt"
)


def compact_pages(stem: str, dest_name: str) -> int:
    rows: list[dict] = []
    for page in sorted(RAW.glob(f"{stem}.page*.json")):
        data = json.loads(page.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"FAILED:harvest {page} is not a list")
        for rel in data:
            rows.append(
                {
                    "tag_name": rel.get("tag_name"),
                    "published_at": rel.get("published_at"),
                    "created_at": rel.get("created_at"),
                    "html_url": rel.get("html_url"),
                    "name": rel.get("name"),
                }
            )
        page.unlink()
    dest = RAW / dest_name
    dest.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return len(rows)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    if not ANTHROPIC_SRC.is_file() or not OPENAI_SRC.is_file():
        print(f"FAILED:harvest missing sources a={ANTHROPIC_SRC.is_file()} o={OPENAI_SRC.is_file()}")
        return 1
    shutil.copyfile(ANTHROPIC_SRC, RAW / "anthropic-api-release-notes.md")
    shutil.copyfile(OPENAI_SRC, RAW / "openai-api-changelog.md")
    meta = {
        "retrieved_on": "2026-08-24",
        "anthropic_url": "https://platform.claude.com/docs/en/release-notes/overview",
        "openai_url": "https://developers.openai.com/api/docs/changelog",
        "claude_code_releases_url": "https://api.github.com/repos/anthropics/claude-code/releases",
        "codex_releases_url": "https://api.github.com/repos/openai/codex/releases",
        "window_start": "2026-03-13",
        "window_end": "2026-08-24",
        "window_reason": (
            "Codex GitHub pagination retrieved 400 newest releases whose oldest "
            "published_at is 2026-03-13. A longer window would undercount Codex."
        ),
    }
    n_cc = compact_pages("claude-code-releases", "claude-code-releases.compact.json")
    n_cx = compact_pages("codex-releases", "codex-releases.compact.json")
    meta["claude_code_release_rows"] = n_cc
    meta["codex_release_rows"] = n_cx
    (RAW / "retrieval.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"claude_code_rows={n_cc} codex_rows={n_cx}")
    print("SUCCESS:ARC-0039 harvest frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
