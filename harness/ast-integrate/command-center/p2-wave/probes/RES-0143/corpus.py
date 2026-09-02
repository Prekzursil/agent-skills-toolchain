#!/usr/bin/env python3
"""Committed 30-anecdote sample + 5 vague negative controls.

These are fixtures constructed to exercise the protocol (specified / partial /
hearsay / vague). They are not a live harvest of 30 forum posts.
_USER-PROMPTS.md, sources/REGISTER.md, and CLAIM-REGISTRY.json are absent
on this worktree; the sample is therefore a local, pinned corpus.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Frozen expected dispositions pin the protocol. Live transform() must match.
SAMPLE: list[dict[str, Any]] = [
    {
        "id": "S01",
        "expected": "TRANSFORMABLE",
        "text": "pytest collection fails when I pass --doctest-modules on a namespace package.",
    },
    {
        "id": "S02",
        "expected": "TRANSFORMABLE",
        "text": "The MCP stdio client hangs after I send initialize without notifications/initialized.",
    },
    {
        "id": "S03",
        "expected": "TRANSFORMABLE",
        "text": "npm install sqlite3 fails when I use Node 22 without Python 3 for node-gyp.",
    },
    {
        "id": "S04",
        "expected": "TRANSFORMABLE",
        "text": "git rebase --abort fails to restore the branch after I interrupt the rebase with Ctrl-C.",
    },
    {
        "id": "S05",
        "expected": "TRANSFORMABLE",
        "text": "The JSON Schema validator fails to reject extra keys when I omit additionalProperties on a closed object schema.",
    },
    {
        "id": "S06",
        "expected": "TRANSFORMABLE",
        "text": "curl https://api.github.com/zen fails with 403 after I send a request with an empty User-Agent.",
    },
    {
        "id": "S07",
        "expected": "TRANSFORMABLE",
        "text": "The pytest tmp_path fixture raises PermissionError when I delete the directory inside the test and then write again.",
    },
    {
        "id": "S08",
        "expected": "TRANSFORMABLE",
        "text": "docker build fails when I COPY a file that is listed in .dockerignore.",
    },
    {
        "id": "S09",
        "expected": "TRANSFORMABLE",
        "text": "The SQLite connection raises database is locked after I open two writers without WAL.",
    },
    {
        "id": "S10",
        "expected": "TRANSFORMABLE",
        "text": "python -m pip install -e . fails when I run it from a path whose parent has a space.",
    },
    {
        "id": "S11",
        "expected": "TRANSFORMABLE",
        "text": "The webhook handler drops events after I return HTTP 200 before finishing the work.",
    },
    {
        "id": "S12",
        "expected": "TRANSFORMABLE",
        "text": "make -j fails when I use a recipe that writes the same stamp file from two targets.",
    },
    {
        "id": "S13",
        "expected": "TRANSFORMABLE",
        "text": "The OAuth callback never fires when I register http://localhost as the redirect URI but the server binds to 127.0.0.1.",
    },
    {
        "id": "S14",
        "expected": "TRANSFORMABLE",
        "text": "rsync --delete wiped the destination when I pointed --exclude at a relative path that did not match.",
    },
    {
        "id": "S15",
        "expected": "TRANSFORMABLE",
        "text": "The asyncio task group cancels sibling tasks after I raise CancelledError inside one child.",
    },
    {
        "id": "S16",
        "expected": "TRANSFORMABLE",
        "text": "Hypothesis health-check fails when I mark a test with @example that is rejected by an assume().",
    },
    {
        "id": "S17",
        "expected": "TRANSFORMABLE",
        "text": "The YAML loader silently converts on to True when I load an unquoted country code.",
    },
    {
        "id": "S18",
        "expected": "TRANSFORMABLE",
        "text": "gzip.open in text mode raises UnicodeDecodeError when I pass a latin-1 log without encoding=.",
    },
    {
        "id": "S19",
        "expected": "NOT-TRANSFORMABLE",
        "text": "The agent got slower after the last update.",
    },
    {
        "id": "S20",
        "expected": "NOT-TRANSFORMABLE",
        "text": "Auth is broken.",
    },
    {
        "id": "S21",
        "expected": "NOT-TRANSFORMABLE",
        "text": "Sometimes the tests flake.",
    },
    {
        "id": "S22",
        "expected": "NOT-TRANSFORMABLE",
        "text": "It crashes.",
    },
    {
        "id": "S23",
        "expected": "NOT-TRANSFORMABLE",
        "text": "When I use the tool, things go wrong.",
    },
    {
        "id": "S24",
        "expected": "NOT-TRANSFORMABLE",
        "text": "People on the forum said the Windows build is buggy.",
    },
    {
        "id": "S25",
        "expected": "NOT-TRANSFORMABLE",
        "text": "I had issues with the new API.",
    },
    {
        "id": "S26",
        "expected": "NOT-TRANSFORMABLE",
        "text": "After I upgraded, something felt off.",
    },
    {
        "id": "S27",
        "expected": "NOT-TRANSFORMABLE",
        "text": "The production instance failed last Tuesday.",
    },
    {
        "id": "S28",
        "expected": "NOT-TRANSFORMABLE",
        "text": "If I remember correctly the cache was warm.",
    },
    {
        "id": "S29",
        "expected": "NOT-TRANSFORMABLE",
        "text": "Our CI is red.",
    },
    {
        "id": "S30",
        "expected": "NOT-TRANSFORMABLE",
        "text": "It broke when I did the usual thing.",
    },
]

NEGATIVE_CONTROLS: list[dict[str, Any]] = [
    {"id": "N01", "expected": "NOT-TRANSFORMABLE", "text": "It's weird."},
    {"id": "N02", "expected": "NOT-TRANSFORMABLE", "text": "Stuff doesn't work."},
    {"id": "N03", "expected": "NOT-TRANSFORMABLE", "text": "I had issues."},
    {
        "id": "N04",
        "expected": "NOT-TRANSFORMABLE",
        "text": "Something feels off with the new build.",
    },
    {
        "id": "N05",
        "expected": "NOT-TRANSFORMABLE",
        "text": "People say this is buggy.",
    },
]

GOLD_INJECT = SAMPLE[0]["text"]
STRIP_GOLD_TO_VAGUE = "pytest collection fails."
GOLD_INJECT = GOLD_INJECT
STRIP_GOLD_TO_VAGUE = STRIP_GOLD_TO_VAGUE


def all_records() -> list[dict[str, Any]]:
    out = []
    for row in SAMPLE:
        rec = dict(row)
        rec["cohort"] = "sample-30"
        out.append(rec)
    for row in NEGATIVE_CONTROLS:
        rec = dict(row)
        rec["cohort"] = "negative-control-5"
        out.append(rec)
    return out


def fixture_path(aid: str) -> Path:
    return FIXTURES / f"{aid}.txt"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def ensure_on_disk() -> list[dict[str, Any]]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    pinned: list[dict[str, Any]] = []
    for rec in all_records():
        path = fixture_path(rec["id"])
        text = rec["text"].rstrip() + "\n"
        path.write_text(text, encoding="utf-8")
        raw = path.read_bytes()
        pinned.append(
            {
                **rec,
                "path": relpath(path),
                "sha256": digest_bytes(raw),
                "bytes": len(raw.replace(b"\r\n", b"\n")),
            }
        )
    return pinned


def relpath(path: Path) -> str:
    repo = HERE.parents[3]
    return path.resolve().relative_to(repo).as_posix()


ensure_on_disk = ensure_on_disk
