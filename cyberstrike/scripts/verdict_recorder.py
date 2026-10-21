#!/usr/bin/env python3
"""verdict_recorder.py - garak-style JSONL verdict recorder for the G-13 battery.

Every battery test emits through this module (G-13=C). Design mirrors garak's
per-attempt JSONL event stream, hardened for this estate's S6/S5 contract:

  - IMMUTABLE status vocabulary: SUCCESS / FAILED / INTERRUPTED / PENDING-OWNER.
    Anything else raises ValueError (fail-closed; a status outside the
    vocabulary can never silently appear in a receipt).
  - Per-run append-only `verdicts.jsonl` (one line per test attempt, with a
    per-test monotonic `attempt` sequence) and a SEPARATE `hits.jsonl` for
    individual detector findings (garak keeps hits separate from verdicts;
    so do we - a dead server on the dead-list is a finding, not a test
    failure).
  - Anchors are re-read from disk at record time and stored as sha8. A SUCCESS
    or FAILED claim whose anchor file is missing on disk is DOWNGRADED to
    FAILED (anchor_missing) - "completion claims require disk artifacts"
    (fail-closed completion doctrine). INTERRUPTED/PENDING-OWNER entries keep
    their status (they make no completion claim).
  - close() seals the run: run_summary.json with per-status counts plus
    sha256 of both JSONL files, so post-hoc edits are detectable.

Output location (override with CS_BATTERY_OUT):
  default <receipts>/battery/<run_id>/ under the phase2-5 audit tree.

No network. Never prints or stores credential values; callers pass anchors
and structured fields only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Immutable status constants (S6 vocabulary + owner-lane state)
# ---------------------------------------------------------------------------
SUCCESS = "SUCCESS"
FAILED = "FAILED"
INTERRUPTED = "INTERRUPTED"
PENDING_OWNER = "PENDING-OWNER"

VALID_STATUSES = (SUCCESS, FAILED, INTERRUPTED, PENDING_OWNER)  # tuple: immutable

DEFAULT_OUT_ROOT = Path(r"D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase2-5\battery")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha8(p: Path) -> str:
    """First 8 hex of sha256 - the estate's chat-safe digest form."""
    return sha256_file(p)[:8]


class VerdictRecorder:
    """Append-only per-run verdict + hit recorder."""

    def __init__(
        self,
        out_dir: str | os.PathLike | None = None,
        run_id: str | None = None,
        meta: dict | None = None,
    ):
        if out_dir is None:
            out_dir = os.environ.get("CS_BATTERY_OUT") or None
        if run_id is None:
            run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        if out_dir is None:
            out_dir = DEFAULT_OUT_ROOT / run_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.verdicts_path = self.out_dir / "verdicts.jsonl"
        self.hits_path = self.out_dir / "hits.jsonl"
        self.summary_path = self.out_dir / "run_summary.json"
        self._attempts: dict[str, int] = {}
        self._counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
        self._entries: list[dict] = []
        self.meta = meta or {}
        self.meta.setdefault("argv", sys.argv[:])
        self.meta.setdefault("started_utc", utcnow())

    # -- validation ---------------------------------------------------------
    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"invalid verdict status {status!r}; "
                f"valid: {', '.join(VALID_STATUSES)} (immutable vocabulary)"
            )

    # -- anchors ------------------------------------------------------------
    def _resolve_anchors(self, anchors) -> tuple[list[dict], bool]:
        """Return (anchor rows, all_present). Missing anchor => all_present False."""
        rows, all_present = [], True
        for a in anchors or []:
            p = Path(a["path"]) if isinstance(a, dict) else Path(str(a))
            row = {"path": str(p)}
            if p.is_file():
                row["sha8"] = sha8(p)
                row["bytes"] = p.stat().st_size
            else:
                row["present"] = False
                all_present = False
            rows.append(row)
        return rows, all_present

    # -- core API -----------------------------------------------------------
    def record(
        self,
        test_id: str,
        status: str,
        details: dict | None = None,
        *,
        both_states: dict | None = None,
        anchors=None,
        reason: str | None = None,
    ) -> dict:
        """Append one verdict line. Returns the entry written."""
        self._validate_status(status)
        anchor_rows, all_present = self._resolve_anchors(anchors)
        # Fail-closed completion doctrine: a completion/failure CLAIM without
        # its promised on-disk artifact is FAILED, not SUCCESS/FAILED-as-claimed.
        if not all_present and status in (SUCCESS,):
            status = FAILED
            reason = (reason + "; " if reason else "") + "anchor_missing"
        self._attempts[test_id] = self._attempts.get(test_id, 0) + 1
        entry = {
            "ts": utcnow(),
            "run_id": self.run_id,
            "test_id": test_id,
            "attempt": self._attempts[test_id],
            "status": status,
        }
        if reason:
            entry["reason"] = reason
        if details:
            entry["details"] = details
        if both_states:
            entry["both_states"] = both_states
        if anchor_rows:
            entry["anchors"] = anchor_rows
        with open(self.verdicts_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._counts[status] += 1
        self._entries.append(entry)
        return entry

    def hit(self, test_id: str, kind: str, **fields) -> dict:
        """Append one finding line to the separate hit-log."""
        row = {"ts": utcnow(), "run_id": self.run_id, "test_id": test_id, "kind": kind}
        row.update(fields)
        with open(self.hits_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    # -- seal ---------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "out_dir": str(self.out_dir),
            "finished_utc": utcnow(),
            "counts": dict(self._counts),
            "total_verdicts": len(self._entries),
            "test_ids": sorted(self._attempts),
            "verdicts_sha256": (
                sha256_file(self.verdicts_path) if self.verdicts_path.exists() else None
            ),
            "hits_sha256": (
                sha256_file(self.hits_path) if self.hits_path.exists() else None
            ),
            "meta": self.meta,
            "provenance": "disk-verified: seal re-hashes the JSONL files it "
            "summarizes; statuses restricted to the immutable "
            "vocabulary at write time",
        }

    def close(self) -> dict:
        s = self.summary()
        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
        return s

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.record(
                "battery.harness",
                INTERRUPTED,
                reason="exception",
                details={"error": str(exc)[:500]},
            )
        self.close()
        return False


if __name__ == "__main__":
    # Self-test: exercise the recorder against a temp dir, prove (a) the
    # vocabulary gate fires on a bad status, (b) missing anchor downgrades
    # SUCCESS, (c) seal hashes both files.
    import tempfile

    self_path = Path(__file__).resolve()
    with tempfile.TemporaryDirectory() as td:
        with VerdictRecorder(out_dir=td, run_id="selftest") as rec:
            rec.record("X-1", SUCCESS, details={"n": 1}, anchors=[self_path])
            try:
                rec.record("X-2", "PASSED")
                raise SystemExit("SELFTEST-FAILED vocabulary gate did not fire")
            except ValueError:
                pass
            rec.record(
                "X-3",
                SUCCESS,
                details={"claim": "no artifact"},
                anchors=[Path(td) / "does-not-exist.txt"],
            )
            rec.hit("X-1", "sample_hit", note="hit-log is separate")
            s = rec.close()
        ok = (
            s["counts"][SUCCESS] == 1
            and s["counts"][FAILED] == 1  # X-3 downgraded anchor_missing
            and s["verdicts_sha256"]
            and s["hits_sha256"]
        )
        print("SELFTEST-" + ("PASS" if ok else "FAIL"), json.dumps(s["counts"]))
        sys.exit(0 if ok else 1)
