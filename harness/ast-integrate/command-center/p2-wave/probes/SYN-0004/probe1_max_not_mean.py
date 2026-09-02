#!/usr/bin/env python3
"""Probe 1: max-not-mean aggregation and closed severity vocabulary.

Re-runs the engine on fixtures and independently checks that the mean of
P0 and P2 is P1, which must be reported as DILUTION, not ALIGNED.
Unknown tokens must raise; they must never become P3/low.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import OUTPUT_REL, SENTINEL  # noqa: E402
from reconcile import UnknownSeverityError, reconcile  # noqa: E402
from schema_util import report_body  # noqa: E402
from severity import RANK, nearest_mean_token, parse_severity  # noqa: E402

RECEIPT = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0004-probe1 {msg}")
    return 1


def load_fixture(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    mean_tokens = ["P0", "P2"]
    mean = nearest_mean_token(mean_tokens)
    mx = "P0" if RANK["P0"] >= RANK["P2"] else "P2"
    print(f"independent mean(P0,P2)={mean} max={mx}")
    if mean != "P1":
        return fail(f"mean of P0 and P2 is {mean}, expected P1")
    if mx == mean:
        return fail("max equals mean; fixture would not discriminate")

    dilution = reconcile(load_fixture("mean_dilution.json"))
    row = next(r for r in dilution["rows"] if r["cause_id"] == "CAUSE-DILUTED")
    print(
        f"dilution recorded={row['recorded_severity']} "
        f"computed={row['computed_max_child_severity']} "
        f"delta={row['delta']} verdict={row['verdict']} "
        f"child={row['child_claim_id']}"
    )
    if row["recorded_severity"] != "P1":
        return fail("dilution fixture recorded is not P1")
    if row["computed_max_child_severity"] != "P0":
        return fail("max-not-mean did not recompute P0")
    if row["verdict"] != "DILUTION":
        return fail(f"mean aggregation not flagged DILUTION: {row['verdict']}")
    if row["child_claim_id"] != "CLAIM-P0-MEAN":
        return fail("DILUTION did not name the P0 child claim id")
    if row["delta"] <= 0:
        return fail("DILUTION delta was not > 0")

    aligned = reconcile(load_fixture("aligned_max.json"))
    arow = next(r for r in aligned["rows"] if r["cause_id"] == "CAUSE-ALIGNED")
    if arow["verdict"] != "ALIGNED" or arow["computed_max_child_severity"] != "P0":
        return fail(f"aligned fixture misfired {arow}")

    for token in ("LOW", "HIGH", "CRITICAL", "INFO", "P4", "0", ""):
        try:
            parsed = parse_severity(token)
        except UnknownSeverityError as exc:
            text = str(exc)
            if "never defaults to low" not in text:
                return fail(f"unknown {token!r} error was not loud: {text}")
            continue
        return fail(f"unknown token {token!r} parsed as {parsed}")

    try:
        reconcile(load_fixture("unknown_token.json"))
        return fail("unknown_token fixture did not raise")
    except UnknownSeverityError as exc:
        if "CRITICAL" not in str(exc) and "LOW" not in str(exc):
            return fail(f"unknown fixture error omitted token: {exc}")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    body = report_body(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if body.get("unexplained_deltas_open") != 0:
        return fail("unexplained_deltas_open != 0")
    if body.get("aggregation_rule") != "max-not-mean":
        return fail("aggregation_rule is not max-not-mean")
    by_id = {c["id"]: c for c in body.get("controls") or [] if isinstance(c, dict)}
    dil_ctl = by_id.get("max-not-mean-dilution") or {}
    if dil_ctl.get("result") != "FIRED":
        return fail("receipt dilution control not FIRED")
    unk_ctl = by_id.get("unknown-token-fails-loudly") or {}
    if unk_ctl.get("result") != "FIRED":
        return fail("receipt unknown-token control not FIRED")
    if unk_ctl.get("defaulted_to_vocab") is True:
        return fail("receipt claims unknown token defaulted into vocab")
    inputs = body.get("inputs") or {}
    live_hier = (REPO / "command-center/synthesis/SYN-0001.root-cause-hierarchy.json").is_file()
    if bool(inputs.get("hierarchy_present")) != live_hier:
        return fail("receipt hierarchy_present does not match disk")
    print(
        "max-not-mean=DILUTION unknown=loud aligned=SILENT "
        f"unexplained={body.get('unexplained_deltas_open')}"
    )
    print("SUCCESS:SYN-0004-probe1 max-not-mean closed-vocab")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
