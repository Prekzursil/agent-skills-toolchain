"""Lawful public-Tor sweep policy for RES-0119."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

UNIT_ID = "RES-0119"
SENTINEL = "SUCCESS:RES-0119"
OUTPUT_REL = "command-center/research/RES-0119.json"

ALLOWED_HOSTS = frozenset(
    {
        "onionoo.torproject.org",
        "community.torproject.org",
        "support.torproject.org",
        "www.torproject.org",
        "torproject.org",
    }
)

CLEAR_WEB_TARGETS = (
    {
        "id": "onionoo-summary",
        "url": "https://onionoo.torproject.org/summary?limit=1",
        "kind": "structured-api",
        "rail": "R1",
        "why": (
            "Public JSON directory of Tor relays. A live structured API on the "
            "clear web; not a research index of this program's topics."
        ),
    },
    {
        "id": "community-onion-overview",
        "url": "https://community.torproject.org/onion-services/overview/",
        "kind": "prose",
        "rail": "R2",
        "why": (
            "Official Tor Project prose describing onion services as an access "
            "path, not as a unique corpus of agent-orchestration research."
        ),
    },
    {
        "id": "support-onion-v3",
        "url": "https://support.torproject.org/onionservices/onionservices-3/",
        "kind": "prose",
        "rail": "R2b",
        "why": "Operator-facing onion-service documentation on the clear web.",
    },
    {
        "id": "torproject-home",
        "url": "https://www.torproject.org/",
        "kind": "prose",
        "rail": "R2c",
        "why": (
            "Official homepage scanned for operator-published .onion addresses "
            "(clear-web advertisements of mirrors). Addresses are recorded, "
            "not fetched over Tor."
        ),
    },
)

NEVER_LIST = (
    "transact",
    "buy_sell",
    "access_stolen_data",
    "bypass_access_control",
    "deploy_malware",
    "facilitate_fraud",
    "collect_illegal_content",
    "deanonymize",
    "operational_assistance",
)

PROGRAM_TOPIC_NEEDLES = (
    "prompt-native",
    "slash-command",
    "mcp server",
    "model context protocol",
    "agent orchestration",
    "work-unit catalog",
    "command-center/research",
    "council deliberation",
    "subagent task semantics",
)

OPTIN_NAME_FRAGMENTS = (
    "tor-opt-in",
    "onion-opt-in",
    "controversial-source-opt-in",
    "owner-opt-in-tor",
    "tor-owner-gate",
)

SKIP_DIR_NAMES = frozenset(
    {".git", "node_modules", "__pycache__", ".venv", "captures", "fixtures"}
)

USER_AGENT = (
    "RES-0119-lawful-public-research/1.0 "
    "(+clear-web-allowlist-only; no-onion-circuit)"
)


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www.") and host[4:] in ALLOWED_HOSTS:
        return True
    return host in ALLOWED_HOSTS


def looks_like_optin(path: Path) -> bool:
    name = path.name.lower()
    return any(frag in name for frag in OPTIN_NAME_FRAGMENTS)
