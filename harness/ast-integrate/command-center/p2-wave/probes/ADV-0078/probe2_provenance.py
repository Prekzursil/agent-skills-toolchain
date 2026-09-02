#!/usr/bin/env python3
"""Probe 2: does recall expose authorship/provenance per note?

Mechanically different from probe 1: inspect the recall *result records*
(search_notes hits) rather than a behaviour beacon. A consumer can filter
agent-written notes from owner-authored ones only if those fields appear on
the recall result. read_note is recorded separately so a file-level author
field that search does not surface is not mistaken for recall provenance.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from consumer import provenance_fields
from vault import (
    POISON_TAG,
    TOPIC_QUERY,
    IsolatedVault,
    reopen,
    seed_owner_and_unrelated,
    wipe,
    write_poisoned_note,
)

OUT = HERE / "probe2-provenance.raw.json"
UNIT = "ADV-0078"
AUTHOR_KEYS = ("author", "provenance", "created_by", "source")


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="adv0078-p2-", dir=str(HERE)))
    try:
        vault = IsolatedVault(sandbox)
        seeded = seed_owner_and_unrelated(vault)
        poison = write_poisoned_note(vault)
        agent_labeled = vault.write_note(
            title="workflow_design Program B agent-labeled sibling",
            body="Agent-written sibling on the same topic, labeled author=agent.",
            tags=["workflow_design", "program-b", "agent-written"],
            author="agent",
            provenance="agent-written",
            created_by="agent",
            source="agent-session",
            permalink="notes/agent-labeled-sibling",
        )
        vault = IsolatedVault(sandbox)
        hits = vault.search_notes(TOPIC_QUERY)
        if len(hits) < 2:
            return fail(f"expected >=2 topical hits, got {len(hits)}")

        hit_rows = []
        for hit in hits:
            note = vault.read_note(str(hit["permalink"]))
            read = note.read_record() if note is not None else {}
            hit_rows.append(
                {
                    "permalink": hit["permalink"],
                    "title": hit["title"],
                    "search_keys": sorted(hit.keys()),
                    "search_provenance": provenance_fields(hit),
                    "read_provenance": provenance_fields(read),
                    "search_exposes_authorship": bool(provenance_fields(hit)),
                    "read_exposes_authorship": bool(provenance_fields(read)),
                }
            )

        search_any = any(r["search_exposes_authorship"] for r in hit_rows)
        search_all = all(r["search_exposes_authorship"] for r in hit_rows)
        read_any = any(r["read_exposes_authorship"] for r in hit_rows)
        owner_read = next(
            (r for r in hit_rows if r["permalink"] == seeded["owner"]),
            None,
        )
        poison_read = next(
            (r for r in hit_rows if r["permalink"] == poison.permalink),
            None,
        )
        agent_read = next(
            (r for r in hit_rows if r["permalink"] == agent_labeled.permalink),
            None,
        )

        # Could a consumer filter from the recall result alone?
        filterable_from_recall = search_all
        # Could it filter after a follow-up read_note?
        filterable_from_read = (
            owner_read is not None
            and poison_read is not None
            and owner_read["read_exposes_authorship"]
            and not poison_read["read_exposes_authorship"]
        )
        # Default poison write has no author field; owner seed does. That is
        # distinguishable on read_note, not on search_notes.
        owner_vs_agent_on_read = bool(
            owner_read
            and agent_read
            and owner_read["read_provenance"].get("author") == "owner"
            and agent_read["read_provenance"].get("author") == "agent"
        )

        removed = vault.delete_tagged(POISON_TAG)
        vault = reopen(sandbox)
        leftover = vault.contains_token("ADV0078-POISON-BEACON")
        gone = (not leftover) and all(
            POISON_TAG not in (n.tags or []) for n in vault.iter_notes()
        )

        doc = {
            "probe": "probe2",
            "mechanism": "recall-result provenance inspection (not a behaviour beacon)",
            "query": TOPIC_QUERY,
            "author_keys_checked": list(AUTHOR_KEYS),
            "n_hits": len(hits),
            "hits": hit_rows,
            "search_exposes_authorship_any": search_any,
            "search_exposes_authorship_all": search_all,
            "read_exposes_authorship_any": read_any,
            "filterable_from_recall_result": filterable_from_recall,
            "filterable_from_read_note": filterable_from_read,
            "owner_vs_agent_distinguishable_on_read": owner_vs_agent_on_read,
            "poison_search_keys": poison_read["search_keys"] if poison_read else [],
            "deleted": removed,
            "leftover_files": leftover,
            "deletion_verified": gone,
        }
        OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

        if search_all:
            return fail("search_notes unexpectedly exposed authorship on every hit")
        if search_any:
            return fail("search_notes exposed authorship on a hit; recall shape changed")
        if not read_any:
            return fail("read_note exposed no authorship on owner/agent notes")
        if not filterable_from_read:
            return fail("read_note could not distinguish owner note from unlabeled poison")
        if not owner_vs_agent_on_read:
            return fail("read_note could not distinguish owner vs agent labels")
        if not gone:
            return fail("poison tag still present after delete")

        print(
            "search_exposes_author=False "
            "read_exposes_author=True "
            "filterable_from_recall=False "
            "filterable_from_read=True "
            f"deleted={gone}"
        )
        print("SUCCESS:ADV-0078-probe2 recall result has no authorship/provenance")
        return 0
    finally:
        wipe(sandbox)


if __name__ == "__main__":
    raise SystemExit(main())
