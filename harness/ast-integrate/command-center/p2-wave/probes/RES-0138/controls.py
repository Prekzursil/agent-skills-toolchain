"""Single source of truth for RES-0138 technical vs prompt-only controls.

The catalog names four technical-control families (egress allowlist,
read-only method allowlist, no-credential store, mandatory transcript)
and five prohibitions (transact, buy/sell, access stolen data, bypass
access control, deanonymise). A prompt-only row is recorded as
NOT ENFORCED: the kernel never reads it.
"""
from __future__ import annotations

from typing import Any

CATALOG_PROHIBITIONS = (
    "transact",
    "buy_sell",
    "stolen_data",
    "access_control_bypass",
    "deanonymise",
)

METHOD_ALLOWLIST = frozenset({"GET", "HEAD"})
FORBIDDEN_METHODS = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "CONNECT",
        "TRACE",
        "BIND",
        "UDP-ASSOCIATE",
        "RESOLVE",
        "RESOLVE_PTR",
    }
)

# Synthetic v3-shaped labels (56-char base32). Not live hosts. Never fetched.
LAWFUL_PUBLIC_ONION = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.onion"
STOLEN_DATA_MARKET_ONION = (
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.onion"
)
EGRESS_ALLOWLIST = frozenset({LAWFUL_PUBLIC_ONION})

FORBIDDEN_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-wallet",
        "x-api-key",
        "x-operator-identity",
        "x-payment-token",
    }
)

DEFAULT_OWNER_OPT_IN = False

# Prompt text is recorded so a later auditor can see it was considered
# and explicitly marked NOT ENFORCED. The kernel does not import these.
PROMPT_ONLY = (
    {
        "id": "prompt-transact",
        "prohibition": "transact",
        "text": "Do not transact on onion services.",
        "enforcement_status": "NOT ENFORCED",
    },
    {
        "id": "prompt-buy-sell",
        "prohibition": "buy_sell",
        "text": "Do not buy or sell via onion services.",
        "enforcement_status": "NOT ENFORCED",
    },
    {
        "id": "prompt-stolen",
        "prohibition": "stolen_data",
        "text": "Do not access stolen-data markets.",
        "enforcement_status": "NOT ENFORCED",
    },
    {
        "id": "prompt-bypass",
        "prohibition": "access_control_bypass",
        "text": "Do not bypass access control.",
        "enforcement_status": "NOT ENFORCED",
    },
    {
        "id": "prompt-deanon",
        "prohibition": "deanonymise",
        "text": "Do not deanonymise operators or onion services.",
        "enforcement_status": "NOT ENFORCED",
    },
)

TECHNICAL_CONTROLS: tuple[dict[str, Any], ...] = (
    {
        "prohibition": "transact",
        "kind": "read-only-method-allowlist",
        "enforcement_point": "method_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "RequestBuilder.method_gate rejects every method outside "
            "{GET, HEAD} before FixtureTransport is reached. POST/PUT/"
            "PATCH/DELETE/CONNECT never become packets."
        ),
    },
    {
        "prohibition": "buy_sell",
        "kind": "read-only-method-allowlist",
        "enforcement_point": "method_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "Buy/sell is a POST-shaped act. The same method allowlist "
            "makes the request unconstructable."
        ),
    },
    {
        "prohibition": "buy_sell",
        "kind": "no-credential-store",
        "enforcement_point": "credential_lookup",
        "enforcement_status": "ENFORCED",
        "how": (
            "CredentialStore is sealed empty. Payment tokens, wallet keys "
            "and API keys cannot be retrieved, so a buy/sell body cannot "
            "be authenticated even if a method slipped through."
        ),
    },
    {
        "prohibition": "stolen_data",
        "kind": "egress-allowlist",
        "enforcement_point": "egress_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "EgressAllowlist is a closed set of lawful-public research "
            "onion names. Stolen-data market hosts are not members, so "
            "the transport is never invoked for them."
        ),
    },
    {
        "prohibition": "access_control_bypass",
        "kind": "no-credential-store",
        "enforcement_point": "header_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "Authorization, Cookie, Proxy-Authorization and wallet "
            "headers are rejected at header_gate. There is no "
            "retry-with-credentials path after 401/403."
        ),
    },
    {
        "prohibition": "access_control_bypass",
        "kind": "read-only-method-allowlist",
        "enforcement_point": "method_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "HTTP CONNECT, SOCKS BIND and UDP-ASSOCIATE are outside the "
            "method allowlist, so tunneling around the gate is "
            "unconstructable."
        ),
    },
    {
        "prohibition": "deanonymise",
        "kind": "read-only-method-allowlist",
        "enforcement_point": "method_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "RESOLVE and RESOLVE_PTR (Tor SOCKS extensions used for "
            "identity-linking lookups) are outside the method allowlist."
        ),
    },
    {
        "prohibition": "deanonymise",
        "kind": "isolation-token",
        "enforcement_point": "isolation_gate",
        "enforcement_status": "ENFORCED",
        "how": (
            "Caller-supplied SOCKS username/password is rejected. The "
            "stage injects a session isolation token that is not derived "
            "from operator identity. x-operator-identity is a forbidden "
            "header."
        ),
    },
    {
        "prohibition": "transact",
        "kind": "mandatory-transcript",
        "enforcement_point": "transcript_append",
        "enforcement_status": "ENFORCED",
        "how": (
            "Every BLOCKED and ALLOWED decision is appended to the "
            "transcript before return. A missing log sink refuses enable."
        ),
    },
)


def missing_technical_enforcement(
    table: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
) -> list[str]:
    """Return catalog prohibitions that lack an ENFORCED technical control."""
    rows = list(TECHNICAL_CONTROLS if table is None else table)
    missing: list[str] = []
    for prohibition in CATALOG_PROHIBITIONS:
        enforced = [
            r
            for r in rows
            if r.get("prohibition") == prohibition
            and r.get("enforcement_status") == "ENFORCED"
        ]
        if not enforced:
            missing.append(prohibition)
    return missing


def prompt_only_not_enforced() -> bool:
    return all(p.get("enforcement_status") == "NOT ENFORCED" for p in PROMPT_ONLY)
