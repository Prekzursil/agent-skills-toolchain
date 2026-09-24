#!/usr/bin/env python3
"""killlist.py - OUTPUT-side zero-fabrication gate for the template emitter.

tools/zerofab.py lints the PROFILE (the input). This module lints the EMITTED
ARTEFACT (the output): the academic CV's RenderCV YAML, the cover letters, the
LinkedIn text, the platform packs and the Europass emission.

Design rule: FAIL CLOSED.
  * A violation is an ERROR and the artefact is NOT written.
  * An artefact that trips a wording-lock trigger and does not carry the lock
    is an ERROR too - the gate is two-sided, so a lock cannot be silently lost.
  * An empty rule set raises - an unarmed gate must never read green.

Self-test: `python killlist.py --self-test` proves BOTH states - a clean text
scores zero findings, and one deliberately defective text per rule is caught by
that rule. A gate that has only ever been shown a clean input has not been
shown to work.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Normalisation                                                                #
# --------------------------------------------------------------------------- #
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {ord("‘"): "'", ord("’"): "'",
           ord("“"): '"', ord("”"): '"'}


def normalise(text: str) -> str:
    """Lower-case, fold unicode dashes/quotes, collapse whitespace.

    Kill-list evasion here is almost never deliberate; it is an en-dash or a
    line wrap landing between two words. Normalising first means a rule written
    once catches every typographic spelling of the same claim.
    """
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_DASHES).translate(_QUOTES)
    t = t.lower()
    t = re.sub(r"\s+", " ", t)
    return t


# --------------------------------------------------------------------------- #
# Rules                                                                        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    why: str
    severity: str = "ERROR"          # ERROR | WARN
    allow_near: str | None = None    # a hit inside this context is permitted

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


# The KILL LIST as regexes over normalised text. Every entry traces to
# profile.yaml x_forbidden.claims, x_style.locks or x_privacy.
RULES: tuple[Rule, ...] = (
    Rule("F01", r"1,?590\s+merged\s+prs?", "kill list: 1,590 merged PRs"),
    Rule("F02", r"6,?432\s+contributions", "kill list: 6,432 contributions"),
    Rule("F03", r"\b(556|345)\s?k\b.{0,20}\bloc\b|\bloc\b.{0,20}\b(556|345)\s?k\b",
         "kill list: 556K/345K LOC"),
    Rule("F04", r"8,?000\s+passing\s+tests",
         "kill list: '8,000 PASSING tests' - the allowed form is 'ships 8,000 test functions'"),
    Rule("F05", r"\b400\+?\s+skills\s+authored",
         "kill list: '400+ skills authored' - it is a 415-skill tree CURATED, ~140 AUTHORED"),
    Rule("F06", r"\b(40\+?|[4-9]\d|\d{3,})\s+mcp\s+servers",
         "kill list: MCP-server count inflation - the true figure is 18"),
    Rule("F07", r"1,?000[\s-]agent\s+audit", "kill list: '1000-agent audit'"),
    Rule("F08", r"97[\s-]slice|1,?582\s+findings|3\s+critical\s+rce",
         "kill list: the 97-slice / 1,582-findings / 3-critical-RCE audit"),
    Rule("F09", r"12,?272[\s-]record", "kill list: '12,272-record corpus'"),
    Rule("F10", r"\b26[\s-]repo\s+fleet\b", "kill list: '26-repo fleet'"),
    Rule("F11", r"\bv?1\.4\.2\b",
         "kill list: Reframe v1.4.2 does not exist - the latest release is v1.4.0"),
    Rule("F12", r"peer[\s-]reviewed\s+(publication|paper|article|journal)",
         "kill list (highest severity): there is NO peer-reviewed publication - preprints only"),
    Rule("F13", r"(finished|placed|ranked)\s+4th\b|\b4th\s+overall\b",
         "kill list (highest severity): 'finished 4th overall at GRACE' traces to a "
         "fabricated document and ends a candidacy"),
    Rule("F14", r"608[\s-]unit|databricks\s+fan[\s-]?out",
         "kill list (highest severity): the 608-unit Databricks fan-out is another "
         "person's account in a corporate workspace"),
    Rule("F15", r"all\s+gates\s+green", "kill list: 'all gates green'"),
    Rule("F16", r"\bwidely\s+used\b", "kill list: 'widely used'"),
    Rule("F17",
         r"(reframe|tracelines|llm[\s-]anthology)[^.]{0,90}?"
         r"\b(downloads?|installs?|installations?|adoption|active users)\b",
         "kill list: no download / install / adoption figure exists for Reframe, "
         "tracelines or llm-anthology"),
    Rule("F18", r"open[\s-]sourced?\b",
         "kill list: 'open-source' may only describe a repository with a LICENSE file. "
         "ZHMModSDK qualifies; the owner's own repositories are unverified - write "
         "'released' or 'public' instead",
         allow_near=r"zhmmodsdk"),
    Rule("F19", r"andrei\s+mihai\s+visalon",
         "name rule: the canonical spelling is hyphenated - 'Andrei-Mihai Visalon'"),
    Rule("F20", r"\b(8\s+june\s+2002|2002-06-08|08[./]06[./]2002|1993-06-08)\b",
         "privacy: a date of birth renders on NO view"),
    Rule("F22",
         r"\bsubmitted\b[^.]{0,40}\bmanuscript\b|"
         r"\bmanuscript\b[^.]{0,40}\b(submitted|under review|forthcoming)\b",
         "wording lock: the second manuscript is 'in preparation' - never submitted, "
         "under review or forthcoming"),
)


# LINE rules are evaluated against ONE physical line at a time, never against
# the whitespace-collapsed document. A Europass field that is deliberately EMPTY
# is followed on the NEXT line by the next field label; collapsing the document
# first would read that next label as the field's value and fail a correct file.
LINE_RULES: tuple[Rule, ...] = (
    Rule("F21",
         # The separator is a field separator (colon or table pipe), never a
         # prose dash - "fara cetatenie - nici pe platforma" is guidance, not a
         # disclosure. The lookahead lets the field be present and EMPTY, which
         # is exactly what the Europass emission is required to produce.
         r"(nationality|cetatenie|date of birth|data nasterii|marital status|"
         r"stare civila)\s*[:|]\s*"
         r"(?!\"\"|''|null\b|none\b|n/a\b|\|)\S",
         "privacy: a nationality / DOB / marital-status field must render EMPTY"),
    Rule("F23", r"(str\.|strada|street|bd\.|bulevardul)\s+[a-z0-9]",
         "privacy: no street address on any surface"),
)


# Two-sided locks: an artefact that MENTIONS the trigger must ALSO carry the lock.
@dataclass(frozen=True)
class Lock:
    id: str
    trigger: str
    required: str
    why: str


LOCKS: tuple[Lock, ...] = (
    Lock("L01", r"chemrxiv", r"preprint",
         "every ChemRxiv mention must carry the word 'preprint'"),
    Lock("L02", r"second manuscript", r"in preparation",
         "the second manuscript renders as 'in preparation' only"),
    Lock("L03", r"pbinfo", r"(as of september 2026|septembrie 2026)",
         "pbinfo's ranking is dated: it can move (EN 'as of September 2026' or "
         "RO 'septembrie 2026')"),
    Lock("L04", r"pbinfo", r"(high[\s-]school|liceu|elevi)",
         "pbinfo must be named as Romania's national HIGH-SCHOOL judge, so it is not "
         "read as a university or professional ranking"),
    Lock("L05", r"0\.743", r"0\.705",
         "the GRACE metric sentence renders in full or not at all: 0.743 dev strict "
         "macro-F1 against 0.705 for the best backbone, best individual run 0.737, "
         "chosen without dev-set model selection"),
    Lock("L06", r"0\.743", r"without dev[\s-]set model selection",
         "the GRACE metric sentence must keep the no-model-selection caveat"),
    Lock("L07", r"415[\s-]skill", r"curat",
         "the 415-skill tree is CURATED, not authored"),
)


# --------------------------------------------------------------------------- #
# Documentation exemption (use vs. mention)                                    #
# --------------------------------------------------------------------------- #
# A template's own "never write X" guidance has to QUOTE X to be useful, and a
# blunt gate reads that quotation as the claim itself. The fix is an explicit,
# narrow, AUDITED region - not a softer rule.
#
#   <!-- killlist:allow-mentions -->  ... guidance ...  <!-- killlist:end -->
#
# Inside such a region the kill-list CLAIM rules are suspended. Three things stop
# this from becoming a loophole:
#   1. the region must be opened and closed explicitly, in the template source;
#   2. every exemption is REPORTED as a NOTE finding, so it is never silent;
#   3. the PRIVACY line rules still apply inside - a date of birth or an address
#      is forbidden in documentation too, because the file ships as it stands.
EXEMPT_OPEN = "<!-- killlist:allow-mentions -->"
EXEMPT_CLOSE = "<!-- killlist:end -->"
_EXEMPT_RX = re.compile(
    re.escape(EXEMPT_OPEN) + r"(.*?)" + re.escape(EXEMPT_CLOSE), re.DOTALL)


def strip_exempt(text: str) -> tuple[str, int, int]:
    """Blank out documentation regions, preserving offsets.

    Returns (text_with_regions_blanked, region_count, exempted_char_count).
    """
    count = chars = 0

    def _blank(m: re.Match[str]) -> str:
        nonlocal count, chars
        count += 1
        chars += len(m.group(1))
        return " " * len(m.group(0))

    return _EXEMPT_RX.sub(_blank, text), count, chars


@dataclass(frozen=True)
class Finding:
    artefact: str
    rule: str
    severity: str
    why: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.severity} [{self.rule}] {self.artefact}: {self.why} | ...{self.excerpt}..."


def _excerpt(text: str, start: int, end: int, pad: int = 45) -> str:
    return text[max(0, start - pad):min(len(text), end + pad)].strip()


def scan(text: str, artefact: str = "<text>") -> list[Finding]:
    """Scan one emitted artefact. Returns every finding; [] means clean."""
    if not RULES:                                  # an unarmed gate never reads green
        raise RuntimeError("killlist.RULES is empty - the gate is unarmed")
    if not LINE_RULES:
        raise RuntimeError("killlist.LINE_RULES is empty - the gate is unarmed")
    body, regions, exempt_chars = strip_exempt(text)
    norm = normalise(body)
    found: list[Finding] = []
    if regions:
        # NOTE severity: reported, printed, never an error. An exemption that
        # nobody can see is an exemption nobody audits.
        found.append(Finding(artefact, "NOTE", "NOTE",
                             f"{regions} documentation region(s) exempted from the "
                             f"claim rules ({exempt_chars} chars); privacy rules "
                             f"still applied there",
                             EXEMPT_OPEN))

    for rule in RULES:
        allow = re.compile(rule.allow_near) if rule.allow_near else None
        for m in rule.compiled().finditer(norm):
            if allow is not None:
                window = norm[max(0, m.start() - 70):m.end() + 70]
                if allow.search(window):
                    continue
            found.append(Finding(artefact, rule.id, rule.severity, rule.why,
                                 _excerpt(norm, m.start(), m.end())))

    for raw_line in text.splitlines():
        line = normalise(raw_line)
        for rule in LINE_RULES:
            for m in rule.compiled().finditer(line):
                found.append(Finding(artefact, rule.id, rule.severity, rule.why,
                                     _excerpt(line, m.start(), m.end())))

    for lock in LOCKS:
        if re.search(lock.trigger, norm) and not re.search(lock.required, norm):
            found.append(Finding(artefact, lock.id, "ERROR",
                                 f"wording lock unmet: {lock.why}",
                                 f"(trigger /{lock.trigger}/ present, "
                                 f"required /{lock.required}/ absent)"))
    return found


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "ERROR"]


# --------------------------------------------------------------------------- #
# Self-test - proves BOTH states                                               #
# --------------------------------------------------------------------------- #
DEFECTS: dict[str, str] = {
    "F01": "He has 1,590 merged PRs to his name.",
    "F02": "GitHub shows 6,432 contributions last year.",
    "F03": "The monorepo is 556K LOC of Python.",
    "F04": "The suite has 8,000 passing tests.",
    "F05": "400+ skills authored for the agent platform.",
    "F06": "40+ MCP servers written and deployed.",
    "F07": "Ran a 1000-agent audit across the estate.",
    "F08": "A 97-slice audit produced 1,582 findings.",
    "F09": "Curated a 12,272-record corpus.",
    "F10": "Operates a 26-repo fleet.",
    "F11": "Latest Reframe release is v1.4.2.",
    "F12": "Author of a peer-reviewed publication.",
    "F13": "Finished 4th overall at the shared task.",
    "F14": "Drove the 608-unit fan-out.",
    "F15": "All gates green on every repository.",
    "F16": "A widely used developer tool.",
    "F17": "Reframe has over 5,000 downloads.",
    "F18": "Open-sourced the benchmark harness himself.",
    "F19": "Prepared by Andrei Mihai Visalon.",
    "F20": "Born 8 June 2002 in Romania.",
    "F21": "Nationality: Romanian",
    "F22": "The manuscript was submitted to a journal.",
    "F23": "Str. Exemplu 14, Bucharest.",
}

CLEAN = """
Andrei-Mihai Visalon. Master's student, University of Bucharest.
Preprint posted on ChemRxiv; a second manuscript is in preparation.
Ranked first all-time on pbinfo.ro, Romania's national high-school
competitive-programming judge, as of September 2026.
The ensemble reached 0.743 dev strict macro-F1 against 0.705 for the best
backbone averaged over three seeds (best individual run 0.737), chosen
without dev-set model selection.
Wrote 18 MCP servers; curates a 415-skill tree of which roughly 140 are
self-authored. Merged a C++ contribution to ZHMModSDK, a third-party
open-source SDK. Reframe ships nine releases, the latest v1.4.0.
Nationality:
Date of birth:
nationality: ""
date_of_birth: ""
| English | | | | Advanced |
Fara adresa, fara data nasterii, fara cetatenie - nici pe platforma.
"""

LOCK_PROBES: dict[str, str] = {
    "L01": "Posted on ChemRxiv in 2026.",
    "L02": "A second manuscript exists.",
    "L03": "Ranked first on pbinfo.ro, the national high-school judge.",
    "L04": "Ranked first on pbinfo.ro as of September 2026.",
    "L05": "The ensemble reached 0.743 dev strict macro-F1.",
    "L06": "0.743 against 0.705 for the best backbone.",
    "L07": "A 415-skill tree.",
}


def self_test() -> int:
    failures: list[str] = []

    clean = errors(scan(CLEAN, "clean-fixture"))
    if clean:
        failures.append(f"CLEAN fixture produced {len(clean)} error(s): "
                        + "; ".join(f"{f.rule}" for f in clean))

    covered = {r.id for r in RULES} | {r.id for r in LINE_RULES}
    missing = covered - set(DEFECTS)
    extra = set(DEFECTS) - covered
    if missing:
        failures.append(f"no defect fixture for rule(s): {sorted(missing)}")
    if extra:
        failures.append(f"defect fixture for unknown rule(s): {sorted(extra)}")

    for rule_id, text in sorted(DEFECTS.items()):
        hits = {f.rule for f in scan(text, f"defect:{rule_id}")}
        if rule_id not in hits:
            failures.append(f"DEFECT fixture for {rule_id} was NOT caught "
                            f"(caught: {sorted(hits) or 'nothing'})")

    lock_ids = {lock.id for lock in LOCKS}
    if lock_ids - set(LOCK_PROBES):
        failures.append(f"no probe for lock(s): {sorted(lock_ids - set(LOCK_PROBES))}")
    for lock in LOCKS:
        probe = LOCK_PROBES.get(lock.id)
        if probe is None:
            continue
        hits = {f.rule for f in scan(probe, f"lock:{lock.id}")}
        if lock.id not in hits:
            failures.append(f"LOCK {lock.id} did not fire on its probe "
                            f"(caught: {sorted(hits) or 'nothing'})")

    inside = (f"{EXEMPT_OPEN}\nNever write: a peer-reviewed publication.\n"
              f"{EXEMPT_CLOSE}\n")
    if errors(scan(inside, "exempt-inside")):
        failures.append("EXEMPT region did not suppress a claim rule")
    if not any(f.rule == "NOTE" for f in scan(inside, "exempt-inside")):
        failures.append("EXEMPT region was not REPORTED as a NOTE finding")
    outside = inside + "He is the author of a peer-reviewed publication.\n"
    if not any(f.rule == "F12" for f in scan(outside, "exempt-outside")):
        failures.append("a claim OUTSIDE the exempt region was not caught")
    privacy = f"{EXEMPT_OPEN}\nNationality: Romanian\n{EXEMPT_CLOSE}\n"
    if not any(f.rule == "F21" for f in scan(privacy, "exempt-privacy")):
        failures.append("PRIVACY rule was wrongly suppressed inside an exempt region")

    if failures:
        for f in failures:
            print(f"FAIL {f}")
        print(f"FAILED:killlist-self-test ({len(failures)} problem(s))")
        return 1
    print(f"clean fixture: 0 errors | {len(DEFECTS)} defect fixtures all caught | "
          f"{len(LOCKS)} locks all fire | exemption: suppresses claims, reports "
          f"itself, still catches privacy and anything outside it")
    print("SUCCESS:killlist-self-test")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="killlist.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="emitted artefacts to scan")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the gate fires (clean -> 0, each defect -> caught)")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.files:
        ap.error("give at least one file, or --self-test")

    total: list[Finding] = []
    for name in args.files:
        p = Path(name)
        if not p.exists():
            print(f"ERROR [IO] {name}: file not found")
            return 2
        total.extend(scan(p.read_text(encoding="utf-8"), p.name))
    for f in total:
        print(f)
    errs = errors(total)
    if errs:
        print(f"FAILED:killlist ({len(errs)} error(s))")
        return 1
    print(f"SUCCESS:killlist ({len(args.files)} artefact(s) clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
