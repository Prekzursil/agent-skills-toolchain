#!/usr/bin/env python3
"""Independent recount of envelope-rest G-1 results. Evidence only."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

SH = Path(__file__).resolve().parent


def load_ids(name: str) -> list[str]:
    p = SH / name
    if not p.is_file():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def jsonl_last(name: str) -> dict[str, dict]:
    p = SH / name
    rows: dict[str, dict] = {}
    n = 0
    if not p.is_file():
        return rows
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        uid = rec.get("id")
        if uid:
            rows[uid] = rec
            n += 1
    rows["_n_lines"] = {"n": n}  # type: ignore
    return rows


def main() -> None:
    assigned: list[str] = []
    seen: set[str] = set()
    by_file = {}
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        ids = load_ids(name)
        by_file[name] = len(ids)
        for uid in ids:
            if uid not in seen:
                seen.add(uid)
                assigned.append(uid)

    rem = load_ids("class-other.remaining.txt")
    rem_text = (SH / "class-other.remaining.txt").read_text(encoding="utf-8") if (SH / "class-other.remaining.txt").is_file() else ""
    rem_fp = hashlib.sha256(rem_text.encode("utf-8")).hexdigest()

    result = json.loads((SH / "class-other.txt.result.json").read_text(encoding="utf-8"))
    p1 = json.loads((SH / "class-envelope.measure.json").read_text(encoding="utf-8"))
    p2 = json.loads((SH / "class-envelope.pass2.json").read_text(encoding="utf-8"))

    p1_rows = jsonl_last("class-envelope.measure.jsonl")
    p1_n = p1_rows.pop("_n_lines", {}).get("n", 0)
    p2_rows = jsonl_last("class-envelope.pass2.jsonl")
    p2_n = p2_rows.pop("_n_lines", {}).get("n", 0)

    p1_fail = set(p1.get("fail_ids") or [])
    p2_ok = [uid for uid, rec in p2_rows.items() if rec.get("ok") and rec.get("line", "").startswith("SUCCESS:delivered")]
    p2_fail = [uid for uid, rec in p2_rows.items() if not rec.get("ok")]
    p2_ok_line = [
        uid
        for uid, rec in p2_rows.items()
        if rec.get("line") == f"SUCCESS:delivered {uid}"
    ]

    # Pass1 jsonl last-wins SUCCESS among assigned
    p1_ok_assigned = []
    p1_fail_assigned = []
    p1_missing = []
    for uid in assigned:
        rec = p1_rows.get(uid)
        if rec is None:
            p1_missing.append(uid)
            continue
        if rec.get("ok") and rec.get("line") == f"SUCCESS:delivered {uid}":
            p1_ok_assigned.append(uid)
        else:
            p1_fail_assigned.append(uid)

    # Merge: pass2 last-wins over pass1
    merged_ok = []
    merged_fail = []
    merged_unmeasured = []
    src = Counter()
    for uid in assigned:
        r2 = p2_rows.get(uid)
        r1 = p1_rows.get(uid)
        rec = r2 if r2 is not None else r1
        if rec is None:
            # inferred from fail_ids absence
            if uid in p1_fail:
                merged_fail.append(uid)
                src["inferred-fail-no-jsonl"] += 1
            else:
                merged_ok.append(uid)
                src["inferred-ok-absent-fail_ids"] += 1
            merged_unmeasured.append(uid)
            continue
        line_ok = rec.get("line") == f"SUCCESS:delivered {uid}" and rec.get("ok") is True
        if line_ok:
            merged_ok.append(uid)
            src["jsonl-SUCCESS"] += 1 if r2 is None else 0
            src["pass2-SUCCESS"] += 1 if r2 is not None else 0
        else:
            merged_fail.append(uid)
            src["jsonl-FAIL"] += 1 if r2 is None else 0
            src["pass2-FAIL"] += 1 if r2 is not None else 0

    out = {
        "assigned_n": len(assigned),
        "by_file": by_file,
        "p1_summary": {"n": p1.get("n"), "ok": p1.get("ok"), "fail": p1.get("fail"), "fail_ids_n": len(p1_fail), "ts": p1.get("ts"), "classes": p1.get("classes")},
        "p1_jsonl_lines": p1_n,
        "p1_jsonl_assigned_ok_line": len(p1_ok_assigned),
        "p1_jsonl_assigned_fail": len(p1_fail_assigned),
        "p1_jsonl_assigned_missing": len(p1_missing),
        "p2_summary": {"n": p2.get("n"), "ok": p2.get("ok"), "fail": p2.get("fail"), "ts": p2.get("ts"), "classes": p2.get("classes")},
        "p2_jsonl_lines": p2_n,
        "p2_ok_ids": p2_ok_line,
        "p2_ok_n": len(p2_ok_line),
        "p2_fail_n": len(p2_fail),
        "result_file_ok": result.get("ok"),
        "result_file_fail": result.get("fail"),
        "result_ok_ids_n": len(result.get("ok_ids") or []),
        "result_fail_ids_n": len(result.get("fail_ids") or []),
        "remaining_file_n": len(rem),
        "remaining_fp_live": rem_fp,
        "remaining_fp_result": result.get("remaining_fp"),
        "fp_match": rem_fp == result.get("remaining_fp"),
        "merged_ok": len(merged_ok),
        "merged_fail": len(merged_fail),
        "merged_unmeasured": len(merged_unmeasured),
        "src": dict(src),
        "inferred_ok_ids": [u for u in merged_ok if u not in p1_ok_assigned and u not in p2_ok_line],
    }
    dest = SH / "_handoff_verify.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "inferred_ok_ids"}, indent=2))
    print("inferred_ok_ids", out["inferred_ok_ids"])
    print("p2_ok_ids", p2_ok_line)


if __name__ == "__main__":
    main()
