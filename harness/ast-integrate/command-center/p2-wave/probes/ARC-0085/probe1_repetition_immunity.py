#!/usr/bin/env python3
"""Probe 1: repetition-immunity plus live encoding of >=10 real claims.

Two records with the same canonical mechanism and different authors must collapse
to one canonical claim carrying two lineage entries. Ranking must not rise when a
third author repeats the same independence key. Contradiction edges between
COMPLETE-SSOT and INEXPRESSIBLE-OPAQUE must remain valid after collapse.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import claims as C  # noqa: E402
import validator as V  # noqa: E402

SAMPLES_IDS = {"CLAIM-A1-SAMPLES-AUTHOR", "CLAIM-A1-SAMPLES-INDEP"}
CONTRA = ("CLAIM-A2-COMPLETE-SSOT", "CLAIM-A2-INEXPRESSIBLE-OPAQUE")


def snippet_in_source(entry: dict) -> bool:
    path = REPO / str(entry["path"])
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    snippet = str(entry.get("snippet") or "")
    if snippet and snippet not in text:
        return False
    line_no = int(entry["line"])
    lines = text.splitlines()
    if line_no < 1 or line_no > len(lines):
        return False
    return True


def main() -> int:
    schema = V.load_schema()
    if "SUCCESS:ARC-0085" not in json.dumps(schema):
        print("FAILED:ARC-0085-probe1 sentinel missing from contract")
        return 1
    jsonschema_errs = []
    try:
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(schema)
    except Exception as exc:  # pragma: no cover - defensive
        jsonschema_errs.append(str(exc))
    if jsonschema_errs:
        print(f"FAILED:ARC-0085-probe1 schema not draft-2020-12: {jsonschema_errs[0]}")
        return 1

    records, source = C.load_encoded()
    C.write_fixture(records, source)
    if len(records) < 10:
        print(f"FAILED:ARC-0085-probe1 encoded={len(records)} need>=10")
        return 1

    missing_snip = []
    for rec in records:
        for e in rec.get("source_lineage") or []:
            if not snippet_in_source(e):
                missing_snip.append(f"{rec['claim_id']} {e.get('path')}:{e.get('line')}")
    if missing_snip:
        print("FAILED:ARC-0085-probe1 lineage not on disk: " + "; ".join(missing_snip[:6]))
        return 1

    report = V.validate_records(records, schema)
    if report["schema_errors"]:
        print(f"FAILED:ARC-0085-probe1 schema_errors={report['schema_errors']}")
        return 1
    if report["edge_errors"]:
        print(f"FAILED:ARC-0085-probe1 edge_errors={report['edge_errors']}")
        return 1

    collapsed = report["collapsed"]
    alias_map = report["alias_map"]
    if SAMPLES_IDS <= set(alias_map) and len({alias_map[i] for i in SAMPLES_IDS}) != 1:
        print(f"FAILED:ARC-0085-probe1 duplicate pair did not collapse {alias_map}")
        return 1
    canonical_id = alias_map[next(iter(SAMPLES_IDS))]
    survivor = next(r for r in collapsed if r["claim_id"] == canonical_id)
    authors = {e["author"] for e in survivor["source_lineage"]}
    if len(survivor["source_lineage"]) < 2 or len(authors) < 2:
        print(
            f"FAILED:ARC-0085-probe1 expected two lineage authors on {canonical_id} "
            f"got lineage={len(survivor['source_lineage'])} authors={sorted(authors)}"
        )
        return 1
    if survivor.get("duplicate_of"):
        print(f"FAILED:ARC-0085-probe1 canonical still alias {survivor}")
        return 1

    a, b = CONTRA
    if a not in alias_map or b not in alias_map:
        print(f"FAILED:ARC-0085-probe1 contradiction pair missing from encoding source={source}")
        return 1
    ca, cb = alias_map[a], alias_map[b]
    rec_a = next(r for r in collapsed if r["claim_id"] == ca)
    rec_b = next(r for r in collapsed if r["claim_id"] == cb)
    if cb not in (rec_a.get("contradicts") or []) and ca not in (rec_b.get("contradicts") or []):
        print(f"FAILED:ARC-0085-probe1 contradiction edge dropped ca={ca} cb={cb}")
        return 1
    if rec_a["verification_status"] == rec_b["verification_status"] == "CONFIRMED":
        print("FAILED:ARC-0085-probe1 both contradiction sides CONFIRMED")
        return 1

    ranked = V.rank_canonical(collapsed)
    base_order = [r["claim_id"] for r in ranked]
    base_score = {
        r["claim_id"]: r["_rank_score"] for r in ranked if r["claim_id"] == canonical_id
    }
    if canonical_id not in base_score:
        print("FAILED:ARC-0085-probe1 collapsed samples missing from rank")
        return 1

    mutant_records = copy.deepcopy(records)
    extra = copy.deepcopy(next(r for r in records if r["claim_id"] == "CLAIM-A1-SAMPLES-AUTHOR"))
    extra["claim_id"] = "CLAIM-A1-SAMPLES-REPEAT"
    extra["source_lineage"][0]["author"] = "third-agent-repeat"
    mutant_records.append(extra)
    mutant = V.validate_records(mutant_records, schema)
    if not mutant["ok"]:
        print(f"FAILED:ARC-0085-probe1 mutant invalid {mutant['schema_errors']} {mutant['edge_errors']}")
        return 1
    m_can = mutant["alias_map"]["CLAIM-A1-SAMPLES-AUTHOR"]
    m_surv = next(r for r in mutant["collapsed"] if r["claim_id"] == m_can)
    if len(m_surv["source_lineage"]) < 3:
        print(
            f"FAILED:ARC-0085-probe1 repeat did not add a lineage row n={len(m_surv['source_lineage'])}"
        )
        return 1
    if V.independent_evidence_score(m_surv) != V.independent_evidence_score(survivor):
        print(
            "FAILED:ARC-0085-probe1 ranking used author repeats as independent evidence "
            f"base={V.independent_evidence_score(survivor)} mutant={V.independent_evidence_score(m_surv)}"
        )
        return 1
    m_ranked = V.rank_canonical(mutant["collapsed"])
    m_order = [r["claim_id"] for r in m_ranked]
    if m_order != base_order:
        print(f"FAILED:ARC-0085-probe1 rank order shifted on agent repeat {base_order} vs {m_order}")
        return 1

    print(
        json.dumps(
            {
                "encoded": len(records),
                "source": source,
                "canonical_after_collapse": report["canonical_count"],
                "duplicate_canonical": canonical_id,
                "lineage_entries": len(survivor["source_lineage"]),
                "lineage_authors": sorted(authors),
                "independent_evidence_score": V.independent_evidence_score(survivor),
                "contradiction": {"a": ca, "b": cb},
                "rank_repeat_immune": True,
                "registry_absent": not C.REGISTRY.is_file(),
            },
            sort_keys=True,
        )
    )
    print(
        f"encoded={len(records)} collapsed_canonical={report['canonical_count']} "
        f"dup_lineage={len(survivor['source_lineage'])} authors={len(authors)} "
        f"contra={ca}/{cb}"
    )
    print("SUCCESS:ARC-0085-probe1 repetition-immunity and ten-claim encoding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
