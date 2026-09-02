"""Probe 1: write a personal field through the live writer, then try to erase.

Erasure of that field requires mutating the append-only log or leaving the
bytes in place. Isolated tempfile only; never the live EVENTS.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import close  # noqa: E402
from inspect_impl import inspect_writer  # noqa: E402

CANARY_EMAIL = "adv0045-canary@example.test"
CANARY_PATH = "/home/adv0045-synthetic/private/notes.txt"
CONTROL_TOKEN = "ADV0045-CONTROL-NO-PII"
FIXED_TS = "2026-08-24T00:00:00+00:00"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _prefix_ok(pre: bytes, post: bytes) -> bool:
    return post.replace(b"\r\n", b"\n").startswith(pre.replace(b"\r\n", b"\n"))


def _rewrite_email(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    if CANARY_EMAIL not in text:
        raise RuntimeError("canary missing before rewrite")
    return text.replace(CANARY_EMAIL, "REDACTED-SUBJECT").encode("utf-8")


def measure() -> dict[str, Any]:
    writer = inspect_writer()
    with tempfile.TemporaryDirectory(prefix="adv0045-p1-") as tmp:
        events = Path(tmp) / "EVENTS.jsonl"
        close.append_event(
            {
                "id": "ADV-0045-SEED",
                "payload": {
                    "home_path": CANARY_PATH,
                    "note": "synthetic personal field for ADV-0045",
                    "subject_email": CANARY_EMAIL,
                },
                "ts": FIXED_TS,
                "verb": "note",
            },
            events,
        )
        close.append_event(
            {
                "id": "ADV-0045-CONTROL",
                "payload": {"note": CONTROL_TOKEN, "unit": "ADV-0045"},
                "ts": "2026-08-24T00:00:01+00:00",
                "verb": "note",
            },
            events,
        )
        original = events.read_bytes()
        pii_present = CANARY_EMAIL.encode("utf-8") in original
        control_present = CONTROL_TOKEN.encode("utf-8") in original
        leave = {
            "mutated": False,
            "pii_still_recoverable": pii_present,
            "erasure_achieved": False,
            "prefix_preserved": True,
            "content_sha256": _sha(original),
        }
        rewritten = _rewrite_email(original)
        mutate = {
            "mutated": True,
            "pii_still_recoverable": CANARY_EMAIL.encode("utf-8") in rewritten,
            "erasure_achieved": CANARY_EMAIL.encode("utf-8") not in rewritten,
            "prefix_preserved": _prefix_ok(original, rewritten),
            "original_sha256": _sha(original),
            "rewritten_sha256": _sha(rewritten),
            "original_bytes": len(original),
            "rewritten_bytes": len(rewritten),
        }
        conflict = pii_present and (
            (not leave["erasure_achieved"] and leave["prefix_preserved"])
            and (mutate["erasure_achieved"] and not mutate["prefix_preserved"])
        )
        # Search still works: control token remains in the unmutated log.
        search_works = control_present and CONTROL_TOKEN.encode("utf-8") in original
        return {
            "pass": bool(
                conflict
                and search_works
                and not writer["erase_or_redact_api"]
                and writer["opens_append_mode"]
                and not writer["wrote_to_live_events"]
            ),
            "probe": "probe1-conflict",
            "unit_id": "ADV-0045",
            "canary_email": CANARY_EMAIL,
            "canary_is_synthetic": True,
            "wrote_to_live_events": False,
            "writer": writer,
            "pii_written_recoverable": pii_present,
            "control_token_findable": search_works,
            "leave_in_place": leave,
            "mutate_to_erase": mutate,
            "conflict": (
                "Erasure of the planted personal field requires rewriting the "
                "JSONL line (prefix hash changes) or leaving the field in place "
                "(append-only preserved, data remains)."
            ),
            "conflict_demonstrated": conflict,
        }
