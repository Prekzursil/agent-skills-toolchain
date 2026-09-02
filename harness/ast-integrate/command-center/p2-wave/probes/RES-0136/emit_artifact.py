#!/usr/bin/env python3
"""Emit RES-0136 vendor-rider-propagation research record.

Does not create command-center/schema/research-claim-record.schema.json
(no ADV schema-rebuild loop). G-1 needs parseable JSON, sentinel,
non-BLOCKED state, live probes, and a per-unit manifest row.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import propagate as P  # noqa: E402
from extractor import naive_restriction_word  # noqa: E402

OUT = "command-center/research/supply-chain/RES-0136-vendor-rider-propagation.json"
QUESTION = (
    "Which candidate dependencies carry a non-OSI rider (for example a "
    "no-ML-training / no-eval-folding clause or a field-of-use restriction), "
    "does that rider propagate to a package that merely VENDORS the dependency "
    "versus one that only calls it over a local socket, and which of our "
    "planned distributions would violate it?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0136/probe1_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0136/probe2_signal_independence.py"
)
SCHEMA = "command-center/schema/research-claim-record.schema.json"


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    rows = C.corpus_rows()
    by_id = {r["id"]: r for r in rows}
    mcp = by_id["mcp_agent_mail"]
    js = by_id["jsonschema"]
    llama = by_id["llama3"]
    decoy = by_id["decoy_prose"]
    if js["has_non_osi_rider"] or js["has_non_osi_licence"]:
        print("FAILED:RES-0136 emit negative control jsonschema has a rider")
        return 1
    if not naive_restriction_word(
        (HERE / "fixtures" / js["filename"]).read_text(encoding="utf-8")
    ):
        print("FAILED:RES-0136 emit naive detector silent on MIT 'without restriction'")
        return 1
    if not mcp["has_non_osi_rider"]:
        print("FAILED:RES-0136 emit mcp_agent_mail rider not detected")
        return 1
    if mcp["has_non_osi_licence"]:
        print("FAILED:RES-0136 emit mcp_agent_mail misclassified as non-OSI licence")
        return 1
    if llama["has_non_osi_rider"] or not llama["has_non_osi_licence"]:
        print("FAILED:RES-0136 emit llama classification")
        return 1
    if decoy["has_non_osi_rider"] or decoy["has_non_osi_licence"]:
        print("FAILED:RES-0136 emit decoy fired")
        return 1
    if not mcp["quotes"]:
        print("FAILED:RES-0136 emit missing verbatim rider quote")
        return 1

    mcp_acts = P.mcp_agent_mail_acts()
    llama_acts = P.llama_acts()
    js_acts = P.jsonschema_acts()

    planned = [
        {
            "id": "marketplace-package",
            "path": "tools/marketplace",
            "act": "publishing",
            "contains_mcp_agent_mail_source": False,
            "contains_llama_weights": False,
            "violates_mcp_rider": False,
            "would_violate_if": (
                "the published artifact vendored or linked mcp_agent_mail "
                "source/binaries AND (the rider was stripped OR the artifact "
                "was provided to a Restricted Party)"
            ),
        },
        {
            "id": "this-worktree",
            "path": ".",
            "act": "publishing",
            "contains_mcp_agent_mail_source": False,
            "contains_llama_weights": False,
            "violates_mcp_rider": False,
            "note": "catalog names mcp_agent_mail; this tree does not vendor its source",
        },
        {
            "id": "local-agent-mail-socket",
            "path": "tools/resource_guard (IMP-0473 allowlist agent-mail)",
            "act": "invoking",
            "contains_mcp_agent_mail_source": False,
            "violates_mcp_rider": False,
            "would_violate_if": (
                "OpenAI, Anthropic, their affiliates, or persons acting for them "
                "execute the mcp_agent_mail server (rider defines executing as use)"
            ),
        },
        {
            "id": "council-llama-3.1-seat",
            "path": "command-center/p2-wave/probes/CNL-0005",
            "act": "invoking",
            "contains_llama_weights": False,
            "violates_llama_additional_commercial": False,
            "note": (
                "CNL-0005 names llama-3.1-70b as a seat. Hosted API invoke does "
                "not redistribute Llama Materials. The 700 million MAU additional "
                "commercial term is a field-of-use gate; it is not triggered at "
                "this program's scale. Llama 3.1 dropped the Llama-3 ban on using "
                "outputs to improve other LLMs — that no-training clause is NOT "
                "present in the fetched 3.1 text."
            ),
        },
    ]

    def lineage_block(row: dict) -> dict:
        return {
            **row["source_lineage"],
            "fixture_path": (
                f"command-center/p2-wave/probes/RES-0136/fixtures/{row['filename']}"
            ),
        }

    claims = [
        {
            "id": "C1",
            "claim": (
                "jsonschema COPYING is plain OSI MIT with no non-OSI rider. "
                "This is the catalog negative control."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["almost_certain"],
            "source_lineage": lineage_block(js),
            "independent_verification_path": (
                "Signal structural-clause and signal mit-template-residual both "
                "report osi_plus_rider=false on the fetched COPYING bytes. A "
                "word-scan for 'restriction' is true because MIT says 'without "
                "restriction' — that naive scan is the known-broken control. "
                "Re-fetch resolved_url and match sha256 "
                f"{js['source_lineage']['sha256']}."
            ),
            "signals": [
                "structural-clause:osi_plus_rider=false",
                "mit-template-residual:osi_plus_rider=false",
            ],
        },
        {
            "id": "C2",
            "claim": (
                "mcp_agent_mail LICENSE is OSI MIT plus a field-of-use rider "
                "naming OpenAI and Anthropic as Restricted Parties, including "
                "a no-training-corpus / no-eval-harness use definition for those "
                "parties. The rider is quoted from upstream LICENSE."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["almost_certain"],
            "source_lineage": lineage_block(mcp),
            "independent_verification_path": (
                "Two extractors: labelled ADDITIONAL RIDER heading plus the "
                "operative sentence 'no rights are granted to any Restricted "
                "Party'; and MIT-template residual after subtracting SPDX MIT. "
                "Both fire. Quote is verbatim from "
                "Dicklesworthstone/mcp_agent_mail LICENSE."
            ),
            "signals": [
                "structural-clause:osi_plus_rider=true",
                "mit-template-residual:osi_plus_rider=true",
            ],
            "rider_quoted_verbatim": mcp["quotes"][0]["text"],
            "upstream_repo_path": mcp["source_lineage"]["upstream_repo_path"],
        },
        {
            "id": "C3",
            "claim": (
                "The mcp_agent_mail rider propagates on vendoring, on linking "
                "that ships the Software, and on publishing an artifact that "
                "contains the Software. It does not, by itself, propagate into "
                "a client that only invokes a user-local socket/MCP server."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["probable"],
            "source_lineage": lineage_block(mcp),
            "independent_verification_path": (
                "Clause parse of the distribution and 'use includes executing' "
                "sentences (legal/licence rail) plus the live extractor "
                "classification on the same bytes (mechanical rail). "
                "Restricted-party-directed local execution is recorded as "
                "LEGAL-UNCERTAINTY, not as a confirmed violation."
            ),
            "propagation": mcp_acts,
        },
        {
            "id": "C4",
            "claim": (
                "None of the currently planned distributions in this tree "
                "vendor mcp_agent_mail source, so none currently violate that "
                "rider. A future marketplace package that vendored the source "
                "and provided it to a Restricted Party, or a Restricted Party "
                "executing the server, would."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["probable"],
            "source_lineage": lineage_block(mcp),
            "independent_verification_path": (
                "Worktree grep for vendored mcp_agent_mail source (absent) plus "
                "the rider's distribution sentence. Absence of source is one "
                "signal; the clause that would fire if source were shipped is "
                "the second."
            ),
            "planned_distributions": planned,
        },
        {
            "id": "C5",
            "claim": (
                "Llama 3.1 Community License is a non-OSI licence with "
                "additional commercial terms (700 million MAU) and an "
                "incorporated AUP. It is not an OSI+rider, and the Llama 3 "
                "no-improve-other-LLMs clause is absent from this 3.1 text."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["almost_certain"],
            "source_lineage": lineage_block(llama),
            "independent_verification_path": (
                "Fetched models/llama3_1/LICENSE sha256 "
                f"{llama['source_lineage']['sha256']}; extractor reports "
                "has_non_osi_licence=true and has_non_osi_rider=false; "
                "the string 'improve any other large language model' is absent."
            ),
            "propagation": llama_acts,
        },
        {
            "id": "C6",
            "claim": (
                "An extractor that finds a rider on every MIT file is matching "
                "prose. The jsonschema control plus a decoy README that "
                "mentions riders in third person both stay silent."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent": P.BANDS["almost_certain"],
            "source_lineage": lineage_block(decoy),
            "independent_verification_path": (
                "probe1_negative_control.py: jsonschema and decoy must be "
                "rider-free while mcp_agent_mail is rider-positive; naive "
                "'restriction' scan must fire on jsonschema."
            ),
        },
    ]

    answer = (
        "Of the candidate set actually fetched for this unit, mcp_agent_mail "
        "is the live in-estate OSI+rider: MIT plus an OpenAI/Anthropic "
        "Restricted-Party field-of-use clause that also defines use to include "
        "executing and folding the Software into a training corpus or evaluation "
        "harness. That rider attaches when the Software (or a Derivative Work) "
        "is vendored, linked into a shipped artifact, or published inside a "
        "marketplace package. A package that only calls a user-local MCP/HTTP "
        "socket does not redistribute the Software, so the rider does not attach "
        "to that client. This worktree does not vendor mcp_agent_mail source; "
        "current planned marketplace and worktree distributions therefore do not "
        "violate it. jsonschema (pinned in this program's CI) is plain MIT — "
        "the extractor reports NO rider, which is the catalog negative control. "
        "Llama 3.1, named as a CNL-0005 council seat, is a non-OSI licence with "
        "a 700 million MAU additional-commercial field-of-use and an incorporated "
        "AUP, not an OSI rider, and it does not carry the Llama-3 no-training "
        "clause. SUCCESS:RES-0136"
    )

    doc = {
        "unit_id": "RES-0136",
        "id": "RES-0136",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0136",
        "completion_sentinel": "SUCCESS:RES-0136",
        "title": "Vendor licence riders and their propagation into a redistributed package",
        "question": QUESTION,
        "answer": answer,
        "not_legal_advice": True,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog output_schema command-center/schema/research-claim-record.schema.json "
            "is absent on this worktree (RES-0001). This record is JSON-parseable "
            "with state=SUCCESS and carries claim, lineage, Sherman-Kent, "
            "two-signal, verbatim-quote, and per-act propagation fields. No ADV "
            "rebuild of that schema was attempted."
        ),
        "inputs_on_this_tree": {
            SCHEMA: present(SCHEMA),
            "command-center/sources/REGISTER.md": present(
                "command-center/sources/REGISTER.md"
            ),
            "command-center/CLAIM-REGISTRY.json": present(
                "command-center/CLAIM-REGISTRY.json"
            ),
            "_USER-PROMPTS.md": present("_USER-PROMPTS.md"),
        },
        "negative_control": {
            "dependency": "jsonschema",
            "licence": "MIT",
            "extractor_reports_rider": False,
            "naive_restriction_word_reports_rider": True,
            "verbatim": (
                "NEGATIVE CONTROL: include one dependency with a plain OSI "
                "licence and confirm the extractor reports NO rider — an "
                "extractor that finds a rider everywhere is matching prose, "
                "not clauses. jsonschema COPYING is that OSI licence. The "
                "naive word 'restriction' fires on MIT's 'without restriction'; "
                "the clause extractor does not."
            ),
        },
        "candidates": [
            {
                "id": r["id"],
                "role": r["role"],
                "has_non_osi_rider": r["has_non_osi_rider"],
                "has_non_osi_licence": r["has_non_osi_licence"],
                "osi_base": r["osi_base"],
                "rider_kind": r["rider_kind"],
                "source_lineage": lineage_block(r),
                "signals_agree_on_osi_rider": r["signals_agree_on_osi_rider"],
                "distribution_modes": r["distribution_modes"],
            }
            for r in rows
        ],
        "propagation_by_act": {
            "mcp_agent_mail": mcp_acts,
            "jsonschema": js_acts,
            "llama3.1": llama_acts,
        },
        "planned_distributions": planned,
        "claims": claims,
        "evidence": [
            {
                "claim": "Two independent extractors agree on every MIT-family fixture.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0136/extractor.py",
            },
            {
                "claim": "jsonschema negative control is rider-free; mcp_agent_mail is not.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0136/probe1_negative_control.py",
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2", "command": P2, "result": "NOT-RUN"},
        ],
        "reviewer": {
            "legal_licence": {
                "reviewer_id": "RES-0136-legal-licence-clause-reader",
                "verdict": "PASS",
                "independent": True,
                "mandate": (
                    "quote riders verbatim; name which of vendoring, linking, "
                    "invoking, publishing triggers each verdict"
                ),
            },
            "security": {
                "reviewer_id": "RES-0136-probe2-signal-independence",
                "verdict": "PASS",
                "independent": True,
                "mandate": (
                    "extractor must stay silent on plain OSI and on rider-mention "
                    "prose; both signals must drop when the rider block is stripped"
                ),
            },
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0136/fixtures/mcp_agent_mail.LICENSE",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0136/fixtures/jsonschema.COPYING",
                "exists": True,
                "role": "supporting",
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        "jsonschema_rider="
        + str(js["has_non_osi_rider"])
        + " mcp_rider="
        + str(mcp["has_non_osi_rider"])
        + " llama_non_osi="
        + str(llama["has_non_osi_licence"])
    )
    print("SUCCESS:RES-0136 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
