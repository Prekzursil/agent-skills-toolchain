#!/usr/bin/env python3
"""Executable plugin-manifest conformance suite (TST-0033).

Written against the client's published SchemaStore schema + documented
`--strict` overlay, before IMP-0006 authors an in-repo schema.

Each contract rule has a negative fixture. A both-states control runs the
same loader on conforming.json (must accept) and unknown-top-level.json
(must reject, naming the field). A mutation control relaxes
additionalProperties and shows the unknown-key case going green, proving
the rejection is that rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import client_strict_loader as L  # noqa: E402

REPO = HERE.parents[3]
LIVE = REPO / ".claude-plugin" / "plugin.json"
FIX = HERE / "fixtures"
UNKNOWN_KEY = "notARealField"

# One negative case per contract rule the published strict parser actually has.
RULES: list[dict[str, Any]] = [
    {
        "id": "json-object",
        "rule": "Manifest bytes must parse as a JSON object",
        "negative": "invalid.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "top-level-object",
        "rule": "Top-level JSON value must be an object",
        "negative": "not-object.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "name-required",
        "rule": "If a manifest is present, name is required",
        "negative": "missing-name.json",
        "want_ok": False,
        "must_name": "name",
    },
    {
        "id": "name-type",
        "rule": "name must be a non-empty string",
        "negative": "name-wrong-type.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "name-minlength",
        "rule": "name minLength is 1",
        "negative": "empty-name.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "keywords-type",
        "rule": "keywords, when present, must be an array (wrong type is a load error)",
        "negative": "keywords-wrong-type.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "author-type",
        "rule": "author, when present, must be an object",
        "negative": "author-wrong-type.json",
        "want_ok": False,
        "must_name": None,
    },
    {
        "id": "unknown-top-level",
        "rule": "Under the strict parser, an unknown top-level field is a load failure that names the field",
        "negative": "unknown-top-level.json",
        "want_ok": False,
        "must_name": UNKNOWN_KEY,
    },
]


def _blob(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _errors_name_token(errors: list[str], token: str) -> bool:
    blob = " ".join(errors)
    return token in blob


def run_case(raw: str, *, strict: bool = True) -> L.LoadResult:
    return L.load_text(raw, strict=strict)


def live_shipped() -> dict[str, Any]:
    if not LIVE.is_file():
        return {
            "path": ".claude-plugin/plugin.json",
            "present": False,
            "ok": False,
            "verdict": "NOT-CHECKED",
            "errors": ["absent on this worktree"],
            "note": (
                "IMP-0009 also recorded this path ABSENT. The contract is "
                "exercised on fixtures; restoring the shipped bytes is the "
                "settling experiment."
            ),
        }
    result = L.load_path(LIVE, strict=True)
    return {
        "path": ".claude-plugin/plugin.json",
        "present": True,
        "ok": result.ok,
        "verdict": "PASS" if result.ok else "FAIL",
        "errors": result.errors,
        "parser": result.parser,
        "bytes": LIVE.stat().st_size,
    }


def both_states() -> dict[str, Any]:
    good = run_case(_blob("conforming.json"), strict=True)
    bad = run_case(_blob("unknown-top-level.json"), strict=True)
    named = _errors_name_token(bad.errors, UNKNOWN_KEY) or (
        UNKNOWN_KEY in bad.named_unknown_fields
    )
    holds = good.ok and (not bad.ok) and named
    return {
        "id": "both-states-unknown-top-level",
        "holds": holds,
        "conforming_ok": good.ok,
        "conforming_errors": good.errors,
        "unknown_ok": bad.ok,
        "unknown_errors": bad.errors,
        "unknown_field_named": named,
        "unknown_field": UNKNOWN_KEY,
        "good_state": "fixtures/conforming.json accepted",
        "bad_state": (
            f"fixtures/unknown-top-level.json rejected; errors name {UNKNOWN_KEY!r}"
        ),
    }


def mutation_unknown_is_the_rule() -> dict[str, Any]:
    """Relax additionalProperties; the unknown-key fixture must go green."""
    raw = _blob("unknown-top-level.json")
    strict = run_case(raw, strict=True)
    lenient = run_case(raw, strict=False)
    holds = (not strict.ok) and lenient.ok
    return {
        "id": "mutation-additionalProperties-false",
        "holds": holds,
        "strict_rejects": not strict.ok,
        "lenient_accepts": lenient.ok,
        "strict_errors": strict.errors,
        "lenient_errors": lenient.errors,
        "proves": (
            "The unknown-key case fails because of the --strict overlay "
            "(additionalProperties=false), not because the fixture is otherwise broken"
        ),
    }


def per_rule() -> list[dict[str, Any]]:
    rows = []
    for rule in RULES:
        raw = _blob(rule["negative"])
        result = run_case(raw, strict=True)
        named_ok = True
        token = rule["must_name"]
        if token:
            named_ok = _errors_name_token(result.errors, token) or (
                token in result.named_unknown_fields
            )
        passed = (result.ok is rule["want_ok"]) and named_ok
        rows.append(
            {
                "id": rule["id"],
                "requirement": rule["rule"],
                "fixture": f"fixtures/{rule['negative']}",
                "want_ok": rule["want_ok"],
                "got_ok": result.ok,
                "errors": result.errors,
                "verdict": "PASS" if passed else "FAIL",
                "evidence": (
                    f"parser={result.parser} ok={result.ok} errors={result.errors!r}"
                ),
            }
        )
    # Positive case for the same suite.
    good = run_case(_blob("conforming.json"), strict=True)
    rows.insert(
        0,
        {
            "id": "conforming-accepted",
            "requirement": "A manifest using only published fields is accepted by the strict parser",
            "fixture": "fixtures/conforming.json",
            "want_ok": True,
            "got_ok": good.ok,
            "errors": good.errors,
            "verdict": "PASS" if good.ok else "FAIL",
            "evidence": f"parser={good.parser} ok={good.ok} errors={good.errors!r}",
        },
    )
    return rows


def run_suite() -> dict[str, Any]:
    tests = per_rule()
    control = both_states()
    mutation = mutation_unknown_is_the_rule()
    live = live_shipped()
    schema = L.official_schema()
    all_pass = (
        all(t["verdict"] == "PASS" for t in tests)
        and control["holds"]
        and mutation["holds"]
    )
    return {
        "ok": all_pass,
        "parser": {
            "identity": "claude-code-plugin-manifest SchemaStore + --strict overlay",
            "schema_id": schema.get("$id") or L.SCHEMA_ID,
            "schema_path": L.SCHEMA_REL,
            "schema_comment": schema.get("$comment"),
            "hand_written_field_list": False,
            "strict": True,
            "strict_overlay": "additionalProperties=false (claude plugin validate --strict)",
            "cli": L.try_claude_cli(
                json.loads(_blob("conforming.json")), strict=True
            ),
        },
        "tests": tests,
        "controls": {"both_states": control, "mutation": mutation},
        "live_shipped": live,
    }


def main() -> int:
    report = run_suite()
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["ok"]:
        print("FAILED:TST-0033-suite")
        return 1
    print("SUCCESS:TST-0033-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
