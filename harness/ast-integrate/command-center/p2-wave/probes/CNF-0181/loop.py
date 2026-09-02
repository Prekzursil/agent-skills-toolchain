"""Retention loop for CNF-0181: KEEP only on measured gain + benchmark write-back.

A KEEP without a new case id is refused even if scores moved. A comment-only
candidate is REVERT. After REVERT the tree is byte-identical to the pre-change
snapshot on the candidate's own files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import (
    BASELINE_SRC,
    CASE_ID,
    IMPROVED_SRC,
    IMPROVEMENT_ID,
    MEASURE_CASES,
    NEUTRAL_SRC,
    NEW_CASE,
    ORIGINAL_CASES,
    PUBLIC_AFTER,
)


def lf_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def load_join(src: str):
    ns: dict[str, Any] = {}
    exec(src, ns)  # noqa: S102 — fixture source, not attacker input
    return ns["join_url"]


def score(src: str, cases: list[dict]) -> dict[str, Any]:
    fn = load_join(src)
    rows = []
    ok = 0
    for case in cases:
        got = fn(case["base"], case["path"])
        passed = got == case["want"]
        ok += int(passed)
        rows.append(
            {
                "id": case["id"],
                "got": got,
                "want": case["want"],
                "pass": passed,
            }
        )
    return {
        "n": len(cases),
        "ok": ok,
        "fail": len(cases) - ok,
        "rows": rows,
    }


def new_case_protects(before_src: str, after_src: str, case: dict) -> bool:
    """True iff the case fails on before and passes on after."""
    pre = score(before_src, [case])
    post = score(after_src, [case])
    return (not pre["rows"][0]["pass"]) and post["rows"][0]["pass"]


def decide(
    before_src: str,
    after_src: str,
    *,
    public_before: list[dict],
    public_after: list[dict],
    measure_cases: list[dict],
) -> dict[str, Any]:
    """KEEP only when measure-pack gain AND the new case is in public_after."""
    pre = score(before_src, measure_cases)
    post = score(after_src, measure_cases)
    gain = post["ok"] > pre["ok"]
    protects = new_case_protects(before_src, after_src, NEW_CASE)
    added_ids = {c["id"] for c in public_after} - {c["id"] for c in public_before}
    wrote_case = CASE_ID in added_ids
    keep = bool(gain and protects and wrote_case)
    return {
        "decision": "KEEP" if keep else "REVERT",
        "gain": gain,
        "protects": protects,
        "wrote_case": wrote_case,
        "added_case_ids": sorted(added_ids),
        "before": {"ok": pre["ok"], "n": pre["n"], "rows": pre["rows"]},
        "after": {"ok": post["ok"], "n": post["n"], "rows": post["rows"]},
        "refuse_reason": None
        if keep
        else (
            "no-gain"
            if not gain
            else ("new-case-does-not-protect" if not protects else "benchmark-not-updated")
        ),
    }


def tree_bytes(join_src: str, public_cases: list[dict]) -> dict[str, bytes]:
    return {
        "join.py": join_src.encode("utf-8"),
        "benchmark/public.json": (
            json.dumps(public_cases, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }


def write_tree(root: Path, files: dict[str, bytes]) -> dict[str, str]:
    hashes = {}
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[rel] = lf_sha(data)
    return hashes


def revert_equal(pre: dict[str, bytes], post: dict[str, bytes]) -> bool:
    if set(pre) != set(post):
        return False
    return all(
        pre[k].replace(b"\r\n", b"\n") == post[k].replace(b"\r\n", b"\n") for k in pre
    )


def census_production(repo: Path) -> dict[str, Any]:
    """Honest scan: production retain.py / ledgers are inputs, not assumed present."""
    candidates = [
        "tools/selfimprove/retain.py",
        "tools/selfimprove/writeback.py",
        "tools/selfimprove/measure.py",
        "command-center/receipts/IMP-0373.json",
        "command-center/receipts/IMP-0374.json",
        "command-center/receipts/IMP-0255.json",
    ]
    found = []
    missing = []
    for rel in candidates:
        p = repo / rel
        (found if p.is_file() and p.stat().st_size > 0 else missing).append(rel)
    ledgers = []
    skip = "p2-wave/probes/CNF-0181"
    for pattern in (
        "**/retention-ledger.jsonl",
        "**/selfimprove/**/*.jsonl",
        "**/retain-ledger.json",
    ):
        for hit in repo.glob(pattern):
            if hit.is_file() and skip not in hit.as_posix():
                ledgers.append(hit.relative_to(repo).as_posix())
    return {
        "production_modules_present": found,
        "production_modules_absent": missing,
        "foreign_ledgers": sorted(set(ledgers)),
        "production_retained_improvements": 0 if not found and not ledgers else None,
    }


def run_retention_demo(root: Path) -> dict[str, Any]:
    """Exercise KEEP (gain+writeback) and REVERT (neutral) in an isolated tree."""
    pre_files = tree_bytes(BASELINE_SRC, ORIGINAL_CASES)
    keep_files = tree_bytes(IMPROVED_SRC, PUBLIC_AFTER)
    pre_dir = root / "pre"
    keep_dir = root / "keep"
    reverted_dir = root / "reverted-neutral"
    pre_h = write_tree(pre_dir, pre_files)
    keep_h = write_tree(keep_dir, keep_files)

    keep_verdict = decide(
        BASELINE_SRC,
        IMPROVED_SRC,
        public_before=ORIGINAL_CASES,
        public_after=PUBLIC_AFTER,
        measure_cases=MEASURE_CASES,
    )
    neutral_verdict = decide(
        IMPROVED_SRC,
        NEUTRAL_SRC,
        public_before=PUBLIC_AFTER,
        public_after=PUBLIC_AFTER,
        measure_cases=MEASURE_CASES,
    )
    no_wb = decide(
        BASELINE_SRC,
        IMPROVED_SRC,
        public_before=ORIGINAL_CASES,
        public_after=ORIGINAL_CASES,
        measure_cases=MEASURE_CASES,
    )

    if neutral_verdict["decision"] == "REVERT":
        write_tree(reverted_dir, keep_files)
        post_revert = {rel: (reverted_dir / rel).read_bytes() for rel in keep_files}
        revert_ok = revert_equal(keep_files, post_revert)
    else:
        revert_ok = False

    ledger = [
        {
            "id": IMPROVEMENT_ID,
            "decision": keep_verdict["decision"],
            "case_id": CASE_ID,
            "before_ok": keep_verdict["before"]["ok"],
            "after_ok": keep_verdict["after"]["ok"],
        },
        {
            "id": IMPROVEMENT_ID + "-neutral",
            "decision": neutral_verdict["decision"],
            "refuse_reason": neutral_verdict["refuse_reason"],
        },
        {
            "id": IMPROVEMENT_ID + "-no-writeback",
            "decision": no_wb["decision"],
            "refuse_reason": no_wb["refuse_reason"],
        },
    ]
    (root / "ledger.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in ledger),
        encoding="utf-8",
    )
    return {
        "keep": keep_verdict,
        "neutral": neutral_verdict,
        "no_writeback": no_wb,
        "revert_byte_identical": revert_ok,
        "pre_hashes": pre_h,
        "keep_hashes": keep_h,
        "ledger": ledger,
        "improvement_id": IMPROVEMENT_ID,
        "case_id": CASE_ID,
    }
