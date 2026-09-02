"""Tiny estate-shaped subject plus TST-0015-style operator mutants.

Observation is through the same readers the estate actually uses
(universal newlines, POSIX path join, case-sensitive JSON). Equivalence
is measured: original vs mutant on a published oracle pack.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Callable

SENTINEL = "SUCCESS:LIVE"

Impl = dict[str, Callable[..., Any]]


def _read_universal(data: bytes) -> str:
    text = data.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write_lines_lf(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_lines_crlf(lines: list[str]) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _dump_json(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"))


def _dump_json_key_case_flip(obj: dict) -> str:
    flipped = {str(k).swapcase(): v for k, v in obj.items()}
    return json.dumps(flipped, separators=(",", ":"))


def _parse_json(text: str) -> dict:
    return json.loads(text)


def _join_posix(*parts: str) -> str:
    return "/".join(p.replace("\\", "/").strip("/") for p in parts if p)


def _join_backslash(*parts: str) -> str:
    return "\\".join(p.replace("/", "\\").strip("\\") for p in parts if p)


def _payload_with_sentinel() -> str:
    return f"header\n{SENTINEL}\ntrailer\n"


def _payload_without_sentinel() -> str:
    return "header\ntrailer\n"


def _has_sentinel(text: str) -> bool:
    return SENTINEL in text


def _write_all(payload: bytes) -> bytes:
    buf = bytearray(len(payload))
    buf[:] = payload
    return bytes(buf)


def _write_truncated(payload: bytes) -> bytes:
    cut = max(1, len(payload) // 2)
    return payload[:cut]


def _timeout(timeout: int = 30) -> int:
    return timeout


def _timeout_zero(timeout: int = 0) -> int:
    return timeout


def _mention_ok() -> str:
    # The word "blocked" below is a mention in a comment, not a use.
    # blocked
    return "ok"


def _mention_ok_swapped() -> str:
    # The word "allowed" below is a mention in a comment, not a use.
    # allowed
    return "ok"


def original_impl() -> Impl:
    return {
        "write_lines": _write_lines_lf,
        "read": _read_universal,
        "dump": _dump_json,
        "parse": _parse_json,
        "join": _join_posix,
        "payload": _payload_with_sentinel,
        "has_sentinel": _has_sentinel,
        "write_all": _write_all,
        "timeout": _timeout,
        "mention": _mention_ok,
    }


def _consume_path(path: str) -> str:
    """Estate path consumer: separators are folded to '/' before compare."""
    return path.replace("\\", "/")


def observe(impl: Impl) -> dict[str, Any]:
    """Published oracle pack. Equivalence is identity of this dict."""
    raw_lines = impl["write_lines"](["alpha", "beta"])
    dumped = impl["dump"]({"UnitId": "TST-0120"})
    payload = impl["payload"]()
    return {
        "newlines": impl["read"](raw_lines),
        "json_obj": impl["parse"](dumped),
        "path": _consume_path(impl["join"]("pkg", "mod.py")),
        "sentinel_present": impl["has_sentinel"](payload),
        "written": list(impl["write_all"](b"ABCDEFGH")),
        "timeout_default": impl["timeout"](),
        "mention": impl["mention"](),
    }


def _swap(impl: Impl, key: str, fn: Callable[..., Any]) -> Impl:
    out = dict(impl)
    out[key] = fn
    return out


# Mutants: one TST-0015 operator each. expected_equivalent is the policy
# prior; the oracle pack is the measurement.
MUTANTS: dict[str, dict[str, Any]] = {
    "M-EQ-LF-CRLF": {
        "operator": "lf-crlf-flip",
        "location": "subject.write_lines",
        "apply": lambda impl: _swap(impl, "write_lines", _write_lines_crlf),
        "expected_equivalent": True,
        "justification": (
            "The mutant emits CRLF instead of LF. Observation always runs "
            "read_universal, which folds CR LF CR into LF before any later "
            "comparison, so the oracle dict is identical to the original."
        ),
    },
    "M-KILL-JSON-CASE": {
        "operator": "json-key-case-flip",
        "location": "subject.dump",
        "apply": lambda impl: _swap(impl, "dump", _dump_json_key_case_flip),
        "expected_equivalent": False,
        "justification": None,
    },
    "M-EQ-PATH-SEP": {
        "operator": "path-separator-flip",
        "location": "subject.join",
        "apply": lambda impl: _swap(impl, "join", _join_backslash),
        "expected_equivalent": True,
        "justification": (
            "The mutant joins with backslashes. join_posix and the oracle "
            "path observation normalize separators to '/', so pkg/mod.py is "
            "unchanged for every published input."
        ),
    },
    "M-KILL-SENTINEL": {
        "operator": "sentinel-deletion",
        "location": "subject.payload",
        "apply": lambda impl: _swap(impl, "payload", _payload_without_sentinel),
        "expected_equivalent": False,
        "justification": None,
    },
    "M-KILL-TRUNC": {
        "operator": "mid-write-truncation",
        "location": "subject.write_all",
        "apply": lambda impl: _swap(impl, "write_all", _write_truncated),
        "expected_equivalent": False,
        "justification": None,
    },
    "M-KILL-DEFAULT": {
        "operator": "default-argument-change",
        "location": "subject.timeout",
        "apply": lambda impl: _swap(impl, "timeout", _timeout_zero),
        "expected_equivalent": False,
        "justification": None,
    },
    "M-EQ-MENTION": {
        "operator": "use-vs-mention-swap",
        "location": "subject.mention",
        "apply": lambda impl: _swap(impl, "mention", _mention_ok_swapped),
        "expected_equivalent": True,
        "justification": (
            "The mutant swaps a commented mention ('blocked' vs 'allowed') "
            "and leaves the returned value 'ok' unchanged. The oracle only "
            "observes the return value, so this is use-vs-mention, not a use."
        ),
    },
}


def run_corpus() -> dict[str, Any]:
    base = original_impl()
    original = observe(base)
    rows = []
    for mid, spec in MUTANTS.items():
        mutant_obs = observe(spec["apply"](base))
        identical = mutant_obs == original
        diverged = sorted(k for k in original if original[k] != mutant_obs[k])
        killed = not identical
        rows.append(
            {
                "mutant_id": mid,
                "operator": spec["operator"],
                "location": spec["location"],
                "oracle_identical": identical,
                "killed": killed,
                "diverged_oracles": diverged,
                "expected_equivalent": spec["expected_equivalent"],
                "proposed_justification": spec["justification"],
                "mutant_observation": deepcopy(mutant_obs),
            }
        )
    return {
        "original": original,
        "mutants": rows,
        "total": len(rows),
        "killed": sum(1 for r in rows if r["killed"]),
        "oracle_equivalent": [r["mutant_id"] for r in rows if r["oracle_identical"]],
        "oracle_killed": [r["mutant_id"] for r in rows if r["killed"]],
    }


run_corpus = run_corpus
original_impl = original_impl
observe = observe
