"""30-chunk completeness sample over the live UTF-8 corpus."""
from __future__ import annotations

import os
import random
from pathlib import Path

from taxonomy import classify_chunk
from threshold import CHUNK_CHARS, SAMPLE_N, SAMPLE_SEED

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "_install",
    "_install-probe1",
    "_install-probe2",
    "_scratch",
    "_scratch-probe1",
    "_scratch-probe2",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".whl", ".png", ".jpg", ".jpeg", ".gif"}
TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".md",
    ".mdx",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".jsonl",
    ".schema.json",
}
EXCLUDE_RELS = {
    "command-center/adversarial/ADV-0143-content-redistribution.json",
    "command-center/p2-wave/probes/ADV-0143/SUBAGENT-RETURN.json",
    "command-center/p2-wave/probes/ADV-0143/UNIT-ARTIFACT-MANIFEST.json",
}
MAX_FILE_BYTES = 1_500_000


def _rel(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def iter_text_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.endswith(".dist-info")
        ]
        for name in filenames:
            path = Path(dirpath) / name
            rel = _rel(repo, path)
            if rel in EXCLUDE_RELS:
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            suf = path.suffix.lower()
            if suf not in {".py", ".json", ".md", ".mdx", ".txt", ".yml", ".yaml", ".toml", ".jsonl"}:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size <= 0 or size > MAX_FILE_BYTES:
                continue
            out.append(path)
    out.sort(key=lambda p: _rel(repo, p))
    return out


def file_chunks(repo: Path, path: Path) -> list[tuple[str, int, str]]:
    rel = _rel(repo, path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    except UnicodeDecodeError:
        return [(rel, 1, None)]  # type: ignore[list-item]
    chunks: list[tuple[str, int, str]] = []
    buf: list[str] = []
    n = 0
    start_line = 1
    lines = text.splitlines(True)
    if not lines:
        return [(rel, 1, text)]
    for i, line in enumerate(lines, 1):
        buf.append(line)
        n += len(line)
        if n >= CHUNK_CHARS:
            chunks.append((rel, start_line, "".join(buf)))
            buf = []
            n = 0
            start_line = i + 1
    if buf:
        chunks.append((rel, start_line, "".join(buf)))
    return chunks


def all_chunks(repo: Path) -> list[tuple[str, int, str | None]]:
    rows: list[tuple[str, int, str | None]] = []
    for path in iter_text_files(repo):
        rows.extend(file_chunks(repo, path))
    return rows


def draw_sample(repo: Path, n: int = SAMPLE_N, seed: int = SAMPLE_SEED) -> dict:
    population = all_chunks(repo)
    if len(population) < n:
        raise RuntimeError(f"chunk population {len(population)} < {n}")
    rng = random.Random(seed)
    picks = rng.sample(population, n)
    classified = []
    unclassifiable = []
    for rel, line, text in picks:
        binary = text is None
        cid = classify_chunk(rel, text, binary=binary)
        row = {
            "path": rel,
            "line": line,
            "class_id": cid,
            "chars": 0 if text is None else len(text),
        }
        classified.append(row)
        if cid is None:
            unclassifiable.append(row)
    return {
        "n": n,
        "seed": seed,
        "population": len(population),
        "chunk_chars": CHUNK_CHARS,
        "rows": classified,
        "unclassifiable": unclassifiable,
        "unclassifiable_count": len(unclassifiable),
    }


def mutant_only_binary(rel: str, text: str | None, *, binary: bool = False) -> str | None:
    """Broken taxonomy: only the binary class. UTF-8 chunks are unclassifiable."""
    if binary or text is None:
        return "undecodable-or-binary"
    return None


def mutant_sample(repo: Path, n: int = SAMPLE_N, seed: int = SAMPLE_SEED) -> dict:
    population = all_chunks(repo)
    rng = random.Random(seed)
    picks = rng.sample(population, n)
    unclassifiable = 0
    for rel, line, text in picks:
        binary = text is None
        if mutant_only_binary(rel, text, binary=binary) is None:
            unclassifiable += 1
    return {"n": n, "unclassifiable_count": unclassifiable}
