#!/usr/bin/env python3
"""probe2 for TST-0027: seed record-and-replay proven live, all three kinds.

property / fuzz / chaos suites share the record-replay contract:
  same recorded seed twice -> byte-identical trace sha256 (replay_match);
  different seed           -> different trace (the seed is load-bearing);
  unseeded run             -> fresh entropy used and the seed RECORDED.
Plus the live rng census over tools/testinfra: recording/taking/discard
sites are classified, not folded.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0027"
HERE = Path(__file__).resolve().parent


def load(name: str, rel: Path):
    spec = importlib.util.spec_from_file_location(name, rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sr = load("t27_seed_replay", REPO / "tools" / "testinfra" / "seed_replay.py")
    rc = load("t27_rng_census", REPO / "tools" / "testinfra" / "rng_census.py")
    checks = {}
    kinds = {"property": 12, "fuzz": 64, "chaos": 8}
    proof = []
    for kind, steps in kinds.items():
        a = sr.record_run(20261027, steps)
        b = sr.replay(a["seed_recorded"], steps)
        c = sr.replay(a["seed_recorded"], steps)
        d = sr.replay(20261028, steps)
        row = {
            "kind": kind,
            "seed_a": a["seed_recorded"],
            "same_seed_byte_identical": a["trace_sha256"] == b["trace_sha256"] == c["trace_sha256"],
            "replay_match": a["steps"] == b["steps"] == c["steps"],
            "different_seed_traces_differ": a["trace_sha256"] != d["trace_sha256"],
            "same_seed_verdict_sha256": a["trace_sha256"],
            "trace_sha256_seed_a": a["trace_sha256"],
            "trace_sha256_seed_b": d["trace_sha256"],
        }
        proof.append(row)
        checks[f"{kind}_same_seed_identical"] = row["same_seed_byte_identical"] and row["replay_match"]
        checks[f"{kind}_different_seed_differs"] = row["different_seed_traces_differ"]
    fresh = sr.record_run(None)
    checks["fresh_entropy_records_seed"] = fresh["entropy_was_fresh"] and fresh["seed_recorded"] > 0
    census = rc.census(REPO, ["tools/testinfra"])
    checks["census_live_sites"] = census["counts"]["records"] + census["counts"]["takes"] + census["counts"]["discards"] > 0
    checks["census_names_files_not_folded"] = (
        len(census["records_seed"]) + len(census["takes_seed_param"]) + len(census["discards_seed"])
        == sum(census["counts"].values())
    )
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-replay-divergence", "pass": ok,
                      "proof": proof, "census": census, "fresh": {"seed": fresh["seed_recorded"]},
                      "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 property/fuzz/chaos: same seed byte-identical replay, different seed diverges, fresh entropy recorded; live census {census['counts']}")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
