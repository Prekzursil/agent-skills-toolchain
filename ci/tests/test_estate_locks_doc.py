"""V18 -- the estate locks (L1-L7, G-32, G-36) are written down once, in a doc
whose cited repo paths must exist and whose table must render.

Stdlib only (``re`` + ``pathlib``). The doc under test is
``docs/plans/estate-locks.md``; its data twin is ``locks[]`` in ``.agents/models.json``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = REPO_ROOT / "docs" / "plans" / "estate-locks.md"

LOCK_IDS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "G-32", "G-36")
ENFORCED_COLUMN = (
    3  # cells of a row split on "|": "", id, rule, ENFORCED, DOCUMENTED, ""
)

CODE_SPAN = re.compile(r"`([^`\n]+)`")
# Tokens starting with these never name a repo-relative path: Windows drives, home
# directories, URLs, shell / cmd environment references, and absolute POSIX or URL
# paths such as `/v1` (a repo-relative path never starts with a slash).
SKIP_PREFIXES = ("C:\\", "~", "http", "$", "%", "/")
# A slash-free token counts as a path only when it ends in a source or doc suffix,
# so `glm-5.3`, `targets.cursor` and `127.0.0.1` are identifiers, not files.
PATH_SUFFIXES = (
    ".py",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".ps1",
    ".mjs",
    ".js",
    ".ts",
    ".sh",
)
PLACEHOLDER_CHARS = frozenset("<>*{}")


def doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def code_span_tokens(text: str) -> list[str]:
    """Whitespace-split tokens of every single-backtick span, in document order."""
    return [
        token.rstrip(".,;:")
        for span in CODE_SPAN.findall(text)
        for token in span.split()
    ]


def is_repo_path_candidate(token: str) -> bool:
    """True when the doc means ``token`` as a repo-relative path.

    A candidate contains a ``/`` or ends in one of PATH_SUFFIXES, and is none of:
    a Windows path, a home path, a URL, an env reference, an absolute path, or a
    placeholder / glob (``<repo>/x``, ``skills/*/SKILL.md``).
    """
    if not token or token.startswith(SKIP_PREFIXES):
        return False
    if PLACEHOLDER_CHARS & set(token):
        return False
    return "/" in token or token.lower().endswith(PATH_SUFFIXES)


def missing_paths(tokens: Iterable[str]) -> list[str]:
    """The path candidates among ``tokens`` that do not exist under REPO_ROOT."""
    return sorted(
        {
            token
            for token in tokens
            if is_repo_path_candidate(token) and not (REPO_ROOT / token).exists()
        }
    )


def table_rows(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("|")]


def code_span_contains_raw_pipe(line: str) -> bool:
    """The table lint: a ``|`` inside backticks still splits a GFM cell."""
    return any("|" in span for span in CODE_SPAN.findall(line))


def test_doc_exists() -> None:
    # Known-broken: V18 found the locks in five files and a brief nobody could cite.
    assert DOC.is_file(), f"missing {DOC}"


def test_every_backticked_repo_path_in_the_doc_exists() -> None:
    # Known-broken: nothing checked that a lock's cited enforcement path still existed,
    # so a moved validator or test silently turned an ENFORCED cell into fiction.
    tokens = code_span_tokens(doc_text())
    candidates = [token for token in tokens if is_repo_path_candidate(token)]
    assert candidates, "the doc cites no repo paths; the existence check is vacuous"
    assert missing_paths(tokens) == []


def test_doc_names_every_lock_exactly_once_as_a_table_row() -> None:
    # "Written down ONCE": each id owns one row, no more, no less.
    text = doc_text()
    rows = table_rows(text)
    for lock_id in LOCK_IDS:
        assert lock_id in text, f"{lock_id} is not named in {DOC.name}"
        owning = [row for row in rows if row.startswith(f"| {lock_id} |")]
        assert len(owning) == 1, f"{lock_id} owns {len(owning)} rows, expected 1"


def test_every_lock_row_cites_a_repo_path_in_its_enforced_cell() -> None:
    # A lock with no address is the V18 state this doc exists to end. Even a lock
    # nothing enforces (G-36) must point at the nearest data and say so.
    for row in table_rows(doc_text()):
        lock_id = row.split("|")[1].strip()
        if lock_id not in LOCK_IDS:
            continue
        cell = row.split("|")[ENFORCED_COLUMN]
        cited = [t for t in code_span_tokens(cell) if is_repo_path_candidate(t)]
        assert cited, f"{lock_id}: ENFORCED cell cites no repo path"


def test_no_table_row_hides_a_raw_pipe_inside_a_code_span() -> None:
    # A raw `|` inside backticks renders as a cell separator, so the row gains a
    # column and the lock silently loses its ENFORCED / DOCUMENTED split.
    rows = table_rows(doc_text())
    assert rows, f"no table rows in {DOC.name}"
    offenders = [row for row in rows if code_span_contains_raw_pipe(row)]
    assert offenders == []


def test_every_table_row_has_the_header_column_count() -> None:
    # With the pipe lint above holding, a bare count of `|` per row is the cell count.
    rows = table_rows(doc_text())
    header_pipes = rows[0].count("|")
    assert header_pipes == 5, rows[0]
    uneven = [row for row in rows if row.count("|") != header_pipes]
    assert uneven == []


def test_pipe_lint_predicate_both_states() -> None:
    assert not code_span_contains_raw_pipe("| L1 | rule | `a` and `b/c.py` | prose |")
    assert code_span_contains_raw_pipe("| L1 | rule | `a | b` | prose |")
    # Pipes outside a span are cell separators, never offenders.
    assert not code_span_contains_raw_pipe("| L1 | rule | ENFORCED | DOCUMENTED |")


def test_path_candidate_predicate_both_states() -> None:
    for token in (
        "docs/plans/estate-locks.md",
        ".agents/models.json",
        ".agents/skills/",
        "tools/mcp/inference-hub/",
        "AGENTS.md",
        ".gitleaks.toml",
    ):
        assert is_repo_path_candidate(token), token
    for token in (
        "locks[]",
        "glm-5.3",
        "targets.cursor",
        "127.0.0.1",
        ":8317",
        "/v1",
        "HUGGINGFACE_TOKEN_INFERENCE",
        "https://router.huggingface.co/v1",
        "C:\\Users\\owner\\.agents\\agents.json",
        "~/.codex/config.toml",
        "$HOME/.local/bin/ruff",
        "%APPDATA%\\Cursor\\mcp.json",
        "<repo>/docs/x.md",
        "skills/*/SKILL.md",
    ):
        assert not is_repo_path_candidate(token), token


def test_missing_path_detector_both_states() -> None:
    # Control: the existence check must be able to fail, or a green run proves nothing.
    assert missing_paths(["docs/plans/estate-locks.md", "glm-5.3", "/v1"]) == []
    ghost = "docs/plans/no-such-file-7c1e.md"
    assert missing_paths([ghost, "AGENTS.md"]) == [ghost]


def test_code_span_tokens_split_commands_and_strip_trailing_punctuation() -> None:
    text = "run `python -m pytest ci/tests/x.py` then read `AGENTS.md,` last"
    tokens = code_span_tokens(text)
    assert tokens == ["python", "-m", "pytest", "ci/tests/x.py", "AGENTS.md"]
