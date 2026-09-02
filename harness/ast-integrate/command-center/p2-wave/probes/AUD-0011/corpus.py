"""Build the 88-file repo/live rules pair for AUD-0011.

Host ~/.claude/rules and repo rules/ are absent on this Linux worktree.
The corpus reconstructs the catalog arithmetic (5 identical, 55 EOL-only,
28 content-differing = 25 repo-larger + 3 live-larger) with the three
catalog-pinned live-larger names and byte deltas. It is a measured
fixture pair, not a claim that C:\\Users\\Prekzursil was read.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from paths import (
    FIX,
    IDENTICAL,
    LEDGER_REL,
    LIVE_LARGER,
    LIVE_RULES,
    REPO_LARGER_EXACT,
    REPO_RULES,
)

N_EOL = 55
N_REPO_FILL = 22

LIVE_MTIME_LIVE_AHEAD = datetime(2026, 8, 9, 16, 0, 0, tzinfo=timezone.utc)
LIVE_MTIME_REPO_AHEAD = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
LIVE_MTIME_EOL = datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
COMMIT_LIVE_AHEAD = "2026-07-11T15:02:00+00:00"
COMMIT_REPO_AHEAD = "2026-08-05T12:00:00+00:00"
COMMIT_EOL = "2026-06-15T09:00:00+00:00"
COMMIT_IDENTICAL = "2026-06-01T12:00:00+00:00"


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _utime(path: Path, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def _exact(prefix: bytes, size: int, fill: bytes) -> bytes:
    """Pad to an exact byte size while keeping a trailing newline (line-set safe)."""
    if not prefix.endswith(b"\n"):
        prefix += b"\n"
    if len(prefix) > size:
        raise ValueError(f"prefix {len(prefix)} exceeds target {size}")
    need = size - len(prefix)
    if need == 0:
        return prefix
    if need == 1:
        raise ValueError("cannot pad 1 byte without breaking line structure")
    out = prefix + fill * (need - 1) + b"\n"
    if len(out) != size:
        raise ValueError(f"exact size {len(out)} != {size}")
    return out


def _append_exact(base: bytes, extra: int, unique_line: bytes, fill: bytes) -> bytes:
    """Append exactly `extra` bytes as new lines so `base` remains a line-subset."""
    if not base.endswith(b"\n"):
        raise ValueError("base must end with newline")
    if not unique_line.endswith(b"\n"):
        unique_line += b"\n"
    if extra < len(unique_line):
        raise ValueError("extra shorter than unique line")
    need = extra - len(unique_line)
    if need == 1:
        raise ValueError("cannot pad 1 leftover byte without merging lines")
    if need == 0:
        body = unique_line
    else:
        body = unique_line + fill * (need - 1) + b"\n"
    if len(body) != extra:
        raise ValueError(f"extra {len(body)} != {extra}")
    return base + body


def repo_larger_fillers() -> tuple[str, ...]:
    named = {p for p, _, _ in REPO_LARGER_EXACT}
    extra = (
        "common/windows-shell.md",
        "common/fan-out-contract.md",
        "project/naming.md",
        "project/reviews.md",
        "project/testing.md",
        "project/release.md",
        "project/branch-policy.md",
        "project/owners-override.md",
        "project/docs.md",
        "project/ci-matrix.md",
        "project/changelog.md",
        "common/timeouts.md",
        "common/retry.md",
        "common/sandbox.md",
        "common/network.md",
        "common/secrets-handling.md",
        "common/model-routing.md",
        "common/subagents.md",
        "common/context-budget.md",
        "common/output-style.md",
        "common/unicode.md",
        "common/prompt-budget.md",
    )
    if len(extra) != N_REPO_FILL:
        raise ValueError("filler count")
    if named & set(extra):
        raise ValueError("name collision")
    return extra


def all_rels() -> list[str]:
    live = [p for p, _, _ in LIVE_LARGER]
    repo = [p for p, _, _ in REPO_LARGER_EXACT] + list(repo_larger_fillers())
    eol = [f"eol/e{i:02d}.md" for i in range(N_EOL)]
    out = list(IDENTICAL) + live + repo + eol
    if len(out) != 88 or len(set(out)) != 88:
        raise ValueError(f"expected 88 unique paths, got {len(out)}/{len(set(out))}")
    return out


def build() -> dict:
    _wipe(FIX / "repo")
    _wipe(FIX / "live")
    FIX.mkdir(parents=True, exist_ok=True)
    ledger: dict[str, str] = {}

    for rel in IDENTICAL:
        body = f"# {rel}\nidentical on both trees after any encoding.\n".encode()
        rp, lp = REPO_RULES / rel, LIVE_RULES / rel
        _write(rp, body)
        _write(lp, body)
        _utime(lp, LIVE_MTIME_EOL)
        ledger[rel] = COMMIT_IDENTICAL

    for rel, extra, tag in LIVE_LARGER:
        shared = (
            f"# {rel}\n"
            "Shared policy. Mechanical comparison must not be delegated to an LLM.\n"
            f"REPO-SHARED {tag}\n"
        ).encode()
        unique = f"LIVE-UNIQUE:{tag} additional hard bans observed as live-ahead.\n".encode()
        live = _append_exact(shared, extra, unique, b"L")
        rp, lp = REPO_RULES / rel, LIVE_RULES / rel
        _write(rp, shared)
        _write(lp, live)
        if len(live) - len(shared) != extra:
            raise ValueError(tag)
        _utime(lp, LIVE_MTIME_LIVE_AHEAD)
        ledger[rel] = COMMIT_LIVE_AHEAD

    for rel, repo_n, live_n in REPO_LARGER_EXACT:
        live_prefix = f"# {rel}\nShared live/repo heading.\n".encode()
        live = _exact(live_prefix, live_n, b"l")
        unique = f"REPO-UNIQUE:{rel} squash-merge detector pin lives only in repo.\n".encode()
        extra = repo_n - live_n
        repo = _append_exact(live, extra, unique, b"R")
        if len(repo) != repo_n or len(live) != live_n:
            raise ValueError(rel)
        rp, lp = REPO_RULES / rel, LIVE_RULES / rel
        _write(rp, repo)
        _write(lp, live)
        _utime(lp, LIVE_MTIME_REPO_AHEAD)
        ledger[rel] = COMMIT_REPO_AHEAD

    for i, rel in enumerate(repo_larger_fillers()):
        live = f"# {rel}\nshared prefix for repo-larger filler {i}.\n".encode()
        unique = f"REPO-UNIQUE:{rel} extra authored rule body.\n".encode()
        extra = 80 + i * 3
        if rel == "common/windows-shell.md":
            unique = (
                b"REPO-UNIQUE:windows-shell drive-qualified mention "
                b"C:\\Users\\Prekzursil\\source\\ast-integrate (citation, not a live read).\n"
            )
            extra = 220
        repo = _append_exact(live, extra, unique, b"R")
        rp, lp = REPO_RULES / rel, LIVE_RULES / rel
        _write(rp, repo)
        _write(lp, live)
        _utime(lp, LIVE_MTIME_REPO_AHEAD)
        ledger[rel] = COMMIT_REPO_AHEAD

    for i in range(N_EOL):
        rel = f"eol/e{i:02d}.md"
        lf = f"# {rel}\nEOL-only pair {i}: same logical lines, live uses CRLF.\nline-two\n".encode()
        crlf = lf.replace(b"\n", b"\r\n")
        rp, lp = REPO_RULES / rel, LIVE_RULES / rel
        _write(rp, lf)
        _write(lp, crlf)
        _utime(lp, LIVE_MTIME_EOL)
        ledger[rel] = COMMIT_EOL

    LEDGER_REL.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(ledger) != 88:
        raise ValueError("ledger size")
    return {"files": 88, "ledger": str(LEDGER_REL)}


def load_ledger() -> dict[str, str]:
    return json.loads(LEDGER_REL.read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
