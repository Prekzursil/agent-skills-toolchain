#!/usr/bin/env python3
"""Probe 1: leak fixture DENIED; exclusive tokens do not cross partitions.

Re-runs the harness. Does not rewrite the catalog artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402
import partition as P  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0008.candidate-syntheses.json"
UNIT = "SYN-0008"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def tokens_in(candidate: dict) -> set[str]:
    syn = candidate.get("synthesis") or {}
    observed = {str(t) for t in (syn.get("tokens_observed") or [])}
    for finding in syn.get("findings") or []:
        tok = finding.get("token")
        if tok:
            observed.add(str(tok))
    return observed


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')!r}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:SYN-0008" not in text:
        return fail("sentinel absent")
    errs = S.errors(doc)
    if errs:
        return fail(f"artifact schema {errs[0]}")

    rep = S.payload(doc)
    if rep.get("kind") != "synthesis-candidate":
        return fail(f"report.kind {rep.get('kind')!r}")
    art_leak = rep.get("leak_fixture") or {}
    if art_leak.get("status") != "DENIED":
        return fail(f"artifact leak status {art_leak.get('status')!r}")
    if art_leak.get("logged") is not True:
        return fail("artifact leak denial not logged")

    panel = H.run_panel()
    live = panel["leak_fixture"]
    print(
        json.dumps(
            {
                "probe": "probe1-leak-fixture",
                "unit_id": UNIT,
                "live_status": live.get("status"),
                "worker_status": (live.get("worker_denial") or {}).get("status"),
                "dispatcher_status": (live.get("dispatcher_denial") or {}).get(
                    "status"
                ),
                "target_existed_during_request": live.get(
                    "target_existed_during_request"
                ),
                "severed_counts": panel["severed_control"].get("counts_as_result"),
                "inline_class": panel["inline_control"].get("classification"),
            },
            sort_keys=True,
        )
    )

    if live.get("status") != "DENIED":
        return fail(f"live leak status {live.get('status')!r}")
    worker = live.get("worker_denial") or {}
    if worker.get("status") != "DENIED":
        return fail(f"worker leak {worker}")
    disp = live.get("dispatcher_denial") or {}
    if disp.get("status") != "DENIED":
        return fail(f"dispatcher leak {disp}")
    if live.get("target_existed_during_request"):
        return fail("sibling candidate file existed during leak request")

    if panel["severed_control"].get("counts_as_result"):
        return fail("severed job-receipt counted as a result")
    if panel["severed_control"].get("classification") != "severed-stream":
        return fail(f"severed class {panel['severed_control']}")
    if panel["inline_control"].get("classification") != "win-arg-limit":
        return fail(f"inline {panel['inline_control']}")
    if panel["inline_control"].get("counts_as_result"):
        return fail("inline counted as a result")

    by_id = {c["id"]: c for c in panel["admitted"]}
    for agent in P.AGENTS:
        agent_id = agent["id"]
        cand = by_id.get(agent_id)
        if not cand:
            return fail(f"missing admitted candidate {agent_id}")
        observed = tokens_in(cand)
        missing = P.tokens_expected(agent_id) - observed
        leaked = observed & P.tokens_forbidden(agent_id)
        if missing:
            return fail(f"{agent_id} missing expected tokens {sorted(missing)}")
        if leaked:
            return fail(f"{agent_id} observed forbidden tokens {sorted(leaked)}")

    art_by_id = {c["id"]: c for c in (rep.get("candidates") or [])}
    for agent in P.AGENTS:
        leaked = tokens_in(art_by_id[agent["id"]]) & P.tokens_forbidden(agent["id"])
        if leaked:
            return fail(f"artifact {agent['id']} leaked {sorted(leaked)}")

    print(
        "live=DENIED worker=DENIED dispatcher=DENIED "
        "exclusive-tokens-isolated=True severed-not-counted=True"
    )
    print("SUCCESS:SYN-0008-probe1 leak fixture DENIED and partition tokens isolated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
