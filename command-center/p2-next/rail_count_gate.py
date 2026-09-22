r"""CI gate: the cross-vendor rail number an OWNER acts on must be RE-DERIVED, never stored.

WHY THIS EXISTS
===============
P2NEXT produced one number the owner is meant to price a decision against -- how many BLOCKED
Prompt Two units are waiting on a review rail that is down. The lane measured it three times and
got three different answers, and every one of those answers was published somewhere:

  * `command-center/CROSS-VENDOR-RAIL-STATUS.md` said "it gates 43 blocked units" / "43 of 47".
  * `command-center/p2-next/VENDOR-SATISFIABILITY.json` said 41 of 51 (a WORKTREE measurement that
    silently included a sibling lane's uncommitted edit to ADV-0041).
  * Re-running the producer after this lane edited six receipts printed 47 of 51.

An independent auditor and an adversarial refuter both landed on the same root cause: the number
was STORED and the derivation was not re-run, so a receipt edit anywhere in the tree moved the
truth while every published copy kept its old value. `vendor_satisfiability.py` was fixed (rule-D
gate, `--basis committed` default, CHECK-not-write). But a fixed script that nothing invokes is not
a fix -- it is a script. This gate is the part that makes the fix reachable: it re-derives the
number on every push and PR and fails when any published copy disagrees.

WHAT IT CHECKS (each one fails CLOSED)
======================================
  C1  the doc carries a machine-readable RAIL-COUNT block, and every field in it equals a fresh
      derivation from the COMMITTED tree through the shipped resolver. A missing/unparseable block
      is a FAILURE, not a skip.
  C2  no unit-count claim in the doc's PROSE contradicts that derivation. A line may quote a
      different figure only when it carries a dated marker on the SAME line -- `[superseded ...]`
      for a retired number, `[worktree-observed ...]` for a point-in-time reading of a dirty tree.
      The gate prints how many claims used that escape, so a document cannot be quietly marked
      instead of fixed. This is what catches "43 of 47" rotting in the headline while the JSON is
      correct.
  C3  the committed VENDOR-SATISFIABILITY.json headline equals the same fresh derivation -- the
      stored-answer check the refuter asked for, turned into a re-derivation.
  C4  the derived population is plausible (>= MIN_BLOCKED). A resolver or catalog shape change that
      silently yields "0 blocked units, 0 rail-blocked" would otherwise make every other check pass
      vacuously. A control must count the thing being compared and be loud when it cannot.
  C5  every unit the derivation calls same-vendor-satisfiable actually carries an independent
      reviewer PASS, AND that PASS carries a review behind it -- notes over a calibrated floor
      that name a falsification attempt. This is the lane's DoD item 2 held open over time: if a
      future edit creates a satisfiable-but-unreviewed unit, that is newly reachable work and the
      owner should see it.
      Until this round C5 was VERDICT-SHAPED ONLY, and this file's own header claimed "every
      check in both states" while C5 had no self-test case at all. Measured consequence
      (`_g3_c5_content_probe.py`): emptying EVERY reviewer note across all ten satisfiable units
      changed nothing -- reviewed=10, problems=0 -- while flipping a verdict fired on all ten, so
      the probe could see failure and the silence was a real gap rather than a dead detector.
      The floor is calibrated on the committed receipts (1027-2092 chars), not invented; the
      resolvable-evidence-anchor half is REPORTED AND NOT ENFORCED, because 0 of 10 receipts
      carry one and a gate that fails every existing input on its first run is a gate that gets
      switched off. See MIN_REVIEW_NOTES and check_reviewed.
  C6  the rail VERDICT is declared ONCE and dated (`rail_state`, `rail_probed`), and no page in
      the scanned set asserts a state contradicting it without the same dated marker C2 uses.
      MEASURED, and the reason it exists: round 3 retracted "the rail is DOWN" in the owning doc
      and left `E2E-WAVE-STATUS.md:124` -- a page THIS GATE ALREADY SCANNED -- asserting it. The
      gate stayed green for a whole round, because the unit count in that sentence (42) was still
      correct and C2 only reads numbers. A citing-doc check that returns SUCCESS whether or not
      the two pages contradict each other is a control that looks the same under both hypotheses.
      LIMIT, INLINE: C6 proves CONSISTENCY, never TRUTH. This gate makes no network call and
      cannot know whether the rail answers (`ci-hygiene.md` §2 keeps a live endpoint out of the
      per-PR suite), so its silence means the corpus stopped contradicting itself -- nothing more.
      SECOND LIMIT, INLINE: matching is present-tense and NEGATION-BLIND. "the rail does not
      answer" reads as an UP assertion and would pass under `rail_state: up`. Measured cost today:
      0 -- no scanned page contains a negated assertion (`K1-PREMISE-SCAN.json`). Settling
      experiment: add a negation window to STATE_ASSERT and re-run `_k1_premise_scan.py`, which
      must keep finding exactly the same 3 assertions in the owning doc and 0 in the citing one.

DETECTOR CONTROL. `--self-test` runs every check against a KNOWN-BROKEN input and requires it to
FIRE, then against the known-good input and requires SILENCE -- including the ways this gate could
be inert rather than clean: C2 must not fire on ordinary numbers that are not unit counts (a date,
a port, a version, an option number in a neighbouring clause), and the exemption marker must not
degrade into "any line with a digit passes". Run it FIRST; a gate whose own controls are broken
must not judge a pull request.

RED-PROOF. `_i3_redproof.py` clones the repo, commits this lane's files into the clone, and runs
four injections drawn from what actually happened -- the owning doc rotting back to 43, a
receipt's `failure.blocked_on` moving a unit across the split, a receipt forging SUCCESS, and the
CITING status doc rotting while the owning doc stays right. It records whether the PRE-EXISTING CI
stays green on each. Receipt: `I3-REDPROOF.json`.

KNOWN RECALL LIMIT, inline: C2 is LINE-scoped, so a count whose unit noun wraps onto the next
markdown line is not seen (measured: E2E-WAVE-STATUS.md had `The "43` ending one line and
`blocked units"` starting the next). Settling experiment: match per PARAGRAPH and require the
exemption marker to be paragraph-scoped too -- which weakens the marker, hence not done here.

USAGE
  python command-center/p2-next/rail_count_gate.py --self-test
  python command-center/p2-next/rail_count_gate.py                 # committed basis (CI)
  python command-center/p2-next/rail_count_gate.py --basis worktree # authoring
  python command-center/p2-next/rail_count_gate.py --doc <path>     # judge a copy (red-proof)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC_REL = "command-center/CROSS-VENDOR-RAIL-STATUS.md"
ART_REL = "command-center/p2-next/VENDOR-SATISFIABILITY.json"
READY_REL = "command-center/READY-UNITS.json"

#: Documents that CITE the rail number without owning it. E2E-WAVE-STATUS.md says outright that
#: its "43 blocked units" is *anchored* at CROSS-VENDOR-RAIL-STATUS.md:1 -- so correcting the
#: anchor while leaving the citation behind just moves the stale number one file over. They are
#: NOT required to carry a RAIL-COUNT block (they do not own the measurement) and C2 is applied
#: only to lines ON TOPIC: a status doc legitimately counts other things (ADV units, READY units,
#: casualty receipts), and demanding markers on all of them would be a gate reaching past its
#: evidence.
SECONDARY_DOCS = ("command-center/E2E-WAVE-STATUS.md",)
RAIL_TOPIC = re.compile(r"cross[-_ ]?vendor|review rail|\brail\b|blocked units", re.I)

#: Fail closed below this. The real population has been 51-52 all program; a derivation that
#: collapses to a handful means the catalog or the resolver changed shape, not that the queue
#: emptied. Chosen well under the observed floor so ordinary churn cannot trip it.
MIN_BLOCKED = 40

#: C5 used to read ONLY `verdict` and `independent`. Measured by `_g3_c5_content_probe.py`:
#: emptying EVERY reviewer note across all ten satisfiable units changed nothing (reviewed=10,
#: problems=0), while flipping a verdict DID fire (problems=10) -- so the probe could see failure
#: and the silence was informative. A check that proves a review HAPPENED but not that it SAID
#: anything is a receipt reader, not a gate.
#:
#: CALIBRATED, NOT INVENTED. The ten committed receipts carry 1027-2092 chars of reviewer notes
#: (`_c1_calibrate_floor.py`). 200 sits ~5x below the observed minimum, so a terse-but-genuine
#: review passes and only an emptied or stub note fails. The risk this floor is chosen against is
#: a FALSE POSITIVE on a short valid review, not a tight fit to today's data.
MIN_REVIEW_NOTES = 200

#: A review must name how it tried to BREAK the claim, not merely that it agreed. All ten
#: committed receipts already do. The detector is controlled in BOTH directions by
#: `_c2_control_detectors.py`: it is silent on bland approval prose, and stripping the matched
#: vocabulary out of every real note silences it -- so 10/10 is a measurement rather than a regex
#: catching incidental words.
_FALSIFICATION = re.compile(
    r"falsif|refut|mutat|counter-?example|tried to break|both[- ]states"
    r"|control|disconfirm|negative case",
    re.I,
)

#: An evidence anchor: claim_gate's own shape, reused rather than re-invented.
#: REPORTED, NEVER BLOCKING -- see `check_reviewed`. Measured: 0 of 10 committed receipts carry
#: one that RESOLVES to a file on disk, so enforcing it today would fail all ten.
_ANCHOR = re.compile(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,6}):(\d+)|https?://\S+")

_spec = importlib.util.spec_from_file_location(
    "_vs_rail", Path(__file__).with_name("vendor_satisfiability.py")
)
_vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vs)

#: The declared block the doc must carry. Keys are checked individually so a partial block is a
#: failure rather than a silent pass on the fields that happen to be present.
BLOCK_RE = re.compile(r"<!--\s*RAIL-COUNT\s*(?P<body>.*?)-->", re.S | re.I)
#: `(.+?)` not `(\S+)`: `derived_by` carries a command line with spaces, and a single-token
#: pattern silently drops the field -- which reads as "block is missing derived_by" rather than
#: "the pattern is wrong". Measured while writing this gate.
FIELD_RE = re.compile(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.M)

REQUIRED_FIELDS = (
    "basis",
    "blocked_units",
    "rail_blocked",
    #: DEMAND vs UNMET DEMAND. `rail_blocked` is what receipts ASK FOR;
    #: `rail_blocked_unfulfilled` is what is still OWED. They differed by 3 the day
    #: this field was added (ADV-0023/0035/0042 already hold an executed openai PASS),
    #: and publishing only the first overstated what restoring the rail buys.
    "rail_blocked_unfulfilled",
    "rail_blocked_fulfilled",
    "satisfiable_now",
    "reviewed_satisfiable",
    "catalog_units",
    #: C6. The rail VERDICT, declared ONCE and dated, so every other page has something to agree
    #: with. Without it the retraction of a premise is unenforceable: round 3 corrected the owning
    #: doc and a citing page kept the old verdict for a full round with CI green.
    "rail_state",
    "rail_probed",
    "derived_by",
)

#: A UNIT-COUNT claim: an integer bound to a unit noun, either directly ("43 blocked units",
#: "the 43 review-gated units") or through an "N of M" pair ("43 of 47 BLOCKED receipts").
#: Deliberately NOT a bare digit scan -- counting every number in the document instead of the
#: field is the use-vs-mention error this repo keeps paying for.
#:
#: MEASURED FALSE POSITIVE, and the reason the direct form is a NOUN-PHRASE match rather than a
#: proximity window: the first version allowed any 45 characters between the number and the noun,
#: and it flagged "Option 2 would move some units but must not be silently substituted for option
#: 1 on the receipts" -- two option numbers read as unit counts. A proximity window measures
#: nearness, not grammatical binding. The direct form now permits only up to three MODIFIER words
#: between the number and the noun and bars the function/verb words that mark a clause boundary.
UNIT_NOUN = r"(?:units?|receipts?)"
COUNT_DIRECT = re.compile(
    rf"\b(\d{{1,4}})\s+((?:[A-Za-z][\w*-]*\s+){{0,3}}?){UNIT_NOUN}\b", re.I
)
#: The "N of M" pair is scoped to LINES that mention a unit noun anywhere, rather than requiring
#: the noun within a fixed window. A markdown table row puts the noun in the header or a later
#: cell, so a window-bound pattern silently missed "| 43 of 47 | ... |" -- measured on the first
#: draft of the very document this gate guards. Line scope keeps the precision (a bare "3 of 5" in
#: a sentence about workflows is not a unit count) while restoring the recall.
COUNT_OF_PAIR = re.compile(r"\b(\d{1,4})\s+of\s+(?:the\s+)?(\d{1,4})\b")
LINE_HAS_UNIT_NOUN = re.compile(rf"\b{UNIT_NOUN}\b", re.I)
#: Words that cannot appear inside the noun phrase "<N> ... units". Their presence means the
#: number belongs to a different clause than the noun.
BARRED_BETWEEN = frozenset(
    """would will could should may might must move moves moved is are was were be been being
    on in at to and or but that which with from for by not no do does did have has had if then
    than as into over under per via some more most all other another this these those it its
    make makes made give gives adds add""".split()
)
#: The ONE escape hatch, and it is deliberately the only one. A unit count that cannot be
#: re-derived today must be marked explicitly and dated: `[superseded 2026-08-13]` for a retired
#: figure, `[worktree-observed 2026-08-13]` for a point-in-time reading of a dirty tree.
#:
#: MEASURED, and the reason the earlier design was wrong: C2 used to accept any number that
#: matched a LIVE worktree derivation on a line containing the word "worktree". On this machine
#: the worktree carries sibling lanes' uncommitted edits, so 41-of-51 was "valid". In a fresh
#: clone -- which is what CI checks out -- the worktree IS the committed tree, that derivation
#: returns 42-of-52, and the same sentence became a violation. An escape whose truth depends on
#: the checker's local dirt is not a check; it is a fail-open that happens to pass for the author.
#: Proven by running this gate inside a throwaway clone (see _i3_redproof.py leg "good").
EXEMPT_MARKER = re.compile(r"\[(?:superseded|worktree-observed)\b[^\]]*\]", re.I)

#: C6 -- CONSISTENCY, NEVER TRUTH. This gate makes no network call and cannot know whether the
#: rail answers; `ci-hygiene.md` §2 forbids a live endpoint in the per-PR suite. What it CAN
#: prove is that every page in the declared set agrees with the ONE declared verdict, so a
#: retraction can no longer land in the owning doc while a citing page keeps asserting the
#: retracted premise. Read its silence as "the corpus stopped contradicting itself", never as
#: "the rail is up".
#:
#: MEASURED, and the reason this check exists at all: round 3 retracted "the rail is DOWN" in
#: `CROSS-VENDOR-RAIL-STATUS.md` and left `E2E-WAVE-STATUS.md:124` -- a doc THIS GATE ALREADY
#: SCANS as a citing doc -- asserting it. The gate stayed green, because the unit count in that
#: sentence (42) was still correct and C2 only reads numbers. A citing-doc check that returns
#: SUCCESS whether or not the two pages contradict each other is a control that looks the same
#: under both hypotheses. Receipt: `K1-PREMISE-SCAN.json`.
RAIL_STATES = ("up", "down")
RAIL_PROBED_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

#: A present-tense rail-state ASSERTION: `rail ... is DOWN|UP`, or the copula-free `rail ANSWERS`
#: the owning doc's own title uses. Past-tense narration ("was pronounced down", "was never
#: down") is deliberately NOT matched -- this asks what a page asserts today, not what it recounts
#: about a previous round, and this lane is required to keep refuted wording rather than delete it.
STATE_ASSERT = re.compile(
    r"\brail\b[^.\n]{0,40}?(?:\b(?:is|are)\b\s*\**\s*(?P<c>DOWN|UP)|\**\s*(?P<v>ANSWERS?))\b",
    re.I,
)
#: MEASURED FALSE POSITIVE, first run of `_k1_premise_scan.py`: the owning doc was reported as
#: asserting UP on the strength of *"...whether the rail is up or down. That is a control that
#: looks the same under both hypotheses"* -- a sentence about the GATE being state-blind. The
#: conclusion was right and the evidence was wrong, which is the worse failure. A hypothetical is
#: not an assertion. That miss is also why the declared state is READ FROM A FIELD below instead
#: of inferred from the owning doc's prose.
STATE_DISJUNCTION = re.compile(r"\A\s*or\s+(?:up|down)\b", re.I)
#: A quoted span is a MENTION, not a use. The owning doc quotes its own retracted headline
#: verbatim under a REFUTED marker; that is a record of what was refuted. Measured: without this,
#: C6 fires on `CROSS-VENDOR-RAIL-STATUS.md:16` -- on the retraction itself.
QUOTED_SPAN = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`")


def counts_at(basis: str) -> dict[str, int]:
    rows = _vs.load_units(basis)
    c = Counter(r["verdict"] for r in rows)
    return {
        "blocked_units": len(rows),
        "rail_blocked": c[_vs.BLOCKED_RAIL],
        "rail_blocked_unfulfilled": sum(
            1 for r in rows if r.get("still_needs_cross_vendor")
        ),
        "rail_blocked_fulfilled": sum(
            1
            for r in rows
            if r["verdict"] == _vs.BLOCKED_RAIL and r.get("cross_vendor_fulfilled")
        ),
        "satisfiable_now": c[_vs.SAT],
    }


def satisfiable_rows(basis: str) -> list[dict]:
    return [r for r in _vs.load_units(basis) if r["verdict"] == _vs.SAT]


def read_text(basis: str, rel: str) -> str | None:
    if basis == "committed":
        return _vs.batch_blobs("HEAD", [rel])[rel]
    p = REPO / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def parse_block(doc: str) -> tuple[dict[str, str], list[str]]:
    """Return (fields, problems). A missing or partial block is a problem, never a skip."""
    m = BLOCK_RE.search(doc)
    if not m:
        return {}, [
            "C1 the doc carries no <!-- RAIL-COUNT ... --> block; the published number is "
            "therefore unverifiable and this gate fails closed"
        ]
    fields = {k: v for k, v in FIELD_RE.findall(m.group("body"))}
    missing = [k for k in REQUIRED_FIELDS if k not in fields]
    return fields, (
        [f"C1 RAIL-COUNT block is missing field(s): {missing}"] if missing else []
    )


def check_block(
    fields: dict[str, str],
    derived: dict[str, int],
    reviewed: int,
    catalog_units: int,
    basis: str,
) -> list[str]:
    problems = []
    expected = {
        "basis": basis,
        "blocked_units": str(derived["blocked_units"]),
        "rail_blocked": str(derived["rail_blocked"]),
        "rail_blocked_unfulfilled": str(derived["rail_blocked_unfulfilled"]),
        "rail_blocked_fulfilled": str(derived["rail_blocked_fulfilled"]),
        "satisfiable_now": str(derived["satisfiable_now"]),
        "reviewed_satisfiable": str(reviewed),
        "catalog_units": str(catalog_units),
    }
    for k, want in expected.items():
        got = fields.get(k)
        if got is not None and got != want:
            problems.append(
                f"C1 RAIL-COUNT {k}: doc says {got}, fresh derivation says {want}"
            )
    got_by = fields.get("derived_by", "")
    if "vendor_satisfiability.py" not in got_by:
        problems.append(
            f"C1 RAIL-COUNT derived_by must name the producing script, got {got_by!r}"
        )
    return problems


def prose_claims(doc: str) -> list[tuple[int, str, int]]:
    """Every unit-count claim as (lineno, line, value). Both regexes, deduped by position."""
    out: list[tuple[int, str, int]] = []
    for lineno, line in enumerate(doc.splitlines(), 1):
        if line.lstrip().startswith("<!--") or "RAIL-COUNT" in line:
            continue
        seen: set[int] = set()
        if LINE_HAS_UNIT_NOUN.search(line):
            for m in COUNT_OF_PAIR.finditer(line):
                for g in (1, 2):
                    v = int(m.group(g))
                    if v not in seen:
                        seen.add(v)
                        out.append((lineno, line, v))
        for m in COUNT_DIRECT.finditer(line):
            between = [w.lower() for w in m.group(2).split()]
            if any(w in BARRED_BETWEEN for w in between):
                continue  # the number belongs to another clause, not to this noun
            v = int(m.group(1))
            if v not in seen:
                seen.add(v)
                out.append((lineno, line, v))
    return out


def check_prose(
    doc: str,
    derived: dict[str, int],
    catalog_units: int,
    reviewed: int,
    ready: int = -1,
    topic_only: bool = False,
    where: str = "",
) -> tuple[list[str], int]:
    """Return (problems, exempted). `exempted` is printed so the escape hatch stays visible:
    a reviewer watching that number sees a document being marked quiet rather than fixed."""
    ok = set(derived.values()) | {catalog_units, reviewed, ready}
    problems, exempted = [], 0
    tag = f"{where} " if where else ""
    for lineno, line, v in prose_claims(doc):
        if topic_only and not RAIL_TOPIC.search(line):
            continue
        if v in ok:
            continue
        if EXEMPT_MARKER.search(line):
            exempted += 1
            continue
        problems.append(
            f"C2 {tag}line {lineno}: unit count {v} matches no fresh derivation "
            f"({sorted(x for x in ok if x >= 0)}) and the line carries no dated "
            f"[superseded ...] / [worktree-observed ...] marker: {line.strip()[:110]!r}"
        )
    return problems, exempted


def state_assertions(doc: str) -> list[tuple[int, str, str]]:
    """Every present-tense rail-state assertion as (lineno, 'up'|'down', line)."""
    out: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(doc.splitlines(), 1):
        if line.lstrip().startswith("<!--") or "RAIL-COUNT" in line:
            continue
        probe = QUOTED_SPAN.sub(" ", line)
        for m in STATE_ASSERT.finditer(probe):
            if STATE_DISJUNCTION.match(probe[m.end() :]):
                continue
            token = (m.group("c") or m.group("v")).lower()
            out.append((lineno, "down" if token == "down" else "up", line))
    return out


def check_state_fields(fields: dict[str, str]) -> tuple[str, list[str]]:
    """Return (declared_state, problems). Shape only -- the prose comparison is separate so a
    citing doc cannot re-report the owning block's own field errors."""
    problems: list[str] = []
    declared = (fields.get("rail_state") or "").strip().lower()
    if declared not in RAIL_STATES:
        problems.append(
            f"C6 RAIL-COUNT rail_state must be one of {list(RAIL_STATES)}, got {declared!r}"
        )
        declared = ""
    probed = (fields.get("rail_probed") or "").strip()
    if not RAIL_PROBED_RE.fullmatch(probed):
        problems.append(
            f"C6 RAIL-COUNT rail_probed must be an ISO date (YYYY-MM-DD), got {probed!r}; "
            "an undated verdict cannot be told apart from a stale one"
        )
    return declared, problems


def check_state_prose(doc: str, declared: str, where: str = "") -> list[str]:
    """Every page in the declared set must agree with the declared verdict, or carry the same
    dated marker C2 uses. An empty `declared` judges nothing -- C6's field check has already
    fired, and re-reporting it per document would inflate one defect into several."""
    if declared not in RAIL_STATES:
        return []
    tag = f"{where} " if where else ""
    return [
        f"C6 {tag}line {lineno}: asserts the rail is {state.upper()} while the RAIL-COUNT block "
        f"declares {declared.upper()}, and the line carries no dated [superseded ...] marker: "
        f"{line.strip()[:110]!r}"
        for lineno, state, line in state_assertions(doc)
        if state != declared and not EXEMPT_MARKER.search(line)
    ]


def check_artifact(basis: str, derived: dict[str, int]) -> list[str]:
    txt = read_text(basis, ART_REL)
    if txt is None:
        return [f"C3 {ART_REL} absent at basis={basis}"]
    try:
        art = json.loads(txt)
    except Exception as exc:  # pragma: no cover - malformed JSON is a hard failure
        return [f"C3 {ART_REL} does not parse: {exc}"]
    problems = []
    if art.get("blocked_units") != derived["blocked_units"]:
        problems.append(
            f"C3 {ART_REL} blocked_units={art.get('blocked_units')} but fresh derivation says "
            f"{derived['blocked_units']}"
        )
    vc = art.get("verdict_counts") or {}
    for key, want in ((_vs.BLOCKED_RAIL, "rail_blocked"), (_vs.SAT, "satisfiable_now")):
        if vc.get(key) != derived[want]:
            problems.append(
                f"C3 {ART_REL} verdict_counts[{key}]={vc.get(key)} but fresh derivation says "
                f"{derived[want]}"
            )
    return problems


def review_problems(unit_id: str, rec: dict) -> list[str]:
    """C5 for ONE receipt: an independent PASS, AND notes that carry actual review content.

    Pure over the parsed receipt so `_selftest` can drive both states without touching git.
    The count of units carrying an independent PASS is deliberately NOT narrowed by the content
    floor: `reviewed_satisfiable` in the RAIL-COUNT block means "carries an independent PASS",
    C1 compares it against that, and silently redefining it here would move a published number
    as a side effect of adding a check.
    """
    rv = rec.get("reviewer") or {}
    if not (
        str(rv.get("verdict", "")).upper() == "PASS" and rv.get("independent") is True
    ):
        return [
            f"C5 {unit_id} is satisfiable by a same-vendor independent reviewer but carries "
            f"no independent PASS (verdict={rv.get('verdict')!r}, "
            f"independent={rv.get('independent')!r}) -- newly reachable work"
        ]
    notes = rv.get("notes")
    notes = notes.strip() if isinstance(notes, str) else ""
    if len(notes) < MIN_REVIEW_NOTES:
        return [
            f"C5 {unit_id} carries an independent PASS with {len(notes)} chars of reviewer "
            f"notes (floor {MIN_REVIEW_NOTES}). A verdict with no reasoning behind it is a "
            f"stamp, not a review, and the verdict-shaped check could not tell them apart."
        ]
    if not _FALSIFICATION.search(notes):
        return [
            f"C5 {unit_id} reviewer notes name no falsification attempt -- no control, "
            f"mutation, counter-example or refutation. An independent reviewer who only "
            f"records agreement has not tested the claim (all 10 committed receipts do)."
        ]
    return []


def check_reviewed(basis: str, rows: list[dict]) -> tuple[int, list[str], int]:
    """C5: every same-vendor-satisfiable unit must already carry an independent reviewer PASS
    whose notes clear the content floor. Third return value is the ADVISORY anchor count."""
    blobs = (
        _vs.batch_blobs("HEAD", [r["output_path"] for r in rows])
        if basis == "committed"
        else {
            r["output_path"]: (REPO / r["output_path"]).read_text(encoding="utf-8")
            for r in rows
        }
    )
    reviewed, problems, anchored = 0, [], 0
    for r in rows:
        txt = blobs.get(r["output_path"])
        rec = json.loads(txt) if txt else {}
        rv = rec.get("reviewer") or {}
        if (
            str(rv.get("verdict", "")).upper() == "PASS"
            and rv.get("independent") is True
        ):
            reviewed += 1
        problems += review_problems(r["id"], rec)
        # ADVISORY, never blocking. Reported so the gap cannot stay invisible: measured 0 of 10
        # today, so making it blocking would fail every existing receipt at once (and the only
        # anchor-SHAPED token in the ten is a TIMESTAMP, `2026-08-12T05:15:00`).
        #
        # STALE, corrected: that sentence used to end "...which satisfies claim_gate's `\S+:\d+`
        # anchor rule -- a second reason not to enforce that shape here". claim_gate no longer has
        # that rule; it rejected the timestamp from round 1 and rejects `example.com:443` from
        # round 2. This check is unaffected either way, and deliberately so: `_ANCHOR` above is
        # only a SHAPE, and the `.exists()` test below is what decides, which is strictly stronger
        # than any shape rule -- a host:port cannot pass it because no such file exists.
        notes = rv.get("notes")
        for match in _ANCHOR.finditer(notes if isinstance(notes, str) else ""):
            path = match.group(1)
            if path is None or (REPO / path.replace("\\", "/")).exists():
                anchored += 1
                break
    return reviewed, problems, anchored


# --------------------------------------------------------------------------------------------
# both-states controls
# --------------------------------------------------------------------------------------------

GOOD_DOC = """# Cross-vendor review rail is DOWN -- and it gates 42 blocked units

<!-- RAIL-COUNT
basis: committed
blocked_units: 52
rail_blocked: 42
rail_blocked_unfulfilled: 39
rail_blocked_fulfilled: 3
satisfiable_now: 10
reviewed_satisfiable: 10
catalog_units: 2007
rail_state: down
rail_probed: 2026-08-12
derived_by: command-center/p2-next/vendor_satisfiability.py --basis committed
-->

42 of 52 blocked units wait on the rail. The other 10 units were reviewed on 2026-08-12 at
port 8812 with python 3.11.
39 units are still owed a cross-vendor review.
On the authoring box the dirty tree gave 41 units. [worktree-observed 2026-08-13]
The earlier census said 43 of 47 receipts. [superseded 2026-08-13]
"""


def _selftest() -> int:
    d = {
        "blocked_units": 52,
        "rail_blocked": 42,
        "rail_blocked_unfulfilled": 39,
        "rail_blocked_fulfilled": 3,
        "satisfiable_now": 10,
    }
    bad = 0

    def prose(doc: str) -> list[str]:
        return check_prose(doc, d, 2007, 10)[0]

    #: Counted, not asserted. The header used to hardcode "30 cases" and was already stale by
    #: the time this line was read -- the same rot the gate exists to catch in the doc.
    ran = [0, 0]  # [total, cases that expected a FIRE]

    def expect(label: str, problems: list[str], want_fire: bool) -> None:
        nonlocal bad
        ran[0] += 1
        ran[1] += 1 if want_fire else 0
        fired = bool(problems)
        if fired != want_fire:
            bad += 1
            print(
                f"FAILED:selftest [{label}] expected "
                f"{'FIRE' if want_fire else 'SILENCE'}, got {problems[:2] or 'SILENCE'}"
            )

    # C1 -- block present and correct, then each way it can be wrong.
    fields, probs = parse_block(GOOD_DOC)
    expect("C1 good block parses", probs, False)
    expect(
        "C1 good block matches", check_block(fields, d, 10, 2007, "committed"), False
    )
    expect("C1 missing block", parse_block("# no block here\n")[1], True)
    expect(
        "C1 partial block",
        parse_block("<!-- RAIL-COUNT\nbasis: committed\n-->")[1],
        True,
    )
    expect(
        "C1 stale field",
        check_block({**fields, "rail_blocked": "43"}, d, 10, 2007, "committed"),
        True,
    )
    expect(
        "C1 derived_by not naming the producer",
        check_block(
            {**fields, "derived_by": "a person, from memory"}, d, 10, 2007, "committed"
        ),
        True,
    )
    # The DEMAND-vs-UNMET field. Silence on the correct value is only meaningful next to a
    # fire on a wrong one and on its absence -- otherwise the field is declared and unchecked,
    # which is the shape the whole C5 content hole had.
    expect(
        "C1 rail_blocked_unfulfilled correct is silent",
        check_block(fields, d, 10, 2007, "committed"),
        False,
    )
    expect(
        "C1 rail_blocked_unfulfilled stale fires",
        check_block(
            {**fields, "rail_blocked_unfulfilled": "42"}, d, 10, 2007, "committed"
        ),
        True,
    )
    expect(
        "C1 rail_blocked_unfulfilled missing fires",
        parse_block(GOOD_DOC.replace("rail_blocked_unfulfilled: 39\n", ""))[1],
        True,
    )
    # C4 -- the subset invariant, both directions.
    expect("C4 unfulfilled within range is silent", plausibility(d), False)
    expect(
        "C4 unfulfilled above rail_blocked fires",
        plausibility({**d, "rail_blocked_unfulfilled": 43}),
        True,
    )
    expect(
        "C4 a dropped predicate reporting zero owed fires",
        plausibility({**d, "rail_blocked_unfulfilled": 0}),
        True,
    )
    expect(
        "C4 fulfilled + unfulfilled must partition rail_blocked",
        plausibility({**d, "rail_blocked_fulfilled": 7}),
        True,
    )

    # C2 -- the headline rot, both directions.
    expect("C2 good doc", prose(GOOD_DOC), False)
    expect(
        "C2 untagged stale count",
        prose(GOOD_DOC + "\nIt gates 43 blocked units.\n"),
        True,
    )
    expect(
        "C2 same count once marked superseded",
        prose(GOOD_DOC + "\nIt gated 43 blocked units. [superseded 2026-08-13]\n"),
        False,
    )
    # The escape is the MARKER, never the word "worktree". An earlier version accepted any number
    # matching a live worktree derivation on a line saying "worktree" -- which is true only on a
    # dirty tree and false in the clean clone CI checks out. Both directions are pinned here.
    expect(
        "C2 a worktree figure is NOT exempt just for saying worktree",
        prose(GOOD_DOC + "\nAgainst the worktree the rail gates 41 units.\n"),
        True,
    )
    expect(
        "C2 a worktree figure IS exempt once dated and marked",
        prose(
            GOOD_DOC
            + "\nAgainst the worktree the rail gated 41 units. [worktree-observed 2026-08-13]\n"
        ),
        False,
    )
    # ...and the two ways C2 could be inert rather than clean.
    expect(
        "C2 must ignore numbers that are not unit counts",
        prose(
            GOOD_DOC
            + "\nMeasured 2026-08-12 on port 8812 with python 3.11 across 99 files.\n"
        ),
        False,
    )
    expect(
        "C2 an exemption marker must not whitelist a whole doc",
        prose("[superseded]\nline two claims 43 units with no marker of its own.\n"),
        True,
    )
    # The MEASURED false positive: option numbers near a unit noun are not unit counts. This case
    # exists because the first version of COUNT_DIRECT flagged this exact sentence from the real
    # doc. Its partner below keeps the fix from degrading into "never fire on a nearby noun".
    expect(
        "C2 option numbers in a different clause are not unit counts",
        prose(
            "Option 2 would move some units but must not be silently substituted for option 1 "
            "on the receipts that demand cross-vendor.\n"
        ),
        False,
    )
    expect(
        "C2 still binds a real noun phrase (review-gated units)",
        prose("Until the rail is restored, the 43 review-gated units cannot move.\n"),
        True,
    )
    expect(
        "C2 still binds an 'N of the M' pair",
        prose("43 of the 47 BLOCKED Prompt Two receipts name a review gate.\n"),
        True,
    )
    # The MEASURED recall gap: a markdown table row keeps the unit noun in another cell, so a
    # window-bound pair pattern missed it. Its partner keeps the line-scoped fix from becoming a
    # bare "any N of M is a unit count" scan.
    expect(
        "C2 catches a table row whose unit noun sits in a later cell",
        prose("| 43 of 47 | this page | tag occurrences, not units |\n"),
        True,
    )
    expect(
        "C2 leaves an 'N of M' alone when the line names no unit noun",
        prose(
            "Checked 3 of 5 workflows and 2 of 7 hooks; ruff 0.15.17 on python 3.11.\n"
        ),
        False,
    )
    # Secondary-doc scoping, both directions. A citing status doc must be held to the rail number
    # on rail lines and left alone everywhere else, or the gate reaches past its evidence and
    # starts demanding markers on other lanes' unrelated counts.
    citing = (
        "5. The cross-vendor review rail is DOWN, and it gates 43 blocked units.\n"
        "- Two casualties in the adversarial build wave: 38 of 40 ADV units substantial.\n"
    )
    sp, _ = check_prose(citing, d, 2007, 10, 449, topic_only=True, where="secondary")
    expect("C2 secondary: a stale rail count on a rail line FIRES", sp, True)
    expect(
        "C2 secondary: an unrelated 38-of-40 count on a non-rail line is left alone",
        [p for p in sp if "38" in p or " 40" in p],
        False,
    )
    sp2, _ = check_prose(
        "5. The cross-vendor review rail is DOWN, and it gates 42 blocked units.\n"
        "- 449 READY units all name an independent cross-vendor reviewer.\n",
        d,
        2007,
        10,
        449,
        topic_only=True,
        where="secondary",
    )
    expect(
        "C2 secondary: corrected rail line plus a derived READY count is silent",
        sp2,
        False,
    )

    # C6 -- the rail VERDICT, in both directions. Every case below is drawn from a real line in
    # one of the two pages, because the defect this check exists for was a real sentence that a
    # green gate read and did not judge.
    good_fields, _ = parse_block(GOOD_DOC)
    declared_down, fp = check_state_fields(good_fields)
    expect("C6 a well-formed rail_state/rail_probed pair is silent", fp, False)
    expect(
        "C6 the fixture's own DOWN headline agrees with its declared DOWN",
        check_state_prose(GOOD_DOC, declared_down),
        False,
    )
    # THE MEASURED DEFECT, frozen: the citing page's sentence, verbatim, against an UP block.
    citing_stale = (
        "5. **The cross-vendor review rail is DOWN, and it gates 42 blocked units.** "
        "`codex --version` works.\n"
    )
    expect(
        "C6 a citing page asserting DOWN under an UP block FIRES",
        check_state_prose(citing_stale, "up", where="E2E-WAVE-STATUS.md"),
        True,
    )
    expect(
        "C6 the same line is exempt once dated and marked",
        check_state_prose(
            citing_stale.rstrip("\n") + " [superseded 2026-08-14]\n",
            "up",
            where="E2E-WAVE-STATUS.md",
        ),
        False,
    )
    # Precision, both directions. A retraction QUOTES the wording it retracts; that must not fire,
    # and the quote-stripper must not become a way to smuggle a live assertion past the check.
    expect(
        "C6 a quoted retracted headline is a mention, not an assertion",
        check_state_prose(
            '> ## *"Cross-vendor review rail is DOWN - and it gates 42 blocked units"*\n',
            "up",
        ),
        False,
    )
    expect(
        "C6 a bare assertion still fires on a line that also quotes something",
        check_state_prose(
            'Despite the "rail ANSWERS" title, the rail is DOWN for this lane.\n', "up"
        ),
        True,
    )
    # The measured false positive from `_k1_premise_scan.py`: a hypothetical is not an assertion.
    expect(
        "C6 'whether the rail is up or down' is a hypothetical, not a claim",
        check_state_prose(
            "It returns the identical SUCCESS whether the rail is up or down. That is a control "
            "that looks the same under both hypotheses.\n",
            "up",
        ),
        False,
    )
    expect(
        "C6 past-tense narration of the retracted verdict is not an assertion",
        check_state_prose(
            "The rail was pronounced down on one transport, and the rail was never down.\n",
            "up",
        ),
        False,
    )
    expect(
        "C6 an agreeing page is silent (the check is not 'DOWN is always wrong')",
        check_state_prose("The rail is DOWN and 39 units wait on it.\n", "down"),
        False,
    )
    expect(
        "C6 a bogus rail_state value fires",
        check_state_fields({**good_fields, "rail_state": "probably fine"})[1],
        True,
    )
    expect(
        "C6 an undated rail_probed fires",
        check_state_fields({**good_fields, "rail_probed": "recently"})[1],
        True,
    )
    expect(
        "C6 a missing rail_state is caught by C1 rather than passing quietly",
        parse_block(GOOD_DOC.replace("rail_state: down\n", ""))[1],
        True,
    )
    expect(
        "C6 with no declared state the prose check judges nothing (C1 owns that failure)",
        check_state_prose(citing_stale, ""),
        False,
    )

    # C4 -- an empty/implausible derivation must be loud, not vacuously clean.
    expect("C4 plausible", plausibility(d), False)
    expect("C4 collapsed population", plausibility({**d, "blocked_units": 0}), True)

    # C5 -- the content floor. THE HEADER OF THIS FILE CLAIMED "every check in both states" while
    # C5 had NO self-test case at all, which is how a verdict-shaped check survived: emptying every
    # reviewer note across all ten units left it silent (`_g3_c5_content_probe.py`, whose control
    # flipped a verdict and DID fire, so the silence was real and not a dead probe). These are that
    # missing case, in both directions.
    def receipt(**rv: object) -> dict:
        base: dict = {
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-derived the split from the committed blobs with a separate reader, then "
                "ran a control in both states: flipping the verdict makes the check fire, so "
                "silence on the unmutated receipt is informative rather than dead. "
            )
            * 2,
        }
        base.update(rv)
        return {"reviewer": base}

    expect("C5 a real receipt is silent", review_problems("U-1", receipt()), False)
    expect(
        "C5 a FAIL verdict fires", review_problems("U-1", receipt(verdict="FAIL")), True
    )
    expect(
        "C5 a non-independent PASS fires",
        review_problems("U-1", receipt(independent=False)),
        True,
    )
    # THE MEASURED GAP: this exact mutation left the pre-round check silent on all ten units.
    expect("C5 emptied notes fire", review_problems("U-1", receipt(notes="")), True)
    expect(
        "C5 a stub note under the floor fires",
        review_problems("U-1", receipt(notes="LGTM, reviewed independently.")),
        True,
    )
    # ...and the way the floor itself could be inert rather than clean: length alone is satisfied
    # by padding, so a long note that never tried to break anything must still fire.
    expect(
        "C5 a long note naming no falsification fires",
        review_problems(
            "U-1", receipt(notes="I read the unit and I agree with it. " * 12)
        ),
        True,
    )
    # ...and the FALSE-POSITIVE direction, which is what the ~5x margin under the observed
    # 1027-char minimum exists for: a terse but genuine review must NOT be blocked.
    expect(
        "C5 a terse-but-real review just over the floor passes",
        review_problems(
            "U-1",
            receipt(
                notes=(
                    "Read the receipt and the produced artifact, then tried to break the "
                    "claim by re-running the producer against the committed blob rather "
                    "than the worktree; the counter-example I went looking for did not "
                    "appear, so the narrower claim stands."
                )
            ),
        ),
        False,
    )

    print(
        f"  selftest: {'PASS' if not bad else 'FAIL'} ({ran[0]} cases, {ran[1]} of them "
        f"expecting a FIRE, every check in both states)"
    )
    #: A suite of only-silent cases proves the instrument runs, not that it discriminates.
    if ran[1] == 0 or ran[1] == ran[0]:
        print("FAILED:selftest cases are one-sided; this suite cannot discriminate")
        bad += 1
    return bad


def plausibility(derived: dict[str, int]) -> list[str]:
    if derived["blocked_units"] < MIN_BLOCKED:
        return [
            f"C4 derivation returned only {derived['blocked_units']} blocked units (floor "
            f"{MIN_BLOCKED}). The catalog or the resolver changed shape; every other check in "
            f"this gate would pass vacuously, so it fails closed instead."
        ]
    if derived["rail_blocked"] + derived["satisfiable_now"] != derived["blocked_units"]:
        return [
            "C4 verdict counts do not sum to the population -- resolver shape change"
        ]
    #: Unfulfilled is a SUBSET of rail-blocked by construction. If the producer ever stops
    #: emitting `still_needs_cross_vendor`, `counts_at` sums zero and this reads as "the
    #: whole queue is already served" -- the most flattering possible wrong answer, and the
    #: one an owner would act on. Fail closed on both ends rather than publish it.
    if not 0 <= derived["rail_blocked_unfulfilled"] <= derived["rail_blocked"]:
        return [
            f"C4 rail_blocked_unfulfilled={derived['rail_blocked_unfulfilled']} is outside "
            f"0..rail_blocked={derived['rail_blocked']} -- the producer changed shape"
        ]
    if (
        derived["rail_blocked_unfulfilled"] + derived["rail_blocked_fulfilled"]
        != derived["rail_blocked"]
    ):
        return [
            f"C4 fulfilled({derived['rail_blocked_fulfilled']}) + "
            f"unfulfilled({derived['rail_blocked_unfulfilled']}) != "
            f"rail_blocked({derived['rail_blocked']}) -- the split does not partition"
        ]
    if derived["rail_blocked"] and not derived["rail_blocked_unfulfilled"]:
        return [
            "C4 every rail-blocked unit reports as already fulfilled. That is either the end "
            "of the queue or a dropped field; it fails closed so a missing predicate cannot "
            "publish itself as completion"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--basis", choices=("committed", "worktree"), default="committed")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--doc", help="judge this file instead of the tracked doc (red-proof)"
    )
    args = ap.parse_args(argv)

    if args.self_test:
        if _selftest():
            print("FAILED:rail-count-gate self-test did not discriminate")
            return 1
        print("SUCCESS:rail-count-gate self-test")
        return 0

    derived = counts_at(args.basis)
    problems = plausibility(derived)
    if problems:  # C4 fails closed before anything else is allowed to look clean
        print(f"FAILED:rail-count-gate {problems}")
        return 1

    cat_txt = _vs.batch_blobs("HEAD", [_vs.CATALOG_REL])[_vs.CATALOG_REL]
    catalog_units = len(json.loads(cat_txt)["work_units"]) if cat_txt else -1

    sat_rows = satisfiable_rows(args.basis)
    reviewed, problems, anchored = check_reviewed(args.basis, sat_rows)

    if args.doc:
        doc = Path(args.doc).read_text(encoding="utf-8")
        where = args.doc
    else:
        doc = read_text(args.basis, DOC_REL)
        where = f"{DOC_REL} @ {args.basis}"
    if doc is None:
        print(f"FAILED:rail-count-gate {DOC_REL} absent at basis={args.basis}")
        return 1

    fields, block_problems = parse_block(doc)
    problems += block_problems
    declared_state = ""
    if fields:
        problems += check_block(fields, derived, reviewed, catalog_units, args.basis)
        declared_state, state_problems = check_state_fields(fields)
        problems += state_problems
        problems += check_state_prose(doc, declared_state)
    # `ready_units` is an INT at HEAD and a LIST in a sibling lane's uncommitted rewrite of the
    # same file -- measured, as a TypeError, the first time this ran on the worktree basis. Accept
    # both shapes rather than assuming one; -1 means "not derivable", which can never match a
    # printed count and so never silently widens the allowed set.
    ready_txt = read_text(args.basis, READY_REL)
    ready = -1
    if ready_txt:
        raw = json.loads(ready_txt).get("ready_units")
        ready = (
            raw if isinstance(raw, int) else (len(raw) if isinstance(raw, list) else -1)
        )

    prose_problems, exempted = check_prose(doc, derived, catalog_units, reviewed, ready)
    problems += prose_problems
    problems += check_artifact(args.basis, derived)

    # Documents that CITE the number without owning it. Skipped entirely when --doc is used,
    # because that mode is judging one file on purpose.
    secondary_claims = 0
    state_claims = len(state_assertions(doc))
    if not args.doc:
        for rel in SECONDARY_DOCS:
            txt = read_text(args.basis, rel)
            if txt is None:
                problems.append(f"C2 secondary doc {rel} absent at basis={args.basis}")
                continue
            sp, sx = check_prose(
                txt, derived, catalog_units, reviewed, ready, topic_only=True, where=rel
            )
            problems += sp
            exempted += sx
            secondary_claims += sum(
                1 for _, line, _ in prose_claims(txt) if RAIL_TOPIC.search(line)
            )
            # C6. The count in a citing sentence can be right while the VERDICT around it is the
            # one this lane retracted -- measured, and green for a full round.
            problems += check_state_prose(txt, declared_state, where=rel)
            state_claims += len(state_assertions(txt))

    print(f"  basis={args.basis}  doc={where}")
    print(
        f"  FRESH DERIVATION: {derived['blocked_units']} blocked units, "
        f"{derived['rail_blocked']} rail-blocked "
        f"({derived['rail_blocked_unfulfilled']} still owed a cross-vendor review, "
        f"{derived['rail_blocked_fulfilled']} already served), "
        f"{derived['satisfiable_now']} satisfiable now, "
        f"{reviewed} of those reviewed; catalog carries {catalog_units} units, "
        f"{ready} of them READY"
    )
    print(
        f"  unit-count claims examined: {len(prose_claims(doc))} in the owning doc + "
        f"{secondary_claims} on-topic in {len(SECONDARY_DOCS)} citing doc(s); "
        f"{exempted} exempted by an explicit dated marker"
    )
    print(
        f"  C6 rail verdict: the block declares {(declared_state or '?').upper()} probed "
        f"{fields.get('rail_probed', '?')}; {state_claims} rail-state assertion(s) across "
        f"{1 + (0 if args.doc else len(SECONDARY_DOCS))} page(s) checked for agreement. "
        f"CONSISTENCY ONLY -- this gate calls nothing, so its silence never means the rail answers."
    )
    print(
        f"  C5 content floor: {len(sat_rows)} satisfiable receipts checked against "
        f"{MIN_REVIEW_NOTES}-char notes + a named falsification method. "
        f"ADVISORY (not blocking): {anchored} of {len(sat_rows)} carry a RESOLVING "
        f"file:line/URL evidence anchor."
    )

    if problems:
        for p in problems:
            print(f"  {p}")
        print(f"FAILED:rail-count-gate {len(problems)} problem(s)")
        return 1
    print("SUCCESS:rail-count-gate the published number equals a fresh derivation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
