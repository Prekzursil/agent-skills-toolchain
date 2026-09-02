"""Contract checks for the RES-0119 research artifact."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from policy import NEVER_LIST, SENTINEL, UNIT_ID

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
RAIL_KEYS = ("permalink", "fetch_timestamp", "http_status", "sha256")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(doc: Any, repo: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["artifact-not-object"]

    if doc.get("unit_id") != UNIT_ID:
        errors.append("unit_id")
    state = str(doc.get("state") or "")
    if state != "SUCCESS" or state in NOT_DELIVERING:
        errors.append(f"state:{state or 'missing'}")
    if SENTINEL not in str(doc.get("sentinel") or ""):
        errors.append("sentinel-field")
    catalog_sentinel = (
        "SUCCESS:RES-0119 in the receipt AND an attached egress log plus either "
        "labelled corroborated findings or an explicit null result"
    )
    if catalog_sentinel not in str(doc.get("completion_sentinel") or ""):
        errors.append("completion-sentinel")

    null = doc.get("explicit_null_result") or {}
    if not isinstance(null, dict) or null.get("recorded") is not True:
        errors.append("explicit-null-not-recorded")
    if len(str(null.get("statement") or "")) < 40:
        errors.append("explicit-null-statement-short")

    findings = doc.get("labelled_corroborated_findings")
    if findings is None:
        errors.append("labelled-findings-field-absent")
    elif not isinstance(findings, list):
        errors.append("labelled-findings-not-list")
    elif findings:
        errors.append("unexpected-onion-findings-while-null")

    egress = doc.get("egress_log")
    if not isinstance(egress, list) or len(egress) < 2:
        errors.append("egress-log-missing-or-short")
    else:
        clear_ok = 0
        onion_completed = 0
        for i, row in enumerate(egress):
            if not isinstance(row, dict):
                errors.append(f"egress[{i}]-not-object")
                continue
            if row.get("auth_required") or row.get("payment_required"):
                errors.append(f"egress[{i}]-auth-or-payment")
            if row.get("class") == "clear-web" and row.get("completed"):
                clear_ok += 1
                if int(row.get("http_status") or 0) != 200:
                    errors.append(f"egress[{i}]-non-200")
            if row.get("class") == "onion" and row.get("completed"):
                onion_completed += 1
        if clear_ok < 2:
            errors.append("egress-clear-web-completed-lt-2")
        if onion_completed:
            errors.append("onion-fetch-completed-without-gate")

    policy = doc.get("policy_check") or {}
    if policy.get("no_auth_or_payment") is not True:
        errors.append("policy-no-auth-or-payment")
    if policy.get("no_transaction") is not True:
        errors.append("policy-no-transaction")
    if policy.get("no_access_control_bypass") is not True:
        errors.append("policy-no-bypass")
    never = policy.get("never_list_verdict") or {}
    for item in NEVER_LIST:
        if never.get(item) != "not-attempted":
            errors.append(f"never-list-{item}")

    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 2:
        errors.append("claims-missing")
    load_bearing = [
        c for c in claims if isinstance(c, dict) and c.get("load_bearing")
    ]
    if len(load_bearing) < 2:
        errors.append("load-bearing-claims-lt-2")
    for c in load_bearing:
        cid = c.get("id") or "?"
        rails = c.get("rails") or []
        if not isinstance(rails, list) or len(rails) < 2:
            errors.append(f"claim-{cid}-rails-lt-2")
            continue
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if "structured-api" not in kinds or "prose" not in kinds:
            errors.append(f"claim-{cid}-rails-not-api-plus-prose")
        for r in rails:
            if not isinstance(r, dict):
                errors.append(f"claim-{cid}-rail-not-object")
                continue
            for k in RAIL_KEYS:
                if r.get(k) in (None, ""):
                    errors.append(f"claim-{cid}-rail-missing-{k}")
            if int(r.get("http_status") or 0) != 200:
                errors.append(f"claim-{cid}-rail-http")
        if c.get("onion_derived"):
            if not c.get("labelled_tor_derived"):
                errors.append(f"claim-{cid}-unlabeled-tor")
            if not c.get("clear_web_corroboration"):
                errors.append(f"claim-{cid}-uncorroborated-tor")

    captures = doc.get("captures") or []
    if not isinstance(captures, list) or len(captures) < 2:
        errors.append("captures-missing")
    for cap in captures:
        if not isinstance(cap, dict):
            errors.append("capture-not-object")
            continue
        rel = cap.get("path")
        if not rel:
            errors.append("capture-path-missing")
            continue
        path = repo / str(rel)
        if not path.is_file() or path.stat().st_size <= 0:
            errors.append(f"capture-absent:{rel}")
            continue
        if _sha_file(path) != cap.get("sha256"):
            errors.append(f"capture-sha-mismatch:{rel}")
        if cap.get("program_topic_hits"):
            errors.append(f"capture-unexpected-program-topic:{rel}")

    env = doc.get("environment") or {}
    if env.get("tor_client_present") is True:
        errors.append("artifact-claims-tor-present")
    if env.get("owner_optin_present") is True:
        errors.append("artifact-claims-optin-present")
    if int(doc.get("onion_fetches_completed") or 0) != 0:
        errors.append("onion-fetches-completed-nonzero")

    review = doc.get("legal_safety_review") or {}
    if review.get("verdict") != "PASS":
        errors.append("legal-safety-review")
    if review.get("onion_content_collected") is True:
        errors.append("review-claims-onion-content")

    tests = doc.get("tests") or []
    needed = {
        "egress-log-attached",
        "null-result-recorded",
        "no-auth-or-payment",
    }
    by_id = {t.get("id"): t for t in tests if isinstance(t, dict)}
    for tid in needed:
        if (by_id.get(tid) or {}).get("result") != "PASS":
            errors.append(f"test-{tid}")

    return errors


def mutants(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []

    m = deepcopy(doc)
    m["egress_log"] = []
    out.append(("drop-egress-log", m))

    m = deepcopy(doc)
    m["explicit_null_result"] = {"recorded": False, "statement": ""}
    m["labelled_corroborated_findings"] = []
    out.append(("drop-null-and-findings", m))

    m = deepcopy(doc)
    m["labelled_corroborated_findings"] = [
        {
            "id": "planted-unlabeled-onion",
            "onion_derived": True,
            "labelled_tor_derived": False,
            "text": "planted unique onion-only orchestration paper",
        }
    ]
    planted_claim = {
        "id": "C-PLANT",
        "load_bearing": True,
        "onion_derived": True,
        "labelled_tor_derived": False,
        "clear_web_corroboration": None,
        "claim": "planted unlabeled onion finding",
        "evidence_grade": "E3",
        "rails": [
            {
                "kind": "structured-api",
                "permalink": "http://example.onion/x",
                "fetch_timestamp": "x",
                "http_status": 200,
                "sha256": "0" * 64,
            },
            {
                "kind": "prose",
                "permalink": "http://example.onion/y",
                "fetch_timestamp": "x",
                "http_status": 200,
                "sha256": "1" * 64,
            },
        ],
    }
    m["claims"] = list(m.get("claims") or []) + [planted_claim]
    out.append(("unlabeled-onion-claim", m))

    m = deepcopy(doc)
    if m.get("egress_log"):
        m["egress_log"][0] = dict(m["egress_log"][0])
        m["egress_log"][0]["auth_required"] = True
        m["policy_check"] = dict(m.get("policy_check") or {})
        m["policy_check"]["no_auth_or_payment"] = False
    out.append(("auth-required-resource", m))

    m = deepcopy(doc)
    claims = deepcopy(m.get("claims") or [])
    if claims and isinstance(claims[0].get("rails"), list):
        claims[0]["rails"] = claims[0]["rails"][:1]
    m["claims"] = claims
    out.append(("single-rail-load-bearing", m))

    m = deepcopy(doc)
    m["state"] = "BLOCKED"
    out.append(("self-declared-blocked", m))

    m = deepcopy(doc)
    m["captures"] = []
    out.append(("drop-captures", m))

    return out
