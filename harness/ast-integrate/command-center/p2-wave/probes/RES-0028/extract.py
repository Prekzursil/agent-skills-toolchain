"""Parse the frozen Aider repomap.py snapshot for ranking citations."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "aider-repomap.py"
CAPTURE = HERE / "fixtures" / "capture.json"

PAGERANK_RE = re.compile(r"ranked\s*=\s*nx\.pagerank\(")
GET_RANKED_RE = re.compile(r"^\s*def get_ranked_tags\(")
BINSEARCH_START_RE = re.compile(r"^\s*while lower_bound <= upper_bound:")
MAP_TOKENS_RE = re.compile(r"map_tokens=1024")
MUL_RE = re.compile(r"map_mul_no_files=8")


def load_capture() -> dict:
    return json.loads(CAPTURE.read_text(encoding="utf-8"))


def snapshot_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def numbered_lines() -> list[tuple[int, str]]:
    return list(enumerate(snapshot_text().splitlines(), 1))


def first_line(pred) -> int:
    for i, line in numbered_lines():
        if pred(line):
            return i
    raise RuntimeError("required ranking marker missing from frozen snapshot")


def ranking_loci() -> dict:
    pagerank_lines = [i for i, line in numbered_lines() if PAGERANK_RE.search(line)]
    if not pagerank_lines:
        raise RuntimeError("nx.pagerank call missing from frozen snapshot")
    return {
        "source_path": "aider/repomap.py",
        "get_ranked_tags_line": first_line(lambda s: GET_RANKED_RE.match(s)),
        "pagerank_primary_line": pagerank_lines[0],
        "pagerank_fallback_line": pagerank_lines[1] if len(pagerank_lines) > 1 else None,
        "binary_search_line": first_line(lambda s: BINSEARCH_START_RE.match(s)),
        "default_map_tokens_line": first_line(lambda s: MAP_TOKENS_RE.search(s)),
        "no_files_multiplier_line": first_line(lambda s: MUL_RE.search(s)),
        "pagerank_primary_text": next(
            line.strip() for i, line in numbered_lines() if i == pagerank_lines[0]
        ),
        "commit": load_capture()["source"]["commit"],
        "permalink": (
            f"{load_capture()['source']['permalink']}#L{pagerank_lines[0]}"
        ),
        "sha256": load_capture()["source"]["sha256"],
    }


def file_line_citation() -> str:
    loc = ranking_loci()
    return f"{loc['source_path']}:{loc['pagerank_primary_line']}"
