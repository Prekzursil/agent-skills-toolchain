"""Flake quarantine ledger: classify tests from N independent repetitions (TST-0032)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Iterable

MIN_N = 20
FLAKY = "FLAKY"
DETERMINISTIC = "DETERMINISTIC"
BROKEN = "BROKEN"


class InsufficientRepetitionsError(Exception):
    pass


class RetryWithoutHypothesisError(Exception):
    pass


def _sha_files(paths: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
        h.update(Path(path).as_posix().encode("utf-8"))
        h.update(raw)
    return h.hexdigest()


def worktree_fingerprint(paths: list[Path] | None = None, extra: str = "") -> dict[str, Any]:
    files = list(paths or [])
    digest = _sha_files(files) if files else hashlib.sha256(extra.encode("utf-8")).hexdigest()
    if extra:
        digest = hashlib.sha256((digest + extra).encode("utf-8")).hexdigest()
    return {"sha": digest, "method": "sha256-of-named-files", "n_files": len(files)}


def ordered_suite(items: list[tuple[str, Callable[[], Any]]]) -> list[tuple[str, Callable[[], Any]]]:
    return list(items)


def _classify(passes: int, n: int) -> tuple[str, bool]:
    if n <= 0:
        return DETERMINISTIC, False
    if passes == n:
        return DETERMINISTIC, False
    if passes == 0:
        return BROKEN, False
    return FLAKY, True


def independent_ratios(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        outcomes = list(row.get("outcomes") or [])
        n = len(outcomes)
        passes = sum(1 for x in outcomes if x)
        cls, quarantined = _classify(passes, n)
        out[str(row["id"])] = {
            "class": cls,
            "quarantined": quarantined,
            "pass_ratio": (passes / n) if n else 0.0,
            "passes": passes,
            "n": n,
        }
    return out


def measure(
    suite: list[tuple[str, Callable[[], Any]]],
    n: int = MIN_N,
    fingerprint: dict[str, Any] | None = None,
    order: Iterable[str] | None = None,
    prior: dict[str, Any] | None = None,
    hypothesis: str | None = None,
) -> dict[str, Any]:
    if n < MIN_N:
        raise InsufficientRepetitionsError(f"n={n} < {MIN_N}")
    names = [item[0] for item in suite]
    if order is not None and list(order) != names:
        # keep declared order
        by = {k: v for k, v in suite}
        suite = [(k, by[k]) for k in order]
        names = list(order)
    fp = dict(fingerprint or {})
    sha = str(fp.get("sha") or "")
    if prior is not None:
        same = (
            prior.get("sha") == sha
            and list(prior.get("order") or []) == names
            and int(prior.get("n") or 0) == n
        )
        if same and not hypothesis:
            raise RetryWithoutHypothesisError("same (sha, order, n) without new hypothesis")
    rows = []
    quarantined: list[str] = []
    quarantined_named: list[str] = []
    for name, fn in suite:
        outcomes: list[bool] = []
        for _ in range(n):
            try:
                fn()
                outcomes.append(True)
            except Exception:
                outcomes.append(False)
        passes = sum(1 for x in outcomes if x)
        cls, is_q = _classify(passes, n)
        row = {
            "id": name,
            "n": n,
            "passes": passes,
            "pass_ratio": passes / n,
            "class": cls,
            "quarantined": is_q,
            "outcomes": outcomes,
        }
        rows.append(row)
        if is_q:
            quarantined.append(name)
            quarantined_named.append(name)
    return {
        "n": n,
        "order": names,
        "same_order": True,
        "rows": rows,
        "quarantined": quarantined,
        "quarantined_named": quarantined_named,
        "hidden_quarantine": False,
        "fingerprint": fp if fp else worktree_fingerprint([]),
        "sha": sha,
        "hypothesis": hypothesis,
    }


def suite_green_claim(
    *,
    claimed_green: bool,
    tests_in_path: list[str],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    qset = set(ledger.get("quarantined") or [])
    broken = {
        str(r.get("id"))
        for r in (ledger.get("rows") or [])
        if r.get("class") == BROKEN
    }
    q_in = [t for t in tests_in_path if t in qset and t not in broken]
    b_in = [t for t in tests_in_path if t in broken]
    blocked_by: list[str] = []
    if q_in:
        blocked_by.append("quarantined-in-path")
    if b_in:
        blocked_by.append("broken-in-path")
    blocked = bool(claimed_green and blocked_by)
    still = True
    if qset:
        still = all(any(r.get("id") == name for r in ledger.get("rows") or []) for name in qset)
    return {
        "blocked": blocked,
        "allowed": (not blocked) and bool(claimed_green),
        "quarantined_in_path": q_in,
        "blocked_by": blocked_by,
        "quarantine_still_in_report": still,
    }
