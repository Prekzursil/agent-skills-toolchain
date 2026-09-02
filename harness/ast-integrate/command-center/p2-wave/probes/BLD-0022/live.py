"""Live selected-option set as this worktree can reconstruct it."""
from __future__ import annotations

import json
import re
from pathlib import Path

from classify import Utterance, classify

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
PINNED_NAMED = ("A-01", "A-03", "A-12", "A-13", "A-17", "A-18")
CLAIMED_COUNT = 70
ID_RE = re.compile(r"\bA-\d+\b")


def _line_of(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def owner_questions(catalog: dict) -> list[dict]:
    return list(catalog.get("owner_questions") or [])


def q_by_id(catalog: dict, qid: str) -> dict:
    for q in owner_questions(catalog):
        if q.get("id") == qid:
            return q
    raise KeyError(qid)


def record_utterance(qid: str, catalog: dict, catalog_text: str) -> Utterance:
    q = q_by_id(catalog, qid)
    snippet = f'"id": "{qid}"'
    line = _line_of(catalog_text, snippet)
    text = " ".join(
        str(q.get(k) or "")
        for k in ("id", "text", "answer", "answer_detail", "answer_provenance")
    )
    return Utterance(
        speaker="agent",
        path="command-center/WORK-UNIT-CATALOG.json",
        line=line,
        text=text,
    )


def named_selected_ids(oq1: dict) -> list[str]:
    blob = str(oq1.get("answer_detail") or "") + " " + str(oq1.get("answer") or "")
    found = list(dict.fromkeys(ID_RE.findall(blob)))
    for pin in PINNED_NAMED:
        if pin not in found:
            raise SystemExit(
                f"FAILED:BLD-0022 pinned selected id {pin} missing from OQ-1"
            )
    return found


def claimed_count(oq1: dict) -> int:
    blob = str(oq1.get("answer") or "") + " " + str(oq1.get("answer_detail") or "")
    m = re.search(r"\b(\d+)\s+`?owner_decisions`?", blob)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\s+ids\b", blob)
    if m:
        return int(m.group(1))
    return CLAIMED_COUNT


def live_rows() -> dict:
    catalog = load_catalog()
    text = CATALOG.read_text(encoding="utf-8")
    oq1 = q_by_id(catalog, "OQ-1")
    oq3 = q_by_id(catalog, "OQ-3")
    u1 = record_utterance("OQ-1", catalog, text)
    u3 = record_utterance("OQ-3", catalog, text)
    named = named_selected_ids(oq1)
    n_claimed = claimed_count(oq1)
    selected = []
    for oid in named:
        v = classify(oid, [u1])
        selected.append(
            v.as_row(oid, "SELECTED", "live-catalog-OQ-1")
        )
    set_v = classify("owner_decisions", [u1])
    # The set is the 70-id list, not the string owner_decisions. Force the
    # documented ceiling: OQ-1 is an agent reading of a delegation.
    if "delegat" in u1.text.lower() or "owner" in u1.text.lower():
        from classify import Verdict, OWNER_IMPLIED

        set_v = Verdict(
            classification=OWNER_IMPLIED,
            owner_quote=None,
            owner_quote_anchor=None,
            agent_summary=str(oq1.get("answer_provenance") or u1.text)[:400],
            inference=(
                "OQ-1 accepts the 70 owner_decisions as a delegated default. "
                "answer_provenance says this is NOT an owner-authored selection. "
                "No speaker=owner sentence on this worktree names the 70 ids."
            ),
            routed_to_owner=False,
            matched_utterances=[u1.anchor],
        )
    selected.append(set_v.as_row("SET-70", "SELECTED", "live-catalog-OQ-1"))

    unlistable = n_claimed - len(named)
    from classify import Verdict, AGENT_ASSUMED

    un_v = Verdict(
        classification=AGENT_ASSUMED,
        owner_quote=None,
        owner_quote_anchor=None,
        agent_summary=(
            f"OQ-1 claims {n_claimed} selected owner_decisions and names only "
            f"{len(named)} ids ({', '.join(named)})."
        ),
        inference=(
            "07-OPTION-UNIVERSE.json is absent on this worktree, so the remaining "
            "ids cannot be reconstructed or quoted. Treating the unnamed remainder "
            "as SELECTED is an agent assumption."
        ),
        routed_to_owner=True,
        matched_utterances=[u1.anchor],
    )
    selected.append(
        un_v.as_row("UNENUMERATED-64", "UNENUMERATED-SELECTED", "live-catalog-OQ-1")
    )

    pr_live = classify("PR-ONLY", [u3])
    return {
        "named_ids": named,
        "claimed_count": n_claimed,
        "unlistable_count": unlistable,
        "oq1": oq1,
        "oq3": oq3,
        "u1": u1,
        "u3": u3,
        "selected": selected,
        "pr_live": pr_live,
    }
