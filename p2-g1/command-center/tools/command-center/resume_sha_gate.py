"""Pinned-SHA resume gate. Mismatch without an explicit choice does not continue."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

RESUME_OK = "resume-ok"
HEAD_ACCEPTED = "head-accepted"
ABORTED = "aborted"
STAY_PINNED = "stay-pinned"
CHOICE_ACCEPT_NEW_HEAD = "accept_new_head"
CHOICE_ABORT = "abort"
CHOICE_STAY_PINNED = "stay_pinned"


class ShaMismatchDecisionRequired(Exception):
    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__(record.get("prompt") or "SHA mismatch")
        self.record = record


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )


def head_sha(repo: Path) -> str:
    proc = git(repo, "rev-parse", "HEAD")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return (proc.stdout or "").strip()


def dump_checkpoint(path: Path, sha: str, extra: dict[str, Any] | None = None) -> None:
    doc = {"pinned_sha": sha, "sha": sha}
    if extra:
        doc.update(extra)
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _files_changed(repo: Path, pinned: str, head: str) -> list[str]:
    proc = git(repo, "diff", "--name-only", f"{pinned}..{head}")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _mismatch_record(
    pinned: str,
    head: str,
    files: list[str],
    *,
    auto_accepted: bool = False,
    work_continued: bool = False,
) -> dict[str, Any]:
    prompt = (
        f"HEAD moved. pinned_sha={pinned} head_sha={head}. "
        f"files_changed={files}. Choose {CHOICE_ACCEPT_NEW_HEAD}, "
        f"{CHOICE_STAY_PINNED}, or {CHOICE_ABORT}."
    )
    return {
        "status": "mismatch",
        "pinned_sha": pinned,
        "head_sha": head,
        "files_changed": files,
        "prompt": prompt,
        "work_continued": work_continued,
        "auto_accepted": auto_accepted,
        "choice": None,
    }


def resume(
    checkpoint: Path,
    repo: Path,
    *,
    choice: str | None = None,
    on_continue: Callable[[], None] | None = None,
) -> dict[str, Any]:
    doc = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
    pinned = str(doc.get("pinned_sha") or doc.get("sha") or "")
    head = head_sha(repo)
    if pinned == head:
        if on_continue:
            on_continue()
        return {
            "status": RESUME_OK,
            "pinned_sha": pinned,
            "head_sha": head,
            "prompt": None,
            "work_continued": True,
            "choice": choice,
            "auto_accepted": False,
        }
    files = _files_changed(repo, pinned, head)
    if choice is None:
        rec = _mismatch_record(pinned, head, files)
        raise ShaMismatchDecisionRequired(rec)
    if choice == CHOICE_ACCEPT_NEW_HEAD:
        if on_continue:
            on_continue()
        return {
            "status": HEAD_ACCEPTED,
            "pinned_sha": pinned,
            "head_sha": head,
            "prompt": None,
            "work_continued": True,
            "choice": choice,
            "auto_accepted": False,
            "files_changed": files,
        }
    if choice == CHOICE_ABORT:
        return {
            "status": ABORTED,
            "pinned_sha": pinned,
            "head_sha": head,
            "work_continued": False,
            "choice": choice,
            "prompt": None,
            "auto_accepted": False,
        }
    if choice == CHOICE_STAY_PINNED:
        return {
            "status": STAY_PINNED,
            "pinned_sha": pinned,
            "head_sha": head,
            "work_continued": False,
            "choice": choice,
            "prompt": None,
            "auto_accepted": False,
        }
    rec = _mismatch_record(pinned, head, files)
    raise ShaMismatchDecisionRequired(rec)


class AutoAcceptResume:
    @staticmethod
    def resume(
        checkpoint: Path,
        repo: Path,
        *,
        on_continue: Callable[[], None] | None = None,
        choice: str | None = None,
    ) -> dict[str, Any]:
        doc = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        pinned = str(doc.get("pinned_sha") or doc.get("sha") or "")
        head = head_sha(repo)
        files = _files_changed(repo, pinned, head) if pinned != head else []
        if on_continue:
            on_continue()
        return {
            "status": HEAD_ACCEPTED,
            "pinned_sha": pinned,
            "head_sha": head,
            "prompt": None,
            "work_continued": True,
            "auto_accepted": True,
            "choice": choice or CHOICE_ACCEPT_NEW_HEAD,
            "files_changed": files,
        }
