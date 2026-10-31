#!/usr/bin/env python3
"""TST-0094 probe1: three empty-looking runs, three TYPED outcomes.

Live: genuinely-nothing-to-harvest, filter-mismatch, connection-failure
each produce a DIFFERENT typed outcome (never a shared empty), the
nonempty control harvests, and the collapsing mutant turns all three
into the same EMPTY - proving the detector distinguishes what the
mutant conflates. Asserts the receipt's three-run table re-derives."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0094"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from harvest import CollapsingMutantHarvest, RemoteHarvest, RemoteSubstrate  # noqa: E402

UNIT = "TST-0094"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 2048, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0094" in text, "sentinel-absent")

    art = [{"id": "art-old", "session_id": "job-ok"}]
    runs = {
        "genuinely_nothing": RemoteHarvest(RemoteSubstrate("job-ok", art), local_store={"art-old"}).harvest("job-ok"),
        "filter_mismatch": RemoteHarvest(RemoteSubstrate("job-x", art, filter_matches=False)).harvest("job-ok"),
        "connection_failure": RemoteHarvest(RemoteSubstrate("job-ok", art, connected=False)).harvest("job-ok"),
    }
    outcomes = {k: v["outcome"] for k, v in runs.items()}
    chk(outcomes["genuinely_nothing"] == "NOTHING_TO_HARVEST", "run-1-typed", outcomes["genuinely_nothing"])
    chk(outcomes["filter_mismatch"] == "FILTER_MISMATCH", "run-2-typed", outcomes["filter_mismatch"])
    chk(outcomes["connection_failure"] == "CONNECTION_FAILURE", "run-3-typed", outcomes["connection_failure"])
    rcs = {v["exit_code"] for v in runs.values()}
    chk(len(rcs) == 3, "distinct-exit-codes", str(sorted(rcs)))
    chk(all(v["empty_result"] is False for v in runs.values()), "no-shared-empty-flag")
    nonempty = RemoteHarvest(RemoteSubstrate("job-ok", art + [{"id": "art-new", "session_id": "job-ok"}]), local_store={"art-old"}).harvest("job-ok")
    chk(nonempty["outcome"] == "HARVESTED" and nonempty["new_artifact_delta"] == 1 and nonempty["exit_code"] == 0, "nonempty-control-harvests")
    mutant = CollapsingMutantHarvest()
    mutant_runs = {k: mutant.harvest("job-ok") for k in runs}
    mutant_outcomes = {v["outcome"] for v in mutant_runs.values()}
    chk(mutant_outcomes == {"EMPTY"}, "mutant-collapses-to-shared-empty", str(mutant_outcomes))
    ev = doc.get("evidence") or {}
    chk(ev.get("mutant_collapsed") is True, "receipt-mutant-collapsed-flag")
    nonrec = ev.get("nonempty_control") or {}
    chk(str((nonrec.get("first") or {}).get("outcome")) == "HARVESTED", "receipt-nonempty-first")
    impl = doc.get("implementation") or {}
    chk(sorted(impl.get("typed_outcomes") or []) == sorted(["CONNECTION_FAILURE", "FILTER_MISMATCH", "HARVESTED", "NOTHING_TO_HARVEST"]), "receipt-typed-outcomes")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({"runs": {k: {"outcome": v["outcome"], "rc": v["exit_code"]} for k, v in runs.items()},
                      "nonempty_control": nonempty["outcome"] + " rc=" + str(nonempty["exit_code"]),
                      "mutant_outcomes": sorted(mutant_outcomes)}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 live three runs yield three distinct typed outcomes with distinct exit codes (1/2/3), nonempty control HARVESTED rc 0, collapsing mutant reduces all three to the shared EMPTY - the conflation the unit forbids is detectable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
