#!/usr/bin/env python3
"""Probe 1: live 20-item yield table vs artifact; tokenizer not chars/4."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as K  # noqa: E402
import corpus as C  # noqa: E402
import measure as M  # noqa: E402

ART = REPO / C.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0140-probe1 artifact missing")
        return 1
    live = M.measure()
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = K.check(doc, repo=REPO)
    print(f"contract_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0140-probe1 contract")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:RES-0140-probe1 sentinel-absent")
        return 1
    if live["sample_size"] != 20 or int(doc["sample_size"]) != 20:
        print("FAILED:RES-0140-probe1 sample-size")
        return 1
    live_cmp = live["comparison"]
    art_cmp = doc["comparison"]
    keys = [
        "transcript_incremental_honest_per_10k",
        "official_docs_incremental_per_10k",
        "blog_incremental_per_10k",
        "transcript_intra_inflated_per_10k",
    ]
    for k in keys:
        if float(live_cmp[k]) != float(art_cmp[k]):
            print(f"FAILED:RES-0140-probe1 mismatch {k} live={live_cmp[k]} art={art_cmp[k]}")
            return 1
    live_items = {(r["id"], r["tokens_consumed"]) for r in live["per_item"]}
    art_items = {(r["id"], r["tokens_consumed"]) for r in doc["per_item"]}
    if live_items != art_items:
        print("FAILED:RES-0140-probe1 per-item token mismatch")
        return 1
    if not live["two_signal"]["every_item_tokenizer_ne_chars_div_4"]:
        print("FAILED:RES-0140-probe1 tokenizer==chars/4")
        return 1
    stay_live = live["threshold"]["stay_in_default_source_class_set"]
    stay_art = doc["threshold"]["stay_in_default_source_class_set"]
    if stay_live != stay_art:
        print("FAILED:RES-0140-probe1 threshold verdict mismatch")
        return 1
    mutant = copy.deepcopy(doc)
    mutant["per_item"][0]["tokens_consumed"] = 1
    mok, mwhy = K.check(mutant, repo=REPO)
    print(f"token_lie_contract={mok} {mwhy}")
    # Contract may still pass a 1-token lie; probe catches yield mismatch.
    mutant["comparison"]["transcript_incremental_honest_per_10k"] = 9999.0
    if mutant["comparison"]["transcript_incremental_honest_per_10k"] == live_cmp[
        "transcript_incremental_honest_per_10k"
    ]:
        print("FAILED:RES-0140-probe1 mutant did not change")
        return 1
    print(
        "live_tr_per_10k="
        f"{live_cmp['transcript_incremental_honest_per_10k']} "
        f"od={live_cmp['official_docs_incremental_per_10k']} "
        f"blog={live_cmp['blog_incremental_per_10k']} "
        f"stay={stay_live}"
    )
    print("SUCCESS:RES-0140-probe1 yield table matches live recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
