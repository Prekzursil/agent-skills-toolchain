#!/usr/bin/env python3
"""Clause engine: kept N=1 set + omitted control, driven by captured bytes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sources import NEEDLES, OMIT_ID, SENTINEL  # noqa: E402

CAP = HERE / "captures"


def load_meta(sid: str) -> dict:
    path = CAP / f"{sid}.meta.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_search_text(sid: str) -> str:
    decoded = CAP / f"{sid}.decoded.txt"
    if decoded.is_file():
        return decoded.read_text(encoding="utf-8", errors="replace")
    body = CAP / f"{sid}.body"
    if not body.is_file():
        return ""
    raw = body.read_bytes()
    return raw.decode("utf-8", errors="replace")


def snippet_window(text: str, needle: str, pad: int = 72) -> str:
    i = text.find(needle)
    if i < 0:
        return ""
    a = max(0, i - pad)
    b = min(len(text), i + len(needle) + pad)
    return text[a:b].replace("\n", " ").strip()


def citation(sid: str, needle_key: str) -> dict | None:
    meta = load_meta(sid)
    if not meta.get("ok"):
        return None
    text = load_search_text(sid)
    hits = meta.get("needle_hits") or {}
    needle = hits.get(needle_key)
    if not needle:
        # Re-search live text in case meta is stale.
        for n in NEEDLES.get(needle_key, []):
            if n in text:
                needle = n
                break
    if not needle:
        return None
    window = snippet_window(text, needle)
    if not window:
        return None
    return {
        "source_id": sid,
        "rail": meta.get("rail"),
        "family": meta.get("family"),
        "permalink": meta.get("permalink") or meta.get("request_url"),
        "fetched_at": meta.get("fetched_at"),
        "http_status": meta.get("http_status"),
        "sha256": meta.get("sha256"),
        "bytes": meta.get("bytes"),
        "needle_key": needle_key,
        "needle": needle,
        "snippet": window,
        "github_decoded": bool(meta.get("github_decoded")),
    }


def rail_record(sid: str) -> dict | None:
    meta = load_meta(sid)
    if not meta:
        return None
    return {
        "source_id": sid,
        "rail": meta.get("rail"),
        "family": meta.get("family"),
        "permalink": meta.get("permalink") or meta.get("request_url"),
        "request_url": meta.get("request_url"),
        "fetched_at": meta.get("fetched_at"),
        "http_status": meta.get("http_status"),
        "sha256": meta.get("sha256"),
        "bytes": meta.get("bytes"),
        "ok": bool(meta.get("ok")),
        "content_type": meta.get("content_type"),
        "github_decoded": bool(meta.get("github_decoded")),
        "decoded_sha256": meta.get("decoded_sha256"),
    }


def n1_can_honour(clause_id: str) -> bool:
    """True iff the clause can be stated honestly when owner-count == 1."""
    return clause_id != OMIT_ID


def two_rail_cites(pairs: list[tuple[str, str]]) -> list[dict]:
    """pairs: (source_id, needle_key). Keep only hits. Caller checks two rails."""
    out = []
    for sid, key in pairs:
        c = citation(sid, key)
        if c:
            out.append(c)
    return out


def rails_ok(cites: list[dict]) -> bool:
    kinds = {c.get("rail") for c in cites}
    return "api" in kinds and "prose" in kinds and len(cites) >= 2


def build_clauses() -> dict:
    """Return kept clauses, omitted clause, and claim list. Raises on missing evidence."""
    errors: list[str] = []

    def require(cites: list[dict], label: str) -> list[dict]:
        if not rails_ok(cites):
            errors.append(
                f"{label}: need api+prose citations, got "
                f"{[(c.get('source_id'), c.get('rail'), c.get('needle_key')) for c in cites]}"
            )
        return cites

    c_who = require(
        two_rail_cites(
            [
                ("pep541_api", "fcfs"),
                ("pep541_html", "fcfs"),
                ("npm_disputes_api", "fcfs"),
                ("npm_disputes_html", "fcfs"),
            ]
        ),
        "C-WHO-MAY-PUBLISH",
    )
    c_dispute = require(
        two_rail_cites(
            [
                ("pep541_api", "pep541_channel"),
                ("pep541_html", "pep541_channel"),
                ("npm_disputes_api", "npm_no_squat_on_demand"),
                ("npm_disputes_html", "npm_no_squat_on_demand"),
                ("npm_disputes_api", "npm_trademark"),
                ("npm_disputes_html", "npm_trademark"),
            ]
        ),
        "C-HOW-DISPUTE-RAISED",
    )
    c_takedown = require(
        two_rail_cites(
            [
                ("npm_disputes_api", "npm_admin_delete"),
                ("npm_conduct_html", "npm_admin_delete"),
                ("rfc3463_api", "crates_team"),
                ("rfc3463_raw", "crates_team"),
                ("hf_tos_html", "hf_discretion"),
                ("hf_content_html", "hf_discretion"),
            ]
        ),
        "C-WHO-DECIDES-TAKEDOWN",
    )
    c_appeal = require(
        two_rail_cites(
            [
                ("hf_content_html", "hf_contest"),
                ("hf_moderation_api", "hf_report"),
                ("hf_moderation_html", "hf_report"),
                ("rfc3463_api", "crates_help"),
                ("rfc3463_raw", "crates_help"),
                ("rfc3463_api", "crates_no_reverse"),
                ("rfc3463_raw", "crates_no_reverse"),
            ]
        ),
        "C-WHAT-THE-APPEAL-IS",
    )
    c_legal = require(
        two_rail_cites(
            [
                ("hf_content_html", "hf_dmca"),
                ("hf_tos_html", "hf_dmca"),
                ("npm_disputes_html", "npm_trademark"),
                ("npm_disputes_api", "npm_trademark"),
            ]
        ),
        "C-LEGAL-NOTICE-CHANNEL",
    )
    omit_cites = require(
        two_rail_cites(
            [
                ("rfc3463_api", "crates_team"),
                ("rfc3463_raw", "crates_team"),
                ("rfc3463_api", "crates_no_reverse"),
                ("rfc3463_raw", "crates_no_reverse"),
                ("pep541_api", "pep541_not_arbiter"),
                ("pep541_html", "pep541_not_arbiter"),
                ("hf_content_html", "hf_dsa"),
            ]
        ),
        "OMIT-INDEPENDENT-RECUSAL-PANEL",
    )

    kept = [
        {
            "id": "C-WHO-MAY-PUBLISH",
            "slot": "who_may_publish",
            "text": (
                "Who may publish: an authenticated account holder may publish under "
                "a name they currently hold; names are allocated first-come, "
                "first-served and are not held as a reservation for sale. The "
                "operator is not a naming-rights broker."
            ),
            "honourable_at_n1": True,
            "borrowed_from": ["PEP 541", "npm Disputes Policy"],
            "citations": c_who,
        },
        {
            "id": "C-HOW-DISPUTE-RAISED",
            "slot": "how_dispute_raised",
            "text": (
                "How a dispute is raised: name a single public channel (issue "
                "template or support mailbox) and say which disputes that channel "
                "will even consider. Squatting/vanity claims are not transferred "
                "on demand; IP/trademark claims go through the named legal path."
            ),
            "honourable_at_n1": True,
            "borrowed_from": ["PEP 541 name-transfer how-to", "npm Disputes Policy"],
            "citations": c_dispute,
        },
        {
            "id": "C-WHO-DECIDES-TAKEDOWN",
            "slot": "how_takedown_decided",
            "text": (
                "How a takedown is decided: the named Owner (the registry operator) "
                "decides, at stated discretion, whether content violates published "
                "rules or law. Do not describe a committee, vote, or 'maintainers' "
                "plural that does not exist at N=1."
            ),
            "honourable_at_n1": True,
            "borrowed_from": [
                "npm Code of Conduct (administrators' discretion)",
                "Hugging Face Terms of Service (operator discretion)",
            ],
            "citations": c_takedown,
        },
        {
            "id": "C-WHAT-THE-APPEAL-IS",
            "slot": "what_the_appeal_is",
            "text": (
                "What the appeal is: a documented re-review request to the same "
                "Owner at a published address, with a statement that this is not "
                "an independent tribunal. If deletion is treated as final, say so; "
                "do not advertise a reversal panel that cannot be staffed."
            ),
            "honourable_at_n1": True,
            "borrowed_from": [
                "Hugging Face Content Policy contest mailbox",
                "crates.io RFC 3463 (moderation permanence / team mailbox)",
            ],
            "citations": c_appeal,
        },
        {
            "id": "C-LEGAL-NOTICE-CHANNEL",
            "slot": "statutory_notice",
            "text": (
                "Statutory notice channel: publish a distinct mailbox/process for "
                "copyright, trademark, and similar legal notices, separate from "
                "policy disputes. This is a process statement, not a legal opinion."
            ),
            "honourable_at_n1": True,
            "borrowed_from": [
                "Hugging Face Content Policy DMCA mailbox",
                "npm disputes/trademark path",
            ],
            "citations": c_legal,
        },
    ]

    omitted = {
        "id": OMIT_ID,
        "slot": "independent_appellate_recusal",
        "text": (
            "Appeals of a takedown are heard by a multi-member body that does not "
            "include the original decision-maker, and that body can reverse the "
            "operator (independent recusal panel)."
        ),
        "honourable_at_n1": False,
        "omit_reason": (
            "At owner-count N=1 there is no second person to recuse into. Staffing "
            "this clause would fake a committee. Mature multi-person models can "
            "name a crates.io team / PyPI maintainers (plural); a single-owner "
            "marketplace cannot. Hugging Face's DSA out-of-court settlement is a "
            "third-party statutory path for in-scope services, not something an "
            "N=1 operator can honour by renaming themselves a panel."
        ),
        "must_omit_rather_than_fake": True,
        "borrowed_from": [
            "crates.io RFC 3463 (crates.io team; moderation not reversed)",
            "PEP 541 (Package Index maintainers as a set)",
        ],
        "citations": omit_cites,
    }

    graceful = {
        "winner_id": "operator-adjudication",
        "winner_models": ["npm public registry (administrators decide)", "Hugging Face Hub (company ToS)"],
        "why": (
            "Those texts already name an operator (administrators / Hugging Face) "
            "as the decider plus a contact path. Substituting 'the Owner' for "
            "'npm administrators' does not invent a board. PEP 541 and crates.io "
            "RFC 3463 assume a staffed maintainer/team set and degrade into fiction "
            "at N=1 if copied verbatim."
        ),
        "does_not_degrade": [
            "PEP 541 'maintainers of the Package Index' as a plurality",
            "crates.io team as a multi-person adjudicating body with no reversal",
            "DSA certified out-of-court dispute settlement presented as an internal panel",
        ],
    }

    claims = [
        {
            "id": "CL-N1-MUST-NAME-FOUR-SLOTS",
            "claim": (
                "A single-owner marketplace's published governance must at least "
                "state who may publish, how a dispute is raised, who decides a "
                "takedown, and what an appeal is, plus a statutory-notice channel."
            ),
            "evidence_tier": "E2",
            "confidence_band": "probable",
            "citations": c_who + c_dispute + c_takedown + c_appeal + c_legal,
            "caveat": (
                "This is a design minimum extracted from mature registries, not a "
                "jurisdiction-specific legal requirement. Not legal advice."
            ),
        },
        {
            "id": "CL-OPERATOR-MODEL-DEGRADES",
            "claim": (
                "The operator-decides model (npm administrators / HF company ToS) "
                "degrades more gracefully to N=1 than team/maintainer-plural models "
                "(crates.io team, PEP 541 maintainers)."
            ),
            "evidence_tier": "E2",
            "confidence_band": "probable",
            "citations": c_takedown + omit_cites,
            "caveat": (
                "Internal headcount at npm/HF is not N=1; the *text* is written as "
                "operator discretion rather than a foundation committee, which is "
                "the degradable property."
            ),
        },
        {
            "id": "CL-RECUSAL-CANNOT-BE-HONOURED",
            "claim": (
                "An independent recusal panel that can reverse the original "
                "decision-maker cannot be honoured at N=1 and must be omitted "
                "rather than faked."
            ),
            "evidence_tier": "E2",
            "confidence_band": "highly probable",
            "citations": omit_cites,
            "caveat": (
                "A re-review by the same owner is a different, weaker clause and "
                "is listed in the kept set. Statutory third-party processes (DMCA "
                "counter-notice, DSA settlement where in scope) are not the same "
                "as an internal independent panel."
            ),
        },
    ]

    return {
        "errors": errors,
        "kept": kept,
        "omitted": omitted,
        "graceful": graceful,
        "claims": claims,
        "sentinel": SENTINEL,
        "omit_id": OMIT_ID,
    }


def check_artifact(doc: dict) -> list[str]:
    """Independent checks a probe can re-run against the emitted JSON."""
    fails: list[str] = []
    if SENTINEL not in json.dumps(doc, ensure_ascii=False):
        fails.append("sentinel-absent")
    kept = doc.get("minimal_clause_set") or []
    omitted = doc.get("omitted_clauses") or []
    if len(kept) < 4:
        fails.append("kept-clause-count")
    if len(omitted) < 1:
        fails.append("omitted-clause-absent")
    for cl in kept:
        cites = cl.get("citations") or []
        if not cites:
            fails.append(f"clause-{cl.get('id')}-no-citation")
        for c in cites:
            sid = c.get("source_id")
            needle = c.get("needle")
            text = load_search_text(sid) if sid else ""
            if not needle or needle not in text:
                fails.append(f"clause-{cl.get('id')}-snippet-miss-{sid}")
            meta = load_meta(sid) if sid else {}
            if str(c.get("sha256") or "") != str(meta.get("sha256") or ""):
                fails.append(f"clause-{cl.get('id')}-sha-drift-{sid}")
        if cl.get("id") == OMIT_ID:
            fails.append("omitted-id-leaked-into-kept")
        if n1_can_honour(cl.get("id") or "") is False:
            fails.append(f"kept-clause-not-honourable-{cl.get('id')}")
    saw_omit = False
    for cl in omitted:
        if cl.get("id") == OMIT_ID:
            saw_omit = True
            if n1_can_honour(cl.get("id")):
                fails.append("omit-engine-true")
            if cl.get("honourable_at_n1") is True:
                fails.append("omit-marked-honourable")
            if not (cl.get("citations") or []):
                fails.append("omit-uncited")
            for c in cl.get("citations") or []:
                sid = c.get("source_id")
                needle = c.get("needle")
                text = load_search_text(sid) if sid else ""
                if not needle or needle not in text:
                    fails.append(f"omit-snippet-miss-{sid}")
        if n1_can_honour(cl.get("id") or "") and cl.get("must_omit_rather_than_fake"):
            fails.append(f"omit-engine-disagrees-{cl.get('id')}")
    if not saw_omit:
        fails.append("omit-id-missing")
    for claim in doc.get("claims") or []:
        cites = claim.get("citations") or []
        rails = {c.get("rail") for c in cites}
        if claim.get("evidence_tier") in {"E1", "E2"} and not (
            "api" in rails and "prose" in rails
        ):
            fails.append(f"claim-{claim.get('id')}-not-two-rail")
        if len(cites) < 2:
            fails.append(f"claim-{claim.get('id')}-single-signal")
    if doc.get("not_legal_advice") is not True:
        fails.append("missing-not-legal-advice")
    so = doc.get("owner_signoff") or {}
    if so.get("required_before_downstream_action") is not True:
        fails.append("owner-signoff-gate-unstated")
    if so.get("granted") is True:
        fails.append("owner-signoff-faked")
    return fails
