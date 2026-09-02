#!/usr/bin/env python3
"""Labelled router regression rows for IMP-0398."""
from __future__ import annotations

from typing import Any


def _q(
    i: int,
    query: str,
    expected: list[str],
    rationale: str,
) -> dict[str, Any]:
    polarity = "NEGATIVE" if not expected else "POSITIVE"
    return {
        "id": f"q-{i:03d}",
        "query": query,
        "expected_capability_ids": list(expected),
        "rationale": rationale,
        "polarity": polarity,
    }


def build_queries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1

    def add(query: str, expected: list[str], rationale: str) -> None:
        nonlocal n
        rows.append(_q(n, query, expected, rationale))
        n += 1

    # Tail positives — these are the labelled intent. A popularity stub that
    # always returns web.search/file.read/shell.exec cannot hit these sets.
    add(
        "Build capability-index.json from six roots and survive a NUL-named file in a root.",
        ["skill.router.index-build"],
        "Exact IMP-0385 crawler job: six-root enumeration plus NUL survival.",
    )
    add(
        "Re-run index_build so per-root counts match an independent census to zero.",
        ["skill.router.index-build"],
        "Index rebuild with census parity is the index-build capability, not a web search.",
    )
    add(
        "Enumerate ~/.claude/skills and repo workflows/ into a single capability-index.json from six roots.",
        ["skill.router.index-build"],
        "Named six-root crawl; popular file.read/shell.exec do not produce the index.",
    )
    add(
        "Seed a capability root with a NUL-named file and assert the crawler does not abort.",
        ["skill.router.index-build"],
        "NUL-named file is the index-build regression, not generic shell.exec.",
    )
    add(
        "Does the crawler writing capability-index.json from six roots survive a root containing NUL-named files?",
        ["skill.router.index-build"],
        "Question restates the index-build contract; expected set is that one skill.",
    )
    add(
        "Scrub a planted secret-shaped token and an absolute user path from router telemetry.",
        ["skill.privacy.scrub"],
        "Privacy-scrub negative control: planted secret and path must be absent after scrub.",
    )
    add(
        "Run the telemetry scrub so a planted secret-shaped token never appears in the emitted JSON.",
        ["skill.privacy.scrub"],
        "Scrubber, not web search; expected set is privacy.scrub only.",
    )
    add(
        "Remove every absolute user path from a telemetry record before it leaves the estate.",
        ["skill.privacy.scrub"],
        "Absolute user path scrub is the privacy capability.",
    )
    add(
        "Assert privacy-scrub drops both a secret-shaped token and a home-directory path.",
        ["skill.privacy.scrub"],
        "Paired planted controls named in IMP-0397 tests_required.",
    )
    add(
        "Invoke the four-voice council skill: Architect, Skeptic, Pragmatist, Critic as static prompt sections.",
        ["skill.council.four-voice"],
        "Named four roles; not a shell or file-read task.",
    )
    add(
        "Draft a review using the four-voice council without compiling CouncilSpec policy.",
        ["skill.council.four-voice"],
        "Council prompt skill, explicitly not an executable policy compiler.",
    )
    add(
        "List the four-voice council roles Architect, Skeptic, Pragmatist, Critic for a design review.",
        ["skill.council.four-voice"],
        "Role list is the council skill's identity.",
    )
    add(
        "Read stored git blob bytes without using git archive on Windows.",
        ["skill.blob.provenance"],
        "Provenance helper forbids git archive; popular shell.exec would pick the wrong recipe.",
    )
    add(
        "Compare git cat-file, git show, and git archive on the same blob and keep the non-archive routes.",
        ["skill.blob.provenance"],
        "Three-route blob comparison is the provenance capability.",
    )
    add(
        "Replace every Windows git archive prescription with the stored git blob bytes helper.",
        ["skill.blob.provenance"],
        "Census-and-fix of archive recipes is blob provenance, not web.search.",
    )
    add(
        "Author a JSON schema that rejects a receipt missing its sentinel.",
        ["skill.schema.author"],
        "Schema-authoring task; always-top-3 popular tools do not write the schema.",
    )
    add(
        "Add a negative fixture proving a receipt without a sentinel is INVALID under the JSON schema that rejects a receipt missing its sentinel.",
        ["skill.schema.author"],
        "Negative fixture for sentinel absence is schema.author.",
    )
    add(
        "Tighten additionalProperties so a JSON schema that rejects a receipt missing its sentinel also rejects unknown keys.",
        ["skill.schema.author"],
        "Contract strictness work belongs to schema.author.",
    )
    add(
        "Corrupt one router description and assert the regression suite goes red.",
        ["skill.mutation.harness"],
        "Mutation harness: one description corruption must be observed as redness.",
    )
    add(
        "Delete one trigger row in the mutation harness and require the suite to fail closed.",
        ["skill.mutation.harness"],
        "Trigger-row deletion is a named mutation, not a popular generic tool.",
    )
    add(
        "Unpin the embedding model via the mutation harness and check the regression suite goes red.",
        ["skill.mutation.harness"],
        "Fourth mutation class; expected set is the harness only.",
    )
    add(
        "Edit a capability description and prove the next router call sees the change, not a stale cache.",
        ["skill.cache.invalidate"],
        "Cache invalidation on content hash plus mtime.",
    )
    add(
        "Recover from a truncated cache file using content hash plus mtime rather than serving an empty index as OK.",
        ["skill.cache.invalidate"],
        "Corrupted-cache recovery is cache.invalidate, not file.read alone.",
    )
    add(
        "Ban a capability that scores 0.99 and show the owner ban still excludes it.",
        ["skill.override.ban-pin"],
        "Ban-beats-score; popularity of the banned cap must not leak it back.",
    )
    add(
        "Pin a capability always-on and prove the budget ceiling does not drop it.",
        ["skill.override.ban-pin"],
        "Pin-survives-budget is the override layer.",
    )
    add(
        "Return typed NO-CAPABILITY-FITS with closest rejected candidates instead of injecting a weak match.",
        ["skill.nofit.terminal"],
        "No-fit terminal verdict; empty selection is explicit, not a popular tool dump.",
    )
    add(
        "For a labelled no-fit query, emit NO-CAPABILITY-FITS rather than injecting a weak match from the index.",
        ["skill.nofit.terminal"],
        "IMP-0396 no-fit path encoded as a positive expected capability (the no-fit emitter).",
    )

    # Popular-intent positives: expected is a SINGLE popular id, so exact-set
    # match against the three-id stub still misses. Included so the corpus is
    # not only tail queries.
    add(
        "Search the public web for the current Python jsonschema version.",
        ["skill.web.search"],
        "Web search intent; always-top-3 returns two extra popular ids, so exact match fails.",
    )
    add(
        "Read the file capability-index.json from disk.",
        ["skill.file.read"],
        "Singleton file.read; stub returns the whole popular triple.",
    )
    add(
        "Run a shell command to list ~/.claude/skills.",
        ["command.shell.exec"],
        "Singleton shell.exec listing; not the six-root index builder.",
    )

    # NEGATIVE: expected set empty. A router that always offers top-3 is wrong.
    negatives = [
        (
            "What will the weather be on Mars next Tuesday?",
            "No indexed capability forecasts planetary weather; expected set empty.",
        ),
        (
            "Write a sourdough starter schedule for a home kitchen.",
            "Cooking schedule is outside the capability index.",
        ),
        (
            "File my 1994 US federal tax return as if paper forms were still required.",
            "Historical tax filing is not a router capability.",
        ),
        (
            "Recommend a pediatric dentist in Reykjavik.",
            "Local medical referral is not in the indexed repertoire.",
        ),
        (
            "Tune a piano to A440 in a concert hall.",
            "Instrument tuning is not a capability in this index.",
        ),
        (
            "Diagnose a rash on a golden retriever from a photo.",
            "Veterinary diagnosis is outside the estate.",
        ),
        (
            "Plan a wedding seating chart for 180 guests.",
            "Event seating is not an indexed skill, command, or workflow.",
        ),
        (
            "Translate this restaurant menu into conversational Klingon.",
            "Constructed-language menu translation is not indexed.",
        ),
        (
            "What time does the ferry leave Nantucket in 2003?",
            "Historical ferry timetable is not a live capability.",
        ),
        (
            "Calculate the batting average of a fictional baseball player.",
            "Fictional sports stats are not a repertoire item.",
        ),
        (
            "How do I darn a wool sock with a wooden mushroom?",
            "Textile repair is not in capability-index.json.",
        ),
        (
            "Name three edible mosses on the Isle of Skye in winter.",
            "Foraging advice is a no-fit; expected set must stay empty.",
        ),
    ]
    for query, rationale in negatives:
        add(query, [], rationale)

    return rows


def stats(queries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(queries)
    n_neg = sum(1 for q in queries if str(q.get("polarity") or "").upper() == "NEGATIVE")
    if n_neg != sum(1 for q in queries if not (q.get("expected_capability_ids") or [])):
        raise ValueError("polarity NEGATIVE must match empty expected sets")
    return {
        "n": n,
        "n_negative": n_neg,
        "negative_fraction": n_neg / n if n else 0.0,
        "n_positive": n - n_neg,
    }
