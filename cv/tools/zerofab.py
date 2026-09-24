#!/usr/bin/env python3
"""zerofab - a FAIL-CLOSED zero-fabrication lint for a cv-studio profile.

Why this module exists
----------------------
The lint shipped inside ``cv-studio/scripts/cvstudio.py`` FAILS OPEN in three
independently verified ways:

  1. ``validate()`` computes ``haystack = _metric_haystack(profile)`` and then
     guards every figure with ``if haystack and core and core not in haystack``.
     With NO ``x_metrics`` block the haystack is the empty string, the guard
     short-circuits, and *every fabricated figure passes with zero warnings*.
     The worst input produces the cleanest report.
  2. ``_flag_metrics`` is called from exactly ONE site - inside the loop over
     ``work[]``. ``basics.summary``, ``projects[]``, ``education[]``,
     ``volunteer[]``, ``awards[]`` and ``publications[]`` are never scanned.
  3. Everything it does find is a *warning*, and ``cmd_validate`` returns 0
     unless ``errors`` is non-empty. Warnings never change the exit code, so a
     CI gate wired to this lint is green by construction.

  Bonus bug: ``_flag_metrics`` strips commas BEFORE the year test, so any
  comma-grouped 4-digit count in 1900..2099 ("2,024 customers") is silently
  reclassified as a year and dropped.

This module is the fail-closed replacement. Its contract is inverted: a figure
is guilty until an ``x_metrics`` entry with real provenance proves it innocent,
and anything unproven is an ERROR that changes the exit code.

The provenance taxonomy (``x_metrics[].provenance``)
----------------------------------------------------
  M  Measured    - a command was run, a file was read, a count was computed.
                   ``how_known`` must name the instrument.
  E  External    - a third party can verify it in the open (public profile,
                   release page, merged PR). ``how_known`` must name the check.
  B  Believed    - owner-asserted, not verified. MUST NOT render.
  U  Unknown     - unsourced. MUST NOT render.

Only M and E may render, and only with a non-empty ``how_known``. A bare
string in ``x_metrics`` (the legacy shape) is treated as U - it carries no
provenance, so it cannot license a number.

Profile shape consumed
----------------------
    x_metrics:
      - id: pbinfo_solved            # optional, for cross-referencing
        value: "4,244"               # the figure as it will render
        claim: "4,244 problems solved at full score on pbinfo.ro"
        provenance: M                # M | E | B | U
        how_known: "read live from pbinfo.ro/profil 2026-09-24, corroborated
                    against the Wayback capture"
        as_of: "2026-09"             # optional

    x_zerofab:                       # optional, explicit and always reported
      allow:
        - text: "9:16"
          reason: "aspect ratio, not a claim"
      open_source_licensed:
        - "GRACE benchmark"          # substring of the text that may say
                                     # "open-source"; the repo has a LICENSE

Usage
-----
    C:\\Python314\\python.exe zerofab.py PROFILE[.yaml|.json] [--json] [--quiet]

Exit codes: 0 clean, 1 findings, 2 usage/parse failure.
Last line is always ``SUCCESS:zerofab`` or ``FAILED:zerofab``.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "Finding",
    "Metric",
    "lint",
    "lint_file",
    "load_profile",
    "main",
    "ERROR",
    "WARN",
    "INFO",
]

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

# --------------------------------------------------------------------------- #
# Finding codes                                                                #
# --------------------------------------------------------------------------- #
ZF_NO_METRICS = "ZF002"  # digit-bearing claim + absent/empty x_metrics
ZF_UNSOURCED = "ZF001"  # figure resolves to no x_metrics entry
ZF_WEAK_PROV = "ZF003"  # resolves to a B/U entry - must not render
ZF_NO_HOW_KNOWN = "ZF004"  # M/E entry without how_known
ZF_BAD_TAG = "ZF005"  # provenance tag outside M/E/B/U
ZF_KILL_LIST = "ZF006"  # forbidden phrase from the kill list
ZF_BANNED_WORD = "ZF007"  # passing / all gates green / widely used
ZF_OPEN_SOURCE = "ZF008"  # "open-source" with no declared LICENSE
ZF_LEGACY_METRIC = "ZF009"  # bare-string x_metrics entry (no provenance)
ZF_ORPHAN_METRIC = "ZF010"  # x_metrics entry that never renders (advisory)
ZF_BAD_ALLOW = "ZF011"  # x_zerofab.allow entry without a reason
ZF_SHAPE = "ZF012"  # profile is not a mapping / unreadable


# --------------------------------------------------------------------------- #
# Keys that hold identifiers or dates, never numeric CLAIMS.                   #
# Kill-list and banned-word scanning still covers them; only the "this number  #
# must be sourced" rule is relaxed, because a phone number or an ORCID is not  #
# an achievement.                                                              #
# --------------------------------------------------------------------------- #
_IDENTIFIER_KEYS = frozenset(
    {
        "url",
        "email",
        "phone",
        "doi",
        "username",
        "network",
        "startdate",
        "enddate",
        "date",
        "releasedate",
        "countrycode",
        "postalcode",
        "address",
        "id",
        "file",
        "image",
        "score",
        "location",
        "city",
        "region",
        "canonical",
        "version",
    }
)
_IDENTIFIER_PATH_PREFIXES = ("meta",)

# --------------------------------------------------------------------------- #
# Numeric token grammar.                                                       #
#                                                                              #
# `grouped` (a comma inside the number) is captured DELIBERATELY: it is the    #
# discriminator the shipped lint threw away before its year test, which is     #
# exactly why "2,024 customers" was silently ignored there.                    #
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(
    r"(?P<cur>[$\u20ac\u00a3\u00a5]\s?)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)*)"
    r"\s?"
    r"(?P<unit>%|[KMBkmb](?![A-Za-z0-9])|[xX](?![A-Za-z0-9]))?"
    r"(?P<plus>\+)?"
)

# Shapes that are never achievement figures. Masked (length-preserving) before
# tokenising so offsets stay honest.
_MASKS = (
    re.compile(r"\b[ABC][12]\b"),  # CEFR language levels: C1, B2
    re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE),  # v1.4.0
    re.compile(r"\b\d+\.\d+\.\d+(?:\.\d+)*\b"),  # semver 0.15.0
    re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b"),  # ISO dates 2025-09
)


@dataclass(frozen=True)
class Token:
    """One digit-bearing token lifted out of rendered text."""

    raw: str
    digits: str  # commas removed
    unit: str  # '', '%', 'k', 'm', 'b', 'x'
    grouped: bool  # the source text used comma grouping
    currency: bool
    plus: bool

    @property
    def is_year(self) -> bool:
        """A BARE, ungrouped, unsuffixed 4-digit 1900..2099 is a year.

        The shipped lint stripped commas first, so "2,024" reached this test as
        "2024" and was dropped. Grouping, a unit, a currency mark, a '+' or a
        decimal point all disqualify a token from the year exemption.
        """
        if self.grouped or self.unit or self.currency or self.plus:
            return False
        if "." in self.digits:
            return False
        return len(self.digits) == 4 and 1900 <= int(self.digits) <= 2099

    @property
    def forms(self) -> set[str]:
        out = {self.digits}
        if self.unit:
            out.add(f"{self.digits}{self.unit}")
        return out


def _mask(text: str) -> str:
    out = text
    for rx in _MASKS:
        out = rx.sub(lambda m: "\u0000" * len(m.group(0)), out)
    return out


def tokenize(text: str, *, apply_masks: bool = True) -> list[Token]:
    """Every digit-bearing token in ``text``, years and masked shapes included."""
    src = _mask(text) if apply_masks else text
    tokens: list[Token] = []
    for m in _TOKEN_RE.finditer(src):
        num = m.group("num")
        unit = (m.group("unit") or "").lower()
        tokens.append(
            Token(
                raw=m.group(0).strip(),
                digits=num.replace(",", ""),
                unit=unit,
                grouped="," in num,
                currency=bool(m.group("cur")),
                plus=bool(m.group("plus")),
            )
        )
    return tokens


# --------------------------------------------------------------------------- #
# Kill list - every entry is VERIFIED-FORBIDDEN material for this profile.     #
# Matched against normalised text (lowercased, comma-grouping removed, dashes  #
# folded, whitespace collapsed) so "1,590" and "1590" are the same string.     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    label: str
    fix: str


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


KILL_LIST: tuple[Rule, ...] = (
    Rule(
        _rx(r"\b1590\b[^.]{0,24}\bmerged\b[^.]{0,12}\bprs?\b|\b1590\s+prs?\b"),
        "1,590 merged PRs",
        "the verified monorepo figure is 351 PRs",
    ),
    Rule(
        _rx(r"\b6432\b[^.]{0,24}contribution"),
        "6,432 contributions",
        "not verified - drop it; 1,016 commits is the verified figure",
    ),
    Rule(
        _rx(r"\b(?:556|345)\s?k\b[^.]{0,24}(?:\bloc\b|lines of code)"),
        "556K/345K LOC",
        "not verified - drop the LOC claim entirely",
    ),
    Rule(
        _rx(r"\b8000\b[^.]{0,24}\bpassing\b"),
        '"8,000 PASSING tests"',
        'say "ships 8,000 test functions" - passing is a claim about a run',
    ),
    Rule(
        _rx(r"\b400\s?\+?\s*skills\b"),
        '"400+ skills authored"',
        'say "curates a 415-skill tree, authored ~140"',
    ),
    Rule(
        _rx(r"\b40\s?\+?\s*mcp\s+servers\b"),
        '"40+ MCP servers written"',
        "the verified figure is 18 MCP servers written",
    ),
    Rule(
        _rx(r"\b1000\s?-?\s?agent\b"),
        '"1000-agent audit"',
        "the audit died pre-synthesis - do not cite it",
    ),
    Rule(
        _rx(r"\b97\s?-?\s?slice\b"),
        '"97-slice audit"',
        "forbidden - the finding set was 42% refuted",
    ),
    Rule(
        _rx(r"\b1582\b[^.]{0,16}finding"),
        '"1,582 findings"',
        "forbidden - 42% of the findings were refuted",
    ),
    Rule(
        _rx(r"\b3\s+critical\s+rce\b"),
        '"3 critical RCE"',
        "forbidden - traces to the refuted audit",
    ),
    Rule(
        _rx(r"\b12272\b"),
        '"12,272-record corpus"',
        "forbidden",
    ),
    Rule(
        _rx(r"\b26\s?-?\s?repo\s+fleet\b"),
        '"26-repo fleet"',
        "forbidden",
    ),
    Rule(
        _rx(r"\b608\s?-?\s?unit\b|databricks\s+fan-?out"),
        "the 608-unit Databricks fan-out",
        "different person's account, corporate workspace - confidentiality risk",
    ),
    Rule(
        _rx(r"\bv?1\.4\.2\b"),
        "Reframe v1.4.2",
        "the latest Reframe release is v1.4.0",
    ),
    Rule(
        _rx(r"peer[-\s]?reviewed\s+publication"),
        '"peer-reviewed publication"',
        'it is a preprint - the word "preprint" is mandatory',
    ),
    Rule(
        _rx(r"\b4th\s+overall\b|finished\s+4th|\b4th\s+place\b"),
        '"finished 4th overall at GRACE"',
        "TRACED TO A FABRICATED DOCUMENT - this one ends a candidacy",
    ),
    Rule(
        _rx(
            r"\b(?:reframe|tracelines|llm-?anthology)\b[^.]{0,60}"
            r"\b(?:downloads?|installs?|adoptions?|users?|adopters?)\b"
        ),
        "a Reframe/tracelines/llm-anthology download or adoption figure",
        "no download or adoption figure for these is verified - drop it",
    ),
)

BANNED_WORDS: tuple[Rule, ...] = (
    Rule(
        _rx(r"\bpassing\b"),
        'the word "passing"',
        'use a verb of provenance: "ships" (a test that ships is a fact; a test '
        'that "passes" is a claim about a run you are not showing)',
    ),
    Rule(
        _rx(r"\ball\s+gates\s+green\b"),
        '"all gates green"',
        "name the gate and the run, or drop the claim",
    ),
    Rule(
        _rx(r"\bwidely\s+used\b"),
        '"widely used"',
        "give the verified adoption number or drop the claim",
    ),
)

_OPEN_SOURCE_RE = _rx(r"\bopen[-\s]?source(?:d|s)?\b")


def _normalise(text: str) -> str:
    """Lowercase, un-group numbers, fold dashes, collapse whitespace."""
    out = text.lower()
    out = re.sub(r"(?<=\d),(?=\d{3}\b)", "", out)
    out = re.sub(r"[\u2010-\u2015\u2212]", "-", out)
    return re.sub(r"\s+", " ", out).strip()


# --------------------------------------------------------------------------- #
# x_metrics                                                                    #
# --------------------------------------------------------------------------- #
_VALID_TAGS = ("M", "E", "B", "U")
_RENDERABLE_TAGS = ("M", "E")


@dataclass
class Metric:
    index: int
    ident: str
    value: str
    claim: str
    provenance: str
    how_known: str
    legacy: bool = False
    forms: set[str] = field(default_factory=set)
    used: bool = False

    @property
    def renderable(self) -> bool:
        return self.provenance in _RENDERABLE_TAGS and bool(self.how_known)

    @property
    def where(self) -> str:
        return f"x_metrics[{self.index}]" + (f" ({self.ident})" if self.ident else "")


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(_as_text(x) for x in v)
    if isinstance(v, dict):
        return " ".join(f"{k} {_as_text(x)}" for k, x in v.items())
    return str(v).strip()


def parse_metrics(raw: Any) -> tuple[list[Metric], list["Finding"]]:
    """Normalise ``x_metrics`` into Metric rows plus structural findings."""
    findings: list[Finding] = []
    metrics: list[Metric] = []
    if raw is None:
        return metrics, findings
    if isinstance(raw, dict):
        items: list[tuple[Any, Any]] = list(raw.items())
    elif isinstance(raw, (list, tuple)):
        items = [(None, x) for x in raw]
    else:
        findings.append(
            Finding(
                ERROR,
                ZF_SHAPE,
                "x_metrics",
                f"x_metrics must be a list or mapping, got {type(raw).__name__}.",
            )
        )
        return metrics, findings

    for i, (key, entry) in enumerate(items):
        if isinstance(entry, str):
            m = Metric(
                index=i,
                ident=str(key or ""),
                value=entry,
                claim=entry,
                provenance="U",
                how_known="",
                legacy=True,
            )
            findings.append(
                Finding(
                    ERROR,
                    ZF_LEGACY_METRIC,
                    m.where,
                    f"bare-string metric {entry!r} carries no provenance; it is "
                    f"treated as U and cannot license any figure. Convert it to "
                    f"{{value, claim, provenance: M|E, how_known}}.",
                )
            )
        elif isinstance(entry, dict):
            tag = _as_text(entry.get("provenance") or entry.get("prov")).upper()[:1]
            m = Metric(
                index=i,
                ident=_as_text(entry.get("id") or key or ""),
                value=_as_text(entry.get("value")),
                claim=_as_text(entry.get("claim") or entry.get("text")),
                provenance=tag,
                how_known=_as_text(entry.get("how_known")),
            )
            if tag not in _VALID_TAGS:
                findings.append(
                    Finding(
                        ERROR,
                        ZF_BAD_TAG,
                        m.where,
                        f"provenance {entry.get('provenance')!r} is not one of "
                        f"M (measured) / E (externally verifiable) / B (believed) / "
                        f"U (unknown).",
                    )
                )
            elif tag in _RENDERABLE_TAGS and not m.how_known:
                findings.append(
                    Finding(
                        ERROR,
                        ZF_NO_HOW_KNOWN,
                        m.where,
                        f"provenance {tag} requires a non-empty how_known naming "
                        f"the instrument or the public check. Without it the tag "
                        f"is an assertion, not evidence.",
                    )
                )
        else:
            findings.append(
                Finding(
                    ERROR,
                    ZF_SHAPE,
                    f"x_metrics[{i}]",
                    f"metric entry must be a mapping or string, got "
                    f"{type(entry).__name__}.",
                )
            )
            continue

        for tok in tokenize(f"{m.value} {m.claim}", apply_masks=False):
            m.forms |= tok.forms
        metrics.append(m)
    return metrics, findings


# --------------------------------------------------------------------------- #
# Findings                                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"  {self.severity:<5} {self.code} {self.path}: {self.message}"

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


# --------------------------------------------------------------------------- #
# Walk EVERY string-bearing field                                              #
# --------------------------------------------------------------------------- #
def walk_strings(node: Any, path: str = "") -> Iterable[tuple[str, str]]:
    """Yield (dotted path, text) for every string in the profile.

    ``x_`` keys are skipped - they are the evidence bank, not rendered output.
    This is the whole tree, not just ``work[]``: defect (2) in the shipped lint
    was that only ``work[].highlights`` was ever scanned.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            ks = str(k)
            if ks.startswith("x_"):
                continue
            yield from walk_strings(v, f"{path}.{ks}" if path else ks)
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, bool) or node is None:
        return
    elif isinstance(node, str):
        if node.strip():
            yield path, node
    else:
        yield path, str(node)


def _leaf_key(path: str) -> str:
    leaf = path.split(".")[-1]
    return re.sub(r"\[\d+\]$", "", leaf).lower()


def _is_identifier_field(path: str) -> bool:
    if any(path == p or path.startswith(p + ".") for p in _IDENTIFIER_PATH_PREFIXES):
        return True
    return _leaf_key(path) in _IDENTIFIER_KEYS


_ENTITY_RE = re.compile(r"^([A-Za-z_]+\[\d+\])")


def _entity(profile: dict[str, Any], path: str) -> dict[str, Any] | None:
    m = _ENTITY_RE.match(path)
    if not m:
        return None
    key, _, rest = m.group(1).partition("[")
    idx = int(rest.rstrip("]"))
    seq = profile.get(key)
    if isinstance(seq, (list, tuple)) and 0 <= idx < len(seq):
        item = seq[idx]
        return item if isinstance(item, dict) else None
    return None


# --------------------------------------------------------------------------- #
# The lint                                                                     #
# --------------------------------------------------------------------------- #
def lint(profile: Any) -> list[Finding]:
    """Return every finding for ``profile``. ERROR severity means fail."""
    if not isinstance(profile, dict):
        return [
            Finding(
                ERROR,
                ZF_SHAPE,
                "<root>",
                f"profile must be a mapping, got {type(profile).__name__}.",
            )
        ]

    findings: list[Finding] = []
    metrics, metric_findings = parse_metrics(profile.get("x_metrics"))
    findings.extend(metric_findings)

    cfg = profile.get("x_zerofab") or {}
    if not isinstance(cfg, dict):
        findings.append(
            Finding(ERROR, ZF_SHAPE, "x_zerofab", "x_zerofab must be a mapping.")
        )
        cfg = {}

    allow: list[tuple[str, str]] = []
    for i, row in enumerate(cfg.get("allow") or []):
        if isinstance(row, dict):
            text, reason = _as_text(row.get("text")), _as_text(row.get("reason"))
        else:
            text, reason = _as_text(row), ""
        if not text:
            continue
        if not reason:
            findings.append(
                Finding(
                    ERROR,
                    ZF_BAD_ALLOW,
                    f"x_zerofab.allow[{i}]",
                    f"allow-list entry {text!r} has no reason. An exemption "
                    f"without a written reason is a silent pass.",
                )
            )
            continue
        allow.append((text, reason))

    licensed = [_normalise(_as_text(x)) for x in (cfg.get("open_source_licensed") or [])]

    strings = list(walk_strings(profile))
    has_renderable_metrics = any(m.renderable for m in metrics)
    metrics_block_present = bool(metrics)

    for path, text in strings:
        norm = _normalise(text)

        # -- kill list + banned words: scanned on EVERY string, no exceptions --
        for rule in KILL_LIST:
            if rule.pattern.search(norm):
                findings.append(
                    Finding(
                        ERROR,
                        ZF_KILL_LIST,
                        path,
                        f"kill-list phrase {rule.label} - {rule.fix}.",
                    )
                )
        for rule in BANNED_WORDS:
            if rule.pattern.search(norm):
                findings.append(
                    Finding(
                        ERROR,
                        ZF_BANNED_WORD,
                        path,
                        f"banned wording {rule.label} - {rule.fix}.",
                    )
                )

        # -- "open-source" needs a declared LICENSE ---------------------------
        if _OPEN_SOURCE_RE.search(norm):
            ent = _entity(profile, path) or {}
            declared = _as_text(ent.get("license") or ent.get("x_license"))
            covered = any(lic and lic in norm for lic in licensed)
            if not declared and not covered:
                findings.append(
                    Finding(
                        ERROR,
                        ZF_OPEN_SOURCE,
                        path,
                        'says "open-source" but no LICENSE is declared. Add a '
                        "license field to the entry, or list the subject under "
                        "x_zerofab.open_source_licensed once the repo really has "
                        "a LICENSE file. A repo with no LICENSE is not open source.",
                    )
                )

        # -- numeric claims ---------------------------------------------------
        if _is_identifier_field(path):
            continue
        exempt = next((r for t, r in allow if t and t in text), None)

        for tok in tokenize(text):
            if tok.is_year:
                continue
            if exempt is not None:
                findings.append(
                    Finding(
                        INFO,
                        "ZF000",
                        path,
                        f"figure {tok.raw!r} allow-listed: {exempt}.",
                    )
                )
                continue

            if not metrics_block_present:
                findings.append(
                    Finding(
                        ERROR,
                        ZF_NO_METRICS,
                        path,
                        f"figure {tok.raw!r} renders but the profile has NO "
                        f"x_metrics block. Absent evidence is not a pass: every "
                        f"digit-bearing claim needs an M/E entry with how_known.",
                    )
                )
                continue

            hits = [m for m in metrics if tok.forms & m.forms]
            good = [m for m in hits if m.renderable]
            if good:
                for m in good:
                    m.used = True
                continue
            if hits:
                for m in hits:
                    m.used = True
                worst = hits[0]
                if worst.legacy:
                    why = "the entry is a bare string, so it carries no provenance"
                elif worst.provenance not in _VALID_TAGS:
                    why = f"the entry's provenance tag {worst.provenance!r} is invalid"
                elif worst.provenance in _RENDERABLE_TAGS:
                    why = "the entry has no how_known"
                else:
                    why = (
                        f"the entry is tagged {worst.provenance} "
                        f"({'believed' if worst.provenance == 'B' else 'unknown'})"
                    )
                findings.append(
                    Finding(
                        ERROR,
                        ZF_WEAK_PROV,
                        path,
                        f"figure {tok.raw!r} matches {worst.where} but {why}. "
                        f"Only M/E entries with how_known may render.",
                    )
                )
                continue

            hint = (
                ""
                if has_renderable_metrics
                else " (no x_metrics entry in this profile is renderable at all)"
            )
            findings.append(
                Finding(
                    ERROR,
                    ZF_UNSOURCED,
                    path,
                    f"figure {tok.raw!r} resolves to no x_metrics entry{hint}. "
                    f"Add a verified entry with provenance M or E and a "
                    f"how_known, or remove the number.",
                )
            )

    for m in metrics:
        if not m.used and m.renderable:
            findings.append(
                Finding(
                    WARN,
                    ZF_ORPHAN_METRIC,
                    m.where,
                    f"verified metric {m.value or m.claim!r} never renders - "
                    f"evidence you are not using.",
                )
            )

    order = {ERROR: 0, WARN: 1, INFO: 2}
    findings.sort(key=lambda f: (order.get(f.severity, 3), f.path, f.code))
    return findings


def errors(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == ERROR]


# --------------------------------------------------------------------------- #
# IO                                                                           #
# --------------------------------------------------------------------------- #
def load_profile(path: Path) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json":
        return json.loads(text)
    try:
        from ruamel.yaml import YAML

        return YAML(typ="safe").load(text)
    except ImportError:
        pass
    try:
        import yaml

        return yaml.safe_load(text)
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            f"FAILED: no YAML parser available ({exc}). Install ruamel.yaml or "
            f"pyyaml, or pass a .json profile."
        ) from exc


def lint_file(path: str | Path) -> list[Finding]:
    return lint(load_profile(Path(path)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="zerofab",
        description="Fail-closed zero-fabrication lint for a cv-studio profile.",
    )
    ap.add_argument("profile", help="profile.yaml or profile.json")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--quiet", action="store_true", help="only the verdict line")
    args = ap.parse_args(argv)

    path = Path(args.profile)
    try:
        profile = load_profile(path)
    except FileNotFoundError:
        print(f"  {ERROR} {ZF_SHAPE} <file>: {path} not found.")
        print("FAILED:zerofab")
        return 2
    except Exception as exc:  # noqa: BLE001 - any parse failure must fail closed
        print(f"  {ERROR} {ZF_SHAPE} <file>: cannot parse {path}: {exc}")
        print("FAILED:zerofab")
        return 2

    found = lint(profile)
    errs = errors(found)
    warns = [f for f in found if f.severity == WARN]

    if args.json:
        print(
            json.dumps(
                {
                    "profile": str(path),
                    "errors": len(errs),
                    "warnings": len(warns),
                    "findings": [f.as_dict() for f in found],
                },
                indent=2,
            )
        )
    elif not args.quiet:
        print(f"zerofab: {path}")
        for f in found:
            print(f.render())
        print(f"  {len(errs)} error(s), {len(warns)} warning(s)")

    if errs:
        print("FAILED:zerofab")
        return 1
    print("SUCCESS:zerofab")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
