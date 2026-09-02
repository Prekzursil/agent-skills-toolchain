#!/usr/bin/env python3
"""Probe 2: post-hoc predicate edit is refused; independent pin recompute."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import schema_local as SL  # noqa: E402
from predicate import PREDICATE, canonical_dumps  # noqa: E402
from runner import PIN_MISMATCH, REPIN_AFTER_MEASUREMENT, pin_registry, score_registry  # noqa: E402

OUT = REPO / "command-center" / "foundry" / (
    "WFA-0130-pre-registered-fusion-acceptance-metric-set.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0130-probe2 {msg}")
    return 1


def independent_digest(predicate: dict) -> str:
    return hashlib.sha256(canonical_dumps(predicate).encode("utf-8")).hexdigest()


def main() -> int:
    registry = pin_registry(PREDICATE)
    pin_sha = registry["pin"]["sha256"]
    indep = independent_digest(PREDICATE)
    if indep != pin_sha:
        return fail(f"independent hashlib digest {indep} != pin {pin_sha}")

    sources = F.all_sources()
    first = score_registry(registry, F.stage_padded(), sources)
    if first.get("status") != "SCORED" or first.get("cited_pin_sha256") != pin_sha:
        return fail("baseline score against pinned registry failed")

    mutated = copy.deepcopy(registry)
    mutated["predicate"]["minimum_effect_size"] = 0.001
    live = independent_digest(mutated["predicate"])
    if live == pin_sha:
        return fail("mutation did not change the predicate digest")
    refused = score_registry(mutated, F.genuine_improvement(), sources)
    if refused.get("status") != "REFUSED" or refused.get("reason") != PIN_MISMATCH:
        return fail(f"mutated copy was not PIN_MISMATCH: {refused}")
    if refused.get("decision") is not None:
        return fail("runner emitted a decision against the mutated copy")
    if mutated.get("next_seq") != registry.get("next_seq"):
        return fail("refused score advanced the mutated registry seq")

    repinned = copy.deepcopy(registry)
    new_pred = copy.deepcopy(PREDICATE)
    new_pred["minimum_effect_size"] = 0.001
    new_sha = independent_digest(new_pred)
    repinned["predicate"] = new_pred
    repinned["pin"]["sha256"] = new_sha
    frozen = score_registry(repinned, F.genuine_improvement(), sources)
    if frozen.get("reason") != REPIN_AFTER_MEASUREMENT:
        return fail(f"re-pin after measurement not refused: {frozen}")

    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    body = SL.registry_payload(doc)
    art_pin = (body.get("pin") or {}).get("sha256")
    if art_pin != pin_sha:
        return fail("artifact pin does not match independent digest")
    control = body.get("mutation_control") or {}
    if control.get("runner_reason") != PIN_MISMATCH or control.get("scored") is not False:
        return fail("artifact mutation_control did not record a refusal")
    first_m = body.get("first_measurement") or {}
    if first_m.get("cited_pin_sha256") != pin_sha:
        return fail("artifact first measurement does not cite independent pin")
    if "SUCCESS:WFA-0130" not in json.dumps(doc):
        return fail("catalog sentinel absent")

    print(
        f"independent_pin={indep} mutated_live={live} "
        f"mismatch_refused=True repin_refused=True"
    )
    print(
        "SUCCESS:WFA-0130-probe2 post-hoc metric edit refused; "
        "independent hashlib pin matches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
