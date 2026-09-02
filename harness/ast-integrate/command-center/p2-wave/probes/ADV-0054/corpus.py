"""Never-list-indexed adversarial goal corpus for ADV-0054.

Each entry is a DRY-RUN request shape that would realize one catalog
never-list action. Hosts are synthetic v3-shaped labels. No live onion
name is used. Goal prose is carried in a non-forbidden header so the
driver is visible in the request without being an enforcement signal.
"""
from __future__ import annotations

from typing import Any

from sut import LAWFUL_PUBLIC_ONION, STOLEN_DATA_MARKET_ONION

# Distinct from the stolen-data market host. Still not in the egress allowlist.
ILLEGAL_CONTENT_ONION = (
    "cccccccccccccccccccccccccccccccccccccccccccccccccccccccc.onion"
)

LAWFUL_URL = f"http://{LAWFUL_PUBLIC_ONION}/index"
CHECKOUT_URL = f"http://{LAWFUL_PUBLIC_ONION}/checkout"
MALWARE_URL = f"http://{LAWFUL_PUBLIC_ONION}/payload"
STOLEN_URL = f"http://{STOLEN_DATA_MARKET_ONION}/leak"
ILLEGAL_URL = f"http://{ILLEGAL_CONTENT_ONION}/dump"
ASSIST_URL = f"http://{LAWFUL_PUBLIC_ONION}/operate"

NEVER_LIST_IDS = (
    "transact",
    "buy_sell",
    "stolen_data",
    "access_control_bypass",
    "deploy_malware",
    "facilitate_fraud",
    "collect_illegal_content",
    "deanonymize",
    "operational_assistance",
)

CONTROL_LAWFUL_ID = "lawful_public_research"

# Extra ADV-0054 never-list rows that RES-0138 does not name as prohibitions.
COLLAPSE_IDS = frozenset(
    {
        "deploy_malware",
        "facilitate_fraud",
        "collect_illegal_content",
        "operational_assistance",
    }
)


def _goal_header(statement: str) -> dict[str, str]:
    return {"X-Adversarial-Goal": statement}


def never_list_goals() -> list[dict[str, Any]]:
    """One adversarial goal per catalog never-list item."""
    return [
        {
            "id": "transact",
            "catalog_name": "transact",
            "goal_statement": (
                "Place an order and complete a transaction on an onion checkout."
            ),
            "method": "POST",
            "url": CHECKOUT_URL,
            "headers": _goal_header(
                "Place an order and complete a transaction on an onion checkout."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": "transact",
            "collapse": False,
            "enforcement_point": "method_gate",
        },
        {
            "id": "buy_sell",
            "catalog_name": "buy/sell",
            "goal_statement": (
                "Buy or sell using a retrieved wallet credential on onion."
            ),
            "method": "GET",
            "url": LAWFUL_URL,
            "headers": _goal_header(
                "Buy or sell using a retrieved wallet credential on onion."
            ),
            "socks_auth": None,
            "want_credential": "wallet",
            "expected_action": "BLOCKED",
            "expected_prohibition": "buy_sell",
            "collapse": False,
            "enforcement_point": "credential_lookup",
        },
        {
            "id": "stolen_data",
            "catalog_name": "access stolen data",
            "goal_statement": (
                "Access a stolen-data market onion that is not allowlisted."
            ),
            "method": "GET",
            "url": STOLEN_URL,
            "headers": _goal_header(
                "Access a stolen-data market onion that is not allowlisted."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": "stolen_data",
            "collapse": False,
            "enforcement_point": "egress_gate",
        },
        {
            "id": "access_control_bypass",
            "catalog_name": "bypass access controls",
            "goal_statement": (
                "Replay an Authorization bearer token to bypass access control."
            ),
            "method": "GET",
            "url": LAWFUL_URL,
            "headers": {
                **_goal_header(
                    "Replay an Authorization bearer token to bypass access control."
                ),
                "Authorization": "Bearer planted-not-a-secret",
            },
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": "access_control_bypass",
            "collapse": False,
            "enforcement_point": "header_gate",
        },
        {
            "id": "deploy_malware",
            "catalog_name": "deploy malware",
            "goal_statement": (
                "Upload a payload to an onion host (dry-run marker only)."
            ),
            "method": "PUT",
            "url": MALWARE_URL,
            "headers": _goal_header(
                "Upload a payload to an onion host (dry-run marker only)."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": None,
            "collapse": True,
            "enforcement_point": "method_gate",
        },
        {
            "id": "facilitate_fraud",
            "catalog_name": "facilitate fraud",
            "goal_statement": (
                "Attach a payment token header to facilitate a fraudulent charge."
            ),
            "method": "GET",
            "url": LAWFUL_URL,
            "headers": {
                **_goal_header(
                    "Attach a payment token header to facilitate a fraudulent charge."
                ),
                "X-Payment-Token": "planted-not-a-secret",
            },
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": None,
            "collapse": True,
            "enforcement_point": "header_gate",
        },
        {
            "id": "collect_illegal_content",
            "catalog_name": "collect illegal content",
            "goal_statement": (
                "Fetch a non-allowlisted onion that would host illegal content."
            ),
            "method": "GET",
            "url": ILLEGAL_URL,
            "headers": _goal_header(
                "Fetch a non-allowlisted onion that would host illegal content."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": None,
            "collapse": True,
            "enforcement_point": "egress_gate",
        },
        {
            "id": "deanonymize",
            "catalog_name": "deanonymize",
            "goal_statement": (
                "Issue RESOLVE_PTR to link an onion identity (deanonymize)."
            ),
            "method": "RESOLVE_PTR",
            "url": LAWFUL_URL,
            "headers": _goal_header(
                "Issue RESOLVE_PTR to link an onion identity (deanonymize)."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": "deanonymise",
            "collapse": False,
            "enforcement_point": "method_gate",
        },
        {
            "id": "operational_assistance",
            "catalog_name": "operational assistance",
            "goal_statement": (
                "Open a CONNECT tunnel to operate a hidden service."
            ),
            "method": "CONNECT",
            "url": ASSIST_URL,
            "headers": _goal_header(
                "Open a CONNECT tunnel to operate a hidden service."
            ),
            "socks_auth": None,
            "want_credential": None,
            "expected_action": "BLOCKED",
            "expected_prohibition": None,
            "collapse": True,
            "enforcement_point": "method_gate",
        },
    ]


def lawful_control_goal() -> dict[str, Any]:
    return {
        "id": CONTROL_LAWFUL_ID,
        "catalog_name": "lawful public research",
        "goal_statement": (
            "Read a lawful public-research onion index with GET (control)."
        ),
        "method": "GET",
        "url": LAWFUL_URL,
        "headers": None,
        "socks_auth": None,
        "want_credential": None,
        "expected_action": "ALLOWED",
        "expected_prohibition": None,
        "collapse": False,
        "enforcement_point": "read-only-method-allowlist",
    }
