"""Signal A: grep reference graph of files that name 08/09/10."""
from __future__ import annotations

from pathlib import Path

from names import ARTIFACTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_DIR = "command-center/p2-wave/probes/WFA-0006"
OUT_REL = "command-center/wfa/WFA-0006-discovery-only-consumers.json"
FIX_MENTION = f"{UNIT_DIR}/fixtures/mention-only.md"
FIX_PLANT = f"{UNIT_DIR}/fixtures/capability-plant.md"

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "node_modules",
    "agent-transcripts",
}
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".rst",
    ".csv",
}
SKIP_SELF = {
    OUT_REL,
    f"{UNIT_DIR}/SUBAGENT-RETURN.json",
    f"{UNIT_DIR}/UNIT-ARTIFACT-MANIFEST.json",
}
MAX_FILE_BYTES = 20_000_000
QUOTE_CAP = 400


def relpath(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def skip_rel(rel: str) -> bool:
    if rel in SKIP_SELF:
        return True
    if rel.startswith(UNIT_DIR + "/"):
        if "/fixtures/" in rel:
            return False
        return True
    return False


def iter_text_files(root: Path):
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            rel = relpath(path)
        except ValueError:
            continue
        if skip_rel(rel):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path, rel


def quote_line(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index)
    start = 0 if start < 0 else start + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    line = text[start:end].strip()
    if len(line) > QUOTE_CAP:
        local = index - start
        lo = max(0, local - QUOTE_CAP // 2)
        hi = min(len(line), lo + QUOTE_CAP)
        line = line[lo:hi]
    return line


def citation_kind(rel: str) -> str:
    if rel == FIX_PLANT:
        return "planted-capability"
    if rel == FIX_MENTION:
        return "planted-mention"
    return "live"


def iter_citations(root: Path | None = None) -> list[dict]:
    root = REPO if root is None else root
    rows: list[dict] = []
    for path, rel in iter_text_files(root):
        try:
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            text = raw.decode("utf-8", "replace")
        except OSError:
            continue
        kind = citation_kind(rel)
        for name in ARTIFACTS:
            start = 0
            while True:
                idx = text.find(name, start)
                if idx < 0:
                    break
                line_no = text.count("\n", 0, idx) + 1
                rows.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "artifact_named": name,
                        "quoted_sentence": quote_line(text, idx),
                        "kind": kind,
                    }
                )
                start = idx + len(name)
    rows.sort(key=lambda r: (r["path"], r["line"], r["artifact_named"]))
    return rows


def naive_is_consumer(row: dict) -> bool:
    """Known-broken: any namer of an artifact is a consumer (use=mention)."""
    sentence = str(row.get("quoted_sentence") or "")
    return any(name in sentence for name in ARTIFACTS)
