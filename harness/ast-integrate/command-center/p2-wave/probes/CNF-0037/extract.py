"""Extract documented shell commands from user-facing docs.

Every `$ ` line inside a fenced block is a command. Trailing EXIT=N / `->`
annotations are documented expectations, not part of the invocation.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent

CATALOG_INPUTS = [
    "command-center/RUNBOOK.md",
    "README.md",
    "README.rst",
]

DOLLAR_RE = re.compile(r"^\$\s+(.+)$")
EXIT_RE = re.compile(r"\s+EXIT=(\d+)\s*(.*)$")
ARROW_RE = re.compile(r"\s+->\s+(.*)$")
HASH_COMMENT_RE = re.compile(r"\s+#\s.*$")
CMD_TOKENS = {
    "python",
    "python3",
    "bash",
    "sh",
    "zsh",
    "grep",
    "rg",
    "find",
    "ls",
    "cat",
    "curl",
    "wget",
    "pip",
    "pip3",
    "pytest",
    "git",
    "node",
    "npm",
    "npx",
    "make",
    "cargo",
    "go",
    "echo",
    "printf",
    "jq",
    "awk",
    "sed",
    "head",
    "tail",
    "diff",
    "timeout",
    "cd",
    "pwsh",
    "claude",
    "git-crypt",
    "uv",
    "uvx",
    "py",
    "mkdir",
    "cp",
    "mv",
}

USER_FACING_EXTRAS = [
    "docs/multi-agent-quickstart.md",
]


def rel(path: Path, repo: Path = REPO) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def live_doc_paths(repo: Path = REPO) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            return
        seen.add(key)
        found.append(p)

    for spec in CATALOG_INPUTS:
        add(repo / spec)
    for spec in USER_FACING_EXTRAS:
        add(repo / spec)
    return found


def fixture_doc_paths(repo: Path = REPO) -> list[Path]:
    root = HERE / "fixtures" / "docs"
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def corpus_paths(repo: Path = REPO, include_fixtures: bool = True) -> list[Path]:
    paths = live_doc_paths(repo)
    if include_fixtures:
        paths.extend(fixture_doc_paths(repo))
    return paths


def inputs_resolved(repo: Path = REPO) -> list[dict[str, Any]]:
    rows = []
    for spec in CATALOG_INPUTS:
        p = repo / spec
        rows.append(
            {
                "path": spec,
                "present": p.is_file(),
                "role": "catalog-input",
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    docs_dir = repo / "docs"
    rows.append(
        {
            "path": "docs/",
            "present": docs_dir.is_dir(),
            "role": "quick-start-and-advanced",
            "bytes": 0,
        }
    )
    return rows


def _strip_invocation(payload: str) -> tuple[str, int | None, str]:
    documented_exit: int | None = None
    suffix = ""
    m = EXIT_RE.search(payload)
    if m:
        documented_exit = int(m.group(1))
        suffix = (m.group(2) or "").strip()
        payload = payload[: m.start()].rstrip()
    m = ARROW_RE.search(payload)
    if m:
        extra = m.group(1).strip()
        suffix = f"{suffix}\n{extra}".strip() if suffix else extra
        payload = payload[: m.start()].rstrip()
    payload = HASH_COMMENT_RE.sub("", payload).rstrip()
    return payload.strip(), documented_exit, suffix


def _looks_like_command(line: str) -> bool:
    raw = line.strip()
    if not raw or raw.startswith("#") or raw.startswith("```"):
        return False
    token = re.split(r"\s+", raw, maxsplit=1)[0]
    if token in CMD_TOKENS:
        return True
    if token.startswith("./") or token.endswith((".py", ".sh")):
        return True
    return False


def _command_record(
    *,
    rel_path: str,
    line_no: int,
    invocation: str,
    documented_output: str,
    documented_exit: int | None,
    kind: str,
) -> dict[str, Any]:
    return {
        "id": f"{rel_path}:{line_no}",
        "source_path": rel_path,
        "source_line": line_no,
        "invocation": invocation,
        "documented_output": documented_output,
        "documented_exit": documented_exit,
        "kind": kind,
    }


def parse_fence(
    buf: list[tuple[int, str]],
    rel_path: str,
    lang: str,
) -> list[dict[str, Any]]:
    dollar_idx = [i for i, (_ln, text) in enumerate(buf) if DOLLAR_RE.match(text.strip())]
    records: list[dict[str, Any]] = []
    if dollar_idx:
        for j, start in enumerate(dollar_idx):
            line_no, text = buf[start]
            payload = DOLLAR_RE.match(text.strip()).group(1)
            invocation, documented_exit, suffix = _strip_invocation(payload)
            end = dollar_idx[j + 1] if j + 1 < len(dollar_idx) else len(buf)
            body_lines = [buf[k][1] for k in range(start + 1, end)]
            body = "\n".join(body_lines).rstrip()
            documented = body if body else suffix
            if body and suffix and suffix not in body:
                documented = f"{suffix}\n{body}".strip()
            records.append(
                _command_record(
                    rel_path=rel_path,
                    line_no=line_no,
                    invocation=invocation,
                    documented_output=documented,
                    documented_exit=documented_exit,
                    kind="console-dollar",
                )
            )
        return records
    if lang in {"bash", "sh", "shell", "console", "powershell", "text", "cmd", ""}:
        i = 0
        while i < len(buf):
            line_no, text = buf[i]
            stripped = text.strip()
            if not _looks_like_command(stripped):
                i += 1
                continue
            invocation, documented_exit, suffix = _strip_invocation(stripped)
            j = i + 1
            body_lines: list[str] = []
            while j < len(buf):
                nxt = buf[j][1]
                if _looks_like_command(nxt.strip()):
                    break
                if nxt.strip() and not nxt.strip().startswith("#"):
                    body_lines.append(nxt)
                j += 1
            documented = "\n".join(body_lines).rstrip() if body_lines else suffix
            records.append(
                _command_record(
                    rel_path=rel_path,
                    line_no=line_no,
                    invocation=invocation,
                    documented_output=documented,
                    documented_exit=documented_exit,
                    kind="fenced-command",
                )
            )
            i = j
    return records


def extract_from_text(text: str, rel_path: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    records: list[dict[str, Any]] = []
    in_fence = False
    fence_lang = ""
    buf: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_fence and stripped.startswith("```"):
            in_fence = True
            fence_lang = stripped[3:].strip().lower()
            buf = []
            continue
        if in_fence and stripped.startswith("```"):
            records.extend(parse_fence(buf, rel_path, fence_lang))
            in_fence = False
            buf = []
            continue
        if in_fence:
            buf.append((i, line))
    return records


def extract_file(path: Path, repo: Path = REPO) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return extract_from_text(text, rel(path, repo))


def extract_corpus(
    repo: Path = REPO, include_fixtures: bool = True
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in corpus_paths(repo, include_fixtures=include_fixtures):
        for rec in extract_file(path, repo):
            key = rec["id"]
            if key in seen:
                rec = dict(rec)
                rec["id"] = f"{rec['id']}@{len(out)}"
            seen.add(rec["id"])
            out.append(rec)
    return out


def command_key(rec: dict[str, Any]) -> tuple[str, int, str]:
    inv = rec.get("invocation") or rec.get("verbatim_invocation") or ""
    return (
        str(rec.get("source_path") or ""),
        int(rec.get("source_line") or 0),
        str(inv),
    )


def silently_omitted(
    extracted: list[dict[str, Any]], recorded: list[dict[str, Any]]
) -> list[tuple[str, int, str]]:
    rec_keys = {command_key(r) for r in recorded}
    return [command_key(e) for e in extracted if command_key(e) not in rec_keys]


def recorded_commands(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Commands live under report when the receipt uses additionalProperties:false."""
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("commands"), list):
        return list(rep["commands"])
    if isinstance(doc.get("commands"), list):
        return list(doc["commands"])
    return []
