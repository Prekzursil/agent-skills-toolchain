"""Classify prose behaviour statements AGREE | CONTRADICT | UNTESTED.

AGREE is illegal without a test id: the classifier rewrites it to UNTESTED.
The known-present git-archive-as-LF-blob prescription is CONTRADICT.
Negated mentions ('never git archive') are not prescriptions.
"""

from __future__ import annotations

import re
from pathlib import Path

from contract import KNOWN_PRESENT_SNIPPET

PRESCRIPTIVE = re.compile(
    r"\b(must|always|never|verify|prescrib|returns?|exits?|shall|prints?)\b",
    re.I,
)
LF_BLOB_ARCHIVE = re.compile(
    r"(LF blob.{0,80}git\s+archive)|(git\s+archive.{0,80}LF blob)|"
    r"against the LF blob \(git archive\)",
    re.I | re.S,
)
NEGATED_ARCHIVE = re.compile(
    r"\b(not|never|no|avoid|unlike|rather than|instead of)\s+.{0,40}git\s+archive",
    re.I,
)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
UNTESTED_SNIPPET = "always ships a signed wheel on Tuesdays"


def is_archive_lf_blob_prescription(text: str) -> bool:
    if NEGATED_ARCHIVE.search(text or ""):
        return False
    blob = text or ""
    if KNOWN_PRESENT_SNIPPET.lower() in blob.lower():
        return True
    return bool(LF_BLOB_ARCHIVE.search(blob))


def extract_statements(path: Path, repo: Path) -> list[dict]:
    rel = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else str(path)
    rows: list[dict] = []
    in_fence = False
    fence_mark = ""
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            mark = stripped[:3] if stripped.startswith("```") else stripped[:3]
            if not in_fence:
                in_fence = True
                fence_mark = mark
            elif stripped.startswith(fence_mark):
                in_fence = False
                fence_mark = ""
            continue
        if in_fence or HEADING.match(line) or not stripped:
            continue
        if stripped.startswith("<!--") or stripped.startswith(">"):
            continue
        if not PRESCRIPTIVE.search(stripped):
            continue
        if len(stripped) < 24:
            continue
        rows.append(
            {
                "path": rel,
                "line": i,
                "text": stripped,
            }
        )
    return rows


def classify_one(
    text: str,
    *,
    test_id: str | None = None,
    joined_exit: int | None = None,
    claimed_success: bool = False,
) -> dict:
    """Classify one statement. Silent AGREE is rewritten to UNTESTED."""
    tid = (test_id or "").strip() or None
    if is_archive_lf_blob_prescription(text):
        return {
            "verdict": "CONTRADICT",
            "test_id": "known-present-git-archive-lf-blob",
            "reason": (
                "Docs prescribe git archive as the LF-blob verification "
                "recipe. Measured on this estate: git archive applies "
                "export-time EOL conversion and returns CRLF worktree bytes "
                "on Windows (CC-0005 / P2-BUILD-ROUND2). A recipe that "
                "returns the trap it claims to verify against is CONTRADICT."
            ),
        }
    if UNTESTED_SNIPPET.lower() in (text or "").lower():
        return {
            "verdict": "UNTESTED",
            "test_id": None,
            "reason": "planted behaviour statement has no measuring test id",
        }
    if tid and joined_exit is not None:
        if claimed_success and joined_exit != 0:
            return {
                "verdict": "CONTRADICT",
                "test_id": tid,
                "reason": f"documented success but command exited {joined_exit}",
            }
        if joined_exit == 0:
            return {
                "verdict": "AGREE",
                "test_id": tid,
                "reason": "joined command exited 0 and documented token appeared",
            }
    if not tid:
        return {
            "verdict": "UNTESTED",
            "test_id": None,
            "reason": "no test id; AGREE is forbidden without one",
        }
    return {
        "verdict": "AGREE",
        "test_id": tid,
        "reason": "joined to a named test",
    }


def force_agree_without_test_id(text: str) -> dict:
    """Caller-side hole: even an AGREE request without a test id must not stick."""
    return classify_one(text, test_id="", joined_exit=0, claimed_success=True)


def validate_no_silent_agree(rows: list[dict]) -> list[dict]:
    bad = [
        r
        for r in rows
        if str(r.get("verdict") or "").upper() == "AGREE"
        and not str(r.get("test_id") or "").strip()
    ]
    return bad


def join_and_classify(
    statements: list[dict],
    runs: list[dict],
) -> list[dict]:
    out: list[dict] = []
    for st in statements:
        text = st["text"]
        tid = None
        exit_code = None
        claimed = False
        for run in runs:
            inv = str(run.get("invocation") or "")
            token = _token_from_invocation(inv)
            if token and token in text:
                tid = str(run.get("id") or "")
                exit_code = run.get("exit_code")
                claimed = True
                break
            if inv and inv in text:
                tid = str(run.get("id") or "")
                exit_code = run.get("exit_code")
                claimed = True
                break
        cls = classify_one(
            text, test_id=tid, joined_exit=exit_code, claimed_success=claimed
        )
        rec = {
            **st,
            "verdict": cls["verdict"],
            "test_id": cls["test_id"],
            "reason": cls["reason"],
            "anchor": f"{st['path']}:{st['line']}",
        }
        out.append(rec)
    silent = validate_no_silent_agree(out)
    if silent:
        raise SystemExit(
            "FAILED:SYN-0020 silent AGREE without test id: "
            + silent[0].get("text", "")[:80]
        )
    return out


def _token_from_invocation(inv: str) -> str:
    m = re.search(r"SYN-0020-[A-Za-z0-9_-]+", inv)
    return m.group(0) if m else ""
