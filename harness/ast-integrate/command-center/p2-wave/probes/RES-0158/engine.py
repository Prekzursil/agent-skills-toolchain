#!/usr/bin/env python3
"""Live SAT-to-protocol transfer table for RES-0158.

Verdicts are derived from (1) captured primary-source quotes and (2) the
live council protocol catalog. Probe 2 re-runs this module and diffs the
artifact; a table that marks every technique as a protocol, or that drops
the ACH incomplete-set critique, is illegal.
"""
from __future__ import annotations

from typing import Any

from lib import (
    PLAIN_DEBATE,
    SHERMAN_KENT_BANDS,
    lineage,
    live_protocols,
    obligation_ids,
    quote_in_capture,
)

# Contiguous needles that survive two-column PDF layout / HTML entities.
QUOTES = {
    "primer_ach_incomplete_set": (
        "cia-tradecraft-primer",
        "Analysts seldom generate a full set",
        "R1-official-manual",
    ),
    "primer_ach_disconfirm": (
        "cia-tradecraft-primer",
        "disconfrm rather than",
        "R1-official-manual",
    ),
    "primer_ach_matrix": (
        "cia-tradecraft-primer",
        "Prepare a matrix with hypotheses",
        "R1-official-manual",
    ),
    "primer_ach_disprove": (
        "cia-tradecraft-primer",
        "Focus on disproving hypotheses",
        "R1-official-manual",
    ),
    "primer_kac_list": (
        "cia-tradecraft-primer",
        "List and review the key working",
        "R1-official-manual",
    ),
    "primer_kac_hidden": (
        "cia-tradecraft-primer",
        "seldom examined and almost never",
        "R1-official-manual",
    ),
    "primer_da_when": (
        "cia-tradecraft-primer",
        "Devil’s Advocacy is most effective",
        "R1-official-manual",
    ),
    "primer_da_label": (
        "cia-tradecraft-primer",
        "Devil’s Advocate” project",
        "R1-official-manual",
    ),
    "primer_tab_def": (
        "cia-tradecraft-primer",
        "Use of separate analytic teams that",
        "R1-official-manual",
    ),
    "primer_tab_vs_da": (
        "cia-tradecraft-primer",
        "Team A/Team B approach is different",
        "R1-official-manual",
    ),
    "heuer_kac": (
        "heuer-pia-html",
        "When analysis turns out to be wrong, it is often because of key assumptions that went unchallenged and proved invalid.",
        "R2-method-origin",
    ),
    "catalog_kac": (
        "council-protocol-catalog",
        "key-assumptions-check",
        "R2-live-blueprint",
    ),
    "catalog_da": (
        "council-protocol-catalog",
        "mandated-devils-advocate",
        "R2-live-blueprint",
    ),
    "catalog_tab": (
        "council-protocol-catalog",
        "team-b-competitive-estimate",
        "R2-live-blueprint",
    ),
    "heuer_missing_hyp": (
        "heuer-pia-html",
        "If a person does not even generate the correct hypothesis for consideration, obviously he or she will not get the correct answer.",
        "R2-method-origin",
    ),
    "heuer_disprove": (
        "heuer-pia-html",
        "Proceed by trying to disprove the hypotheses rather than prove them.",
        "R2-method-origin",
    ),
    "heuer_diagnosticity": (
        "heuer-pia-html",
        'Analyze the "diagnosticity" of the evidence',
        "R2-method-origin",
    ),
    "mandel_failed": (
        "mandel-dhami-ach-jdm",
        "ACH failed to improve accuracy",
        "R2-peer-eval",
    ),
    "mandel_control_better": (
        "mandel-dhami-ach-jdm",
        "the control group was a little more accurate",
        "R2-peer-eval",
    ),
    "icd_governs_products": (
        "icd-203-pdf",
        "production and evaluation of analytic products",
        "R1-official-standard",
    ),
    "icd_nine": (
        "icd-203-pdf",
        "five Analytic Standards, including the nine",
        "R1-official-standard",
    ),
    "icd_political": (
        "icd-203-pdf",
        "Independent of political consideration",
        "R1-official-standard",
    ),
    "odni_nine": (
        "odni-icd203-page",
        "nine Analytic Tradecraft Standards",
        "R2-official-prose",
    ),
    "klein_failed": (
        "klein-premortem-html",
        "The plan you’ve just discussed has turned out to be a failure",
        "R1-method-origin",
    ),
    "klein_mistake": (
        "klein-premortem-html",
        "Asking the non-challenging question, “What can go wrong?”",
        "R1-method-origin",
    ),
    "hbr_failed": (
        "hbr-premortem-wayback",
        "the project they are planning has just failed",
        "R2-method-origin",
    ),
}

DIRECT = "directly-implementable"
NOT_PROTO = "not-a-protocol-blueprint"

REQUIRED_TECHNIQUES = (
    "ach",
    "key-assumptions-check",
    "devils-advocacy",
    "team-a-team-b",
    "premortem",
    "icd-203",
)


def _lin(*keys: str) -> list[dict[str, Any]]:
    rows = []
    for key in keys:
        cap, quote, rail = QUOTES[key]
        rows.append(lineage(cap, quote, rail))
    return rows


def techniques(protocols: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    proto = protocols if protocols is not None else live_protocols()
    p01 = proto[PLAIN_DEBATE["id"]]
    p38, p39, p10, p11, p43 = proto["P38"], proto["P39"], proto["P10"], proto["P11"], proto["P43"]
    rows = [
        {
            "id": "ach",
            "name": "analysis of competing hypotheses",
            "transfer_verdict": DIRECT,
            "protocol_id": "P38",
            "protocol_slug": p38["slug"],
            "kernel_status": p38["kernel_status"],
            "sherman_kent_band": "likely",
            "plain_debate_delta": (
                "P01 only obliges a contribution on a shared floor. ACH requires "
                "an explicit hypothesis inventory, a hypothesis-by-evidence matrix "
                f"with cell ratings (P38 obligations {obligation_ids(p38)}), "
                "diagnosticity (items consistent with every hypothesis do not "
                "discriminate), and disconfirm-not-confirm scoring."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": True,
                "published_critique": True,
                "summary": (
                    "ACH evaluates a listed set. Heuer: if the correct hypothesis "
                    "is never generated, the matrix cannot recover it. The 2009 "
                    "primer itself lists 'Analysts seldom generate a full set' as "
                    "the opening failure ACH is meant to treat; working the matrix "
                    "can still make a closed, bad set look complete. Mandel, "
                    "Karvetski and Dhami (2018, JDM) found ACH failed to improve "
                    "accuracy versus unaided controls."
                ),
            },
            "quote_keys": [
                "primer_ach_incomplete_set",
                "primer_ach_matrix",
                "primer_ach_disprove",
                "heuer_missing_hyp",
                "heuer_disprove",
                "mandel_failed",
            ],
        },
        {
            "id": "key-assumptions-check",
            "name": "key assumptions check",
            "transfer_verdict": DIRECT,
            "protocol_id": "P39",
            "protocol_slug": p39["slug"],
            "kernel_status": p39["kernel_status"],
            "sherman_kent_band": "likely",
            "plain_debate_delta": (
                "P01 has no assumption ledger. KAC requires listing working "
                f"assumptions then stressing each (P39 obligations {obligation_ids(p39)}); "
                "the primer's value-added is naming what development would force "
                "abandonment."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": False,
                "published_critique": True,
                "summary": (
                    "Hidden assumptions are 'seldom examined and almost never' "
                    "challenged. A KAC that only inventories the already-stated "
                    "premises leaves the unconscious ones, which is the failure "
                    "the technique exists to catch."
                ),
            },
            "quote_keys": ["primer_kac_list", "primer_kac_hidden", "heuer_kac", "catalog_kac"],
        },
        {
            "id": "devils-advocacy",
            "name": "devil's advocacy",
            "transfer_verdict": DIRECT,
            "protocol_id": "P10",
            "protocol_slug": p10["slug"],
            "kernel_status": p10["kernel_status"],
            "sherman_kent_band": "likely",
            "plain_debate_delta": (
                "P01 allows every seat to support the floor case. Devil's advocacy "
                "requires a named seat to attack and a gate that the attack was "
                f"discharged (P10 obligations {obligation_ids(p10)}). The primer "
                "also requires the product be labelled a Devil's Advocate project "
                "so it is not read as the official line."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": False,
                "published_critique": True,
                "summary": (
                    "Unlabelled DA product confuses the reader about the official "
                    "view (primer). A theatrical advocate who never attacks a "
                    "linchpin assumption is indistinguishable from extra debate."
                ),
            },
            "quote_keys": ["primer_da_when", "primer_da_label", "catalog_da"],
        },
        {
            "id": "team-a-team-b",
            "name": "team A / team B",
            "transfer_verdict": DIRECT,
            "protocol_id": "P11",
            "protocol_slug": p11["slug"],
            "kernel_status": p11["kernel_status"],
            "sherman_kent_band": "likely",
            "plain_debate_delta": (
                "P01 shares visibility. Team A/B uses separate analytic teams and "
                "visibility partitions until compare (P11 phases "
                f"{[p.get('id') for p in p11['phases']]}, obligations "
                f"{obligation_ids(p11)}). The primer distinguishes this from "
                "devil's advocacy: DA challenges one dominant mind-set; A/B "
                "develops two competing estimates in parallel."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": False,
                "published_critique": True,
                "summary": (
                    "Offices commonly draft a 'Team B' that is actually devil's "
                    "advocacy (primer). Isolation until compare is the mechanism; "
                    "flattening onto a shared P01 floor contaminates the contrast."
                ),
            },
            "quote_keys": ["primer_tab_def", "primer_tab_vs_da", "catalog_tab"],
        },
        {
            "id": "premortem",
            "name": "premortem",
            "transfer_verdict": DIRECT,
            "protocol_id": "P43",
            "protocol_slug": p43["slug"],
            "kernel_status": p43["kernel_status"],
            "sherman_kent_band": "likely",
            "plain_debate_delta": (
                "P01 never forces prospective hindsight. A premortem requires the "
                "stance that the plan has already failed, then a failure-mode "
                f"ledger and cause/detectability (P43 obligations {obligation_ids(p43)})."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": False,
                "published_critique": True,
                "summary": (
                    "Klein's documented mistake: asking 'What can go wrong?' "
                    "instead of affirming disaster. That collapse turns the "
                    "premortem back into ordinary critique, which is P01."
                ),
            },
            "quote_keys": ["klein_failed", "klein_mistake", "hbr_failed"],
        },
        {
            "id": "icd-203",
            "name": "ICD-203 analytic standards",
            "transfer_verdict": NOT_PROTO,
            "protocol_id": None,
            "protocol_slug": None,
            "kernel_status": "not-a-protocol",
            "sherman_kent_band": "almost-certain",
            "plain_debate_delta": (
                "ICD-203 governs production and evaluation of analytic products "
                "(five analytic standards plus nine tradecraft standards). It has "
                "no speaking order, phases, or role obligations, so it is not a "
                "council protocol blueprint. Transfer is as product-evaluation "
                "gates overlaid on whatever protocol produced the product, not as "
                "a new P-id. P01 does not implement those gates either."
            ),
            "failure_mode": {
                "entrench_bad_hypothesis_set": False,
                "published_critique": True,
                "summary": (
                    "Treating ICD-203 as a deliberation protocol would invent a "
                    "turn schedule the directive does not specify. The overlay is "
                    "real (source quality, uncertainty language, analysis of "
                    "alternatives) but it is a rubric, not a protocol."
                ),
            },
            "quote_keys": ["icd_governs_products", "icd_nine", "icd_political", "odni_nine"],
        },
    ]
    # Attach live lineage now so emit and probes share one walk.
    for row in rows:
        row["source_lineage"] = _lin(*row["quote_keys"])
        row["signals"] = [
            {
                "id": f"{row['id']}-src",
                "mechanism": "quoted-primary-source",
                "observation": row["source_lineage"][0]["quote"],
            },
            {
                "id": f"{row['id']}-impl",
                "mechanism": (
                    "live-protocol-catalog"
                    if row["transfer_verdict"] == DIRECT
                    else "live-protocol-catalog-absent-id"
                ),
                "observation": (
                    f"{row['protocol_id']} status={row['kernel_status']}"
                    if row["protocol_id"]
                    else "no P-id in tools/council/protocol/catalog.py for ICD-203"
                ),
            },
        ]
        row["independent_verification_path"] = (
            "command-center/p2-wave/probes/RES-0158/probe1_source_coverage.py "
            "and probe2_protocol_crosscheck.py"
        )
        if row["sherman_kent_band"] not in SHERMAN_KENT_BANDS:
            raise ValueError(row["id"])
        if p01["kernel_status"] != "expressible":
            raise AssertionError("P01 baseline must be expressible")
        if row["transfer_verdict"] == DIRECT:
            if row["kernel_status"] != "expressible":
                raise AssertionError(f"{row['id']} mapped to non-expressible")
            if row["protocol_id"] not in proto:
                raise AssertionError(row["protocol_id"])
        else:
            if row["protocol_id"] is not None:
                raise AssertionError("ICD-203 must not mint a P-id")
            if "ICD-203" in proto or "icd-203" in {r.get("slug") for r in proto.values()}:
                raise AssertionError("catalog unexpectedly has ICD-203")
    return rows


def evaluate_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [r.get("id") for r in rows]
    missing = [t for t in REQUIRED_TECHNIQUES if t not in ids]
    n_direct = sum(1 for r in rows if r.get("transfer_verdict") == DIRECT)
    n_not = sum(1 for r in rows if r.get("transfer_verdict") == NOT_PROTO)
    ach = next((r for r in rows if r.get("id") == "ach"), None)
    icd = next((r for r in rows if r.get("id") == "icd-203"), None)
    ach_ok = bool(
        ach
        and (ach.get("failure_mode") or {}).get("entrench_bad_hypothesis_set") is True
        and (ach.get("failure_mode") or {}).get("published_critique") is True
    )
    icd_ok = bool(icd and icd.get("transfer_verdict") == NOT_PROTO)
    all_transfer = n_not == 0 and n_direct == len(rows) and len(rows) > 0
    quotes_ok = True
    quote_failures: list[str] = []
    for r in rows:
        for key in r.get("quote_keys") or []:
            cap, quote, _rail = QUOTES[key]
            if not quote_in_capture(cap, quote):
                quotes_ok = False
                quote_failures.append(f"{r.get('id')}:{key}")
        for lin in r.get("source_lineage") or []:
            cid = str(lin.get("id") or "")
            q = str(lin.get("quote") or "")
            if cid and q and not quote_in_capture(cid, q):
                quotes_ok = False
                quote_failures.append(f"lineage:{cid}")
    ok = (
        not missing
        and n_direct >= 1
        and n_not >= 1
        and ach_ok
        and icd_ok
        and quotes_ok
        and not all_transfer
    )
    return {
        "ok": ok,
        "missing": missing,
        "n": len(rows),
        "n_directly_implementable": n_direct,
        "n_not_a_protocol": n_not,
        "ach_critique_present": ach_ok,
        "icd203_not_protocol": icd_ok,
        "all_techniques_marked_protocol": all_transfer,
        "quotes_ok": quotes_ok,
        "quote_failures": quote_failures,
    }


def mutant_drop_ach_critique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = dict(r)
        if item.get("id") == "ach":
            fm = dict(item.get("failure_mode") or {})
            fm["entrench_bad_hypothesis_set"] = False
            fm["published_critique"] = False
            fm["summary"] = "ACH improves analysis."
            item["failure_mode"] = fm
            item["quote_keys"] = [
                k for k in item.get("quote_keys") or [] if not k.startswith("mandel") and k != "heuer_missing_hyp" and k != "primer_ach_incomplete_set"
            ]
        out.append(item)
    return out


def mutant_icd_as_protocol(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = dict(r)
        if item.get("id") == "icd-203":
            item["transfer_verdict"] = DIRECT
            item["protocol_id"] = "P01"
            item["kernel_status"] = "expressible"
        out.append(item)
    return out


def mutant_everything_transfers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = dict(r)
        item["transfer_verdict"] = DIRECT
        item["protocol_id"] = item.get("protocol_id") or "P01"
        item["kernel_status"] = "expressible"
        out.append(item)
    return out
