#!/usr/bin/env python3
"""Probe 2: independent recount / re-tabulation (does not trust probe1 output).

Re-derives sentence counts, idea sets, and the missing hop from the fixtures
and the catalog using a relational join written here. Disagreement with the
artifact (or with lineage.chase_ideas) BLOCKS.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lineage as L  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md"
)
GOOD = HERE / "fixtures/good.json"
ORPHAN = HERE / "fixtures/orphan.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PARENT_FIELDS = {
    "option_cards": "promoted_from_idea_ids",
    "claims": "about_option_card_ids",
    "arguments": "cites_claim_ids",
    "votes": "rests_on_argument_ids",
    "decisions": "tally_of_vote_ids",
    "action_plan": "implements_decision_ids",
}
KIND_OF = {
    "ideas": "idea",
    "option_cards": "option_card",
    "claims": "claim",
    "arguments": "argument",
    "votes": "vote",
    "decisions": "decision",
    "action_plan": "action_plan",
}


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [p.strip() for p in SPLIT_RE.split(text) if p.strip()]


def edges_and_kinds(council: dict) -> tuple[set[tuple[str, str]], dict[str, str]]:
    """Independent index: parent relation as tuples, kinds as a separate map."""
    rel: set[tuple[str, str]] = set()
    kinds: dict[str, str] = {}
    for rec in council.get("ideas") or []:
        kinds[rec["id"]] = "idea"
    for coll, field in PARENT_FIELDS.items():
        for rec in council.get(coll) or []:
            kinds[rec["id"]] = KIND_OF[coll]
            for parent in rec.get(field) or []:
                rel.add((rec["id"], parent))
    return rel, kinds


def ideas_reached(rel: set[tuple[str, str]], kinds: dict[str, str], start: str) -> set[str]:
    frontier = {start}
    seen: set[str] = set()
    ideas: set[str] = set()
    while frontier:
        nxt: set[str] = set()
        for nid in frontier:
            if nid in seen:
                continue
            seen.add(nid)
            if kinds.get(nid) == "idea":
                ideas.add(nid)
                continue
            nxt.update(p for (a, p) in rel if a == nid)
        frontier = nxt
    return ideas


def recount(path: Path) -> dict:
    council = json.loads(path.read_text(encoding="utf-8"))
    rec = council["recommendation"]
    split = split_sentences(rec["text"])
    listed = [s["text"] for s in rec["sentences"]]
    if split != listed:
        raise SystemExit(f"FAILED:CNL-0075-probe2 split/listed mismatch {split} {listed}")
    rel, kinds = edges_and_kinds(council)
    rows = []
    for sent in rec["sentences"]:
        cites = list(sent.get("cites") or [])
        ideas: set[str] = set()
        for cid in cites:
            ideas.update(ideas_reached(rel, kinds, cid))
        orphan = (not cites) or (not ideas)
        rows.append({"id": sent["id"], "ideas": sorted(ideas), "orphan": orphan})
    return {
        "sentence_count": len(rows),
        "resolved": sum(1 for r in rows if not r["orphan"]),
        "orphan_ids": [r["id"] for r in rows if r["orphan"]],
        "rows": rows,
    }


def catalog_first_unauthored_hop() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    hops = [
        ("idea", "option_card", ("idea", "option card")),
        ("option_card", "claim", ("option card", "claim")),
        ("claim", "argument", ("claim", "argument")),
        ("argument", "vote", ("argument", "vote")),
        ("vote", "decision", ("vote", "decision")),
        ("decision", "action_plan", ("action", "decision")),
    ]
    for frm, to, needles in hops:
        authors = []
        for unit in data.get("work_units") or []:
            uid = str(unit.get("id") or "")
            if uid == "CNL-0075" or not re.match(r"^(CNL|IMP)-\d+$", uid):
                continue
            blob = " ".join(
                [str(unit.get("title") or ""), str(unit.get("question_or_target") or "")]
            ).lower()
            if all(n in blob for n in needles):
                authors.append(uid)
        print(f"recount-hop {frm}->{to} authors={authors}")
        if not authors:
            return f"{frm}->{to}"
    return "NONE"


def resolve_anchor(path: str, line: int, snippet: str) -> bool:
    fp = REPO / path
    if not fp.is_file():
        print(f"anchor-miss file {path}")
        return False
    lines = fp.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        print(f"anchor-miss line {path}:{line}")
        return False
    got = lines[line - 1]
    if snippet not in got:
        print(f"anchor-miss snippet {path}:{line} {got!r}")
        return False
    print(f"anchor-ok {path}:{line}")
    return True


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0075-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0075":
        print("FAILED:CNL-0075-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0075" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0075-probe2 sentinel absent")
        return 1

    good = recount(GOOD)
    orphan = recount(ORPHAN)
    print(
        f"recount-good sentences={good['sentence_count']} "
        f"resolved={good['resolved']} orphans={good['orphan_ids']}"
    )
    print(
        f"recount-orphan sentences={orphan['sentence_count']} "
        f"resolved={orphan['resolved']} orphans={orphan['orphan_ids']}"
    )
    if good["sentence_count"] != 2 or good["orphan_ids"] or good["resolved"] != 2:
        print("FAILED:CNL-0075-probe2 good recount")
        return 1
    if orphan["orphan_ids"] != ["s3"] or orphan["resolved"] != 2:
        print("FAILED:CNL-0075-probe2 orphan recount")
        return 1

    # Cross-check against lineage.chase (different function, same numbers).
    chase = L.sentence_report(L.load_council(GOOD), walker="chase")
    if chase["orphan_ids"] != good["orphan_ids"]:
        print("FAILED:CNL-0075-probe2 chase/recount disagreement")
        return 1

    missing = catalog_first_unauthored_hop()
    print(f"recount-missing_link={missing}")
    if missing != "option_card->claim":
        print(f"FAILED:CNL-0075-probe2 missing hop {missing}")
        return 1
    if doc.get("missing_link") != missing:
        print("FAILED:CNL-0075-probe2 artifact missing_link disagrees with recount")
        return 1
    counts = doc.get("decomposition_counts") or {}
    if counts.get("good_sentences") != good["sentence_count"]:
        print("FAILED:CNL-0075-probe2 good_sentences disagreement")
        return 1
    if counts.get("orphan_ids") != orphan["orphan_ids"]:
        print("FAILED:CNL-0075-probe2 orphan_ids disagreement")
        return 1

    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        print("FAILED:CNL-0075-probe2 need >=2 evidence rows")
        return 1
    mechanisms = {str(e.get("mechanism") or "") for e in evidence}
    if len(mechanisms) < 2:
        print(f"FAILED:CNL-0075-probe2 evidence mechanisms not independent {mechanisms}")
        return 1
    for i, row in enumerate(evidence):
        if not resolve_anchor(str(row.get("path") or ""), int(row.get("line") or 0), str(row.get("snippet") or "")):
            print(f"FAILED:CNL-0075-probe2 evidence[{i}] anchor")
            return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNL-0075-probe2 reviewer.independent is not true")
        return 1
    if rev.get("recount_good_sentences") != 2 or rev.get("recount_orphan_ids") != ["s3"]:
        print("FAILED:CNL-0075-probe2 reviewer recount fields stale")
        return 1
    if str(rev.get("verdict") or "").upper() not in {"PASS", "AGREE"}:
        print("FAILED:CNL-0075-probe2 reviewer verdict")
        return 1

    print("SUCCESS:CNL-0075-probe2 independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
