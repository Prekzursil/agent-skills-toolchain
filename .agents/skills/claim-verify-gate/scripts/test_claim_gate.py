#!/usr/bin/env python3
"""Regression suite for claim_gate.py — the mechanical half of claim-verify-gate.

Stdlib-only standalone runner with its own ``__main__`` (the repo has no pytest
autodiscovery: a suite runs only because a CI step names it by path).

Run: ``python .agents/skills/claim-verify-gate/scripts/test_claim_gate.py``
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claim_gate  # noqa: E402

HERE = Path(__file__).resolve().parent
GATE = HERE / "claim_gate.py"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
        return
    FAILURES.append(f"{name}: {detail}")
    print(f"  FAIL {name} {detail}")


def rules_of(report: dict, claim_id: str) -> set[str]:
    for claim in report["claims"]:
        if claim["id"] == claim_id:
            return {violation["rule"] for violation in claim["violations"]}
    return set()


def payload(**claim: object) -> dict:
    base = {
        "id": "C1",
        "text": "The CDP endpoint answered on port 9222.",
        "verdict": "CONFIRMED",
        "source_probe": {
            "tool": "playwright",
            "shell": "powershell",
            "field": "wall_clock",
        },
        "verify_probe": {"tool": "curl", "shell": "bash", "field": "http_status"},
        "evidence": ["tools/mcp/host.py:12"],
    }
    base.update(claim)
    return {"subject": "unit", "claims": [base]}


# --- R1 probe independence -------------------------------------------------


def test_independent_probe_confirms() -> None:
    report = claim_gate.evaluate(payload())
    check("independent probe passes", report["ok"] is True, str(report))
    check("no violations", report["violation_count"] == 0)


def test_same_probe_rerun_fires() -> None:
    same = {"tool": "which", "shell": "bash", "field": "path"}
    report = claim_gate.evaluate(payload(source_probe=same, verify_probe=dict(same)))
    check("same-probe-rerun fires", "same-probe-rerun" in rules_of(report, "C1"))
    check("same-probe-rerun blocks", report["ok"] is False)


def test_command_difference_alone_is_not_independence() -> None:
    report = claim_gate.evaluate(
        payload(
            source_probe={
                "tool": "grep",
                "shell": "bash",
                "field": "count",
                "command": "grep -c a",
            },
            verify_probe={
                "tool": "grep",
                "shell": "bash",
                "field": "count",
                "command": "grep -c b",
            },
        )
    )
    check(
        "command-only difference still fires",
        "same-probe-rerun" in rules_of(report, "C1"),
        "command must be documentation, not a discriminating axis",
    )


def test_missing_verify_probe_fires() -> None:
    report = claim_gate.evaluate(payload(verify_probe=None))
    check("no-verify-probe fires", "no-verify-probe" in rules_of(report, "C1"))


# The absent-SOURCE direction. The suite above covers the absent VERIFIER and was green
# for the whole time the source hole was live -- 30 passing tests that never touched it.
# single-signal-verification.md:75-86 requires BOTH halves of the pair to be declared.


def test_missing_source_probe_fires() -> None:
    report = claim_gate.evaluate(payload(source_probe=None))
    check("no-source-probe fires", "no-source-probe" in rules_of(report, "C1"))
    check("no-source-probe blocks", report["ok"] is False, str(report))


def test_empty_source_probe_fires() -> None:
    """Present-but-vacuous is the same hole: every axis normalises to ''."""
    report = claim_gate.evaluate(payload(source_probe={"tool": "", "shell": ""}))
    check("empty source_probe fires", "no-source-probe" in rules_of(report, "C1"))


def test_refuted_missing_source_probe_fires() -> None:
    report = claim_gate.evaluate(
        payload(
            verdict="REFUTED",
            source_probe=None,
            revised_text="Measured on one host only.",
        )
    )
    check("REFUTED needs a source too", "no-source-probe" in rules_of(report, "C1"))


def test_absent_source_is_not_certified_as_independent() -> None:
    """The exact regression: this input returned violations=[], ok=true, exit 0.

    Asserted in BOTH directions -- the claim must now be blocked, and it must be blocked
    by the SOURCE rule rather than by same-probe-rerun. If same-probe-rerun were the one
    firing, the fix would be an accident of fingerprint equality, not a declared-source
    requirement, and it would evaporate the moment the verifier changed shape.
    """
    report = claim_gate.evaluate(payload(source_probe=None))
    fired = rules_of(report, "C1")
    check("absent source no longer certifies", report["ok"] is False, str(report))
    check("caught by the source rule", "no-source-probe" in fired)
    check(
        "NOT by same-probe-rerun (which cannot fire on an absent source)",
        "same-probe-rerun" not in fired,
        f"fired={fired}",
    )


def test_unverified_does_not_need_a_source_probe() -> None:
    """No false positive on the verdict that is allowed to declare no measurement."""
    report = claim_gate.evaluate(
        payload(
            verdict="UNVERIFIED",
            source_probe=None,
            verify_probe=None,
            evidence=[],
            settling_experiment="Re-run on a second host and compare http_status.",
        )
    )
    check("UNVERIFIED is exempt", "no-source-probe" not in rules_of(report, "C1"))
    check("and still does not block", report["ok"] is True, str(report))


def test_refuted_also_needs_independent_probe() -> None:
    same = {"tool": "pytest", "shell": "bash", "field": "exit_code"}
    report = claim_gate.evaluate(
        payload(
            verdict="REFUTED",
            source_probe=same,
            verify_probe=dict(same),
            revised_text="Measured on one host only.",
        )
    )
    check(
        "REFUTED needs independence too", "same-probe-rerun" in rules_of(report, "C1")
    )


# --- R2/R3 settling experiment + evidence ----------------------------------


def test_unverified_requires_settling_experiment() -> None:
    report = claim_gate.evaluate(payload(verdict="UNVERIFIED", verify_probe=None))
    check(
        "no-settling-experiment fires",
        "no-settling-experiment" in rules_of(report, "C1"),
    )


def test_unverified_with_settling_is_residual_not_violation() -> None:
    report = claim_gate.evaluate(
        payload(
            verdict="UNVERIFIED",
            verify_probe=None,
            evidence=[],
            scope="one host, one run",
            settling_experiment="Re-run on a second host and compare the http_status field.",
        )
    )
    check("scoped residual does not block", report["ok"] is True, str(report))
    check("residual counted", report["residual_count"] == 1)


def test_confirmed_requires_evidence_anchor() -> None:
    report = claim_gate.evaluate(payload(evidence=["I remember seeing it"]))
    check("no-evidence-anchor fires", "no-evidence-anchor" in rules_of(report, "C1"))


def test_url_counts_as_evidence_anchor() -> None:
    report = claim_gate.evaluate(payload(evidence=["https://arxiv.org/abs/2309.11495"]))
    check("URL is an anchor", "no-evidence-anchor" not in rules_of(report, "C1"))


# --- R4 unscoped absolutes -------------------------------------------------


def test_absolute_without_scope_fires() -> None:
    report = claim_gate.evaluate(payload(text="All 7 PRs are clean.", scope=""))
    check("unscoped-absolute fires", "unscoped-absolute" in rules_of(report, "C1"))


def test_absolute_with_scope_passes() -> None:
    report = claim_gate.evaluate(
        payload(text="All 7 PRs are clean.", scope="the 7 PRs open on 2026-07-24")
    )
    check("scoped absolute passes", "unscoped-absolute" not in rules_of(report, "C1"))


def test_numeric_absolute_fires() -> None:
    report = claim_gate.evaluate(payload(text="recall = 1.0 on the corpus.", scope=""))
    check("numeric absolute fires", "unscoped-absolute" in rules_of(report, "C1"))


def test_hyphenated_identifier_is_not_an_absolute() -> None:
    report = claim_gate.evaluate(
        payload(text="The gate emitted no-verify-probe for that row.", scope="")
    )
    check(
        "hyphenated identifier not flagged",
        "unscoped-absolute" not in rules_of(report, "C1"),
        "rule ids like no-verify-probe / zero-issue-coding must not read as absolutes",
    )


def test_plain_claim_is_not_an_absolute() -> None:
    report = claim_gate.evaluate(
        payload(text="The host answered in 1.94 seconds.", scope="")
    )
    check("plain claim not flagged", "unscoped-absolute" not in rules_of(report, "C1"))


# --- R5 hedge bands --------------------------------------------------------


def test_hedge_without_band_fires() -> None:
    report = claim_gate.evaluate(payload(text="This should work on the next host."))
    check("unbanded-hedge fires", "unbanded-hedge" in rules_of(report, "C1"))


def test_hedge_with_band_passes() -> None:
    report = claim_gate.evaluate(
        payload(text="This should work on the next host.", band="likely")
    )
    check("banded hedge passes", "unbanded-hedge" not in rules_of(report, "C1"))


def test_unknown_band_fires() -> None:
    report = claim_gate.evaluate(payload(text="This should work.", band="pretty sure"))
    check("unknown-band fires", "unknown-band" in rules_of(report, "C1"))
    check("bands are enumerated", "almost certain" in claim_gate.SHERMAN_KENT_BANDS)


# --- R6 refuted overclaims must be rewritten -------------------------------


def test_refuted_requires_revised_text() -> None:
    report = claim_gate.evaluate(payload(verdict="REFUTED"))
    check(
        "refuted-without-rewrite fires",
        "refuted-without-rewrite" in rules_of(report, "C1"),
    )


def test_refuted_rewrite_must_differ() -> None:
    text = "Every hook fires."
    report = claim_gate.evaluate(
        payload(verdict="REFUTED", text=text, revised_text=text, scope="4 hooks")
    )
    check(
        "identical rewrite fires", "refuted-without-rewrite" in rules_of(report, "C1")
    )


# --- R7 inline UNVERIFIED placement ---------------------------------------


def test_trailing_unverified_doc_fires() -> None:
    doc = ("filler sentence. " * 60) + "\n## Limitations\nUNVERIFIED: not measured."
    report = claim_gate.evaluate(
        payload(
            verdict="UNVERIFIED",
            verify_probe=None,
            evidence=[],
            settling_experiment="re-probe with curl",
        ),
        doc=doc,
    )
    check("trailing-unverified fires", "trailing-unverified" in rules_of(report, "C1"))


def test_inline_unverified_doc_passes() -> None:
    doc = "UNVERIFIED: the port was not re-probed. " + ("filler sentence. " * 60)
    report = claim_gate.evaluate(
        payload(
            verdict="UNVERIFIED",
            verify_probe=None,
            evidence=[],
            settling_experiment="re-probe with curl",
        ),
        doc=doc,
    )
    check(
        "inline unverified passes", "trailing-unverified" not in rules_of(report, "C1")
    )


def test_missing_unverified_tag_in_doc_fires() -> None:
    report = claim_gate.evaluate(
        payload(
            verdict="UNVERIFIED",
            verify_probe=None,
            evidence=[],
            settling_experiment="re-probe with curl",
        ),
        doc="a document with no tag at all",
    )
    check("untagged doc fires", "untagged-unverified" in rules_of(report, "C1"))


def test_trailing_share_threshold_is_pinned() -> None:
    # The two placement tests above only fix behaviour at the extremes (a tag at
    # position 0, and one at ~96% of the doc), which constrains _TAIL_SHARE only
    # to the wide band (~0.02, 1.0). A WEAKENED threshold (0.15 -> 0.05, a
    # narrower trailing window) therefore survived the suite green. Pin the
    # boundary near 0.15 with a tag just inside and just outside the
    # trailing-15% window (single-signal-verification.md:44).
    def doc_with_tag_at(fraction: float) -> str:
        total = 1000
        head = round(total * fraction)
        filler = total - head - len("UNVERIFIED")
        return ("x" * head) + "UNVERIFIED" + ("y" * filler)

    def trailing_fires(doc: str) -> bool:
        report = claim_gate.evaluate(
            payload(
                verdict="UNVERIFIED",
                verify_probe=None,
                evidence=[],
                settling_experiment="re-probe with curl",
            ),
            doc=doc,
        )
        return "trailing-unverified" in rules_of(report, "C1")

    # Inside the trailing 15% window (tag at 88%): MUST fire; narrowing the
    # window to <=0.10 stops catching it, so reverting the constant goes red.
    check("tag inside trailing window fires", trailing_fires(doc_with_tag_at(0.88)))
    # Outside the trailing 15% window (tag at 82%): MUST NOT fire; widening the
    # window to >=0.20 wrongly flags it.
    check(
        "tag outside trailing window passes",
        not trailing_fires(doc_with_tag_at(0.82)),
    )


# --- input validation ------------------------------------------------------


def test_unknown_verdict_is_input_error() -> None:
    try:
        claim_gate.evaluate(payload(verdict="PROBABLY"))
    except ValueError as exc:
        check("unknown verdict rejected", "PROBABLY" in str(exc), str(exc))
        return
    check("unknown verdict rejected", False, "no ValueError raised")


def test_duplicate_ids_rejected() -> None:
    doc = payload()
    doc["claims"].append(dict(doc["claims"][0]))
    try:
        claim_gate.evaluate(doc)
    except ValueError as exc:
        check("duplicate ids rejected", "C1" in str(exc), str(exc))
        return
    check("duplicate ids rejected", False, "no ValueError raised")


def test_empty_claims_rejected() -> None:
    try:
        claim_gate.evaluate({"subject": "x", "claims": []})
    except ValueError:
        check("empty claim set rejected", True)
        return
    check("empty claim set rejected", False, "no ValueError raised")


# --- rendering + CLI -------------------------------------------------------


def test_markdown_table_has_every_claim_and_verdict() -> None:
    report = claim_gate.evaluate(payload())
    text = claim_gate.render_markdown(report)
    check("md has id", "C1" in text)
    check("md has verdict", "CONFIRMED" in text)
    check("md has header", "| claim |" in text)


def test_cli_exit_codes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.json"
        good.write_text(json.dumps(payload()), encoding="utf-8")
        bad = Path(tmp) / "bad.json"
        same = {"tool": "which", "shell": "bash", "field": "path"}
        bad.write_text(
            json.dumps(payload(source_probe=same, verify_probe=dict(same))),
            encoding="utf-8",
        )
        broken = Path(tmp) / "broken.json"
        broken.write_text("{not json", encoding="utf-8")

        ok = subprocess.run(
            [sys.executable, str(GATE), "--claims", str(good)],
            capture_output=True,
            text=True,
        )
        check("clean gate exits 0", ok.returncode == 0, ok.stdout + ok.stderr)

        fail = subprocess.run(
            [sys.executable, str(GATE), "--claims", str(bad)],
            capture_output=True,
            text=True,
        )
        check("violating gate exits 1", fail.returncode == 1, fail.stdout + fail.stderr)
        check("violating gate names the rule", "same-probe-rerun" in fail.stdout)

        err = subprocess.run(
            [sys.executable, str(GATE), "--claims", str(broken)],
            capture_output=True,
            text=True,
        )
        check("bad input exits 2", err.returncode == 2, err.stdout + err.stderr)

        as_json = subprocess.run(
            [sys.executable, str(GATE), "--claims", str(good), "--format", "json"],
            capture_output=True,
            text=True,
        )
        parsed = json.loads(as_json.stdout)
        check("json output parses", parsed["ok"] is True)


def test_cli_self_test_is_a_both_states_probe() -> None:
    result = subprocess.run(
        [sys.executable, str(GATE), "--self-test"],
        capture_output=True,
        text=True,
    )
    check("self-test exits 0", result.returncode == 0, result.stdout + result.stderr)
    for rule in claim_gate.RULES:
        check(f"self-test fires {rule}", rule in result.stdout, result.stdout)


def test_self_test_covers_every_declared_rule() -> None:
    fired = {rule for rule, ok in claim_gate.self_test() if ok}
    missing = set(claim_gate.RULES) - fired
    check(
        "every rule has a known-broken fixture",
        not missing,
        f"missing={sorted(missing)}",
    )


def main() -> int:
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    print(f"claim_gate regression suite — {len(tests)} tests")
    for test in tests:
        test()
    if FAILURES:
        print(f"\nFAILED: {len(FAILURES)} check(s)")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"\nAll {len(tests)} test functions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
