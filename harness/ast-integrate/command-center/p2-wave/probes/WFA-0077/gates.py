#!/usr/bin/env python3
"""Classify WFA-slice owner-gated actions without re-asking settled questions.

Evidence A: map each spec-named owner-controlled action to the WFA-1.json
units that could trigger it (effect, not the owner_approval_required flag).
Evidence B: search binding decision records before any question is proposed.
Questions with no owner impact are REMOVED, not asked for completeness.
ASK rows are queued one foundation question at a time with a recommendation
and a default-if-unanswered.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SLICE = "WFA-1.json"
UNIT = "WFA-0077"
SENTINEL = "SUCCESS:WFA-0077"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/wfa/WFA-0077-owner-approval-gate-list.json"
DECLARED_SCHEMA = (
    "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
)
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0077/audit_report.schema.json"
)

SPEC_ACTIONS: tuple[str, ...] = (
    "public_publishing",
    "unbounded_spend",
    "credential_rotation",
    "deleting_user_data",
    "security_posture",
    "public_repositories",
    "controversial_source_classes",
)

ASK_ORDER: tuple[str, ...] = (
    "deleting_user_data",
    "controversial_source_classes",
    "public_publishing",
    "unbounded_spend",
    "security_posture",
    "public_repositories",
    "credential_rotation",
)

# Units that can CAUSE the action. Read-only sweeps that merely observe a
# public marketplace or an already-published tag are observers, not triggers.
TRIGGERS: dict[str, tuple[tuple[str, str], ...]] = {
    "public_publishing": (
        (
            "WFA-0031",
            "Licence/ToS gate can permit carrying third-party workflow code "
            "across the estate, which is redistribution (a public-publishing "
            "class action), not mere mechanism extraction.",
        ),
    ),
    "unbounded_spend": (
        (
            "WFA-0021",
            "First-party vendor-doc fetch can hit paid or rate-limited APIs.",
        ),
        (
            "WFA-0023",
            "Public marketplace pack fetch is an external acquisition call.",
        ),
        (
            "WFA-0024",
            "Public GitHub code-search is an external acquisition call.",
        ),
        (
            "WFA-0025",
            "Academic/preprint fetch is an external acquisition call.",
        ),
        (
            "WFA-0026",
            "Practitioner-forum fetch is an external acquisition call.",
        ),
        (
            "WFA-0028",
            "Niche/archival/policy-gated fetch is an external acquisition call.",
        ),
        (
            "WFA-0029",
            "Scheduler for every credentialed external acquisition call in "
            "this bucket; it is the spend/rate throttle, not a rotation tool.",
        ),
    ),
    "credential_rotation": (),
    "deleting_user_data": (
        (
            "WFA-0015",
            "Recently removed worktrees may hold unique user work; discarding "
            "them after the sweep is deletion.",
        ),
        (
            "WFA-0022",
            "Salvage after the DELETE-ALL retirement; further delete of "
            "unsalvaged unique work is irreversible.",
        ),
        (
            "WFA-0064",
            "Terminal RETIRE/REJECT can destroy the last copy of a mechanism.",
        ),
        (
            "WFA-0071",
            "Re-adjudication of RETIRE after DELETE-ALL can confirm more "
            "terminal deletes.",
        ),
        (
            "WFA-0076",
            "Last preservation proof before a disposition becomes terminal "
            "delete.",
        ),
        (
            "WFA-0119",
            "Decertification retires a certified workflow definition.",
        ),
    ),
    "security_posture": (),
    "public_repositories": (),
    "controversial_source_classes": (
        (
            "WFA-0028",
            "Sweep explicitly includes lawful public onion sources under the "
            "opt-in policy; enabling that class is owner-controlled.",
        ),
    ),
}

OBSERVERS: dict[str, tuple[tuple[str, str], ...]] = {
    "public_publishing": (
        (
            "WFA-0016",
            "Reads already-published releases and tags; does not publish.",
        ),
        (
            "WFA-0023",
            "Reads public marketplaces; does not list or ship a pack.",
        ),
    ),
    "public_repositories": (
        (
            "WFA-0024",
            "Searches existing public GitHub repositories; does not create "
            "a public repo or organization.",
        ),
    ),
    "credential_rotation": (
        (
            "WFA-0029",
            "Uses already-provisioned credentials for acquisition; does not "
            "rotate, revoke, or mint credentials.",
        ),
    ),
    "security_posture": (
        (
            "WFA-0038",
            "Reports permission-surface violations; does not widen grants.",
        ),
        (
            "WFA-0121",
            "Adds an untrusted-data / prompt-injection gate (hardening), "
            "which does not weaken posture.",
        ),
    ),
}

FOUNDATION_QUESTIONS: dict[str, dict[str, str]] = {
    "public_publishing": {
        "question": (
            "May this WFA bucket redistribute third-party workflow code "
            "(or publish a pack/marketplace listing), or must every "
            "acquisition stay mechanism-only with no code carried across?"
        ),
        "recommendation": (
            "Refuse redistribution and public listing. Record mechanisms "
            "only. Aligns with the catalog's claimed PR-ONLY release mode "
            "without treating that catalog row as an owner utterance."
        ),
        "default_if_unanswered": (
            "NO public publishing and NO third-party code redistribution. "
            "Mechanism-only records."
        ),
        "strongest_tradeoff": (
            "Mechanism-only drops some repair/fusion fidelity; redistribution "
            "creates a licence and publishing event the spec gates on the owner."
        ),
    },
    "unbounded_spend": {
        "question": (
            "May the WFA acquisition lane incur new paid or unbounded "
            "external API spend, or must credentialed fetches stay inside "
            "already-provisioned free/existing quotas?"
        ),
        "recommendation": (
            "Cap spend at already-provisioned credentials and published "
            "free-tier quotas. WFA-0029 must refuse a provider the moment "
            "the call would require a new paid account or uncapped bill."
        ),
        "default_if_unanswered": (
            "NO new paid spend and NO unbounded spend. Existing credentials "
            "only; skip a source rather than upgrade a plan."
        ),
        "strongest_tradeoff": (
            "A hard cap misses some marketplace/GitHub sources; an open cap "
            "is the unbounded-spend action the spec forbids without approval."
        ),
    },
    "credential_rotation": {
        "question": (
            "Should this WFA bucket rotate, revoke, or mint credentials?"
        ),
        "recommendation": "Out of scope for this slice.",
        "default_if_unanswered": "Do not rotate credentials.",
        "strongest_tradeoff": "n/a — no trigger in slice.",
    },
    "deleting_user_data": {
        "question": (
            "May any WFA terminal disposition (RETIRE, REJECT, further "
            "DELETE-ALL cleanup, decertification) delete candidate or "
            "worktree content, including unique user work found only in "
            "removed trees?"
        ),
        "recommendation": (
            "Do not execute further terminal deletes until WFA-0076 has a "
            "live retrieval proof for that record. Salvage first "
            "(WFA-0015/0022/0064); default is retain."
        ),
        "default_if_unanswered": (
            "RETAIN. No further terminal delete of candidate, worktree, or "
            "user-authored content."
        ),
        "strongest_tradeoff": (
            "Retain-by-default keeps abandoned trees on disk; delete-without-"
            "proof is the irreversible action the spec gates on the owner."
        ),
    },
    "security_posture": {
        "question": (
            "May this WFA bucket weaken a security gate or widen a "
            "permission grant?"
        ),
        "recommendation": "Out of scope — no weakening trigger in this slice.",
        "default_if_unanswered": "Do not weaken security posture.",
        "strongest_tradeoff": "n/a — no trigger in slice.",
    },
    "public_repositories": {
        "question": (
            "May this WFA bucket create a public repository or organization?"
        ),
        "recommendation": "Out of scope — no creation trigger in this slice.",
        "default_if_unanswered": "Do not create public repositories.",
        "strongest_tradeoff": "n/a — no trigger in slice.",
    },
    "controversial_source_classes": {
        "question": (
            "May WFA-0028 enable controversial source classes (lawful public "
            "onion/Tor and other opt-in restricted classes), or must that "
            "class stay OFF so the sweep reports without it?"
        ),
        "recommendation": (
            "Keep controversial classes OFF. WFA-0028 may still sweep niche, "
            "non-English and archival PUBLIC sources. Onion/Tor stays dark "
            "until an owner utterance at path:line enables a named class."
        ),
        "default_if_unanswered": (
            "OFF. Controversial source classes remain disabled. The sweep "
            "must complete and report without them."
        ),
        "strongest_tradeoff": (
            "Leaving onion OFF can miss a niche mechanism; turning it ON "
            "without an owner opt-in is the spec-named owner-controlled action."
        ),
    },
}

BINDING_RECORD_CANDIDATES: tuple[str, ...] = (
    "command-center/OWNER-DECISIONS.md",
    "OWNER-DECISIONS.md",
    "command-center/32-OWNER-DECISIONS.md",
    "32-OWNER-DECISIONS.md",
    "command-center/17-DECISION-LOG.md",
    "17-DECISION-LOG.md",
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
)

OWNER_LINE = re.compile(
    r'(?i)^(?:[-*]\s+)?(?:\*\*)?owner(?: statement)?(?:\*\*)?\s*[:—-]\s*["“]?(.+?)["”]?\s*$'
)
ACK_ONLY = {
    "got it",
    "acknowledged",
    "ok",
    "okay",
    "noted",
    "thanks",
    "thank you",
    "ack",
    "proceed",
    "go",
}
ACTION_TOKENS: dict[str, tuple[str, ...]] = {
    "public_publishing": (
        "pr-only",
        "public marketplace",
        "do not publish",
        "no public marketplace",
        "no public publishing",
        "mechanism-only",
        "do not redistribute",
    ),
    "unbounded_spend": (
        "unbounded spend",
        "no paid",
        "no new paid",
        "spend cap",
        "do not incur",
        "free-tier only",
        "existing credentials only",
    ),
    "credential_rotation": (
        "credential rotation",
        "do not rotate",
        "rotate credentials",
    ),
    "deleting_user_data": (
        "do not delete",
        "retain user data",
        "no terminal delete",
        "delete-all",
        "do not execute further delete",
        "retain.",
    ),
    "security_posture": (
        "security posture",
        "do not weaken",
        "do not widen permission",
    ),
    "public_repositories": (
        "public repository",
        "public organization",
        "do not create public",
    ),
    "controversial_source_classes": (
        "controversial source",
        "onion",
        "tor/",
        " tor ",
        "opt-in source",
        "do not enable controversial",
        "restricted classes",
    ),
}

COMPLETENESS_EXAMPLE_ID = "Q-JSON-INDENT"
COMPLETENESS_EXAMPLE = {
    "id": COMPLETENESS_EXAMPLE_ID,
    "action": "none",
    "question": "Should WFA JSON artifacts use 2-space or 4-space indent?",
    "owner_impact": False,
    "reason": "Formatting has no spec-named owner-controlled effect.",
}


def _get(u: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in u and u[k] is not None:
            return u[k]
    return default


def slice_file_of(u: dict) -> str:
    return str(
        _get(u, "_source_slice_file", "_source_slice_file", default="") or ""
    )


def unit_question(u: dict) -> str:
    return str(
        _get(u, "question_or_target", "question_or_target", default="") or ""
    )


def owner_flag(u: dict) -> bool:
    v = _get(
        u, "owner_approval_required", "owner_approval_required", default=False
    )
    return v is True


def load_catalog(repo: Path) -> dict:
    return json.loads((repo / CATALOG_REL).read_text(encoding="utf-8"))


def wfa_slice_units(catalog: dict, slice_name: str = SLICE) -> list[dict]:
    units = (
        catalog.get("work_units")
        or catalog.get("work_units")
        or catalog.get("units")
        or []
    )
    aliases = {slice_name, "WFA-1.json", "WFA-1.json"}
    out = []
    for u in units:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or "")
        if not uid.startswith("WFA-"):
            continue
        if slice_file_of(u) in aliases:
            out.append(u)
    return out


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_ack(answer: str) -> bool:
    s = re.sub(r"[^a-z]+", " ", (answer or "").lower()).strip()
    return s in ACK_ONLY


def load_decision_docs(
    repo: Path, extra_docs: list[dict] | None = None
) -> list[dict]:
    docs: list[dict] = []
    seen: set[str] = set()
    for rel in BINDING_RECORD_CANDIDATES:
        if rel in seen:
            continue
        seen.add(rel)
        path = repo / rel
        present = path.is_file() and path.stat().st_size > 0
        text = path.read_text(encoding="utf-8") if present else ""
        docs.append(
            {
                "path": rel,
                "present": present,
                "bytes": len(text.encode("utf-8")) if present else 0,
                "sha256": sha256_text(text) if present else None,
                "text": text,
                "source": "live-binding-record",
            }
        )
    for extra in extra_docs or []:
        text = str(extra.get("text") or "")
        docs.append(
            {
                "path": str(extra["path"]),
                "present": True,
                "bytes": len(text.encode("utf-8")),
                "sha256": sha256_text(text),
                "text": text,
                "source": extra.get("source") or "fixture",
            }
        )
    return docs


def owner_hits_for_action(docs: list[dict], action: str) -> list[dict]:
    tokens = ACTION_TOKENS[action]
    hits: list[dict] = []
    for doc in docs:
        text = doc.get("text") or ""
        if not text:
            continue
        for i, raw in enumerate(text.splitlines(), 1):
            m = OWNER_LINE.match(raw.strip())
            if not m:
                continue
            quote = m.group(1).strip()
            if is_ack(quote):
                continue
            low = f" {quote.lower()} "
            if any(tok in low or tok in quote.lower() for tok in tokens):
                hits.append(
                    {
                        "path": doc["path"],
                        "line": i,
                        "quote": quote,
                        "anchor": f"{doc['path']}:{i}",
                        "source": doc.get("source"),
                    }
                )
    return hits


def catalog_delegated_defaults(catalog: dict) -> list[dict]:
    rows = []
    for q in catalog.get("owner_questions") or []:
        if not isinstance(q, dict):
            continue
        prov = str(q.get("answer_provenance") or q.get("provenance") or "")
        state = str(q.get("state") or "")
        delegated = "delegat" in prov.lower() or "spoken" in prov.lower()
        owner_authored_path = bool(re.search(r"\S+\.(md|json):\d+", prov))
        settled = (
            state in {"ANSWERED", "SETTLED"}
            and owner_authored_path
            and not delegated
            and not is_ack(str(q.get("answer") or ""))
        )
        rows.append(
            {
                "id": q.get("id"),
                "state": state,
                "text": q.get("text"),
                "answer": q.get("answer"),
                "provenance": prov,
                "counts_as_settlement": settled,
                "why_not_settlement": (
                    None
                    if settled
                    else (
                        "catalog-row-is-delegated-or-session-summary-without-"
                        "owner-utterance-at-path-line"
                    )
                ),
            }
        )
    return rows


def classify(
    repo: Path,
    extra_docs: list[dict] | None = None,
    include_completeness_bait: bool = False,
) -> dict:
    catalog = load_catalog(repo)
    slice_units = wfa_slice_units(catalog, SLICE)
    by_id = {str(u.get("id")): u for u in slice_units}
    missing_triggers: list[str] = []
    action_rows: list[dict] = []
    docs = load_decision_docs(repo, extra_docs=extra_docs)
    live_docs = [d for d in docs if d.get("source") == "live-binding-record"]
    catalog_oq = catalog_delegated_defaults(catalog)

    for action in SPEC_ACTIONS:
        triggers = []
        for uid, reason in TRIGGERS[action]:
            u = by_id.get(uid)
            if u is None:
                missing_triggers.append(f"{action}:{uid}")
                continue
            triggers.append(
                {
                    "id": uid,
                    "title": u.get("title"),
                    "reason": reason,
                    "owner_approval_required": owner_flag(u),
                    "question_or_target": unit_question(u),
                }
            )
        observers = []
        for uid, reason in OBSERVERS.get(action, ()):
            u = by_id.get(uid)
            if u is None:
                continue
            observers.append(
                {"id": uid, "title": u.get("title"), "reason": reason}
            )

        fq = FOUNDATION_QUESTIONS[action]
        hits = owner_hits_for_action(docs, action)
        owner_impact = len(triggers) > 0
        if not owner_impact:
            disposition = "REMOVED"
            settlement = None
        elif hits:
            disposition = "SETTLED"
            settlement = hits[0]
        else:
            disposition = "ASK"
            settlement = None
        action_rows.append(
            {
                "id": f"Q-{action.replace('_', '-').upper()}",
                "action": action,
                "owner_impact": owner_impact,
                "disposition": disposition,
                "decision_log_checked": True,
                "triggering_units": triggers,
                "observer_units_not_triggers": observers,
                "question": fq["question"] if owner_impact else None,
                "recommendation": fq["recommendation"] if owner_impact else None,
                "default_if_unanswered": (
                    fq["default_if_unanswered"] if owner_impact else None
                ),
                "strongest_tradeoff": (
                    fq["strongest_tradeoff"] if owner_impact else None
                ),
                "settlement": settlement,
                "remove_reason": (
                    None
                    if owner_impact
                    else (
                        "no unit in slice WFA-1.json can trigger this "
                        "spec-named action; asking it would be completeness"
                    )
                ),
            }
        )

    bait = None
    if include_completeness_bait:
        bait = {
            **COMPLETENESS_EXAMPLE,
            "disposition": "REMOVED",
            "decision_log_checked": True,
            "triggering_units": [],
            "remove_reason": COMPLETENESS_EXAMPLE["reason"],
        }

    removed = [r for r in action_rows if r["disposition"] == "REMOVED"]
    if bait:
        removed = removed + [bait]
    settled = [r for r in action_rows if r["disposition"] == "SETTLED"]
    ask = [r for r in action_rows if r["disposition"] == "ASK"]
    ask_sorted = sorted(ask, key=lambda r: ASK_ORDER.index(r["action"]))
    presented = ask_sorted[0] if ask_sorted else None
    deferred = [r["id"] for r in ask_sorted[1:]]

    owner_flag_units = [
        {
            "id": str(u.get("id")),
            "title": u.get("title"),
            "in_spec_trigger_table": any(
                str(u.get("id")) == t[0]
                for pairs in TRIGGERS.values()
                for t in pairs
            ),
        }
        for u in slice_units
        if owner_flag(u)
    ]

    binding_present = [d["path"] for d in live_docs if d["present"]]
    return {
        "slice": SLICE,
        "slice_unit_ids": [str(u.get("id")) for u in slice_units],
        "slice_unit_count": len(slice_units),
        "missing_triggers": missing_triggers,
        "action_rows": action_rows,
        "removed": removed,
        "settled": settled,
        "ask": ask_sorted,
        "presented_now": presented,
        "deferred_ask_ids": deferred,
        "decision_docs": [
            {k: v for k, v in d.items() if k != "text"} for d in docs
        ],
        "live_binding_records_present": binding_present,
        "catalog_owner_questions": catalog_oq,
        "owner_flag_units": owner_flag_units,
        "completeness_bait": bait,
    }


def catalog_anchor(repo: Path, unit_id: str, snippet: str) -> dict:
    rel = CATALOG_REL
    text = (repo / rel).read_text(encoding="utf-8")
    line = find_line(text, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": "catalog",
        "claim": f"{unit_id} catalog row contains this snippet",
        "anchor": f"{rel}:{line}",
    }
