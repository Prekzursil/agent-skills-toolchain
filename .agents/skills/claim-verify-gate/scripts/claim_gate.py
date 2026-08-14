#!/usr/bin/env python3
"""claim_gate — the MECHANICAL half of the claim-verify-gate skill.

The skill (``SKILL.md``) carries the judgement half: decompose an answer into
atomic claims (SAFE, arXiv 2403.18802) and re-verify each one through the
Chain-of-Verification loop (arXiv 2309.11495). This module carries the half a
model must not be trusted with, because it is answerable by an exact algorithm
(``rules/common/fan-out-contract.md:162``: "if a question is answerable by an
exact algorithm ... WRITE THE ALGORITHM").

It answers eleven yes/no questions about a claim ledger and refuses the verdict
when the answer is wrong. It never decides whether a claim is TRUE — only
whether the ledger is allowed to say so.

Anchors (this module ENFORCES these; it does not restate them):
  single-signal-verification.md:34  two signals must be mechanically
      independent, "not the same query re-run"         -> same-probe-rerun
  single-signal-verification.md:75  declare the SOURCE probe, not just the
      verifier: "an undeclared source is zero signals, not one", and a
      mechanised gate INHERITS that obligation           -> no-source-probe
  single-signal-verification.md:40  the both-states test -> --self-test
  fan-out-contract.md:12            enumerate the vocabulary,
      never a bare tag name                            -> unknown-band
  fan-out-contract.md:17            UNVERIFIED must be INLINE; :18 measured
      40% of flags in the final 15% of their document  -> trailing-unverified
  fan-out-contract.md:25            a briefed fact needs a MECHANICALLY
      DIFFERENT re-probe rule                          -> same-probe-rerun
  fan-out-contract.md:74            EVIDENCE block of file:line/URL anchors
                                                       -> no-evidence-anchor
  fan-out-contract.md:110-121       most refutations are OVERCLAIMS; fix the
      SENTENCE; an honestly-scoped residual must NOT block
                                                       -> refuted-without-rewrite
  agent-self/config/AGENTS.md:70    "sycophancy is in model weights;
      external-signal checks are the only reliable counter" -> why this is code

Exit codes: 0 gate passed - 1 violations - 2 unusable input.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

VERDICTS = ("CONFIRMED", "REFUTED", "UNVERIFIED")

# The discriminating axes of a probe. Two probes are INDEPENDENT only when they
# differ on at least one of these. `command` is deliberately absent: a different
# command string with the same tool, engine, shell and measured field is the
# same query re-run, which is exactly what single-signal-verification.md:36
# refuses to count as a second signal.
AXES = ("tool", "engine", "shell", "field")

# Enumerated in full, never shipped as a bare tag name (fan-out-contract.md:12-13:
# bands listed inline scored 20/21 adoption; the same field as a bare tag scored
# 7/21). This is the UNION of the two vocabularies already live in this estate:
# the five-band set in the cross-tool contract (almost certain 90-99 / likely
# 55-80 / roughly even 40-60 / unlikely 20-45 / remote 1-10) plus the three
# extensions the harness corpus already uses (harness-sota-2026-07-18-corpus/
# K06.md:62). Accepting the union is deliberate: a narrower list would reject
# prose that is already correct, and a gate that false-fires gets switched off.
SHERMAN_KENT_BANDS = (
    "almost certain",
    "very likely",
    "likely",
    "roughly even",
    "unlikely",
    "very unlikely",
    "remote",
    "almost certainly not",
)

RULES = (
    "no-verify-probe",
    "no-source-probe",
    "same-probe-rerun",
    "no-evidence-anchor",
    "no-settling-experiment",
    "unscoped-absolute",
    "unbanded-hedge",
    "unknown-band",
    "refuted-without-rewrite",
    "untagged-unverified",
    "trailing-unverified",
)

# A claim asserting an absolute must state the scope it was measured over. The
# shapes are the ones actually measured as overclaims in fan-out-contract.md:92
# ("recall = 1.0", "FP=0 / FN=0", "three holes closed").
# The trailing (?!-) keeps hyphenated identifiers out: this gate's own rule ids
# (`no-verify-probe`) and skill names (`zero-issue-coding`) are mentions, not
# assertions. Use-vs-mention is a measured repeat offender in this estate.
_ABSOLUTE = re.compile(
    r"\b(?:all|every|everything|always|never|none|nothing|zero|no|any"
    r"|fully|completely|entirely|guarantee|guarantees|guaranteed)\b(?!-)"
    r"|=\s*(?:1\.0(?![0-9])|0(?![0-9.]))"
    r"|\b100\s*%",
    re.IGNORECASE,
)

# AGENTS.md §7: a bare "should work" / "likely fine" with no band and no
# evidence is a hedge to flag, not a conclusion.
_HEDGE = re.compile(
    r"\b(?:should|would|likely|probably|presumably|seems|seem|appears|appear"
    r"|might|may|could|apparently|roughly|ought)\b(?!-)",
    re.IGNORECASE,
)

# An evidence anchor is a file:line reference or a URL — the two forms the
# fan-in gate accepts (fan-out-contract.md:56).
#
# This rule used to be `https?://\S+|\S+:\d+`, and `\S+:\d+` is satisfied by anything with a
# colon and a digit. Measured (command-center/p2-next/_d1_anchor_corpus.py, section A) it
# accepted 9 of 9 non-references — a timestamp (`2026-08-12T05:15:00`), a clock time (`05:15`),
# a ratio (`3:1`), a score, a version (`v1.2:3`) — so a CONFIRMED verdict could satisfy its
# evidence requirement by carrying the time it was written. The previous round found the
# timestamp case and disclosed it without fixing it; this closes it.
#
# The OBVIOUS fix is wrong in the other direction. Requiring a file extension (the shape
# rail_count_gate.py:133 uses) rejects `Makefile:12`, `Dockerfile:5` and `LICENSE:3` — measured
# in section B. A gate that false-fires on real anchors gets switched off, so the head must be
# recognised as a PATH rather than merely as having a dot.
_URL = re.compile(r"https?://\S+")
# The negative lookbehind stops a match starting mid-token, so `2026-08-12T05:15:00` cannot be
# rescued by re-matching at `15:00`. `\` is deliberately absent from it: a Windows anchor
# (`C:\...\claim_gate.py:113`) must be able to start after a backslash.
_FILE_LINE = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.][A-Za-z0-9_./\\-]*):(\d+)\b"
)
# A real extension carries at least one LETTER (`.py`, `.md`, `.7z`). Requiring that is what
# separates a filename from a version number: `v1.2` has a dot and is not a file.
_EXTENSION = re.compile(r"\.[A-Za-z0-9]{0,5}[A-Za-z][A-Za-z0-9]{0,5}$")
# The extension-less files a repo actually cites. Kept small and lowercase-compared: this list
# exists to prevent a measured false positive, not to enumerate every possible filename.
_EXTENSIONLESS = frozenset(
    {
        "makefile",
        "dockerfile",
        "license",
        "licence",
        "notice",
        "readme",
        "changelog",
        "codeowners",
        "procfile",
        "gemfile",
        "rakefile",
        "jenkinsfile",
        "vagrantfile",
        "justfile",
    }
)


def _is_path_head(head: str) -> bool:
    """Does the text before `:<line>` name a FILE, rather than merely contain a colon?"""
    if "/" in head or "\\" in head:
        return True
    if _EXTENSION.search(head):
        return True
    return head.lower() in _EXTENSIONLESS


def _is_anchor(item: str) -> bool:
    """A resolvable-shaped evidence anchor: a URL, or `<path>:<line>`."""
    if _URL.search(item):
        return True
    return any(_is_path_head(match.group(1)) for match in _FILE_LINE.finditer(item))


# Share of the document tail in which an UNVERIFIED tag no longer counts as
# inline. fan-out-contract.md:22 measured 40% of real flags sitting in the
# final 15% of their document, where they qualified nothing.
_TAIL_SHARE = 0.15


def _norm(value: object) -> str:
    return " ".join(str(value).lower().split()) if value else ""


def _probe_key(probe: object) -> tuple[str, ...]:
    """The independence fingerprint of a probe, over the discriminating axes."""
    fields = probe if isinstance(probe, dict) else {}
    return tuple(_norm(fields.get(axis)) for axis in AXES)


def _text(claim: dict, key: str) -> str:
    value = claim.get(key)
    return value.strip() if isinstance(value, str) else ""


def _validate(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("claim ledger must be a JSON object")
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("claim ledger must carry a non-empty 'claims' list")
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claim #{index} is not an object")
        claim_id = _text(claim, "id")
        if not claim_id:
            raise ValueError(f"claim #{index} has no 'id'")
        if claim_id in seen:
            raise ValueError(f"duplicate claim id {claim_id!r}")
        seen.add(claim_id)
        if not _text(claim, "text"):
            raise ValueError(f"claim {claim_id!r} has no 'text'")
        verdict = _text(claim, "verdict").upper()
        if verdict not in VERDICTS:
            raise ValueError(
                f"claim {claim_id!r} has verdict {verdict or '(missing)'!r}; "
                f"allowed: {', '.join(VERDICTS)}"
            )
    return claims


def _check_probes(claim: dict, verdict: str) -> list[dict]:
    if verdict == "UNVERIFIED":
        return []
    verify = claim.get("verify_probe")
    if not isinstance(verify, dict) or not any(_probe_key(verify)):
        return [
            {
                "rule": "no-verify-probe",
                "detail": (
                    f"{verdict} needs a verify_probe declaring at least one of "
                    f"{', '.join(AXES)}"
                ),
            }
        ]
    # Independence is a property of a PAIR (single-signal-verification.md:75-78: "an
    # undeclared source is zero signals, not one"). This check must come BEFORE the
    # fingerprint comparison, because an absent source_probe normalises to four empty
    # strings, which any non-empty verifier trivially differs from -- so same-probe-rerun
    # can never fire and the gate certifies a verdict that declares no producing
    # measurement at all. Measured live before this fix: a CONFIRMED claim with no
    # source_probe returned violations=[], ok=true, exit 0.
    source = claim.get("source_probe")
    if not isinstance(source, dict) or not any(_probe_key(source)):
        return [
            {
                "rule": "no-source-probe",
                "detail": (
                    f"{verdict} needs a source_probe declaring at least one of "
                    f"{', '.join(AXES)}: independence is a property of a pair, and an "
                    "absent source cannot be compared against anything"
                ),
            }
        ]
    source_key = _probe_key(source)
    if source_key == _probe_key(verify):
        return [
            {
                "rule": "same-probe-rerun",
                "detail": (
                    "verify_probe is identical to source_probe on every "
                    f"discriminating axis ({', '.join(AXES)}); re-running the "
                    "same probe is not a second signal"
                ),
            }
        ]
    return []


def _check_support(claim: dict, verdict: str) -> list[dict]:
    found: list[dict] = []
    if verdict == "CONFIRMED":
        evidence = claim.get("evidence")
        anchors = [
            item
            for item in (evidence if isinstance(evidence, list) else [])
            if isinstance(item, str) and _is_anchor(item)
        ]
        if not anchors:
            found.append(
                {
                    "rule": "no-evidence-anchor",
                    "detail": "CONFIRMED needs >=1 file:line or URL anchor in 'evidence'",
                }
            )
    if verdict == "UNVERIFIED" and not _text(claim, "settling_experiment"):
        found.append(
            {
                "rule": "no-settling-experiment",
                "detail": "UNVERIFIED must name the experiment that would settle it",
            }
        )
    if verdict == "REFUTED":
        revised = _text(claim, "revised_text")
        if not revised or revised == _text(claim, "text"):
            found.append(
                {
                    "rule": "refuted-without-rewrite",
                    "detail": (
                        "a REFUTED overclaim is fixed by rewriting the SENTENCE to "
                        "the scope actually measured; 'revised_text' must be present "
                        "and different"
                    ),
                }
            )
    return found


def _check_language(claim: dict) -> list[dict]:
    found: list[dict] = []
    text = _text(claim, "text")
    band = _text(claim, "band").lower()
    if _ABSOLUTE.search(text) and not _text(claim, "scope"):
        found.append(
            {
                "rule": "unscoped-absolute",
                "detail": "absolute wording requires 'scope' — the surface actually measured",
            }
        )
    if band and band not in SHERMAN_KENT_BANDS:
        found.append(
            {
                "rule": "unknown-band",
                "detail": f"band {band!r} is not one of: {', '.join(SHERMAN_KENT_BANDS)}",
            }
        )
    elif not band and _HEDGE.search(text):
        found.append(
            {
                "rule": "unbanded-hedge",
                "detail": (
                    "hedged wording needs a calibrated band: "
                    f"{', '.join(SHERMAN_KENT_BANDS)}"
                ),
            }
        )
    return found


def _check_placement(verdict: str, doc: str | None) -> list[dict]:
    """Where the UNVERIFIED tag sits in the prose the ledger describes.

    Scope note (inline, per the rule this enforces): this is a DISTRIBUTION
    check over the whole document, not a per-claim adjacency check. It catches
    the measured failure — every flag parked in a trailing limitations section —
    and does NOT prove any individual tag sits next to its own sentence.
    """
    if verdict != "UNVERIFIED" or doc is None:
        return []
    positions = [match.start() for match in re.finditer("UNVERIFIED", doc)]
    if not positions:
        return [
            {
                "rule": "untagged-unverified",
                "detail": "claim is UNVERIFIED but the document carries no UNVERIFIED tag",
            }
        ]
    tail_start = len(doc) * (1.0 - _TAIL_SHARE)
    if all(position >= tail_start for position in positions):
        return [
            {
                "rule": "trailing-unverified",
                "detail": (
                    f"every UNVERIFIED tag sits in the final "
                    f"{int(_TAIL_SHARE * 100)}% of the document; a limitations "
                    "section at the end does not satisfy the inline requirement"
                ),
            }
        ]
    return []


def evaluate(payload: object, doc: str | None = None) -> dict:
    """Apply every rule to a claim ledger and return the verdict report."""
    claims = _validate(payload)
    rows: list[dict] = []
    violation_count = 0
    residual_count = 0
    for claim in claims:
        verdict = _text(claim, "verdict").upper()
        violations = (
            _check_probes(claim, verdict)
            + _check_support(claim, verdict)
            + _check_language(claim)
            + _check_placement(verdict, doc)
        )
        violation_count += len(violations)
        residual = verdict == "UNVERIFIED" and not violations
        residual_count += int(residual)
        rows.append(
            {
                "id": _text(claim, "id"),
                "text": _text(claim, "text"),
                "verdict": verdict,
                "scope": _text(claim, "scope"),
                "band": _text(claim, "band"),
                "settling_experiment": _text(claim, "settling_experiment"),
                "evidence": [
                    item
                    for item in (claim.get("evidence") or [])
                    if isinstance(item, str)
                ],
                "violations": violations,
                "residual": residual,
            }
        )
    return {
        "subject": _text(payload if isinstance(payload, dict) else {}, "subject"),
        "claims": rows,
        "violation_count": violation_count,
        "residual_count": residual_count,
        "ok": violation_count == 0,
        "rules": list(RULES),
    }


def render_markdown(report: dict) -> str:
    lines = ["| claim | verdict | scope / band | gate |", "|---|---|---|---|"]
    for row in report["claims"]:
        rules = ", ".join(v["rule"] for v in row["violations"])
        gate = (
            f"BLOCKED: {rules}"
            if rules
            else ("residual" if row["residual"] else "pass")
        )
        qualifier = " / ".join(part for part in (row["scope"], row["band"]) if part)
        lines.append(
            f"| {row['id']} {row['text']} | {row['verdict']} | {qualifier or '-'} | {gate} |"
        )
    lines.append("")
    for row in report["claims"]:
        for violation in row["violations"]:
            lines.append(f"- {row['id']} {violation['rule']}: {violation['detail']}")
        if row["residual"]:
            lines.append(
                f"- {row['id']} residual (does NOT block); settles by: "
                f"{row['settling_experiment']}"
            )
    lines.append("")
    lines.append(
        f"violations={report['violation_count']} residuals={report['residual_count']} "
        f"gate={'PASS' if report['ok'] else 'BLOCKED'}"
    )
    return "\n".join(lines)


def _fixtures() -> dict[str, tuple[dict, str | None]]:
    """One KNOWN-BROKEN ledger per rule, for the both-states probe."""
    same = {"tool": "which", "shell": "bash", "field": "path"}
    good_probe = {"tool": "curl", "shell": "powershell", "field": "http_status"}

    def ledger(**claim: object) -> dict:
        base: dict = {
            "id": "F1",
            "text": "The endpoint answered on port 9222.",
            "verdict": "CONFIRMED",
            "source_probe": {
                "tool": "playwright",
                "shell": "powershell",
                "field": "latency",
            },
            "verify_probe": dict(good_probe),
            "evidence": ["tools/mcp/host.py:12"],
        }
        base.update(claim)
        return {"subject": "self-test", "claims": [base]}

    unverified = {
        "verdict": "UNVERIFIED",
        "verify_probe": None,
        "evidence": [],
        "settling_experiment": "re-probe from a second shell",
    }
    return {
        "no-verify-probe": (ledger(verify_probe=None), None),
        "no-source-probe": (ledger(source_probe=None), None),
        "same-probe-rerun": (
            ledger(source_probe=dict(same), verify_probe=dict(same)),
            None,
        ),
        # The broken state is a TIMESTAMP, not "I recall seeing it". Both are missing an anchor,
        # but only the timestamp distinguishes this rule's two hypotheses: the old `\S+:\d+`
        # shape was SILENT on it while firing on the prose. A fixture that fires under the old
        # and the new rule alike would prove the instrument runs, not that it discriminates.
        "no-evidence-anchor": (ledger(evidence=["2026-08-12T05:15:00"]), None),
        "no-settling-experiment": (
            ledger(verdict="UNVERIFIED", verify_probe=None, settling_experiment=""),
            None,
        ),
        "unscoped-absolute": (ledger(text="All 7 PRs are clean."), None),
        "unbanded-hedge": (ledger(text="This should hold on the next host."), None),
        "unknown-band": (ledger(band="pretty sure"), None),
        "refuted-without-rewrite": (ledger(verdict="REFUTED"), None),
        "untagged-unverified": (ledger(**unverified), "a document with no tag"),
        "trailing-unverified": (
            ledger(**unverified),
            ("filler sentence. " * 60) + "\nLimitations\nUNVERIFIED: not measured.",
        ),
    }


def self_test() -> list[tuple[str, bool]]:
    """Run each rule against a known-BROKEN ledger and report whether it FIRES.

    A probe that is silent in the broken state measures nothing
    (single-signal-verification.md:40). This is that check, for this gate.
    """
    results: list[tuple[str, bool]] = []
    fixtures = _fixtures()
    for rule in RULES:
        payload, doc = fixtures[rule]
        report = evaluate(payload, doc=doc)
        fired = any(
            violation["rule"] == rule
            for row in report["claims"]
            for violation in row["violations"]
        )
        results.append((rule, fired))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanical gate over a decomposed claim ledger.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--claims", type=pathlib.Path, help="claim ledger JSON")
    parser.add_argument(
        "--doc",
        type=pathlib.Path,
        help="the prose the ledger describes; enables the UNVERIFIED placement rules",
    )
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="prove every rule FIRES against a known-broken ledger, then exit",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        results = self_test()
        for rule, fired in results:
            print(f"  {'FIRES  ' if fired else 'SILENT '} {rule}")
        silent = [rule for rule, fired in results if not fired]
        if silent:
            print(
                f"FAILED: rules silent in the known-broken state: {silent}",
                file=sys.stderr,
            )
            return 1
        print(f"OK: all {len(results)} rules fire in the known-broken state.")
        return 0

    if args.claims is None:
        parser.error("--claims is required unless --self-test is given")

    try:
        payload = json.loads(args.claims.read_text(encoding="utf-8"))
        doc = args.doc.read_text(encoding="utf-8") if args.doc else None
        report = evaluate(payload, doc=doc)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"FAILED: unusable claim ledger: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(report, indent=2)
        if args.format == "json"
        else render_markdown(report)
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
