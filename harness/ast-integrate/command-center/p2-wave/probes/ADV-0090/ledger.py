"""ADV-0090: SHA-join of cited greens plus fixed-SHA empirical re-runs.

Probe 1 reports attempt *distribution*, never a pass rate, for each cited
green joined to an append-only ledger addressed by commit SHA.
Probe 2 re-executes a stratified sample N=10 times at one pinned SHA.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0090"
N_REPEATS = 10
CONTROL_PHRASE = "ADV-0090 deterministic control v1"
CONTROL_SHA256 = hashlib.sha256(CONTROL_PHRASE.encode("utf-8")).hexdigest()
FLAKY_SEQUENCE = (1, 1, 1, 1, 1, 1, 0, 0, 0, 0)  # 6 of 10

SHA_HONEST = hashlib.sha256(b"adv-0090-honest-single-v1").hexdigest()
SHA_MULTI = hashlib.sha256(b"adv-0090-honest-multi-v1").hexdigest()
SHA_LAUNDER = hashlib.sha256(b"adv-0090-laundered-v1").hexdigest()
PINNED_SHA = hashlib.sha256(b"adv-0090-probe2-pack-v1").hexdigest()

LEDGER_KEYS = (
    "attempt_ledger",
    "attempts",
    "run_history",
    "ci_attempts",
    "sha_addressed_ledger",
)
SHA_KEYS = (
    "commit_sha",
    "generating_commit",
    "git_sha",
    "head_sha",
    "pinned_sha",
)


def _attempt(run_id: str, n: int, outcome: str) -> dict[str, Any]:
    return {"n": n, "outcome": outcome, "run_id": run_id}


def fixture_ledgers() -> dict[str, list[dict[str, Any]]]:
    """Append-only SHA-addressed attempt ledgers (full history)."""
    return {
        SHA_HONEST: [_attempt("run-h1", 1, "pass")],
        SHA_MULTI: [
            _attempt("run-m1", 1, "fail"),
            _attempt("run-m2", 2, "fail"),
            _attempt("run-m3", 3, "pass"),
        ],
        SHA_LAUNDER: [
            _attempt("run-l1", 1, "fail"),
            _attempt("run-l2", 2, "fail"),
            _attempt("run-l3", 3, "fail"),
            _attempt("run-l4", 4, "pass"),
        ],
    }


def fixture_cited_greens() -> list[dict[str, Any]]:
    """Evidence records that cite a green. Laundered cites only the last pass."""
    return [
        {
            "id": "G-honest-single",
            "cited_as": "green",
            "commit_sha": SHA_HONEST,
            "cited_run_ids": ["run-h1"],
            "source": "fixture",
        },
        {
            "id": "G-honest-multi",
            "cited_as": "green",
            "commit_sha": SHA_MULTI,
            "cited_run_ids": ["run-m1", "run-m2", "run-m3"],
            "source": "fixture",
        },
        {
            "id": "G-laundered",
            "cited_as": "green",
            "commit_sha": SHA_LAUNDER,
            "cited_run_ids": ["run-l4"],
            "source": "fixture",
        },
        {
            "id": "G-unjoinable-local-1",
            "cited_as": "green",
            "commit_sha": None,
            "cited_run_ids": ["local-pass"],
            "source": "fixture-local",
        },
        {
            "id": "G-unjoinable-local-2",
            "cited_as": "green",
            "commit_sha": None,
            "cited_run_ids": ["local-pass"],
            "source": "fixture-local",
        },
        {
            "id": "G-unjoinable-local-3",
            "cited_as": "green",
            "commit_sha": None,
            "cited_run_ids": ["local-pass"],
            "source": "fixture-local",
        },
    ]


def join_green(
    green: dict[str, Any], ledgers: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    sha = green.get("commit_sha")
    cited = list(green.get("cited_run_ids") or [])
    if not sha:
        return {
            "id": green["id"],
            "joinable": False,
            "reason": "no-commit-sha",
            "attempt_count": None,
            "cited_only_final_success": None,
            "discarded_earlier_failures": [],
        }
    attempts = ledgers.get(sha)
    if not attempts:
        return {
            "id": green["id"],
            "joinable": False,
            "reason": "ledger-absent",
            "commit_sha": sha,
            "attempt_count": None,
            "cited_only_final_success": None,
            "discarded_earlier_failures": [],
        }
    cited_set = set(cited)
    discarded = [
        a
        for a in attempts
        if a["run_id"] not in cited_set and a["outcome"] != "pass"
    ]
    last_pass = next(
        (a for a in reversed(attempts) if a["outcome"] == "pass"), None
    )
    only_final = bool(
        last_pass and cited_set == {last_pass["run_id"]} and discarded
    )
    return {
        "id": green["id"],
        "joinable": True,
        "reason": "joined-by-sha",
        "commit_sha": sha,
        "attempt_count": len(attempts),
        "outcomes": [a["outcome"] for a in attempts],
        "cited_run_ids": cited,
        "cited_only_final_success": only_final,
        "discarded_earlier_failures": discarded,
    }


def naive_pass_rate(green: dict[str, Any], joined: dict[str, Any]) -> dict[str, Any]:
    """Pass-rate view: a cited green is 100% pass. Hides retries and discards."""
    return {
        "id": green["id"],
        "pass_rate": 1.0 if green.get("cited_as") == "green" else 0.0,
        "flags_laundering": False,
        "attempt_count_visible": False,
        "would_miss_laundering": bool(joined.get("cited_only_final_success")),
    }


def attempt_distribution(joined: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(
        row["attempt_count"]
        for row in joined
        if row.get("joinable") and row.get("attempt_count") is not None
    )
    return {
        "n_joinable": sum(1 for r in joined if r.get("joinable")),
        "n_unjoinable": sum(1 for r in joined if not r.get("joinable")),
        "n_multi_attempt": sum(
            1
            for r in joined
            if r.get("joinable") and (r.get("attempt_count") or 0) > 1
        ),
        "n_laundered": sum(
            1 for r in joined if r.get("cited_only_final_success")
        ),
        "histogram": {str(k): int(v) for k, v in sorted(counts.items())},
        "note": "histogram is attempt counts, not pass rate",
    }


def run_unit(name: str, attempt_index: int) -> bool:
    """Execute one trial at PINNED_SHA. attempt_index is 0..N-1."""
    if name == "deterministic-hash":
        digest = hashlib.sha256(CONTROL_PHRASE.encode("utf-8")).hexdigest()
        return digest == CONTROL_SHA256
    if name == "deterministic-arithmetic":
        return (2 + 2) == 4 and attempt_index >= 0
    if name == "planted-flaky-6-of-10":
        return bool(FLAKY_SEQUENCE[attempt_index])
    raise ValueError(name)


def classify_empirical(pass_n: int, n: int, control_pass_n: int) -> str:
    if control_pass_n != n:
        return "ENVIRONMENT_UNSTABLE"
    if pass_n == n:
        return "STABLE"
    return "FLAKY"


def repeat_at_pinned_sha() -> dict[str, Any]:
    names = [
        "deterministic-hash",
        "deterministic-arithmetic",
        "planted-flaky-6-of-10",
    ]
    control_bits = [run_unit("deterministic-hash", i) for i in range(N_REPEATS)]
    control_pass = sum(1 for b in control_bits if b)
    per: dict[str, Any] = {}
    for name in names:
        bits = [run_unit(name, i) for i in range(N_REPEATS)]
        pass_n = sum(1 for b in bits if b)
        per[name] = {
            "n": N_REPEATS,
            "pass_n": pass_n,
            "fail_n": N_REPEATS - pass_n,
            "bits": [int(b) for b in bits],
            "classification": classify_empirical(pass_n, N_REPEATS, control_pass),
            "pinned_sha": PINNED_SHA,
        }
    env_ok = control_pass == N_REPEATS
    flaky = per["planted-flaky-6-of-10"]
    stable = per["deterministic-arithmetic"]
    return {
        "pinned_sha": PINNED_SHA,
        "n": N_REPEATS,
        "environment_stable": env_ok,
        "control_pass_n": control_pass,
        "control_sha256": CONTROL_SHA256,
        "per_unit": per,
        "both_states": {
            "good_10_of_10_not_flaky": env_ok
            and stable["classification"] == "STABLE",
            "bad_6_of_10_classified_flaky": env_ok
            and flaky["classification"] == "FLAKY"
            and flaky["pass_n"] == 6,
        },
    }


def _receipt_has_ledger(doc: dict[str, Any]) -> bool:
    if any(k in doc for k in LEDGER_KEYS):
        return True
    blob = json.dumps(doc, default=str)
    return "attempt_ledger" in blob or "sha_addressed_ledger" in blob


def _receipt_sha(doc: dict[str, Any]) -> str | None:
    for k in SHA_KEYS:
        v = doc.get(k)
        if isinstance(v, str) and len(v) >= 7:
            return v
    produced = doc.get("produced_by")
    if isinstance(produced, dict):
        v = produced.get("commit") or produced.get("git_sha")
        if isinstance(v, str) and len(v) >= 7:
            return v
    return None


def live_receipt_census(limit: int = 400) -> dict[str, Any]:
    root = REPO / "command-center" / "receipts"
    rows: list[dict[str, Any]] = []
    scanned = 0
    if not root.is_dir():
        return {
            "receipt_dir_exists": False,
            "scanned": 0,
            "success_n": 0,
            "joinable_n": 0,
            "unjoinable_n": 0,
            "sample": [],
        }
    for path in sorted(root.glob("*.json")):
        if scanned >= limit:
            break
        try:
            if path.stat().st_size > 2_000_000:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        scanned += 1
        state = str(doc.get("state") or "").upper()
        if state not in {"SUCCESS", "DELIVERED"}:
            continue
        sha = _receipt_sha(doc)
        has_ledger = _receipt_has_ledger(doc)
        joinable = bool(sha) and has_ledger
        rows.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "unit_id": doc.get("unit_id") or doc.get("id") or path.stem,
                "commit_sha": sha,
                "has_ledger": has_ledger,
                "joinable": joinable,
            }
        )
    return {
        "receipt_dir_exists": True,
        "scanned": scanned,
        "success_n": len(rows),
        "joinable_n": sum(1 for r in rows if r["joinable"]),
        "unjoinable_n": sum(1 for r in rows if not r["joinable"]),
        "sample": rows[:12],
    }


def probe1_report() -> dict[str, Any]:
    ledgers = fixture_ledgers()
    greens = fixture_cited_greens()
    joined = [join_green(g, ledgers) for g in greens]
    naive = [naive_pass_rate(g, j) for g, j in zip(greens, joined)]
    dist = attempt_distribution(joined)
    live = live_receipt_census()
    laundered = next(j for j in joined if j["id"] == "G-laundered")
    honest = next(j for j in joined if j["id"] == "G-honest-single")
    naive_launder = next(n for n in naive if n["id"] == "G-laundered")
    both = {
        "join_fires_on_laundered": bool(laundered["cited_only_final_success"]),
        "join_silent_on_honest_single": honest["cited_only_final_success"]
        is False,
        "naive_pass_rate_misses_laundering": naive_launder[
            "would_miss_laundering"
        ]
        and not naive_launder["flags_laundering"],
    }
    ok = (
        dist["n_unjoinable"] == 3
        and dist["n_multi_attempt"] >= 2
        and dist["n_laundered"] == 1
        and both["join_fires_on_laundered"]
        and both["join_silent_on_honest_single"]
        and both["naive_pass_rate_misses_laundering"]
    )
    return {
        "probe": "probe1-attempt-history-sha-join",
        "unit_id": UNIT,
        "joined": joined,
        "distribution": dist,
        "naive_pass_rate": naive,
        "live_receipts": {
            "scanned": live["scanned"],
            "success_n": live["success_n"],
            "joinable_n": live["joinable_n"],
            "unjoinable_n": live["unjoinable_n"],
            "sample": live["sample"],
        },
        "both_states": both,
        "pass": ok,
    }


def probe2_report() -> dict[str, Any]:
    empirical = repeat_at_pinned_sha()
    both = empirical["both_states"]
    ok = (
        empirical["environment_stable"]
        and both["good_10_of_10_not_flaky"]
        and both["bad_6_of_10_classified_flaky"]
        and empirical["per_unit"]["deterministic-hash"]["pass_n"] == N_REPEATS
    )
    return {
        "probe": "probe2-fixed-sha-repeats",
        "unit_id": UNIT,
        "empirical": empirical,
        "pass": ok,
    }
