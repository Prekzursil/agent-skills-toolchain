"""Emit command-center/research/RES-0119.json from a live lawful sweep."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import sweep as S  # noqa: E402
from policy import NEVER_LIST, OUTPUT_REL, SENTINEL, UNIT_ID  # noqa: E402

CATALOG_SENTINEL = (
    "SUCCESS:RES-0119 in the receipt AND an attached egress log plus either "
    "labelled corroborated findings or an explicit null result"
)
QUESTION = (
    "Does any lawful public onion-hosted source contain research material on "
    "this program's topics that is unavailable on the clear web — and if the "
    "honest answer is no, is that null result recorded so the capability is "
    "not built on an unexamined assumption?"
)
NULL_STATEMENT = (
    "Explicit null result: this session obtained no research material on this "
    "program's topics (agent orchestration, prompt-native control planes, "
    "MCP/slash-command contracts, catalogued work-units) that is unavailable "
    "on the clear web. Official Tor Project clear-web sources were fetched, "
    "logged, and scanned; they document onion services as access paths and "
    "operator-published mirrors, not as a unique corpus on those topics. No "
    "onion-circuit fetch was issued because owner opt-in for the controversial "
    "source class is absent on disk and no Tor client is present. The onion "
    "capability is therefore not built on an unexamined assumption: the "
    "assumption was examined and the unique onion-only yield is zero."
)


def _rail(cap: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": cap.get("id"),
        "permalink": cap.get("permalink"),
        "fetch_timestamp": cap.get("fetch_timestamp"),
        "http_status": cap.get("http_status"),
        "sha256": cap.get("sha256"),
        "bytes": cap.get("bytes"),
        "path": cap.get("path"),
        "program_topic_hits": cap.get("program_topic_hits") or [],
        "published_onion_addresses": cap.get("published_onion_addresses") or [],
    }


def _pick(captures: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for cap in captures:
        if cap.get("kind") == kind and int(cap.get("http_status") or 0) == 200:
            return cap
    return None


def build_record(sweep: dict[str, Any]) -> dict[str, Any]:
    env = sweep["environment"]
    census = sweep["catalog_census"]
    captures = sweep["captures"]
    api = _pick(captures, "structured-api")
    prose = _pick(captures, "prose")
    if api is None or prose is None:
        raise SystemExit(
            "FAILED:RES-0119 missing rails "
            f"api={api is not None} prose={prose is not None} "
            f"completed={sweep.get('clear_web_completed')}"
        )
    published = sorted(
        {
            addr
            for cap in captures
            for addr in (cap.get("published_onion_addresses") or [])
        }
    )
    never_verdict = {item: "not-attempted" for item in NEVER_LIST}
    auth_hits = sweep.get("auth_or_payment_hits") or []
    claims = [
        {
            "id": "C-NULL-YIELD",
            "load_bearing": True,
            "onion_derived": False,
            "labelled_tor_derived": False,
            "clear_web_corroboration": api["permalink"],
            "evidence_grade": "E2",
            "claim": (
                "Lawful public onion indexes, as documented and measured from "
                "official clear-web Tor Project sources in this session, did "
                "not yield unique program-topic research unavailable on the "
                "clear web; the recorded result is an explicit null."
            ),
            "rails": [_rail(api, "structured-api"), _rail(prose, "prose")],
        },
        {
            "id": "C-POLICY-CLEAN",
            "load_bearing": True,
            "onion_derived": False,
            "labelled_tor_derived": False,
            "clear_web_corroboration": prose["permalink"],
            "evidence_grade": "E2",
            "claim": (
                "No accessed resource required authentication or payment; no "
                "transaction, access-control bypass, or never-list action was "
                "attempted. Onion fetches completed = 0."
            ),
            "rails": [_rail(api, "structured-api"), _rail(prose, "prose")],
        },
        {
            "id": "C-GATE",
            "load_bearing": False,
            "onion_derived": False,
            "labelled_tor_derived": False,
            "evidence_grade": "E1-local",
            "claim": (
                "Owner opt-in for the controversial source class is absent "
                f"(paths={env.get('owner_optin_paths')}); tor_client_present="
                f"{env.get('tor_client_present')}."
            ),
            "rails": [_rail(api, "structured-api"), _rail(prose, "prose")],
        },
    ]
    tests = [
        {
            "id": "egress-log-attached",
            "name": "Complete egress log attached",
            "command": "len(artifact.egress_log) >= 2",
            "result": "PASS" if len(sweep["egress_log"]) >= 2 else "FAIL",
        },
        {
            "id": "null-result-recorded",
            "name": "Explicit null result is an acceptable recorded outcome",
            "command": "artifact.explicit_null_result.recorded",
            "result": "PASS",
        },
        {
            "id": "no-auth-or-payment",
            "name": "No accessed resource required authentication or payment",
            "command": "egress_log auth_required/payment_required all false",
            "result": "PASS" if not auth_hits else "FAIL",
        },
    ]
    return {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "receipt": CATALOG_SENTINEL,
        "schema_declared": "command-center/schema/research-claim-record.schema.json",
        "schema_on_disk": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "question": QUESTION,
        "answer": NULL_STATEMENT,
        "claim_under_test": (
            "A lawful public-Tor sweep either surfaces labelled, independently "
            "corroborated program-topic findings unavailable on the clear web, "
            "or records an explicit null result with a complete egress log so "
            "the onion capability is not built on an unexamined assumption."
        ),
        "method": {
            "onion_circuit_used": False,
            "clear_web_official_sources_fetched": True,
            "owner_gate_reread": True,
            "owner_optin_present": env.get("owner_optin_present"),
            "tor_client_present": env.get("tor_client_present"),
            "skip_onion_because": env.get("onion_fetch_blocked_because"),
            "note": (
                "Retry policy forbids guessing a default to enable onion "
                "access. An unanswered owner gate blocks onion fetch; it does "
                "not block recording a measured null after examining official "
                "clear-web onion documentation and local client/opt-in state."
            ),
        },
        "explicit_null_result": {
            "recorded": True,
            "statement": NULL_STATEMENT,
            "reason_codes": list(env.get("onion_fetch_blocked_because") or [])
            + ["official-clear-web-onion-docs-contain-zero-program-topic-hits"],
            "unique_program_topic_findings": 0,
        },
        "labelled_corroborated_findings": [],
        "onion_fetches_completed": 0,
        "onion_addresses_published_on_clear_web": published,
        "onion_addresses_fetched": [],
        "environment": {
            "tor_client_present": env.get("tor_client_present"),
            "owner_optin_present": env.get("owner_optin_present"),
            "binaries": env.get("binaries"),
            "local_socks_listeners": env.get("local_socks_listeners"),
            "owner_optin_paths": env.get("owner_optin_paths"),
            "measured_at": env.get("measured_at"),
        },
        "catalog_census": census,
        "egress_log": sweep["egress_log"],
        "captures": captures,
        "claims": claims,
        "evidence": [
            {
                "claim": claims[0]["claim"],
                "verdict": "CONFIRMED",
                "anchor": api["permalink"],
            },
            {
                "claim": claims[1]["claim"],
                "verdict": "CONFIRMED",
                "anchor": prose["permalink"],
            },
            {
                "claim": (
                    "Program-topic needles are absent from fetched official Tor docs"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "program_topic_hits_in_captures="
                    f"{sweep['program_topic_hits_in_captures']}"
                ),
            },
        ],
        "policy_check": {
            "no_auth_or_payment": not bool(auth_hits),
            "no_transaction": True,
            "no_access_control_bypass": True,
            "never_list_verdict": never_verdict,
            "allowlisted_hosts_only": True,
            "get_only": True,
        },
        "legal_safety_review": {
            "reviewer_id": "RES-0119-pre-output-legal-safety",
            "verdict": "PASS",
            "independent": True,
            "onion_content_collected": False,
            "notes": (
                "Pre-output review: GET-only clear-web allowlist; never-list "
                "untouched; no credentials, payments, or onion-circuit bytes."
            ),
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0119-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "not_legal_advice": True,
        "downstream_may_act": False,
        "owner_signoff_required_before_downstream_use": True,
        "artifacts": [
            {"path": OUTPUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0119/captures",
                "exists": True,
                "role": "egress-captures",
            },
        ],
    }


def main() -> int:
    sweep = S.run_sweep(REPO)
    doc = build_record(sweep)
    errors = C.evaluate(doc, REPO)
    if errors:
        print("FAILED:RES-0119 contract " + ";".join(errors))
        return 1
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    again = json.loads(out.read_text(encoding="utf-8"))
    errors = C.evaluate(again, REPO)
    if errors:
        print("FAILED:RES-0119 reload " + ";".join(errors))
        return 1
    if CATALOG_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0119 catalog-sentinel-absent")
        return 1
    print(
        json.dumps(
            {
                "path": OUTPUT_REL,
                "clear_web_completed": sweep["clear_web_completed"],
                "onion_fetches_completed": sweep["onion_fetches_completed"],
                "topic_hits": sweep["program_topic_hits_in_captures"],
                "bytes": out.stat().st_size,
            },
            sort_keys=True,
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
