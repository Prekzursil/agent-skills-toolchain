"""Planted dual-backend corpus for RES-0190 breadth-versus-depth measurement.

Gold `mechanism_id` is test-only. The live engine never reads it; it clusters
with tools/command-center/mechanism_dedup.py (MERGE = both detectors fire).
"""
from __future__ import annotations

from typing import Any

QUESTIONS: list[dict[str, str]] = [
    {
        "id": "Q-DEDUP",
        "text": (
            "Which rule collapses two claims that describe the same mechanism "
            "while keeping a genuine one-parameter fork apart?"
        ),
    },
    {
        "id": "Q-G1",
        "text": (
            "Which live signals constitute G-1 delivery, and which ledger "
            "fields are not delivery?"
        ),
    },
    {
        "id": "Q-LINEAGE",
        "text": (
            "Which omitted claim-record field must FAIL validation rather "
            "than warn, and what lineage tuple is required?"
        ),
    },
]

# (mechanism_id, docs_abstract, code_abstract, appendix)
# Paraphrase pairs are calibrated to MERGE; cross-mechanism pairs stay DISTINCT.
Q1_MECHS: list[tuple[str, str, str, str]] = [
    (
        "Q1-ANDGATE",
        "Mechanism-level distinctness uses the CC-0020 AND-gate: auto-MERGE only when token Jaccard and embedding cosine both fire.",
        "Mechanism-level distinctness uses the CC-0020 AND-gate: auto-MERGE only when token Jaccard and embedding cosine both fire on the pair.",
        "AND-gate appendix: lexical fire without embedding fire is not enough for auto-MERGE.",
    ),
    (
        "Q1-LEXONLY",
        "Lexical Jaccard used alone is a string comparator and cannot be the distinctness rule for verified claims.",
        "Lexical Jaccard used alone is a string comparator and cannot be the distinctness rule for verified claims at all.",
        "Lexical-only appendix: a near-copy MERGE is string equality, not mechanism identity.",
    ),
    (
        "Q1-EMBONLY",
        "Embedding-only fire is ADJUDICATE not auto-MERGE so a high cosine alone never collapses a distinct unit.",
        "Embedding-only fire is ADJUDICATE not auto-MERGE so a high cosine alone never collapses a distinct unit here.",
        "Embedding-only appendix: ADJUDICATE is a review cost, not an auto-collapse.",
    ),
    (
        "Q1-OVERMERGE",
        "An auto-MERGE on a gold-distinct pair destroys a work unit; that over-merge is the fatal error direction.",
        "An auto-MERGE on a gold-distinct pair destroys a work unit; that over-merge is the fatal error direction today.",
        "Over-merge appendix: destroying a unit cannot be undone by later review.",
    ),
    (
        "Q1-UNDERMERGE",
        "An under-merge of gold-same paraphrases only costs review time and does not destroy a work unit.",
        "An under-merge of gold-same paraphrases only costs review time and does not destroy a work unit itself.",
        "Under-merge appendix: extra review is cheap compared with losing a unit.",
    ),
    (
        "Q1-FORK",
        "A one-parameter fork that adds a timeout conjunct is a true distinction from the dual-signal completion gate.",
        "A one-parameter fork that adds a timeout conjunct is a true distinction from the dual-signal completion gate now.",
        "Fork appendix: the extra conjunct changes the completion predicate.",
    ),
]

Q2_MECHS: list[tuple[str, str, str, str]] = [
    (
        "Q2-PROBES",
        "G-1 delivery requires live named probes to re-run exit 0 and a per-unit manifest sha256 match of the catalog output_path.",
        "G-1 delivery requires live named probes to re-run exit 0 and a per-unit manifest sha256 match of the catalog output_path itself.",
        "Probe appendix: cloud ok true is outside this predicate.",
    ),
    (
        "Q2-CLOUDOK",
        "Cloud ok equals true is not G-1 delivery and must not be treated as a completion predicate.",
        "Cloud ok equals true is not G-1 delivery and must not be treated as a completion predicate here.",
        "Cloud appendix: a remote ledger tick is not a live probe.",
    ),
    (
        "Q2-BLOCKED",
        "A self-declared BLOCKED artifact fails G-1 even when the file exists and parses as JSON.",
        "A self-declared BLOCKED artifact fails G-1 even when the file exists and parses as JSON today.",
        "Blocked appendix: existence is not success.",
    ),
    (
        "Q2-SENTINEL",
        "The catalog completion sentinel string must appear in the live artifact text or G-1 reports sentinel-absent.",
        "The catalog completion sentinel string must appear in the live artifact text or G-1 reports sentinel-absent now.",
        "Sentinel appendix: the string is a substring check on the artifact bytes.",
    ),
    (
        "Q2-MANIFEST",
        "The per-unit UNIT-ARTIFACT-MANIFEST row sha256 must match the live catalog output_path bytes.",
        "The per-unit UNIT-ARTIFACT-MANIFEST row sha256 must match the live catalog output_path bytes exactly.",
        "Manifest appendix: LF-normalized sha256, not git blob hashes.",
    ),
    (
        "Q2-GLOBALWR",
        "Running global unit_manifest.py --write is forbidden for G-1 per-unit delivery on this wave.",
        "Running global unit_manifest.py --write is forbidden for G-1 per-unit delivery on this wave today.",
        "Write appendix: per-unit UNIT-ARTIFACT-MANIFEST.json is the allowed registration.",
    ),
]

Q3_MECHS: list[tuple[str, str, str, str]] = [
    (
        "Q3-LINEAGE",
        "A claim record missing source_lineage must FAIL validation rather than warn.",
        "A claim record missing source_lineage must FAIL validation rather than warn at ingest.",
        "Lineage appendix: fail-closed is the negative control for RES-0001 consumers.",
    ),
    (
        "Q3-KENT",
        "Every load-bearing claim must carry a Sherman-Kent confidence band from the closed almost-certain to remote set in the schema validation envelope.",
        "Every load-bearing claim must carry a Sherman-Kent confidence band from the closed almost-certain to remote set in the schema validation envelope now.",
        "Kent appendix: almost-certain, probable, even, improbable, remote schema validation.",
    ),
    (
        "Q3-TWOSIG",
        "Each load-bearing claim needs two mechanically independent signals; repeating one probe is still one signal.",
        "Each load-bearing claim needs two mechanically independent signals; repeating one probe is still one signal only.",
        "Two-signal appendix: a second shell or a second field counts; a rerun does not.",
    ),
    (
        "Q3-URLTS",
        "Source lineage requires a resolved URL, a fetch timestamp, and a sha256 of the fetched bytes together.",
        "Source lineage requires a resolved URL, a fetch timestamp, and a sha256 of the fetched bytes together here.",
        "URL-ts appendix: path-only citations without sha256 are incomplete lineage.",
    ),
    (
        "Q3-PATH",
        "Each claim names an independent verification path a reviewer can run without trusting the author summary.",
        "Each claim names an independent verification path a reviewer can run without trusting the author summary itself.",
        "Path appendix: the named probe is the verification path for this unit.",
    ),
    (
        "Q3-WARN",
        "Treating a missing source_lineage as a warning would let an uncheckable claim gate a decision.",
        "Treating a missing source_lineage as a warning would let an uncheckable claim gate a decision today.",
        "Warn appendix: that policy is the known-broken validator state.",
    ),
]

ORPHANS: dict[str, list[tuple[str, str]]] = {
    "Q-DEDUP": [
        (
            "Q1-ORPHAN",
            "A singleton source with no second backend peer cannot be verified under the two-signal rule.",
        ),
        (
            "Q1-QUOTE",
            "A remembered quotation without fetched bytes is not a source and cannot verify a claim.",
        ),
        (
            "Q1-FOLK",
            "Operator folklore is not a backend and cannot supply the second independent signal.",
        ),
        (
            "Q1-CACHE",
            "A cached summary with no sha256 of origin bytes cannot enter the verified set.",
        ),
        (
            "Q1-SLIDE",
            "A vendor slide with no retrievable URL cannot enter the verified set.",
        ),
    ],
    "Q-G1": [
        (
            "Q2-ORPHAN",
            "A delivery claim supported by only the cloud ledger cannot be verified on this worktree.",
        ),
        (
            "Q2-RUMOR",
            "A hallway report that probes passed, with no command transcript, cannot verify G-1.",
        ),
        (
            "Q2-SCREEN",
            "A screenshot of a CI badge without the log bytes cannot verify live probe exit codes.",
        ),
        (
            "Q2-MEMO",
            "A retrospective memo that the unit shipped cannot replace the manifest sha256 match.",
        ),
        (
            "Q2-TICKET",
            "A tracker ticket marked done is not a live named probe and cannot verify G-1.",
        ),
    ],
    "Q-LINEAGE": [
        (
            "Q3-ORPHAN",
            "A claim citing an unread private inbox cannot be verified from this worktree.",
        ),
        (
            "Q3-HEARSAY",
            "A second-hand paraphrase of a missing schema file cannot supply source_lineage.",
        ),
        (
            "Q3-STUB",
            "A TODO placeholder in a claim registry is not lineage and cannot pass validation.",
        ),
        (
            "Q3-ORAL",
            "An oral briefing without fetched bytes cannot populate resolved URL or sha256.",
        ),
        (
            "Q3-MIRROR",
            "A mirror URL that was never fetched has no sha256 and cannot complete lineage.",
        ),
    ],
}

BACKENDS: tuple[str, str] = ("docs-backend", "code-backend")


def _body(abstract: str, appendix: str) -> str:
    return f"{abstract} {appendix}"


def _src(
    sid: str,
    question_id: str,
    backend: str,
    mechanism_id: str,
    companion_id: str | None,
    abstract: str,
    body: str,
    verifiable: bool,
) -> dict[str, Any]:
    return {
        "id": sid,
        "question_id": question_id,
        "backend": backend,
        "mechanism_id": mechanism_id,
        "companion_id": companion_id,
        "abstract": abstract,
        "body": body,
        "verifiable": verifiable,
    }


def sources_for_question(
    question_id: str, mechs: list[tuple[str, str, str, str]]
) -> list[dict[str, Any]]:
    """18 sources: s01-s06 docs mechs, s07+s09-s12 orphans, s08 docs paraphrase of mech0, s13-s18 code peers."""
    qslug = {"Q-DEDUP": "q1", "Q-G1": "q2", "Q-LINEAGE": "q3"}[question_id]
    out: list[dict[str, Any]] = []
    orphans = ORPHANS[question_id]
    # s01-s06: docs, companions s13-s18
    for i, (mid, docs_abs, code_abs, extra) in enumerate(mechs, start=1):
        sid = f"{qslug}-s{i:02d}"
        peer = f"{qslug}-s{12 + i:02d}"
        out.append(
            _src(
                sid,
                question_id,
                BACKENDS[0],
                mid,
                peer,
                docs_abs,
                _body(docs_abs, extra),
                True,
            )
        )
    # s07 orphan
    omid, oabs = orphans[0]
    out.append(
        _src(
            f"{qslug}-s07",
            question_id,
            BACKENDS[0],
            omid,
            None,
            oabs,
            _body(oabs, "No companion backend row exists for this source."),
            False,
        )
    )
    # s08 docs paraphrase of first mechanism (same companion as s01)
    mid0, _d, code0, extra0 = mechs[0]
    out.append(
        _src(
            f"{qslug}-s08",
            question_id,
            BACKENDS[0],
            mid0,
            f"{qslug}-s13",
            code0,  # docs-backend carrying the code-paraphrase wording
            _body(code0, extra0),
            True,
        )
    )
    # s09-s12 remaining orphans
    for j, (omid, oabs) in enumerate(orphans[1:5], start=9):
        out.append(
            _src(
                f"{qslug}-s{j:02d}",
                question_id,
                BACKENDS[0],
                omid,
                None,
                oabs,
                _body(oabs, "No companion backend row exists for this source."),
                False,
            )
        )
    # s13-s18 code peers for s01-s06
    for i, (mid, docs_abs, code_abs, extra) in enumerate(mechs, start=1):
        sid = f"{qslug}-s{12 + i:02d}"
        primary = f"{qslug}-s{i:02d}"
        out.append(
            _src(
                sid,
                question_id,
                BACKENDS[1],
                mid,
                primary,
                code_abs,
                _body(code_abs, extra),
                True,
            )
        )
    out.sort(key=lambda r: r["id"])
    return out


def all_sources() -> list[dict[str, Any]]:
    blocks = [
        sources_for_question("Q-DEDUP", Q1_MECHS),
        sources_for_question("Q-G1", Q2_MECHS),
        sources_for_question("Q-LINEAGE", Q3_MECHS),
    ]
    rows: list[dict[str, Any]] = []
    for block in blocks:
        rows.extend(block)
    return rows


def planted_pairs() -> list[dict[str, Any]]:
    """Gold pairs for probe2 both-states: paraphrases MERGE, cross DISTINCT."""
    pairs: list[dict[str, Any]] = []
    n = 0
    for qid, mechs in (
        ("Q-DEDUP", Q1_MECHS),
        ("Q-G1", Q2_MECHS),
        ("Q-LINEAGE", Q3_MECHS),
    ):
        for mid, docs_abs, code_abs, extra in mechs:
            n += 1
            pairs.append(
                {
                    "id": f"PARA-{n:02d}",
                    "question_id": qid,
                    "mechanism_id": mid,
                    "gold_same": True,
                    "left": _body(docs_abs, extra),
                    "right": _body(code_abs, extra),
                }
            )
        # three cross pairs from first three mechs
        for i in range(3):
            a = mechs[i]
            b = mechs[i + 1]
            n += 1
            pairs.append(
                {
                    "id": f"CROSS-{n:02d}",
                    "question_id": qid,
                    "mechanism_id": f"{a[0]}!={b[0]}",
                    "gold_same": False,
                    "left": _body(a[1], a[3]),
                    "right": _body(b[1], b[3]),
                }
            )
    return pairs


def corpus_doc() -> dict[str, Any]:
    return {
        "unit_id": "RES-0190",
        "questions": QUESTIONS,
        "backends": list(BACKENDS),
        "sources": all_sources(),
        "planted_pairs": planted_pairs(),
        "notes": (
            "Local dual-backend planted corpus. Gold mechanism_id is for "
            "probe2 labels only. Engine clustering uses mechanism_dedup MERGE."
        ),
    }
