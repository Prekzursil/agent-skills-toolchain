#!/usr/bin/env python3
"""Probe 2: independent protocol crosscheck + both-states ACH/ICD controls.

Re-derives mapping from tools/council/protocol/catalog.py. Defaults to REFUTED
when quotes are missing or the table does not discriminate.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    DIRECT,
    NOT_PROTO,
    evaluate_table,
    mutant_drop_ach_critique,
    mutant_everything_transfers,
    mutant_icd_as_protocol,
    techniques,
)
from lib import SENTINEL, live_protocols, obligation_ids  # noqa: E402
from lib import ARTIFACT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0158-probe2 {msg}")
    return 1


def main() -> int:
    proto = live_protocols()
    live = techniques(proto)
    good = evaluate_table(live)
    print(
        f"both_states good={good['ok']} ach_critique={good['ach_critique_present']} "
        f"icd_not={good['icd203_not_protocol']}"
    )
    if not good["ok"]:
        return fail(f"good-state-red {good}")

    bad_ach = evaluate_table(mutant_drop_ach_critique(copy.deepcopy(live)))
    print(f"ach_critique_mutant ok={bad_ach['ok']} ach={bad_ach['ach_critique_present']}")
    if bad_ach["ok"] or bad_ach["ach_critique_present"]:
        return fail("ach-critique-mutant-silent")

    bad_icd = evaluate_table(mutant_icd_as_protocol(copy.deepcopy(live)))
    print(f"icd_as_protocol_mutant ok={bad_icd['ok']} icd_not={bad_icd['icd203_not_protocol']}")
    if bad_icd["ok"] or bad_icd["icd203_not_protocol"]:
        return fail("icd-mutant-silent")

    bad_all = evaluate_table(mutant_everything_transfers(copy.deepcopy(live)))
    print(
        f"everything_transfers ok={bad_all['ok']} "
        f"all_marked={bad_all['all_techniques_marked_protocol']}"
    )
    if bad_all["ok"] or not bad_all["all_techniques_marked_protocol"]:
        return fail("everything-transfers-silent")

    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    text = ARTIFACT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    art = doc.get("techniques") or []
    live_by = {r["id"]: r for r in live}
    for rec in art:
        lid = rec.get("id")
        expect = live_by.get(lid)
        if expect is None:
            return fail(f"unknown-technique {lid}")
        if rec.get("transfer_verdict") != expect["transfer_verdict"]:
            return fail(f"verdict-drift {lid}")
        if rec.get("protocol_id") != expect["protocol_id"]:
            return fail(f"pid-drift {lid}")
        if expect["transfer_verdict"] == DIRECT:
            rec_proto = proto.get(str(expect["protocol_id"]) or "")
            if rec_proto is None:
                return fail(f"catalog-missing {expect['protocol_id']}")
            if rec_proto["kernel_status"] != "expressible":
                return fail(f"not-expressible {expect['protocol_id']}")
            if not obligation_ids(rec_proto):
                return fail(f"no-obligations {expect['protocol_id']}")
        if expect["transfer_verdict"] == NOT_PROTO:
            if rec.get("protocol_id") is not None:
                return fail("icd-minted-pid")

    # Independent catalog facts the artifact must not contradict.
    for pid, slug in (
        ("P01", "free-form-moderated-panel"),
        ("P10", "mandated-devils-advocate"),
        ("P11", "team-b-competitive-estimate"),
        ("P38", "analysis-of-competing-hypotheses"),
        ("P39", "key-assumptions-check"),
        ("P43", "premortem"),
    ):
        if proto[pid]["slug"] != slug:
            return fail(f"catalog-slug-drift {pid}")
        if proto[pid]["kernel_status"] != "expressible":
            return fail(f"catalog-not-expressible {pid}")

    rev = doc.get("reviewer") or {}
    if not rev.get("independent"):
        return fail("reviewer-not-independent")
    if str(rev.get("defaults_to") or "").upper() != "REFUTED":
        return fail("reviewer-must-default-refuted")

    print(
        "fired_on_bad=True silent_on_good=True "
        "ach_critique_discriminates=True icd203_not_protocol=True"
    )
    print("SUCCESS:RES-0158-probe2 protocol-crosscheck both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
