"""Probe 2: negative control, schema, overclaim, independent counterexample.

Reviewer re-derives lost counts from serialized traces (recount.py) and
must produce a counterexample instance: k==c pair-caucus with lost_count==0.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import recount as R  # noqa: E402
import topology as T  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md"
)
# Catalog shim $ref-fetches ast-integrate.invalid (RefResolutionError here;
# additionalProperties:false receipt_core on hosts with a disk resolver).
# Local schema is the live contract; it requires negative_controls[].rejects.
SCHEMA = HERE / "note.schema.json"
CATALOG_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
SENTINEL = "SUCCESS:CNL-0031"


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0031-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return _fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return _fail("sentinel-absent")
    doc = json.loads(text)
    if not SCHEMA.is_file():
        return _fail("local note.schema.json missing")
    if not CATALOG_SCHEMA.is_file():
        return _fail("catalog output_schema path missing on disk")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        Draft202012Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        return _fail(f"schema {exc.message}")
    if str(doc.get("state") or "").upper() != "SUCCESS":
        return _fail(f"state={doc.get('state')}")
    if str(doc.get("unit_id") or "") != "CNL-0031":
        return _fail("unit_id")

    ctrl = T.negative_control_verbatim()
    print(f"neg_bad {ctrl['bad_state_output']}")
    print(f"neg_good {ctrl['good_state_output']}")
    recorded = doc.get("negative_controls") or []
    if not recorded:
        return _fail("negative_controls-absent")
    row0 = recorded[0]
    if row0.get("bad_state_output") != ctrl["bad_state_output"]:
        return _fail("bad_state_output mismatch")
    if row0.get("good_state_output") != ctrl["good_state_output"]:
        return _fail("good_state_output mismatch")
    if row0.get("fires_on_bad") is not True or row0.get("silent_on_good") is not True:
        return _fail("schema polarity flags")
    if not str(row0.get("rejects") or "").strip():
        return _fail("rejects-absent")
    if "FIRES" not in ctrl["bad_state_output"] or "SILENT" not in ctrl["good_state_output"]:
        return _fail("verbatim polarity")
    if "lost_count=0" not in ctrl["good_state_output"]:
        return _fail("good state not zero-loss")
    if "lost_count=0" in ctrl["bad_state_output"]:
        return _fail("bad state vacuously silent")

    live = {r["k"]: r for r in T.sweep()}
    measured = (doc.get("fragmentation_threshold") or {}).get("measured") or {}
    rows = measured.get("sweep") or []
    if len(rows) != len(live):
        return _fail(f"sweep-len {len(rows)}!={len(live)}")
    for item in rows:
        k = int(item["k"])
        sim = live[k]
        rec = R.recount(
            {
                "planted_fact": T.PLANTED_FACT_ID,
                "group_transcripts": [
                    {"fact_ids": t["fact_ids"]} for t in sim["group_transcripts"]
                ],
                "plenary_payloads": [
                    {"fact_ids": p["fact_ids"]} for p in sim["plenary_payloads"]
                ],
            }
        )
        if int(item["lost_count"]) != sim["lost_count"] or rec["lost_count"] != sim["lost_count"]:
            return _fail(f"reviewer-recount k={k}")
        print(f"reviewer_recount k={k} lost={rec['lost_count']} family={sim['family']}")

    xo = int((doc.get("fragmentation_threshold") or {}).get("crossover_k") or 0)
    live_xo = T.crossover_k()
    if xo != live_xo:
        return _fail(f"crossover_k claimed={xo} live={live_xo}")

    cex_live = T.lossless_counterexample()
    if cex_live["lost_count"] != 0 or cex_live["k"] != T.C_DEFAULT:
        return _fail("live counterexample not lossless")
    cex = (doc.get("reviewer") or {}).get("counterexample") or {}
    try:
        cex_lost = int(cex["lost_count"])
        cex_k = int(cex["k"])
    except (KeyError, TypeError, ValueError):
        return _fail("reviewer counterexample missing lossless k==c instance")
    if cex_lost != 0 or cex_k != cex_live["k"]:
        return _fail("reviewer counterexample missing lossless k==c instance")
    print(
        f"counterexample k={cex_live['k']} c={cex_live['c']} "
        f"lost={cex_live['lost_count']} family={cex_live['family']} "
        f"refutes={cex_live['what_it_refutes']}"
    )

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return _fail("reviewer not independent")
    if str(rev.get("verdict") or "") != "PASS":
        return _fail("reviewer verdict")

    claims = doc.get("claims") or []
    verdicts = {c.get("id"): c.get("verdict") for c in claims if isinstance(c, dict)}
    if verdicts.get("C4") != "REFUTED":
        return _fail("C4 must REFUTE subgrouping-never-fragments")
    if verdicts.get("C5") != "REFUTED":
        return _fail("C5 must REFUTE any-k-lt-n-fragments")
    for c in claims:
        if c.get("verdict") == "REFUTED" and "anchor" not in c:
            return _fail(f"REFUTED claim {c.get('id')} missing anchor")

    fixtures = doc.get("fixtures") or []
    if len(fixtures) < 10:
        return _fail(f"fixtures-len {len(fixtures)}")
    for fx in fixtures:
        expl = fx.get("explanation") or {}
        try:
            n = int(expl["n"])
            k = int(expl["k"])
            c = int(expl["c"])
            claimed = int(expl["lost_count"])
        except (KeyError, TypeError, ValueError):
            return _fail(f"fixture {fx.get('id')} incomplete explanation")
        live_fx = T.simulate(n=n, k=k, c=c)
        if live_fx["lost_count"] != claimed:
            return _fail(
                f"fixture {fx.get('id')} lost claimed={claimed} live={live_fx['lost_count']}"
            )
        print(
            f"fixture {fx.get('id')} n={n} k={k} c={c} "
            f"lost={claimed} family={live_fx['family']}"
        )

    mutant = copy.deepcopy(doc)
    nc0 = (mutant.get("negative_controls") or [{}])[0]
    if "rejects" not in nc0:
        return _fail("no rejects field to strip")
    del nc0["rejects"]
    try:
        Draft202012Validator(schema).validate(mutant)
        return _fail("mutant without rejects was accepted")
    except jsonschema.ValidationError:
        print("mutant_ok=False stripped-rejects rejected")

    evidence = doc.get("evidence") or []
    mechs = set()
    for i, erow in enumerate(evidence):
        rel = str(erow.get("path") or "")
        line = int(erow.get("line") or 0)
        snippet = str(erow.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            return _fail("unresolved anchor")
        mechs.add(str(erow.get("mechanism") or ""))
    if len(mechs) < 2:
        return _fail(f"single-signal mechanisms={mechs}")

    print("SUCCESS:CNL-0031-probe2 negative-control reviewer-counterexample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
