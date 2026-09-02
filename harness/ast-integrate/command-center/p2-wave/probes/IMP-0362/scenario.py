"""Shared IMP-0362 fixtures: prepared / unprepared / assert-without-fetch."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COUNCIL = REPO / "tools" / "council"
sys.path.insert(0, str(COUNCIL))

from prep import (  # noqa: E402
    AssertionWithoutFetchError,
    PrepArtifact,
    PrepGate,
    UnpreparedError,
    digest_bytes,
    parse_tool_call,
)

WORKSPACE = HERE / "fixtures" / "workspace"
BRIEF = "sources/brief.md"
PROTOCOL = "sources/protocol.md"
URL = "https://example.test/council/prep-requirement"

ALICE_NOTES = (
    "After reading the brief, quorum-recusal-anchor-zeta is the load-bearing "
    "token. The protocol says prep-gate-must-block-unprepared is a speaking right."
)
CAROL_NOTES = "I completed the required reading and I am prepared to speak."


def workspace_root() -> Path:
    return WORKSPACE.resolve()


def file_digest(rel: str) -> tuple[str, int]:
    raw = (WORKSPACE / rel).read_bytes()
    return digest_bytes(raw), len(raw)


def gate() -> PrepGate:
    return PrepGate(workspace_root())


def alice_artifact() -> PrepArtifact:
    return PrepArtifact(
        participant_id="alice",
        notes=ALICE_NOTES,
        source_anchors=[BRIEF, PROTOCOL],
        asserted_prepared=False,
        path="artifact:alice",
    )


def alice_fetches() -> list[dict[str, Any]]:
    b_sha, b_n = file_digest(BRIEF)
    p_sha, p_n = file_digest(PROTOCOL)
    return [
        {
            "tool": "Read",
            "target": BRIEF,
            "status": "ok",
            "sha256": b_sha,
            "bytes": b_n,
        },
        {
            "tool": "Read",
            "arguments": {"path": PROTOCOL},
            "status": "ok",
            "sha256": p_sha,
            "bytes": p_n,
        },
    ]


def bob_empty() -> PrepArtifact:
    return PrepArtifact(
        participant_id="bob",
        notes="",
        source_anchors=[],
        asserted_prepared=False,
        path="artifact:bob-empty",
    )


def carol_asserted() -> PrepArtifact:
    return PrepArtifact(
        participant_id="carol",
        notes=CAROL_NOTES,
        source_anchors=[BRIEF],
        asserted_prepared=True,
        path="artifact:carol-asserted",
    )


def dave_asserted_tool() -> list[dict[str, Any]]:
    """Looks like a Read, but status=asserted so it must not count."""
    return [
        {
            "tool": "Read",
            "target": BRIEF,
            "status": "asserted",
            "asserted": True,
        }
    ]


def eve_url_artifact() -> PrepArtifact:
    return PrepArtifact(
        participant_id="eve",
        notes=(
            "Fetched the remote prep-requirement page. "
            "quorum-recusal-anchor-zeta still applies remotely."
        ),
        source_anchors=[URL],
        asserted_prepared=False,
        path="artifact:eve-url",
    )


def eve_fetches() -> list[dict[str, Any]]:
    snippet = (
        "Remote copy: the load-bearing token is quorum-recusal-anchor-zeta. "
        "Preparation is verified by fetch, not by assertion."
    )
    return [
        {
            "tool": "WebFetch",
            "url": URL,
            "status": "ok",
            "snippet": snippet,
            "sha256": hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
            "bytes": len(snippet.encode("utf-8")),
        }
    ]


def run_cases() -> dict[str, Any]:
    g = gate()
    alice = g.evaluate("alice", alice_artifact(), alice_fetches())
    bob_none = g.evaluate("bob", None, [])
    bob = g.evaluate("bob", bob_empty(), [])
    carol = g.evaluate("carol", carol_asserted(), [])
    dave = g.evaluate("carol", carol_asserted(), dave_asserted_tool())
    eve = g.evaluate("eve", eve_url_artifact(), eve_fetches())
    eve_bare = g.evaluate("eve", eve_url_artifact(), [])

    unprepared_blocked = False
    try:
        g.require_prepared("bob", None, [])
    except UnpreparedError:
        unprepared_blocked = True

    assert_without_fetch_fired = False
    try:
        g.require_prepared("carol", carol_asserted(), [])
    except AssertionWithoutFetchError:
        assert_without_fetch_fired = True

    before_ok = False
    try:
        from prep import before_turn

        before_turn(
            g,
            {"participant_id": "alice"},
            artifacts={"alice": alice_artifact()},
            logs={"alice": alice_fetches()},
        )
        before_ok = True
    except (UnpreparedError, AssertionWithoutFetchError):
        before_ok = False

    return {
        "alice_allowed": alice.allowed_to_speak,
        "alice_prepared": alice.prepared,
        "alice_corroboration_fired": alice.corroboration_fired,
        "alice_notes_grounded": alice.notes_grounded,
        "alice_resolved": len(alice.resolved_anchors),
        "bob_none_allowed": bob_none.allowed_to_speak,
        "bob_none_fired": bob_none.corroboration_fired,
        "bob_empty_allowed": bob.allowed_to_speak,
        "bob_empty_fired": bob.corroboration_fired,
        "unprepared_blocked": unprepared_blocked,
        "carol_allowed": carol.allowed_to_speak,
        "carol_fired": carol.corroboration_fired,
        "dave_asserted_tool_fired": dave.corroboration_fired,
        "dave_asserted_tool_allowed": dave.allowed_to_speak,
        "eve_allowed": eve.allowed_to_speak,
        "eve_fired": eve.corroboration_fired,
        "eve_bare_fired": eve_bare.corroboration_fired,
        "assert_without_fetch_fired": assert_without_fetch_fired,
        "before_turn_alice_ok": before_ok,
        "alice_reasons": alice.reasons,
        "carol_reasons": carol.reasons,
        "bob_reasons": bob_none.reasons,
        "parse_asserted_is_not_fetch": not parse_tool_call(dave_asserted_tool()[0]).is_real_fetch(),
    }


def main() -> int:
    doc = run_cases()
    print(json.dumps(doc, indent=2, sort_keys=True))
    ok = (
        doc["alice_allowed"]
        and doc["unprepared_blocked"]
        and not doc["bob_none_allowed"]
        and doc["carol_fired"]
        and doc["assert_without_fetch_fired"]
        and doc["eve_allowed"]
    )
    print("SUCCESS:IMP-0362-scenario" if ok else "FAILED:IMP-0362-scenario")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
