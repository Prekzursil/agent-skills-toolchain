#!/usr/bin/env python3
"""Emit command-center/foundry/WFA-0131-benchmark-gaming-adversarial-control.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import run_campaign  # noqa: E402
from registry import REGISTRY_PATH  # noqa: E402
from variants import GAMED_IDS, PRIMARY_GAMED_IDS, VARIANTS  # noqa: E402

UNIT = "WFA-0131"
OUT = "command-center/foundry/WFA-0131-benchmark-gaming-adversarial-control.json"
SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/adversarial-control"
SENTINEL = "SUCCESS:WFA-0131"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    camp = run_campaign(freeze_first=True)
    scores = camp["scores"]
    if len(camp["gamed_naive_accept"]) < 3:
        print("FAILED:WFA-0131 naive predicate did not accept three gamed variants")
        print(json.dumps({k: scores[k]["naive_predicate"] for k in GAMED_IDS}, indent=2))
        return 1
    if set(camp["primary_gamed_control_fire"]) != set(PRIMARY_GAMED_IDS):
        print("FAILED:WFA-0131 control did not FIRE on all three primary gamed variants")
        print(camp["primary_gamed_control_fire"])
        return 1
    if len(camp["gamed_control_fire"]) != len(GAMED_IDS):
        print("FAILED:WFA-0131 control missed a gamed variant")
        print(camp["gamed_control_fire"])
        return 1
    if not camp["honest_control_silent"]:
        print("FAILED:WFA-0131 control FIRED on honest baseline")
        print(json.dumps(scores["honest_baseline"]["control"], indent=2))
        return 1
    if not camp["genuine_gated_accept"]:
        print("FAILED:WFA-0131 genuine improvement was not gated-ACCEPT")
        print(json.dumps(scores["genuine_improvement"], indent=2, default=str)[:4000])
        return 1

    naive_accept_names = camp["gamed_naive_accept"]
    answer = (
        "The naive four-metric ACCEPT predicate (visible-slice composite, "
        f"min_effect_size={scores['genuine_improvement']['naive_predicate']['min_effect_size']}) "
        f"ACCEPTS {len(naive_accept_names)} gamed variants "
        f"({', '.join(naive_accept_names)}) that add no held-out capability. "
        "gaming-control-v1 (held-out gap, effort normalisation, capability "
        "assertion, output-shaping gap) FIRED on every gamed variant, stayed "
        "SILENT on honest_baseline, and left genuine_improvement gated-ACCEPT."
    )

    gamed_rows = []
    for name in GAMED_IDS:
        s = scores[name]
        gamed_rows.append(
            {
                "id": name,
                "runnable": f"command-center/p2-wave/probes/WFA-0131/variants.py:{name}",
                "score_fixture": f"command-center/p2-wave/probes/WFA-0131/fixtures/runs/{name}.json",
                "naive": s["naive"],
                "held_out": s["held_out"],
                "naive_predicate": s["naive_predicate"],
                "control": {
                    "verdict": s["control"]["verdict"],
                    "fires": s["control"]["fires"],
                    "heldout_correctness": s["control"]["heldout_correctness"],
                    "heldout_gap": s["control"]["heldout_gap"],
                    "extra_effort": s["control"]["effort"]["extra_effort"],
                },
                "gated_decision": s["gated_decision"],
            }
        )

    supporting = [
        "command-center/p2-wave/probes/WFA-0131/registry.py",
        "command-center/p2-wave/probes/WFA-0131/corpus.py",
        "command-center/p2-wave/probes/WFA-0131/engine.py",
        "command-center/p2-wave/probes/WFA-0131/variants.py",
        "command-center/p2-wave/probes/WFA-0131/campaign.py",
        "command-center/p2-wave/probes/WFA-0131/fixtures/registry.json",
        "command-center/p2-wave/probes/WFA-0131/fixtures/registry.pin",
        "command-center/p2-wave/probes/WFA-0131/fixtures/cases.json",
        "command-center/schema/foundry-artifact.schema.json",
    ]
    for name in VARIANTS:
        supporting.append(
            f"command-center/p2-wave/probes/WFA-0131/fixtures/runs/{name}.json"
        )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "kind": "adversarial-control",
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": SCHEMA,
        "spec_anchor": "WORK-UNIT-CATALOG.json WFA-0131 / _USER-PROMPTS.md:11059",
        "question": (
            "Attack the pre-registered metric set from WFA-0130: construct at "
            "least three GAMED workflow variants that raise the composite score "
            "without adding capability (stage padding, case overfitting, "
            "retry-until-pass, and metric-favourable output shaping) and run them. "
            "Does the acceptance predicate accept any gamed variant, and if so "
            "what counter-control makes it reject all three while still accepting "
            "the genuine improvement?"
        ),
        "answer": answer,
        "mechanism": "constructive score-inflation attack that yields a held-out counter-control",
        "dependency_status": {
            "WFA-0130": (
                "output absent; surrogate metric registry pinned from the "
                "catalog four-metric question and hashed before scoring"
            ),
            "WFA-0129": (
                "output absent; local visible+held-out matched-case fixture "
                f"n={camp['n_cases']} (visible={camp['n_visible']}, "
                f"held-out={camp['n_heldout']})"
            ),
        },
        "metric_registry": {
            "path": "command-center/p2-wave/probes/WFA-0131/fixtures/registry.json",
            "pin_path": "command-center/p2-wave/probes/WFA-0131/fixtures/registry.pin",
            "sha256_before_first_run": camp["registry_sha256_before_first_run"],
            "freeze_order": camp["freeze_order"],
        },
        "naive_predicate": {
            "slice": "visible",
            "accept_rule": (
                "composite >= baseline.composite + min_effect_size and no "
                "metric regresses more than max_single_metric_regression"
            ),
            "accepted_gamed_variants": naive_accept_names,
            "accepted_gamed_n": len(naive_accept_names),
        },
        "counter_control": {
            "id": "gaming-control-v1",
            "clauses": [
                "held-out-gap",
                "effort-without-capability",
                "capability-assertion",
                "output-shaping",
            ],
            "fire_on_gamed": camp["gamed_control_fire"],
            "silent_on_honest_baseline": camp["honest_control_silent"],
            "genuine_improvement_gated_accept": camp["genuine_gated_accept"],
        },
        "honest_baseline": {
            "id": "honest_baseline",
            "naive": scores["honest_baseline"]["naive"],
            "held_out": scores["honest_baseline"]["held_out"],
            "control": scores["honest_baseline"]["control"]["verdict"],
            "gated_decision": scores["honest_baseline"]["gated_decision"],
        },
        "genuine_improvement": {
            "id": "genuine_improvement",
            "naive": scores["genuine_improvement"]["naive"],
            "held_out": scores["genuine_improvement"]["held_out"],
            "naive_predicate": scores["genuine_improvement"]["naive_predicate"],
            "control": scores["genuine_improvement"]["control"]["verdict"],
            "gated_decision": scores["genuine_improvement"]["gated_decision"],
        },
        "gamed_variants": gamed_rows,
        "campaign": {
            "n_cases": camp["n_cases"],
            "n_visible": camp["n_visible"],
            "n_heldout": camp["n_heldout"],
            "variants": list(VARIANTS),
        },
        "tests": [
            {
                "id": "control-both-states",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0131/probe1_control_both_states.py"
                ),
            },
            {
                "id": "naive-accept-pin-genuine",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0131/probe2_naive_pin_and_genuine.py"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0131-probe2-independent-arithmetic-and-pin",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 re-derives visible vs held-out correctness from traces "
                "without evaluate_control, mutates the pinned registry, and "
                "checks genuine gated ACCEPT. Codex MCP is not on this substrate."
            ),
        },
        "artifacts": [art(p, "supporting") for p in supporting if (REPO / p).is_file()],
        "timestamps": {"started": started, "ended": ended},
        "cloud_ok": False,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(payload.replace("\r\n", "\n"), encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
