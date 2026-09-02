#!/usr/bin/env python3
"""Probe 2: trace each cycle to an EXTERNAL evidence root.

Mechanically different from probe 1: rebuilds the graph from live JSON and
planted fixtures, classifies Tarjan SCCs by source-lineage URLs, and does not
read probe 1's cycle list or this unit's report.

Catalog verbatim: for each cycle, trace to the EXTERNAL evidence root; a cycle
whose members all trace to one genuine external source is redundancy, while a
cycle with no external root is unsupported and must be reclassified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from graph import REPO, probe2_payload  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0081-circular-citation-cycle-detection.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0081 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0081 <reason>."
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0081-probe2 {msg}")
    return 1


def main() -> int:
    result = probe2_payload()
    print(json.dumps(result, sort_keys=True, default=str))
    ctrl = result["controls"]
    lost = result["claims_losing_support"]
    print(
        "unsupported={u} redundancy={r} mixed={m} lost_live={ll} lost_planted={lp} "
        "gate_fire={g} silent_chain={c} silent_red={s} f1f2={f}".format(
            u=result["n_unsupported"],
            r=result["n_redundancy"],
            m=result["n_mixed"],
            ll=lost["live_n"],
            lp=lost["planted_n"],
            g=ctrl["gate_fires_on_unsupported"],
            c=ctrl["gate_silent_on_chain"],
            s=ctrl["gate_silent_on_redundancy"],
            f=ctrl["live_f1_f2_redundancy"],
        )
    )
    if not ctrl["planted_unsupported_reclassified"]:
        return fail("planted no-root cycle was not reclassified UNSUPPORTED")
    if not ctrl["planted_redundancy_classified"]:
        return fail("planted shared-origin cycle was not classified REDUNDANCY")
    if not ctrl["gate_silent_on_chain"]:
        return fail("unsupported-cycle gate fired on the planted acyclic chain")
    if not ctrl["gate_silent_on_redundancy"]:
        return fail("unsupported-cycle gate fired on shared-origin redundancy")
    if lost["planted_n"] < 1 or "C-PLANT-UNSUPPORTED" not in lost["planted"]:
        return fail(f"planted unsupported claim did not lose support: {lost}")
    if lost["live_n"] != 0:
        return fail(f"live claims lost support unexpectedly: {lost['live']}")
    if not result["pass"]:
        return fail("probe2 controls failed")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable {exc}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if CATALOG_SENTINEL not in text:
            return fail("catalog sentinel-absent")
        targets = {
            t.get("target_id"): t
            for t in (doc.get("targets") or [])
            if isinstance(t, dict)
        }
        lose = targets.get("CLAIMS-LOSE-SUPPORT") or {}
        if lose.get("live_n") != lost["live_n"]:
            return fail(
                f"artifact CLAIMS-LOSE-SUPPORT live_n {lose.get('live_n')} != {lost['live_n']}"
            )
        named = doc.get("named_probes") or []
        if len(named) < 2:
            return fail("artifact named_probes < 2")
        verbatim = " ".join(str(p.get("catalog_verbatim") or p.get("requirement") or "") for p in named)
        if "EXTERNAL evidence root" not in verbatim and "EXTERNAL evidence root" not in text:
            return fail("probe 2 catalog verbatim missing from artifact")

    print(
        "SUCCESS:ADV-0081-probe2 SCC external-root trace; unsupported vs "
        "redundancy vs mixed; planted chain silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
