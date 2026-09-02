#!/usr/bin/env python3
"""Adjudicator-only loader for the shipped completion reducer.

The clean-room module must not import this file. When the shipped module is
absent, or cannot be imported, this adapter fail-closes to UNKNOWN on every
condition so a missing reducer cannot be mistaken for agreement with the spec
implementation.

The shipped evaluate() takes (receipt, PredicateOptions) and returns a
PredicateResult (NOT-CHECKED / NOT-APPLICABLE vocabulary). This adapter:

  * puts platform/lib on sys.path so `from vendor_identity import Comparison` works
  * feeds live corpus rows the raw receipt bytes, synthetic rows a thin projection
  * maps NOT-CHECKED -> UNKNOWN and NOT-APPLICABLE -> INAPPLICABLE for the differ
  * never raises into the probe
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "platform" / "lib"

SHIPPED_CANDIDATES = (
    "platform/lib/completion_predicate.py",
    "lib/completion_predicate.py",
    "tools/command-center/completion_predicate.py",
    "command-center/completion_predicate.py",
)

UNKNOWN = "UNKNOWN"

OUTCOME_MAP = {
    "SATISFIED": "SATISFIED",
    "UNSATISFIED": "UNSATISFIED",
    "NOT-CHECKED": UNKNOWN,
    "NOT-APPLICABLE": "INAPPLICABLE",
    "UNKNOWN": UNKNOWN,
    "INAPPLICABLE": "INAPPLICABLE",
}


def shipped_path() -> Path | None:
    for rel in SHIPPED_CANDIDATES:
        path = REPO / rel
        if path.is_file():
            return path
    return None


def load_shipped():
    path = shipped_path()
    if path is None:
        return None
    libdir = str(path.parent)
    if libdir not in sys.path:
        sys.path.insert(0, libdir)
    if LIB.is_dir() and str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    # Dataclasses with from __future__ import annotations look up the module in
    # sys.modules during class creation; spec_from_file_location must register it
    # first or exec_module raises AttributeError on None.__dict__.
    existing = sys.modules.get("completion_predicate")
    if existing is not None and getattr(existing, "evaluate", None):
        return existing
    spec = importlib.util.spec_from_file_location("completion_predicate", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["completion_predicate"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("completion_predicate", None)
        return None
    return mod


def _unknown_rows(reason: str) -> list[dict[str, Any]]:
    from clean_room import CONDITION_TEXT

    return [
        {
            "n": n,
            "id": f"C{n}",
            "text": CONDITION_TEXT[n],
            "outcome": UNKNOWN,
            "basis": reason,
        }
        for n in range(1, 13)
    ]


def _unknown_result(reason: str, present: bool, rel: str | None) -> dict[str, Any]:
    return {
        "implementation": "shipped-adapter",
        "shipped_present": present,
        "shipped_path": rel,
        "verdict": "UNKNOWN",
        "failing_condition_ids": [],
        "conditions": _unknown_rows(reason),
    }


def _repo_of(obs: dict[str, Any]) -> Path:
    root = obs.get("repo")
    return Path(root) if root else REPO


def _load_live_receipt(obs: dict[str, Any]) -> dict[str, Any] | None:
    if not obs.get("live"):
        return None
    arts = obs.get("artifacts") or []
    if not arts:
        return None
    first = arts[0]
    rel = first.get("path") if isinstance(first, dict) else first
    if not isinstance(rel, str) or not rel.strip():
        return None
    path = _repo_of(obs) / rel.replace("\\", "/")
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _artifact_rows(obs: dict[str, Any]) -> list[dict[str, Any]]:
    repo = _repo_of(obs)
    out: list[dict[str, Any]] = []
    for item in obs.get("artifacts") or []:
        if isinstance(item, str):
            rel = item.replace("\\", "/")
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            rel = item["path"].replace("\\", "/")
        else:
            continue
        path = repo / rel
        row: dict[str, Any] = {"path": rel, "role": "primary"}
        if path.is_file():
            raw = path.read_bytes()
            row["exists"] = True
            row["bytes"] = path.stat().st_size
            row["sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            row["exists"] = False
        out.append(row)
    return out


def observation_as_receipt(obs: dict[str, Any]) -> dict[str, Any]:
    """Thin projection of a clean-room observation into shipped-receipt fields.

    Maps synonymous keys (fired_on_bad -> fired_on_bad_state). Does not invent
    min_bytes_threshold, test commands, extra evidence anchors, or downstream
    consumers — those absences are real disagreements the differ must see.
    """
    receipt: dict[str, Any] = {
        "state": obs.get("state"),
        "sentinel": obs.get("sentinel"),
        "artifacts": _artifact_rows(obs),
    }
    uid = obs.get("unit_id")
    if isinstance(uid, str) and uid.strip():
        receipt["unit_id"] = uid
    if isinstance(obs.get("min_bytes_threshold"), int):
        receipt["min_bytes_threshold"] = obs["min_bytes_threshold"]

    if "tests" in obs:
        tests = []
        for t in obs.get("tests") or []:
            if not isinstance(t, dict):
                continue
            tests.append(
                {
                    "id": t.get("id") or t.get("name") or "t",
                    "result": t.get("result") or t.get("status"),
                    "command": t.get("command") or "",
                }
            )
        receipt["tests"] = tests

    if "negative_controls" in obs:
        controls = []
        for c in obs.get("negative_controls") or []:
            if not isinstance(c, dict):
                continue
            controls.append(
                {
                    "id": c.get("id") or "nc",
                    "fired_on_bad_state": c.get("fired_on_bad_state", c.get("fired_on_bad")),
                    "silent_on_good_state": c.get(
                        "silent_on_good_state", c.get("silent_on_good")
                    ),
                }
            )
        receipt["negative_controls"] = controls

    if "evidence" in obs:
        items = []
        for e in obs.get("evidence") or []:
            if isinstance(e, dict) and isinstance(e.get("anchor"), str):
                items.append(e)
                continue
            rel = None
            if isinstance(e, dict) and isinstance(e.get("path"), str):
                rel = e["path"].replace("\\", "/")
            elif isinstance(e, str) and e.strip():
                rel = e.split(":")[0].replace("\\", "/")
            if not rel:
                continue
            items.append(
                {
                    "claim": "synthetic evidence path from observation",
                    "verdict": "PARTIAL",
                    "anchor": f"{rel}:1",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": f"stat {rel}",
                            "raw_output": "observed",
                            "fingerprint": f"obs-{rel}",
                        }
                    ],
                }
            )
        receipt["evidence"] = items

    if obs.get("reviewer") is not None:
        receipt["reviewer"] = obs.get("reviewer")
    if "defects" in obs:
        receipt["defects"] = obs.get("defects")

    man = obs.get("manifest")
    if isinstance(man, dict):
        receipt["manifest_registration"] = {
            "registered": man.get("registered"),
            "manifest_path": man.get("manifest_path") or "",
        }
    return receipt


def _schema_rel(obs: dict[str, Any], receipt: dict[str, Any]) -> str | None:
    schema = obs.get("schema_path")
    if isinstance(schema, str) and schema.endswith(".json") and not schema.startswith("http"):
        return schema.replace("\\", "/")
    schema = receipt.get("output_schema") or receipt.get("$schema")
    if isinstance(schema, str) and schema.endswith(".json") and not schema.startswith("http"):
        return schema.replace("\\", "/")
    return None


def _as_condition_dict(row: Any) -> dict[str, Any] | None:
    if hasattr(row, "to_dict"):
        row = row.to_dict()
    if not isinstance(row, dict):
        return None
    try:
        n = int(row.get("n") or 0)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 12:
        return None
    raw = str(row.get("outcome") or "")
    outcome = OUTCOME_MAP.get(raw, UNKNOWN if not raw else raw)
    return {
        "n": n,
        "id": f"C{n}",
        "text": row.get("text") or "",
        "outcome": outcome,
        "basis": row.get("basis") or "",
    }


def normalize_result(result: Any, rel: str) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        payload = result.to_dict()
    elif isinstance(result, dict):
        payload = dict(result)
    else:
        return _unknown_result(
            f"shipped evaluate returned {type(result).__name__}, not a dict/PredicateResult",
            True,
            rel,
        )
    raw_rows = payload.get("conditions") or []
    if hasattr(result, "conditions") and not raw_rows:
        raw_rows = list(result.conditions)
    by_n: dict[int, dict[str, Any]] = {}
    for row in raw_rows:
        parsed = _as_condition_dict(row)
        if parsed:
            by_n[parsed["n"]] = parsed
    from clean_room import CONDITION_TEXT

    conditions = []
    for n in range(1, 13):
        if n in by_n:
            conditions.append(by_n[n])
        else:
            conditions.append(
                {
                    "n": n,
                    "id": f"C{n}",
                    "text": CONDITION_TEXT[n],
                    "outcome": UNKNOWN,
                    "basis": "shipped result omitted this condition; fail-closed UNKNOWN",
                }
            )
    outcomes = [c["outcome"] for c in conditions]
    if any(o == "UNSATISFIED" for o in outcomes):
        verdict = "INCOMPLETE"
    elif any(o == UNKNOWN for o in outcomes):
        verdict = "UNKNOWN"
    else:
        verdict = "COMPLETE"
    return {
        "implementation": "shipped",
        "shipped_present": True,
        "shipped_path": rel,
        "verdict": verdict,
        "failing_condition_ids": [c["id"] for c in conditions if c["outcome"] == "UNSATISFIED"],
        "conditions": conditions,
    }


def evaluate_observation(obs: dict[str, Any]) -> dict[str, Any]:
    """Evaluate using the shipped reducer if present; else fail-closed UNKNOWN."""
    path = shipped_path()
    if path is None:
        reason = (
            "shipped reducer absent (looked for "
            + ", ".join(SHIPPED_CANDIDATES)
            + "); fail-closed UNKNOWN"
        )
        return _unknown_result(reason, False, None)
    rel = path.relative_to(REPO).as_posix()
    try:
        mod = load_shipped()
    except Exception as exc:
        return _unknown_result(
            f"shipped file present at {rel} but import raised {type(exc).__name__}: {exc}",
            True,
            rel,
        )
    if mod is None:
        return _unknown_result(
            f"shipped file present at {rel} but failed to import (vendor_identity path?)",
            True,
            rel,
        )
    try:
        receipt = _load_live_receipt(obs) or observation_as_receipt(obs)
        opts_cls = getattr(mod, "PredicateOptions", None)
        fn = getattr(mod, "evaluate", None)
        if callable(fn) and opts_cls is not None:
            opts = opts_cls(
                repo_root=_repo_of(obs),
                output_schema=_schema_rel(obs, receipt),
            )
            result = fn(receipt, opts)
            return normalize_result(result, rel)
        result = None
        for name in ("evaluate_observation", "complete", "judge"):
            alt = getattr(mod, name, None)
            if callable(alt):
                result = alt(obs)
                break
        if result is None:
            return _unknown_result(
                f"shipped module {rel} has no callable evaluate(receipt, opts)",
                True,
                rel,
            )
        return normalize_result(result, rel)
    except Exception as exc:
        return _unknown_result(
            f"shipped evaluate raised {type(exc).__name__}: {exc}",
            True,
            rel,
        )
