#!/usr/bin/env python3
"""Probe 1: planted re-assertion, planted novelty, use-vs-mention, unnormalisable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_local as S  # noqa: E402
from normalize import as_triple  # noqa: E402

OUT = REPO / "command-center/adversarial/ADV-0130-novelty-accounting.json"
UNIT = "ADV-0130"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def load_artifact() -> dict:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        raise FileNotFoundError("artifact missing")
    return json.loads(OUT.read_text(encoding="utf-8"))


def main() -> int:
    run = E.run(REPO)
    plants = run["planted_controls"]
    by_id = {r["id"]: r for r in run["classified"]}

    if len(plants["reassertion_ids"]) != 5:
        return fail(f"expected 5 reassertion plants, got {plants['reassertion_ids']}")
    if len(plants["novelty_ids"]) != 5:
        return fail(f"expected 5 novelty plants, got {plants['novelty_ids']}")
    if plants["detector_failure"]:
        return fail("detector-failure: planted set misclassified")
    if not plants["reassertion_all_subtracted"]:
        return fail("reassertion plants not all SUBTRACTED")
    if not plants["novelty_all_novel"]:
        return fail("novelty plants not all NOVEL")
    if not plants["use_vs_mention_survived"]:
        return fail("use-vs-mention did not survive as NOVEL")
    if not plants["naive_text_matcher_false_subtracts_uvm"]:
        return fail("naive text matcher did not take the mention bait; control is silent")

    uvm = by_id[plants["use_vs_mention_id"]]
    # Matching must be on the asserted triple, not the quoted declared edge.
    asserted = uvm["_tuple"]
    quoted = as_triple("R-A01", "blocked_by", "R-A31")
    if asserted == quoted:
        return fail("use-vs-mention asserted the mentioned edge; fixture is broken")
    if quoted not in run["declared"]:
        return fail("quoted edge R-A01 blocked_by R-A31 is not in declared; fixture is broken")

    unnorm = [r for r in run["classified"] if r["classification"] == "UNNORMALISABLE"]
    if not unnorm:
        return fail("unnormalisable plant missing")
    for rec in unnorm:
        t = rec.get("_tuple")
        if t is not None and t in run["novel"]:
            return fail(f"{rec['id']} unnormalisable counted as novel")

    try:
        doc = load_artifact()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, FileNotFoundError) as exc:
        return fail(f"artifact: {type(exc).__name__}")

    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    if not S.rejects_garbage():
        return fail("schema accepts garbage")
    errs = S.error_messages(doc)
    if errs:
        return fail("schema-invalid " + "; ".join(errs[:8]))

    text = OUT.read_text(encoding="utf-8")
    if "SUCCESS:ADV-0130" not in text:
        return fail("sentinel-absent")

    body = S.payload(doc)
    filed_class = {r["id"]: r["classification"] for r in body.get("filed") or []}
    for rid in plants["reassertion_ids"]:
        if filed_class.get(rid) != "SUBTRACTED":
            return fail(f"artifact {rid} classification {filed_class.get(rid)}")
    for rid in plants["novelty_ids"]:
        if filed_class.get(rid) != "NOVEL":
            return fail(f"artifact {rid} classification {filed_class.get(rid)}")
    if filed_class.get(plants["use_vs_mention_id"]) != "NOVEL":
        return fail("artifact use-vs-mention not NOVEL")

    pc = body.get("planted_controls") or {}
    if pc.get("detector_failure") is not False:
        return fail("artifact detector_failure is not false")

    summary = {
        "probe": "probe1-planted-controls",
        "unit_id": UNIT,
        "reassertion_all_subtracted": True,
        "novelty_all_novel": True,
        "use_vs_mention_survived": True,
        "naive_text_matcher_false_subtracts_uvm": True,
        "unnormalisable_not_novel": True,
        "artifact_schema_ok": True,
        "pass": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:ADV-0130-probe1 planted controls classify correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
