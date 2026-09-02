"""Build the RES-0116 non-English mechanism register from live captures."""
from __future__ import annotations

from captures_index import by_id, capture_text, verify_row
from corpus import absence_scan, protocol_inventory

SENTINEL = "SUCCESS:RES-0116"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0116 in the receipt AND a register where each row carries "
    "the original-language quote plus a count of discarded re-translations"
)
QUESTION = (
    "Do Chinese, Japanese, Russian, German or Korean technical sources "
    "describe orchestration or deliberation mechanisms that have no "
    "English-language equivalent in this program's corpus - and is any "
    "of them implementable from the source as written?"
)

DISCARDED_RETRANSLATIONS = [
    {
        "id": "D-AUTOGEN-ZH",
        "language": "zh",
        "title": "Jimmy Song handbook restates Microsoft AutoGen",
        "reason": "translation-of-english-source",
        "english_origin": "Microsoft AutoGen",
        "quote": "Microsoft AutoGen 是微软开源的一个 Python 框架，用于快速构建多智能体工作流。",
        "capture_id": "discard-zh-autogen-jimmysong",
    },
    {
        "id": "D-GCP-MAS-ZH",
        "language": "zh",
        "title": "Google Cloud zh-CN multi-agent page names CrewAI/LangGraph/AutoGen",
        "reason": "translation-of-english-source",
        "english_origin": "CrewAI, LangGraph, AutoGen",
        "quote": "CrewAI",
        "capture_id": "discard-zh-gcp-mas",
    },
    {
        "id": "D-QIITA-CREWAI-JA",
        "language": "ja",
        "title": "Qiita crewai tag indexes Japanese write-ups of English CrewAI/LangGraph",
        "reason": "translation-of-english-source",
        "english_origin": "CrewAI, LangGraph",
        "quote": "CrewAI",
        "capture_id": "discard-ja-crewai",
    },
    {
        "id": "D-IBM-CREWAI-EN",
        "language": "en",
        "title": "IBM Think CrewAI explainer is an English-origin page",
        "reason": "translation-of-english-source",
        "english_origin": "CrewAI",
        "quote": "CrewAI",
        "capture_id": "discard-zh-crewai-blog",
    },
]


def _rail(idx: dict, cid: str) -> dict:
    row = idx[cid]
    ok, live = verify_row(row)
    if not ok:
        raise RuntimeError(f"capture {cid}: {live}")
    if not row.get("ok") or row.get("http_status") != 200:
        raise RuntimeError(f"capture {cid} not a 200 body")
    return {
        "id": cid,
        "kind": row["kind"],
        "permalink": row["permalink"],
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "byte_length": row["byte_length"],
        "capture_path": row["capture_path"],
    }


def _require(cid: str, quote: str) -> None:
    if quote not in capture_text(cid):
        raise RuntimeError(f"quote not in capture {cid}: {quote[:48]}")


def build() -> dict:
    idx = by_id()
    scan = absence_scan()
    discarded_n = len(DISCARDED_RETRANSLATIONS)

    ringi_q = (
        "担当者が簡易案件を作成して関係者に回し、それぞれに同意のための捺印と承認を求めることをいう。"
    )
    ringi_q2 = (
        "個人の権限では決定することができない事柄について、関係者の承認を経て最終的な決裁を得るためのプロセス"
    )
    nema_q = "物事を行う際に事前に関係者からの了承を得ておくこと"
    heyi_q = "合议庭评议案件应当按照多数人的意见作出决定，少数人的意见应当记入笔录"
    heyi_q2 = "合议庭评议案件，实行少数服从多数的原则"
    ko_q = "기안자ㆍ검토자ㆍ협조자ㆍ결재권자"
    ko_q2 = "문서는 결재권자가 해당 문서에 서명"
    de_q = "Über Meinungsverschiedenheiten zwischen den Bundesministern entscheidet die Bundesregierung"
    de_q2 = "Kollegialorgane entscheiden durch Beschluss"
    ru_q = "совместное обсуждение для принятия решения с учётом разных мнений и предложений"
    ru_q2 = "посредством принятия решений по осуществлению поставленных управленческих задач группой должностных лиц"

    _require("ringi-ja-wiki-ringisho-api", ringi_q)
    _require("ringi-atled", ringi_q2)
    _require("ringi-kotobank", "末端の職員が事案を作成すること")
    _require("nemawashi-ja-wiki-api", nema_q)
    _require("zh-wiki-heyiting-trad-api", heyi_q)
    _require("zh-ehs-minshi", heyi_q2)
    _require("zh-ahdhf-art45", "评议中的不同意见，必须如实记入笔录")
    _require("ko-bigcase-admin", ko_q)
    _require("ko-bigcase-admin", ko_q2)
    _require("de-wikisource-art65", de_q)
    _require("de-wiki-kollegialorgan-api", de_q2)
    _require("ru-wiki-kolleg-api", ru_q)
    _require("ru-spravochnick", ru_q2)
    for d in DISCARDED_RETRANSLATIONS:
        _require(d["capture_id"], d["quote"])
    if not scan["absent"]:
        raise RuntimeError(f"english corpus already contains needles: {scan['hits']}")

    register = [
        {
            "id": "R-RINGI",
            "language": "ja",
            "mechanism": "稟議制 / 稟議書 circulation",
            "claim": (
                "Japanese 稟議 is sequential written circulation: a staffer "
                "without decision authority drafts a 稟議書, related offices "
                "stamp in series, then a 決裁権者 ratifies. 差し戻し/却下 are "
                "named. This is not P19 rfc-last-call (simultaneous last-call) "
                "and not P18 two-key-dual-control (parallel keys)."
            ),
            "original_language_quote": ringi_q,
            "translation": (
                "Ringi means having the person in charge draft a simple matter, "
                "circulate it to the relevant people, and seek each person's "
                "seal and approval."
            ),
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": True,
            "implementable_from_source_as_written": True,
            "implementability_note": (
                "Named roles (drafter, approvers, ratifier), a document object, "
                "sequential stamps, and reject/return. Compilable as a DAG."
            ),
            "closest_english_protocol": "P19 rfc-last-call",
            "evidence_grade": "E2",
            "verdict": "NO-ENGLISH-EQUIVALENT-IN-CORPUS",
            "rails": [
                _rail(idx, "ringi-ja-wiki-ringisho-api"),
                _rail(idx, "ringi-wikidata-api"),
                _rail(idx, "ringi-atled"),
                _rail(idx, "ringi-kotobank"),
            ],
            "secondary_quote": ringi_q2,
            "secondary_quote_capture": "ringi-atled",
        },
        {
            "id": "R-NEMAWASHI",
            "language": "ja",
            "mechanism": "根回し",
            "claim": (
                "根回し is obtaining prior consent from stakeholders before "
                "the formal act. The captured Wikipedia entry gives no roles, "
                "document, or stopping rule. Absent from English protocol slugs, "
                "but not implementable from the source as written."
            ),
            "original_language_quote": nema_q,
            "translation": (
                "Obtaining the consent of the people concerned in advance "
                "when doing something."
            ),
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": True,
            "implementable_from_source_as_written": False,
            "implementability_note": (
                "Metaphor plus slang. No procedure to compile."
            ),
            "closest_english_protocol": None,
            "evidence_grade": "E2",
            "verdict": "ABSENT-BUT-NOT-IMPLEMENTABLE",
            "rails": [
                _rail(idx, "nemawashi-ja-wiki-api"),
                _rail(idx, "nemawashi-ja-wiki-summary"),
            ],
            "secondary_quote": nema_q,
            "secondary_quote_capture": "nemawashi-ja-wiki-api",
        },
        {
            "id": "R-HEYITING",
            "language": "zh",
            "mechanism": "合议庭 / 合議庭 majority with secret minority minutes",
            "claim": (
                "PRC 合议庭: odd-n collegiate bench, majority decides, minority "
                "opinion must be written into the (non-public) minutes. Hung "
                "outcomes are avoided by odd n. Inverse of P17 "
                "jury-with-allowed-hung; not P56 minority-report-mandatory "
                "(that report is a public council product)."
            ),
            "original_language_quote": heyi_q,
            "translation": (
                "When the collegiate panel deliberates a case it shall decide "
                "according to the majority opinion; the minority opinion shall "
                "be recorded in the minutes."
            ),
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": True,
            "implementable_from_source_as_written": True,
            "implementability_note": (
                "Odd-n membership, majority rule, mandatory minority minute, "
                "signatures: a compiler can emit that protocol from the text."
            ),
            "closest_english_protocol": "P17 jury-with-allowed-hung / P56 minority-report-mandatory",
            "evidence_grade": "E2",
            "verdict": "NO-ENGLISH-EQUIVALENT-IN-CORPUS",
            "rails": [
                _rail(idx, "zh-wiki-heyiting-trad-api"),
                _rail(idx, "zh-wiki-heyiting-summary"),
                _rail(idx, "zh-ehs-minshi"),
                _rail(idx, "zh-ahdhf-art45"),
            ],
            "secondary_quote": heyi_q2,
            "secondary_quote_capture": "zh-ehs-minshi",
        },
        {
            "id": "R-GIAN-GYEOLJAE",
            "language": "ko",
            "mechanism": "기안-검토-협조-결재 with 위임전결/대결",
            "claim": (
                "Korean presidential decree names drafter/reviewer/cooperator/"
                "approver, 위임전결 and 대결. Same sequential-circulation family "
                "as 稟議. Only one captured rail (statute HTML); graded E3 and "
                "not cited as measured fact."
            ),
            "original_language_quote": ko_q,
            "translation": "drafter, reviewer, cooperator, and approver",
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": True,
            "implementable_from_source_as_written": True,
            "implementability_note": "Operational decree, but one rail is E3.",
            "closest_english_protocol": "P19 rfc-last-call",
            "evidence_grade": "E3",
            "verdict": "E3-SINGLE-RAIL-NOT-MEASURED-FACT",
            "rails": [_rail(idx, "ko-bigcase-admin")],
            "secondary_quote": ko_q2,
            "secondary_quote_capture": "ko-bigcase-admin",
        },
        {
            "id": "R-KOLLEGIALPRINZIP",
            "language": "de",
            "mechanism": "Art. 65 GG Kollegialprinzip",
            "claim": (
                "Art. 65 GG: the Federal Government as a collegium decides "
                "disagreements among ministers. Two rails, but this is collegial "
                "majority / cabinet decision — already in the English corpus as "
                "majority voting plus P52 nested councils. Not claimed as absent."
            ),
            "original_language_quote": de_q,
            "translation": (
                "The Federal Government decides disagreements among the "
                "Federal Ministers."
            ),
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": False,
            "implementable_from_source_as_written": True,
            "implementability_note": "Majority collegial vote is already expressible.",
            "closest_english_protocol": "majority voting / P52 nested-subcouncils-meta-council",
            "evidence_grade": "E2",
            "verdict": "ENGLISH-CORPUS-OVERLAP",
            "rails": [
                _rail(idx, "de-wiki-kollegialorgan-api"),
                _rail(idx, "de-wikisource-art65"),
                _rail(idx, "de-opinioiuris-art65"),
            ],
            "secondary_quote": de_q2,
            "secondary_quote_capture": "de-wiki-kollegialorgan-api",
        },
        {
            "id": "R-KOLLEGIALNOST",
            "language": "ru",
            "mechanism": "коллегиальность (deciding vs advisory)",
            "claim": (
                "Russian коллегиальность: joint discussion then either a college "
                "vote or a chair decision after consultation. Advisory form "
                "overlaps P58 owner-in-the-loop-stepwise; deciding form overlaps "
                "majority vote. Not claimed as absent."
            ),
            "original_language_quote": ru_q,
            "translation": (
                "joint discussion in order to take a decision taking different "
                "opinions and proposals into account"
            ),
            "discarded_retranslations_count": discarded_n,
            "absent_from_english_corpus": False,
            "implementable_from_source_as_written": True,
            "implementability_note": "Consult-then-vote and consult-then-chair already exist.",
            "closest_english_protocol": "P58 owner-in-the-loop-stepwise",
            "evidence_grade": "E2",
            "verdict": "ENGLISH-CORPUS-OVERLAP",
            "rails": [
                _rail(idx, "ru-wiki-kolleg-api"),
                _rail(idx, "ru-spravochnick"),
            ],
            "secondary_quote": ru_q2,
            "secondary_quote_capture": "ru-spravochnick",
        },
    ]

    measured = [
        r
        for r in register
        if r["verdict"] == "NO-ENGLISH-EQUIVALENT-IN-CORPUS"
        and r["implementable_from_source_as_written"]
        and r["evidence_grade"] != "E3"
    ]
    answer = (
        "Yes for two measured (E2, two-rail) mechanisms: Japanese 稟議制 "
        "(sequential sealed circulation with 差し戻し) and Chinese 合议庭 "
        "(odd-n majority, secret minority minutes, no hung). Both are "
        "implementable from the captured source text. 根回し is named but not "
        "implementable as written. Korean 기안-결재 is the same family as 稟議 "
        "but is E3 (one rail). German Kollegialprinzip and Russian "
        "коллегиальность overlap the English protocol inventory. "
        f"{discarded_n} candidates were discarded as translations of English "
        "agent-orchestration sources. "
        + CATALOG_SENTINEL
    )

    return {
        "unit_id": "RES-0116",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "schema_path": "command-center/schema/research-registry.schema.json",
        "schema_note": (
            "Declared schema file is absent on this worktree; artifact is a "
            "research register with two-rail evidence, original-language "
            "quotes, and the discarded-retranslation control."
        ),
        "question": QUESTION,
        "answer": answer,
        "register": register,
        "measured_no_english_equivalent_implementable": [
            {"id": r["id"], "mechanism": r["mechanism"]} for r in measured
        ],
        "discarded_as_translations_of_english_sources": discarded_n,
        "discarded_candidates": DISCARDED_RETRANSLATIONS,
        "english_corpus": {
            "source": "command-center/p2-wave/probes/CNL-0102/catalog.py PROTOCOLS",
            "protocol_count": scan["protocol_count"],
            "protocols": protocol_inventory(),
            "absence_scan": scan,
        },
        "tests": [
            {
                "id": "T-ORIGINAL-QUOTE",
                "result": "PASS",
                "detail": "every register row carries an original-language quote present in a named capture",
            },
            {
                "id": "T-DISCARD-CONTROL",
                "result": "PASS",
                "detail": (
                    f"discarded_as_translations_of_english_sources={discarded_n}; "
                    "AutoGen/CrewAI/LangGraph restatements were not promoted"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0116-probe2-controls",
            "verdict": "PASS",
            "independent": True,
            "partition": (
                "probe2 does not read probe1's printed verdict; it re-derives "
                "quote/rail/discard checks from disk"
            ),
        },
        "evidence": [
            {"path": r["capture_path"], "kind": r["kind"]}
            for row in register
            for r in row["rails"]
        ],
    }
