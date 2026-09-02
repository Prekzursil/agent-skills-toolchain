#!/usr/bin/env python3
"""Probe 2: security refuter — both-states, decoys, leak check, independent fire."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import assert_text_has_no_secrets  # noqa: E402
from measure import run_bundle  # noqa: E402
from metric import fire_index, load_prereg  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / (
    "command-center/research/supply-chain/"
    "RES-0133-secret-scanner-coverage-on-prose-artifacts.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    prereg = load_prereg()
    window = int(prereg["window"])
    floor = float(prereg["floor"])
    min_sources = int(prereg["min_sources"])
    early_max = int(prereg["early_max_index"])

    bundle = run_bundle()
    near = bundle["negative_controls"]["near_identical"]
    div = bundle["negative_controls"]["diverse"]
    g_pr = bundle["scanners"]["gitleaks"]["precision_recall"]
    t_pr = bundle["scanners"]["trufflehog"]["precision_recall"]
    h_pr = bundle["scanners"]["github_docs_local"]["precision_recall"]

    near_idx = fire_index(near["yields"], window, floor, min_sources)
    div_idx = fire_index(div["yields"], window, floor, min_sources)

    print(
        json.dumps(
            {
                "near_fired": near["fired"],
                "near_index": near["fire_index"],
                "near_recount": near_idx,
                "near_early": near["early"],
                "diverse_fired": div["fired"],
                "diverse_recount": div_idx,
                "gitleaks_decoys": g_pr["n_decoys"],
                "gitleaks_fp": g_pr["false_positives"],
                "trufflehog_fp": t_pr["false_positives"],
                "github_local_fp": h_pr["false_positives"],
            },
            sort_keys=True,
        )
    )

    if near_idx is None or near_idx > early_max:
        print(f"FAILED:RES-0133-probe2 near-identical did not fire early recount={near_idx}")
        return 1
    if near_idx != near["fire_index"]:
        print("FAILED:RES-0133-probe2 near fire_index != independent recount")
        return 1
    if div_idx is not None or div["fired"]:
        print(f"FAILED:RES-0133-probe2 diverse fired recount={div_idx}")
        return 1
    if g_pr["n_decoys"] != 5 or len(g_pr["decoy_classifications"]) != 5:
        print("FAILED:RES-0133-probe2 decoy control not 5")
        return 1
    classes = {row["class"] for row in g_pr["decoy_classifications"]}
    if not classes.issubset({"FP", "TN"}):
        print("FAILED:RES-0133-probe2 decoy class not FP/TN")
        return 1

    if not ART.is_file():
        print("FAILED:RES-0133-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:RES-0133-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0133" not in text:
        print("FAILED:RES-0133-probe2 sentinel-absent")
        return 1
    assert_text_has_no_secrets(text, bundle["secret_index"], label="artifact")

    nc = doc.get("negative_controls") or {}
    if (nc.get("near_identical") or {}).get("early") is not True:
        print("FAILED:RES-0133-probe2 artifact near_identical.early is not true")
        return 1
    if (nc.get("diverse") or {}).get("fired") is not False:
        print("FAILED:RES-0133-probe2 artifact diverse.fired is not false")
        return 1
    decoy = nc.get("decoy_false_positive_controls") or {}
    if int(decoy.get("n") or 0) != 5:
        print("FAILED:RES-0133-probe2 artifact decoy n != 5")
        return 1

    for row in doc.get("historical_replays") or []:
        rec = fire_index(row.get("yields") or [], window, floor, min_sources)
        if rec != row.get("fire_index"):
            print(
                f"FAILED:RES-0133-probe2 historical recount {row.get('run_id')} "
                f"art={row.get('fire_index')} recount={rec}"
            )
            return 1
        print(f"recount {row.get('run_id')} fire_index={rec} n={row.get('n_sources')}")

    gh = (doc.get("scanner_results") or {}).get("github_secret_scanning") or {}
    if gh.get("hosted_service_invoked") is not False:
        print("FAILED:RES-0133-probe2 hosted GitHub scanning claim not honest")
        return 1

    shutil.rmtree(bundle["tmp"], ignore_errors=True)
    print(
        f"near_early={near['early']} idx={near_idx} diverse_silent={div_idx is None} "
        f"decoys=5 leak_check=ok"
    )
    print("SUCCESS:RES-0133-probe2 both-states control, decoys, independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
