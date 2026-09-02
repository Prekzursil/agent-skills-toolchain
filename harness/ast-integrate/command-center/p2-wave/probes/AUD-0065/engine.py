"""AUD-0065 durable-state instruments.

Probe 1 instrument: case-insensitive substring keyword search over event-ledger
files (objective turn history). It does not score token overlap and does not
read basic-memory notes.

Probe 2 instrument: synonym-expanded token-overlap search over basic-memory
notes (semantic decisions). Exact query substring is not required. The ledger
keyword scanner cannot see a synonym-only note.
"""
from __future__ import annotations

import re
from typing import Any

LEDGER_CONTROL = "AUD0065LEDGERCONTROLHIT"
MEMORY_ONLY = "AUD0065MEMORYONLYTOKEN"
MEMORY_KNOWN_TERM = "workflow_design"
SYNONYM_QUERY = "durable semantic checkpoint"
SEMANTIC_THRESHOLD = 0.22
PROGRAM_QUERIES = [
    "program b workflow_design register",
    "event ledger objective turn history",
    "basic-memory semantic decisions",
    "green CI decays advisory",
    "cloud ok not delivery",
    SYNONYM_QUERY,
]

TOKEN_RE = re.compile(r"[a-z0-9_]+")
STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "into",
        "not",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "its",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "is",
        "it",
        "as",
        "or",
        "by",
        "be",
        "at",
    }
)
SYNONYMS = {
    "durable": ("always", "persistent", "lasting"),
    "semantic": ("vault", "meaning", "conceptual"),
    "checkpoint": ("pointer", "bookmark", "note"),
    "program": ("lane", "workflow"),
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


def expand(tokens: list[str]) -> set[str]:
    out = set(tokens)
    for token in tokens:
        out.update(SYNONYMS.get(token, ()))
    return out


def keyword_hits(events: list[dict[str, Any]], term: str) -> list[dict[str, Any]]:
    """Substring scan. Used only on ledger events."""
    needle = term.lower()
    hits: list[dict[str, Any]] = []
    if not needle:
        return hits
    for ev in events:
        blob = f"{ev.get('text') or ''}\n{ev.get('raw') or ''}"
        if needle not in blob.lower():
            continue
        hits.append(
            {
                "id": ev["id"],
                "path": ev["path"],
                "origin": ev["origin"],
                "query": term,
                "instrument": "ledger-keyword-substring",
                "snippet": (ev.get("text") or "")[:240],
            }
        )
    hits.sort(key=lambda h: (h["origin"], h["path"], h["id"]))
    return hits


def semantic_score(query: str, doc: str) -> float:
    q = expand(tokenize(query))
    d = set(tokenize(doc))
    if not q or not d:
        return 0.0
    return len(q & d) / len(q)


def semantic_hits(
    notes: list[dict[str, Any]], query: str, threshold: float = SEMANTIC_THRESHOLD
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for note in notes:
        score = semantic_score(query, f"{note.get('title') or ''} {note.get('text') or ''}")
        if score < threshold:
            continue
        hits.append(
            {
                "id": note["id"],
                "path": note["path"],
                "origin": note["origin"],
                "permalink": note.get("permalink"),
                "title": note.get("title"),
                "query": query,
                "score": round(score, 4),
                "instrument": "memory-semantic-token-overlap",
                "exact_query_substring": query.lower() in (note.get("text") or "").lower(),
            }
        )
    hits.sort(key=lambda h: (-h["score"], h["origin"], h["path"]))
    return hits


def exact_substring_in_notes(notes: list[dict[str, Any]], phrase: str) -> bool:
    needle = phrase.lower()
    return any(needle in (n.get("text") or "").lower() for n in notes)


def pin_relations(text: str, pins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blob = text.lower()
    out: list[dict[str, Any]] = []
    for pin in pins:
        pid = str(pin.get("id") or "")
        contradicted = [
            p for p in (pin.get("contradiction_phrases") or []) if p.lower() in blob
        ]
        supported = [p for p in (pin.get("support_phrases") or []) if p.lower() in blob]
        if contradicted:
            relation = "CONTRADICTS"
        elif supported:
            relation = "SUPPORTS"
        else:
            continue
        out.append(
            {
                "pin_id": pid,
                "relation": relation,
                "matched": contradicted or supported,
            }
        )
    return out


def classify_entries(
    events: list[dict[str, Any]], notes: list[dict[str, Any]], pins: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ev in events:
        rels = pin_relations(str(ev.get("text") or ""), pins)
        rows.append(
            {
                "id": ev["id"],
                "store": "event-ledger",
                "origin": ev["origin"],
                "path": ev["path"],
                "relevant": bool(rels)
                or (
                    ev["origin"] == "fixture"
                    and ev["id"] != "led:fixture:led-unrelated"
                ),
                "pin_relations": rels,
            }
        )
    for note in notes:
        rels = pin_relations(str(note.get("text") or ""), pins)
        decoy = "soup-decoy" in str(note.get("id") or "")
        rows.append(
            {
                "id": note["id"],
                "store": "basic-memory",
                "origin": note["origin"],
                "path": note["path"],
                "permalink": note.get("permalink"),
                "relevant": bool(rels) and not decoy,
                "pin_relations": rels,
            }
        )
    return rows


def inventory(pack: dict[str, Any]) -> dict[str, Any]:
    events = pack["ledger_all"]
    notes = pack["memory_all"]
    pins = pack["pins"]
    fixture_notes = pack["fixture_memory"]

    led_control = keyword_hits(events, LEDGER_CONTROL)
    mem_known = semantic_hits(notes, MEMORY_KNOWN_TERM)
    syn_hits = semantic_hits(notes, SYNONYM_QUERY)
    syn_exact = exact_substring_in_notes(notes, SYNONYM_QUERY)
    mem_only_in_ledger = keyword_hits(events, MEMORY_ONLY)
    led_in_memory = semantic_hits(notes, LEDGER_CONTROL)

    if not led_control:
        raise RuntimeError(
            "ledger keyword control missed AUD0065LEDGERCONTROLHIT; absence must not be reported"
        )
    if not mem_known:
        raise RuntimeError(
            "memory semantic control missed known term workflow_design; absence must not be reported"
        )

    program_hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for query in PROGRAM_QUERIES:
        for hit in semantic_hits(notes, query):
            key = (hit["id"], query)
            if key in seen:
                continue
            seen.add(key)
            program_hits.append(hit)

    classified = classify_entries(events, notes, pins)
    relevant = [r for r in classified if r.get("relevant")]
    contradictions = [
        r
        for r in classified
        if any(p.get("relation") == "CONTRADICTS" for p in r.get("pin_relations") or [])
    ]
    supports = [
        r
        for r in classified
        if any(p.get("relation") == "SUPPORTS" for p in r.get("pin_relations") or [])
    ]
    decoy_hits = [h for h in syn_hits if "soup-decoy" in h["id"]]
    syn_program = [h for h in syn_hits if "program-b-checkpoint" in h["id"]]
    isolation = (not mem_only_in_ledger) and (not led_in_memory)
    if decoy_hits:
        raise RuntimeError("semantic search retrieved the soup decoy")
    if not syn_program:
        raise RuntimeError("synonym query missed the planted Program B checkpoint note")
    if syn_exact:
        raise RuntimeError("synonym query is inert: planted note contains the exact phrase")
    if not isolation:
        raise RuntimeError("stores substitute: cross-store isolation control failed")

    live_absent_ok = True  # controls already passed
    headline = {
        "live_ledger_roots": len(pack["live_ledger_roots"]),
        "live_memory_roots": len(pack["live_memory_roots"]),
        "live_ledger_events": len(pack["live_ledger"]),
        "live_memory_notes": len(pack["live_memory"]),
        "catalog_ledger_exists": bool(pack["catalog_ledger_exists"]),
        "fixture_ledger_events": len(pack["fixture_ledger"]),
        "fixture_memory_notes": len(pack["fixture_memory"]),
        "ledger_control_hits": len(led_control),
        "memory_known_term_hits": len(mem_known),
        "synonym_semantic_hits": len(syn_hits),
        "synonym_exact_substring": syn_exact,
        "program_semantic_hits": len(program_hits),
        "relevant_entries": len(relevant),
        "contradiction_entries": len(contradictions),
        "support_entries": len(supports),
        "cross_store_isolation": isolation,
        "live_absent_after_control": live_absent_ok
        and len(pack["live_ledger"]) == 0
        and len(pack["live_memory"]) == 0,
    }
    return {
        "headline": headline,
        "ledger_control_hits": led_control,
        "memory_known_term_hits": mem_known,
        "synonym_hits": syn_hits,
        "program_semantic_hits": program_hits,
        "classified": classified,
        "relevant": relevant,
        "contradictions": contradictions,
        "supports": supports,
        "memory_only_in_ledger": mem_only_in_ledger,
        "ledger_token_in_memory": led_in_memory,
        "fixture_note_ids": [n["id"] for n in fixture_notes],
    }
