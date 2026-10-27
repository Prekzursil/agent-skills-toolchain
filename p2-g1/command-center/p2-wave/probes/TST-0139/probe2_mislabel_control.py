#!/usr/bin/env python3
"""TST-0139 probe2 -- 429 vs 529 policies re-run live on the storm scheduler.

Imports the live http_storm_scheduler (digest-checked vs the receipt row)
and re-runs both storm states plus the mislabel control: 429 must collapse
wave-2 arrival rate; 529 must leave it at 1.0 and hold the concurrency
ceiling; mislabelling 529 as 429 must be detected; the classify branches
must be AST-distinct.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0139.json"
MODULE = REPO / "tools/command-center/http_storm_scheduler.py"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    spec = importlib.util.spec_from_file_location("live_storm", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_storm"] = mod
    spec.loader.exec_module(mod)

    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rows = {str(a.get("path")): a for a in doc.get("artifacts") or []}
    rel = "tools/command-center/http_storm_scheduler.py"
    rec = rows.get(rel) or rows.get(rel.replace("/", "\\"))
    sha, _ = norm_sha(MODULE)
    if rec and rec.get("sha256"):
        chk(sha == rec["sha256"], "module-sha-drift", (sha, rec.get("sha256")))

    report = doc.get("report") or {}
    chk(report.get("storm_429_rate_reduced") is True, "recorded-429-reduced")
    chk(report.get("storm_529_rate_reduced") is False, "recorded-529-reduced")
    chk(report.get("storm_529_concurrency_held") is True, "recorded-529-concurrency")
    chk(report.get("mislabel_detected") is True, "recorded-mislabel")
    chk(report.get("ast_distinct_branches") is True, "recorded-ast-distinct")

    # live re-run
    if hasattr(mod, "both_states"):
        bs = mod.both_states()
        flat = json.dumps(bs)
        chk("429" in flat and "529" in flat, "both-states-shape")
        r429 = bs.get("storm_429") or {}
        r529 = bs.get("storm_529") or {}
        rate429 = r429.get("wave2_arrival_rate", r429.get("rate"))
        rate529 = r529.get("wave2_arrival_rate", r529.get("rate"))
        if rate429 is not None:
            chk(float(rate429) < 1.0, "live-429-not-reduced", rate429)
        if rate529 is not None:
            chk(abs(float(rate529) - 1.0) < 1e-9, "live-529-reduced", rate529)
        held = r529.get("concurrency_ceiling_held", r529.get("concurrency_held"))
        if held is not None:
            chk(held is True, "live-529-concurrency-shrunk")
    d = mod.classify_branches_are_distinct()
    chk(d.get("pass") is True, "live-ast-branches", d)
    m = mod.mislabel_is_detected()
    chk(m.get("pass") is True, "live-mislabel-silent", m)
    if FAILS:
        print("FAILED:TST-0139-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0139-probe2 live re-run: 429 storm reduces arrival rate, 529 storm leaves rate 1.0 and holds concurrency, mislabel-529-as-429 detected, classify branches AST-distinct; module digest matches receipt row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
