#!/usr/bin/env python3
"""Probe 1: padding detector both-states on a planted padded set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cases as K  # noqa: E402
import contract as C  # noqa: E402
import engine as E  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0150-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    live = E.detector_both_states(K.genuine_g(), K.padded_g(), K.CLAIM_G, REPO)
    print(
        "genuine_unflagged={gu} padded_flagged={pf} both_states={bs} "
        "n_genuine={ng} n_padded={np}".format(
            gu=live["genuine_unflagged"],
            pf=live["padded_flagged"],
            bs=live["both_states"],
            ng=live["n_genuine"],
            np=live["n_padded"],
        )
    )
    for row in live["genuine"]:
        print(f"genuine {row['id']} flags={row['flags']}")
    for row in live["padded"]:
        print(f"padded {row['id']} flags={row['flags']}")

    if live["n_genuine"] < 2 or live["n_padded"] < 4:
        return fail("fixture too small")
    if not live["genuine_unflagged"]:
        return fail("detector flagged a genuine DISCONFIRM item")
    if not live["padded_flagged"]:
        return fail("detector missed a planted padded objection")
    if not live["both_states"]:
        return fail("both_states false")

    rec = doc.get("detector_control") or {}
    if rec.get("both_states") is not True:
        return fail("artifact detector_control.both_states is not true")
    if rec.get("padded_flagged") is not True:
        return fail("artifact did not record padded_flagged")
    if rec.get("genuine_unflagged") is not True:
        return fail("artifact did not record genuine_unflagged")
    art_ids = {r.get("id"): r.get("flags") for r in rec.get("padded") or []}
    for row in live["padded"]:
        if row["id"] not in art_ids:
            return fail(f"artifact missing padded id {row['id']}")
        if not art_ids[row["id"]]:
            return fail(f"artifact recorded empty flags for {row['id']}")

    print("SUCCESS:RES-0150-probe1 padding detector both-states on planted set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
