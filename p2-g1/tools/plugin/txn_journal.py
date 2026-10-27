"""Append-only transactional install journal (IMP-0028)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any


LEGAL_OLD = "OLD"
LEGAL_NEW = "NEW"

IMPLEMENTER_KILL_POINTS = (
    "before-backup",
    "after-backup-before-stage",
    "after-stage-before-swap",
    "after-swap-before-commit",
    "after-commit-before-cleanup",
)
REVIEWER_KILL_POINT = "after-rename-before-fsync"


class JournalTruncatedError(ValueError):
    def __init__(self, message: str = "REFUSED truncated journal"):
        super().__init__(message)


class KillInjected(Exception):
    def __init__(self, point: str):
        super().__init__(point)
        self.point = point


def _tree_digest(root: Path) -> str:
    rows = []
    if not root.exists():
        return hashlib.sha256(b"").hexdigest()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            rows.append(f"{rel}:{hashlib.sha256(raw).hexdigest()}")
    blob = "\n".join(rows).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def independent_census(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    staging = dest.parent / (dest.name + ".staging")
    old = dest.parent / (dest.name + ".old")
    return {
        "digest": _tree_digest(dest) if dest.exists() else "",
        "staging_exists": staging.exists(),
        "old_exists": old.exists(),
        "dest_exists": dest.exists(),
    }


def expected_new_census(payload: Path) -> dict[str, Any]:
    return {"digest": _tree_digest(Path(payload))}


def classify_legal_state(
    live: dict[str, Any],
    old_census: dict[str, Any],
    new_census: dict[str, Any],
    *,
    old_dest_existed: bool = True,
) -> str:
    digest = live.get("digest") or ""
    if digest and digest == new_census.get("digest"):
        return LEGAL_NEW
    return LEGAL_OLD


def seed_payload(root: Path) -> Path:
    payload = Path(root) / "payload"
    (payload / "rules").mkdir(parents=True, exist_ok=True)
    (payload / "plugin.json").write_text(
        '{"name":"txn-demo","version":"2.0.0"}\n', encoding="utf-8"
    )
    (payload / "rules" / "a.md").write_text("new-rules\n", encoding="utf-8")
    (payload / "skills").mkdir(parents=True, exist_ok=True)
    (payload / "skills" / "x.md").write_text("skill-v2\n", encoding="utf-8")
    return payload


def seed_old_dest(dest: Path) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "plugin.json").write_text(
        '{"name":"txn-demo","version":"1.0.0"}\n', encoding="utf-8"
    )
    (dest / "rules").mkdir(parents=True, exist_ok=True)
    (dest / "rules" / "a.md").write_text("old-rules\n", encoding="utf-8")
    return independent_census(dest)


class TxnJournal:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True) + "\n"
        data = line.encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(str(self.path), flags, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    def read_complete(self) -> tuple[list[dict[str, Any]], bytes]:
        if not self.path.is_file():
            return [], b""
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise JournalTruncatedError("REFUSED truncated journal (missing trailing newline)")
        records = []
        leftover = b""
        for line in raw.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                leftover = line
                break
            text = line.decode("utf-8").strip()
            if not text:
                continue
            try:
                rec = json.loads(text)
            except json.JSONDecodeError as exc:
                raise JournalTruncatedError(f"REFUSED unparseable journal: {exc}") from exc
            records.append(rec)
        if leftover:
            raise JournalTruncatedError("REFUSED truncated journal")
        return records, leftover

    def prefix_fingerprint(self, n: int) -> tuple[int, str]:
        raw = self.path.read_bytes()[:n]
        return n, hashlib.sha256(raw).hexdigest()


class JournaledInstall:
    def __init__(self, dest: Path, payload: Path, journal_path: Path, kill_at: str | None = None):
        self.dest = Path(dest)
        self.payload = Path(payload)
        self.journal = TxnJournal(journal_path)
        self.kill_at = kill_at
        self.staging = self.dest.parent / (self.dest.name + ".staging")
        self.old = self.dest.parent / (self.dest.name + ".old")

    def _maybe_kill(self, point: str) -> None:
        if self.kill_at == point:
            raise KillInjected(point)

    def run(self) -> dict[str, Any]:
        txn = f"txn-{time.time_ns()}"
        self.journal.append({"ts": time.time(), "event": "open", "kind": "open", "txn": txn})
        self._maybe_kill("before-backup")
        self.journal.append(
            {"ts": time.time(), "event": "step", "kind": "backup", "txn": txn, "op": "backup"}
        )
        if self.dest.exists():
            if self.old.exists():
                shutil.rmtree(self.old)
            shutil.copytree(self.dest, self.old)
        self._maybe_kill("after-backup-before-stage")
        self.journal.append(
            {"ts": time.time(), "event": "step", "kind": "stage", "txn": txn, "op": "stage"}
        )
        if self.staging.exists():
            shutil.rmtree(self.staging)
        shutil.copytree(self.payload, self.staging)
        self._maybe_kill("after-stage-before-swap")
        self.journal.append(
            {"ts": time.time(), "event": "step", "kind": "swap", "txn": txn, "op": "swap"}
        )
        if self.dest.exists():
            shutil.rmtree(self.dest)
        os.rename(self.staging, self.dest)
        self._maybe_kill("after-rename-before-fsync")
        self._maybe_kill("after-swap-before-commit")
        self.journal.append(
            {"ts": time.time(), "event": "commit", "kind": "commit", "txn": txn}
        )
        self._maybe_kill("after-commit-before-cleanup")
        if self.old.exists():
            shutil.rmtree(self.old)
        if self.staging.exists():
            shutil.rmtree(self.staging)
        return {"status": "committed", "txn": txn}


def recover_on_launch(journal_path: Path, dest: Path) -> dict[str, Any]:
    journal = TxnJournal(journal_path)
    try:
        records, leftover = journal.read_complete()
    except JournalTruncatedError:
        raise
    dest = Path(dest)
    staging = dest.parent / (dest.name + ".staging")
    old = dest.parent / (dest.name + ".old")
    kinds = [r.get("kind") for r in records]
    if "commit" in kinds:
        if staging.exists():
            shutil.rmtree(staging)
        if old.exists():
            shutil.rmtree(old)
        action = "already-committed"
        legal = LEGAL_NEW
    elif old.exists():
        if dest.exists():
            shutil.rmtree(dest)
        os.rename(old, dest)
        if staging.exists():
            shutil.rmtree(staging)
        action = "restore-old"
        legal = LEGAL_OLD
    elif staging.exists() and not dest.exists():
        os.rename(staging, dest)
        action = "promote-staging"
        legal = LEGAL_NEW
    else:
        action = "noop"
        legal = LEGAL_OLD
    journal.append(
        {
            "ts": time.time(),
            "event": "recovered",
            "kind": "recover",
            "action": action,
            "claimed_legal_state": legal,
        }
    )
    return {
        "status": "recovered",
        "action": action,
        "claimed_legal_state": legal,
    }


def run_kill_trial(point: str, work: Path) -> dict[str, Any]:
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    dest = work / "dest"
    payload = seed_payload(work)
    old_census = seed_old_dest(dest)
    old_digest = old_census["digest"]
    new_digest = expected_new_census(payload)["digest"]
    journal_path = work / "dest.txn.jsonl"
    landed = False
    try:
        JournaledInstall(dest, payload, journal_path, kill_at=point).run()
    except KillInjected:
        landed = True
    recover = recover_on_launch(journal_path, dest)
    live = independent_census(dest)
    legal = classify_legal_state(
        live, old_census, {"digest": new_digest}, old_dest_existed=True
    )
    valid = (
        live.get("staging_exists") is False
        and live.get("old_exists") is False
        and legal in {LEGAL_OLD, LEGAL_NEW}
        and (
            (legal == LEGAL_NEW and live["digest"] == new_digest)
            or (legal == LEGAL_OLD and live["digest"] == old_digest)
        )
    )
    return {
        "kill_at": point,
        "kill_landed": landed,
        "legal_state": legal,
        "valid": valid,
        "live": live,
        "live_digest": live["digest"],
        "old_digest": old_digest,
        "new_digest": new_digest,
        "matches_old": live["digest"] == old_digest,
        "matches_new": live["digest"] == new_digest,
        "recover": recover,
    }


def run_implementer_kill_sweep(root: Path) -> list[dict[str, Any]]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, point in enumerate(IMPLEMENTER_KILL_POINTS):
        rows.append(run_kill_trial(point, root / f"k{i}-{point}"))
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("recover")
    rec.add_argument("--journal", required=True)
    rec.add_argument("--dest", required=True)
    args = p.parse_args(argv)
    if args.cmd == "recover":
        try:
            recover_on_launch(Path(args.journal), Path(args.dest))
        except JournalTruncatedError as exc:
            print(f"REFUSED {exc}", file=sys.stderr)
            return 3
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
