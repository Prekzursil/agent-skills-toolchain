"""Read-only public-research legal/safety review. Must pass before consume."""
from __future__ import annotations

from urllib.parse import urlparse

NEVER = (
    "transaction",
    "purchase",
    "buy",
    "sell",
    "payment",
    "stolen-data",
    "stolen data",
    "access-control-bypass",
    "bypass access control",
    "deanonymize",
    "deanonymisation",
    "deanonymization",
)
ALLOWED_SCHEMES = {"http", "https"}
READ_ACTIONS = frozenset({"read-public-http", "read-fixture", "skip"})


def review(*, actions: list[str], urls: list[str], quotes: list[str], **kw) -> dict:
    onion_fetches = kw.get("onion_fetches")
    if onion_fetches is None:
        onion_fetches = kw.get("onion_fetches", 0)
    onion_fetches = int(onion_fetches or 0)
    hits: list[str] = []
    for token in NEVER:
        if any(token in a.lower() for a in actions) or any(
            token in (u or "").lower() for u in urls
        ):
            hits.append(token)
    bad_actions = [a for a in actions if a not in READ_ACTIONS]
    bad_schemes = []
    for url in urls:
        if not url:
            continue
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        scheme = (parsed.scheme or "").lower()
        if host.endswith(".onion"):
            continue
        if scheme and scheme not in ALLOWED_SCHEMES:
            bad_schemes.append(url)
    ok = not hits and not bad_actions and not bad_schemes and onion_fetches == 0
    return {
        "pass": ok,
        "mandatory_before_downstream_consume": True,
        "scope": "read-only-public-research",
        "never_list_hits": hits,
        "disallowed_actions": bad_actions,
        "disallowed_schemes": bad_schemes,
        "onion_live_fetches": onion_fetches,
        "wfa0031_artifact": {
            "path": "command-center/wfa/WFA-0031-acquisition-legal-gate.json",
            "present": False,
            "note": (
                "WFA-0031 is a dependency and is absent on this worktree. "
                "This unit still performs its own pre-output review and does "
                "not treat that absence as a licence to skip review."
            ),
        },
        "consume_allowed": ok,
        "verdict": "PASS" if ok else "FAIL-CLOSED",
    }


def refuse_if_action(action: str) -> dict:
    return review(actions=[action], urls=[], quotes=[], onion_fetches=0)


refuse_if_action = refuse_if_action
