#!/usr/bin/env python3
"""Estate census: success-by-attempt-number from recorded run history.

Two mechanically independent signals:
  S1  supervisor.log LAUNCH/DONE-OK/RETRYABLE/PARK/INFRA lines
  S2  on-tree retry.attempts + two-strike probe pairs + SUBAGENT-RETURN status
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
SUPERVISOR_LIVE = Path("/opt/p2/supervisor.log")
DISPATCH = REPO / "command-center" / "p2-wave" / "seed-stage" / "dispatch_cursor.py"
LAUNCH_RE = re.compile(r"LAUNCH (\S+) attempt=(\d+)")
DONE_RE = re.compile(r"DONE-OK (\S+)")
RETRY_RE = re.compile(r"RETRYABLE (\S+)")
PARK_RE = re.compile(r"PARK (\S+)")
INFRA_RE = re.compile(r"INFRA (\S+)")
TWO_STRIKES_RE = re.compile(r"TWO_STRIKES\s*=\s*(\d+)")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw.replace(b"\r\n", b"\n")), len(raw)


def supervisor_log_path() -> Path:
    snap = HERE / "captures" / "supervisor-log.body"
    if snap.is_file() and snap.stat().st_size > 0:
        return snap
    return SUPERVISOR_LIVE


def parse_supervisor(text: str) -> dict[str, Any]:
    launches = LAUNCH_RE.findall(text)
    done = DONE_RE.findall(text)
    retryable = RETRY_RE.findall(text)
    parked = PARK_RE.findall(text)
    infra = INFRA_RE.findall(text)
    by_unit: dict[str, list[int]] = {}
    for uid, att in launches:
        by_unit.setdefault(uid, []).append(int(att))
    done_set = set(done)
    success_by_attempt: dict[str, int] = {"1": 0, "2": 0, "3": 0, "other": 0}
    for uid in done_set:
        attempts = by_unit.get(uid) or [1]
        n = max(attempts)
        key = str(n) if n in (1, 2, 3) else "other"
        success_by_attempt[key] += 1
    n_attempt2 = sum(1 for _, a in launches if int(a) >= 2)
    n_attempt3 = sum(1 for _, a in launches if int(a) >= 3)
    return {
        "launch_events": len(launches),
        "unique_launched": len(by_unit),
        "done_ok": len(done_set),
        "retryable_events": len(retryable),
        "park_events": len(parked),
        "infra_events": len(infra),
        "launches_attempt_ge_2": n_attempt2,
        "launches_attempt_ge_3": n_attempt3,
        "success_by_max_launch_attempt": success_by_attempt,
        "p_done_ok_given_attempt1_only": (
            (success_by_attempt["1"] / len(done_set)) if done_set else None
        ),
        "second_attempt_successes": success_by_attempt["2"],
        "third_attempt_successes": success_by_attempt["3"],
        "note": (
            "Success-by-attempt uses max LAUNCH attempt=N seen for that uid "
            "before DONE-OK. INFRA skips are not strikes."
        ),
    }


def _walk_retry_attempts(obj: Any, found: list[list[dict]]) -> None:
    if isinstance(obj, dict):
        attempts = obj.get("attempts")
        if isinstance(attempts, list) and attempts:
            rows = [a for a in attempts if isinstance(a, dict)]
            if any(
                "error_fingerprint" in a
                or "error_fingerprint" in a
                or "fp" in a
                or "fingerprint" in a
                for a in rows
            ):
                found.append(rows)
        for v in obj.values():
            _walk_retry_attempts(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_retry_attempts(v, found)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def retry_sequences_from_tree() -> dict[str, Any]:
    seqs: list[dict[str, Any]] = []
    roots = [
        PROBES,
        REPO / "command-center" / "receipts",
        REPO / "command-center" / "adversarial",
        REPO / "command-center" / "research",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            name = path.name
            if name in {"SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                continue
            posix = path.as_posix()
            if "/probes/RES-0167/" in posix or posix.endswith(
                "RES-0167-fix-review-repair-loop-limits.json"
            ):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            doc = load_json(path)
            if doc is None:
                continue
            found: list[list[dict]] = []
            _walk_retry_attempts(doc, found)
            for rows in found:
                fps = [
                    str(
                        a.get("error_fingerprint")
                        or a.get("error_fingerprint")
                        or a.get("fp")
                        or a.get("fingerprint")
                        or ""
                    )
                    for a in rows
                ]
                outcomes = [str(a.get("outcome") or a.get("result") or "") for a in rows]
                same = len(fps) >= 2 and bool(fps[-1]) and fps[-1] == fps[-2]
                seqs.append(
                    {
                        "path": path.relative_to(REPO).as_posix(),
                        "n_attempts": len(rows),
                        "fingerprints": fps,
                        "outcomes": outcomes,
                        "trailing_same_fingerprint": same,
                    }
                )
    same_then_success = 0
    same_still_fail = 0
    changed_fp = 0
    for s in seqs:
        fps = s["fingerprints"]
        outs = [o.upper() for o in s["outcomes"]]
        if s["trailing_same_fingerprint"]:
            if outs and outs[-1] in {"SUCCESS", "DELIVERED", "PASS"}:
                same_then_success += 1
            else:
                same_still_fail += 1
        elif len(fps) >= 2 and fps[-1] != fps[-2]:
            changed_fp += 1
    return {
        "sequences": seqs,
        "n_sequences": len(seqs),
        "trailing_same_fingerprint_then_success": same_then_success,
        "trailing_same_fingerprint_still_not_success": same_still_fail,
        "trailing_fingerprint_changed": changed_fp,
    }


def two_strike_pairs() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not PROBES.is_dir():
        return {"n_pairs": 0, "delivered_after_two_strikes": 0, "rows": []}
    for d in sorted(PROBES.iterdir()):
        if not d.is_dir():
            continue
        s1 = sorted(d.glob("_strike1*.json")) + sorted(d.glob("_strike_1*.json"))
        s2 = sorted(d.glob("_strike2*.json")) + sorted(d.glob("_strike_2*.json"))
        if not s1 or not s2:
            continue
        ret_path = d / "SUBAGENT-RETURN.json"
        status = None
        state = None
        if ret_path.is_file():
            doc = load_json(ret_path)
            if isinstance(doc, dict):
                status = doc.get("status")
                state = doc.get("state")
        delivered = str(status or "").upper() == "DELIVERED" or str(state or "").upper() == "SUCCESS"
        rows.append(
            {
                "unit_id": d.name,
                "strike1": s1[0].name,
                "strike2": s2[0].name,
                "has_subagent_return": ret_path.is_file(),
                "status": status,
                "state": state,
                "delivered": delivered,
            }
        )
    n_del = sum(1 for r in rows if r["delivered"])
    return {
        "n_pairs": len(rows),
        "delivered_after_two_strikes": n_del,
        "not_delivered_after_two_strikes": len(rows) - n_del,
        "rows": rows,
    }


def subagent_retry_counts() -> dict[str, Any]:
    n = 0
    delivered = 0
    with_retry_key = 0
    nonzero = 0
    for path in sorted(PROBES.glob("*/SUBAGENT-RETURN.json")):
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        n += 1
        if str(doc.get("status") or "").upper() == "DELIVERED":
            delivered += 1
        retry = doc.get("retry")
        if isinstance(retry, dict):
            with_retry_key += 1
            if int(retry.get("count") or 0) > 0:
                nonzero += 1
    return {
        "n_returns": n,
        "delivered": delivered,
        "with_retry_key": with_retry_key,
        "retry_count_nonzero": nonzero,
        "retry_count_zero_or_absent": n - nonzero,
    }


def dispatch_two_strikes() -> dict[str, Any]:
    if not DISPATCH.is_file():
        return {"present": False}
    text = DISPATCH.read_text(encoding="utf-8")
    m = TWO_STRIKES_RE.search(text)
    sha, size = sha256_file(DISPATCH)
    return {
        "present": True,
        "path": DISPATCH.relative_to(REPO).as_posix(),
        "two_strikes": int(m.group(1)) if m else None,
        "sha256": sha,
        "bytes": size,
        "quote_park": "if len(rec[\"attempts\"]) >= TWO_STRIKES:" in text,
    }


def census() -> dict[str, Any]:
    log_path = supervisor_log_path()
    log_text = (
        log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    )
    log_sha, log_bytes = sha256_file(log_path) if log_path.is_file() else ("", 0)
    s1 = parse_supervisor(log_text)
    s2_seq = retry_sequences_from_tree()
    s2_pairs = two_strike_pairs()
    s2_ret = subagent_retry_counts()
    policy = dispatch_two_strikes()
    tree = {
        "retry_sequences": {
            "n_sequences": s2_seq["n_sequences"],
            "trailing_same_fingerprint_then_success": s2_seq[
                "trailing_same_fingerprint_then_success"
            ],
            "trailing_same_fingerprint_still_not_success": s2_seq[
                "trailing_same_fingerprint_still_not_success"
            ],
            "trailing_fingerprint_changed": s2_seq["trailing_fingerprint_changed"],
            "sequences": list(s2_seq["sequences"]),
        },
        "two_strike_pairs": s2_pairs,
        "subagent_returns": s2_ret,
        "source_kind": "json-retry-attempts-and-strike-pairs",
    }
    printed = (
        "success_by_attempt "
        f"attempt1={s1['success_by_max_launch_attempt']['1']} "
        f"attempt2={s1['success_by_max_launch_attempt']['2']} "
        f"attempt3={s1['success_by_max_launch_attempt']['3']} "
        f"launches_ge2={s1['launches_attempt_ge_2']} "
        f"launches_ge3={s1['launches_attempt_ge_3']} "
        f"same_fp_then_success={s2_seq['trailing_same_fingerprint_then_success']} "
        f"same_fp_still_fail={s2_seq['trailing_same_fingerprint_still_not_success']} "
        f"two_strike_pairs={s2_pairs['n_pairs']} "
        f"two_strike_delivered={s2_pairs['delivered_after_two_strikes']}"
    )
    return {
        "harvested_at": utc_now(),
        "signal1_supervisor": {
            **s1,
            "log_path": str(log_path),
            "log_sha256": log_sha,
            "log_bytes": log_bytes,
            "source_kind": "supervisor-log-regex",
        },
        "signal2_tree": tree,
        "signal2_tree": tree,
        "dispatch_policy": policy,
        "printed_success_by_attempt": printed,
    }


def main() -> int:
    doc = census()
    print(json.dumps(
        {
            "printed_success_by_attempt": doc["printed_success_by_attempt"],
            "signal1": {
                k: v
                for k, v in doc["signal1_supervisor"].items()
                if k != "note"
            },
            "signal2_pairs": {
                "n_pairs": doc["signal2_tree"]["two_strike_pairs"]["n_pairs"],
                "delivered": doc["signal2_tree"]["two_strike_pairs"][
                    "delivered_after_two_strikes"
                ],
            },
            "signal2_retry": {
                k: v
                for k, v in doc["signal2_tree"]["retry_sequences"].items()
                if k != "sequences"
            },
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

census = census
