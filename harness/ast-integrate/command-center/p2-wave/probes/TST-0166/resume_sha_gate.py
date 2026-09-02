"""Pinned-SHA resume gate. Unchanged HEAD continues; moved HEAD requires a choice."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

RESUME_OK = "RESUME_OK"
HEAD_ACCEPTED = "HEAD_ACCEPTED"
ABORTED = "ABORTED"
STAY_PINNED = "STAY_PINNED"
CHOICE_ABORT = "abort"
CHOICE_ACCEPT_NEW_HEAD = "accept_new_head"
CHOICE_STAY_PINNED = "stay_pinned"
class AutoAcceptResume:
    @staticmethod
    def resume(
        checkpoint: Path,
        repo: Path,
        *,
        on_continue: Callable[[], None] | None = None,
        choice: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ck = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
        pinned = str(ck.get("pinned_sha") or "")
        head = head_sha(repo)
        files = _files_changed(repo, pinned, head) if pinned != head else []
        if on_continue:
            on_continue()
        return {
            "status": HEAD_ACCEPTED,
            "prompt": None,
            "work_continued": True,
            "auto_accepted": True,
            "pinned_sha": pinned,
            "head_sha": head,
            "files_changed": files,
            "choice": choice or CHOICE_ACCEPT_NEW_HEAD,
        }


class ShaMismatchDecisionRequired(RuntimeError):
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record
        super().__init__(record.get("prompt") or "sha mismatch")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


def head_sha(repo: Path) -> str:
    proc = git(Path(repo), "rev-parse", "HEAD")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "rev-parse failed").strip())
    return (proc.stdout or "").strip()


def dump_checkpoint(path: Path, pinned_sha: str, extra: dict[str, Any] | None = None) -> None:
    doc = {"pinned_sha": pinned_sha}
    if extra:
        doc.update(extra)
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _files_changed(repo: Path, pinned: str, head: str) -> list[str]:
    proc = git(Path(repo), "diff", "--name-only", f"{pinned}..{head}")
    if proc.returncode != 0:
        return []
    return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]


def resume(
    checkpoint: Path,
    repo: Path,
    *,
    on_continue: Callable[[], None] | None = None,
    choice: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    ck = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
    pinned = str(ck.get("pinned_sha") or "")
    head = head_sha(repo)
    if pinned == head:
        if on_continue:
            on_continue()
        return {
            "status": RESUME_OK,
            "prompt": None,
            "work_continued": True,
            "pinned_sha": pinned,
            "head_sha": head,
            "files_changed": [],
            "choice": choice,
        }
    files = _files_changed(repo, pinned, head)
    prompt = (
        f"HEAD moved. pinned_sha={pinned} head_sha={head}. "
        f"files={files}. Choose {CHOICE_ACCEPT_NEW_HEAD}, {CHOICE_STAY_PINNED}, or {CHOICE_ABORT}."
    )
    record = {
        "status": "SHA_MISMATCH",
        "prompt": prompt,
        "work_continued": False,
        "auto_accepted": False,
        "pinned_sha": pinned,
        "head_sha": head,
        "files_changed": files,
        "choice": choice,
    }
    if choice is None:
        raise ShaMismatchDecisionRequired(record)
    if choice == CHOICE_ABORT:
        record["status"] = ABORTED
        return record
    if choice == CHOICE_STAY_PINNED:
        record["status"] = STAY_PINNED
        return record
    if choice == CHOICE_ACCEPT_NEW_HEAD:
        if on_continue:
            on_continue()
        record["status"] = HEAD_ACCEPTED
        record["work_continued"] = True
        record["choice"] = CHOICE_ACCEPT_NEW_HEAD
        return record
    raise ShaMismatchDecisionRequired(record)
