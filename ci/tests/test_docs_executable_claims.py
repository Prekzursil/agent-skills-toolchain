#!/usr/bin/env python3
"""Executable-claim gate for the repo's front-door doc (``README.md``).

WHY THIS EXISTS
---------------
Measured 2026-08-12 on this tree, every one of these was live and committed:

* ``README.md`` advertised ``skills/`` as holding **158** skills. ``git ls-files``
  counts **337** ``skills/<name>/SKILL.md``, corroborated independently by
  ``python ci/gen_skills_manifest.py --check`` printing ``skills_tracked=337``
  and by ``.agents/skills`` (346 canonical) minus the 9 canonical-only wrappers
  README itself documents.
* the scholarly-access quick-start comment claimed **22** offline policy tests;
  ``pytest tests/test_policy.py --collect-only -q`` collects **24**.
* the Windows config-snapshot row claimed Codex 41 / Claude 40 MCP servers; the
  committed snapshots declare **40** and **39**.

The same drift was already recorded on 2026-07-18 in the harness-sota corpus
(``harness-sota-2026-07-18-corpus/P1C06.md``, finding P1C06-A21-F5: "README
counts and manifest freshness metadata contradict the measured tree") and was
still there three weeks later, because nothing ever executed the claims. Prose
that asserts a number rots silently; a number a gate recomputes cannot.

A SECOND ROT MECHANISM, ADDED IN ROUND 2
----------------------------------------
Numbers are not the only claim that rots. ``README.md`` carried
``> **Latest (2026-06-10):** ...`` -- a hand-maintained currency banner -- while
line 38 of the SAME file documented a 2026-08-09 event and the file's own last
commit was 2026-08-12. A banner that says "latest" is a claim about the
document, so ``currency_violations`` recomputes it: any ``**Latest (DATE)**``
marker must carry the newest ISO date in the file, or it is stale by
construction. Measured precision over the 160 tracked ``.md`` files in
``docs/`` + ``README.md`` + ``AGENTS.md`` + ``CLAUDE.md``: **1 hit, 1 true
positive, 0 false positives** -- the defect itself.

Disclosed inline, because it is the difference between a live check and a
tripwire: the fix REMOVED the banner rather than re-dating it (git is the
changelog; a hand-maintained "latest" line is the rot mechanism). So on the
shipped file this arm currently has no marker to compare and is a
REINTRODUCTION tripwire. Its discriminating power is not assumed -- it is
proven on real committed bytes by ``docs/_lane_docs_bothstates_probe.py``,
which replays README blob ``6c8b0138`` (the pre-round-2 state, banner present)
and requires the arm to fire there, plus an in-suite injected-marker control
here.

WHAT THIS GATE DELIBERATELY DOES NOT DO
---------------------------------------
It does not lint prose for dead PATH mentions. Measured on this corpus: 249 raw
path references, 204 pointing at something absent, 29 of those in live
non-archive docs -- and **0** genuine broken promises, because every one sits
inside an explicit "deleted / retired / closed / does not exist" sentence or
names an out-of-repo path. A dead-path linter here would be ~100% false
positive. Only claims a machine can EXECUTE or COUNT are gated.

It also does not lint for decapitated sections (a paragraph that opens with a
lowercase word, the shape left behind when commit 49ca83f7 deleted whole lines
during a terminology scrub and beheaded the Scholarly Access section). That
detector was BUILT and MEASURED before being rejected: 29 hits across 14 of the
same 160 files, of which the README's own three are 2 true positives and 1 false
positive (line 316 is a deliberate sentence that resumes after a list). ~17%
tree-wide precision is a linter that trains people to ignore it, so the two real
instances were fixed by hand and no gate was shipped.

WHERE IT RUNS
-------------
Two workflows, on purpose, because one of them was demonstrably not enough.

``.github/workflows/skill-dual-write.yml`` collects ``ci/tests`` as a DIRECTORY
(``python -m pytest ci/tests tools/d001-dual-write/tests -q``), so this suite
runs there with no named step -- but that workflow's ``on:`` block holds exactly
one event key, ``pull_request``. Every commit in this program lands by pushing
``main`` directly, so for its first day this gate executed on ZERO of the
commits that shipped it. Its silence meant "never invoked", not "the docs agree
with the tree" -- which is the same defect class the suite itself exists to
catch, one level up.

``quality.yml`` is the workflow carrying ``push: branches: [main]``. It has no
tree-wide ``ci/tests`` step -- it names its suites one at a time -- so it now
names this one: ``gate-tests-coverage docs executable claims (README +
roadmap)``, in the ``test-python`` job, immediately ABOVE the ``setup python
3.12`` pivot (that action repoints the default ``python``, and this step uses a
bare one). ``ci/tests/test_docs_gate_ci_wiring.py`` pins that step -- its name,
both run lines, its containing job, the push-to-main trigger and that ordering
constraint -- and lives in ``ci/tests/`` itself, so deleting the step turns
skill-dual-write.yml red on the next pull request instead of silently
un-wiring this gate.

Residual, disclosed rather than closed: a direct push to ``main`` that deletes
BOTH the ``quality.yml`` step and the wiring suite is caught by nothing, because
skill-dual-write.yml has no ``push:`` trigger either. Settling experiment (owner
action, it widens a shared workflow's blast radius): give skill-dual-write.yml a
``push: branches: [main]`` trigger and confirm its D-001 diff gate still behaves
when ``--base origin/main --head HEAD`` spans an empty range.

DEPENDENCY BUDGET, AND THE PROBE THAT WAS REJECTED
--------------------------------------------------
stdlib + pytest only, and proven: in a venv holding nothing but pytest 8.4.2,
``python -m pytest tests/test_policy.py --collect-only -q`` inside
``tools/scholarly-access-mcp`` collects 24 and exits 0 (``scholarly_access``
imports nothing at package level and ``policy`` imports only ``urllib.parse``).

``list_tools.py`` is NOT the oracle for the tool-surface claim even though it
prints exactly the number README advertises. It imports
``scholarly_access.server``, which needs the third-party ``mcp`` package, and it
dies with ``ModuleNotFoundError`` in that bare venv -- so using it would have
red-blocked the runner. The tool count and names come from the ``@mcp.tool()``
decorators via ``ast`` instead.

COUPLING THIS ACCEPTS
---------------------
Adding a skill now also means bumping two README numbers. That is the same
contract ``ci/gen_skills_manifest.py --check`` already imposes (it demands the
manifest be regenerated byte-for-byte on every skill add), so the convention is
pre-existing rather than new.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap.md"
SCHOLARLY = REPO_ROOT / "tools" / "scholarly-access-mcp"
RELEASE_WINDOWS = REPO_ROOT / "release" / "platforms" / "windows"

# Surface -> how the count is derived. Every entry is measured from tracked
# files, never from another document.
SURFACE_FILE_PATTERNS = {
    "skills/": r"skills/[^/]+/SKILL\.md",
    "skills-claude-only/": r"skills-claude-only/[^/]+/SKILL\.md",
    "tools/lib/": r"tools/lib/[^/]+\.mjs",
    "release/platforms/windows/": r"release/platforms/windows/[^/]+",
}
SURFACE_SUBDIRS = ("tools/mcp/", "tools/web/", "tools/editor/")

# Fail-closed plausibility floors. A pathspec or repo-shape change that makes a
# measurement collapse to 0 must be LOUD, not silently agree with a zeroed doc.
# (The manifest-DICT trap: four probes once reported "3 and 3" on both sides
# because they counted the wrong collection, and all four agreed and were wrong.)
PLAUSIBILITY_FLOORS = {
    "skills/": 100,
    "skills-claude-only/": 10,
    "tools/mcp/": 10,
    "tools/lib/": 3,
    "tools/editor/": 2,
    "release/platforms/windows/": 5,
}

SNAPSHOT_SOURCES = {
    "Codex": ("codex-config.toml", "mcp_servers"),
    "Claude": ("claude-config.json", "mcpServers"),
    "Gemini": ("gemini-settings.json", "mcpServers"),
}

_SNAPSHOT_CLAIM = re.compile(
    r"Codex \((\d+) MCPs\), Claude \((\d+) MCPs\), Gemini \((\d+) MCPs\)"
)
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_CURRENCY_MARKER = re.compile(
    r"\*\*(Latest|Current|Now|As of|Updated)\s*\((\d{4}-\d{2}-\d{2})\)"
)
_SPLIT_CLAIM = re.compile(r"\((\d+) shared \+ (\d+) Claude-only\)")
_POLICY_CLAIM = re.compile(r"#\s*(\d+) offline policy/gate tests")
# ``\r?\n``, not ``\n``. Measured 2026-08-13: the working tree of README.md on
# Windows holds 328 CR bytes while the stored blob holds 0 (windows-shell 8b).
# Anything that hands this regex the RAW bytes -- a probe reading with
# ``newline=""``, a tool reading the worktree instead of the blob -- got
# ``tools-missing`` on a README whose claim was present and correct. It fails
# loud rather than silent, so it was never a false green, but a gate that
# reports a defect that is not there is still a broken gate.
_TOOLS_CLAIM = re.compile(r"^(\d+) tools: (.*?)\.\r?\n", re.MULTILINE | re.DOTALL)


# --------------------------------------------------------------------------
# measurement (reality side)
# --------------------------------------------------------------------------
def _git_ls(pathspec: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", pathspec],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [p for p in proc.stdout.split("\0") if p]


def measured_surface_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for surface, pattern in SURFACE_FILE_PATTERNS.items():
        rx = re.compile(pattern)
        counts[surface] = sum(1 for p in _git_ls(surface) if rx.fullmatch(p))
    for surface in SURFACE_SUBDIRS:
        seen: set[str] = set()
        for path in _git_ls(surface):
            rest = path[len(surface) :]
            if "/" in rest:
                seen.add(rest.split("/", 1)[0])
        counts[surface] = len(seen)
    return counts


def measured_snapshot_mcp_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for platform, (filename, key) in SNAPSHOT_SOURCES.items():
        raw = (RELEASE_WINDOWS / filename).read_bytes()
        parsed = (
            tomllib.loads(raw.decode("utf-8"))
            if filename.endswith(".toml")
            else json.loads(raw)
        )
        servers = parsed.get(key)
        assert isinstance(servers, dict), f"{filename}: {key} is not a table/object"
        counts[platform] = len(servers)
    return counts


def measured_tool_names() -> list[str]:
    """Names of ``@mcp.tool()``-decorated functions in the MCP server source."""
    tree = ast.parse(
        (SCHOLARLY / "scholarly_access" / "server.py").read_text(encoding="utf-8")
    )
    names: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Attribute) and target.attr == "tool":
                names.append(node.name)
                break
    return names


def collected_policy_tests() -> int:
    """EXECUTE the collector. Not a read of a number someone wrote down."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_policy.py",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=SCHOLARLY,
        capture_output=True,
        text=True,
        timeout=600,
    )
    match = re.search(r"^(\d+) tests? collected", proc.stdout, re.MULTILINE)
    assert proc.returncode == 0 and match is not None, (
        "the collection probe itself failed, so its silence proves nothing "
        f"(exit={proc.returncode})\n--- stdout ---\n{proc.stdout[-2000:]}\n"
        f"--- stderr ---\n{proc.stderr[-2000:]}"
    )
    return int(match.group(1))


# --------------------------------------------------------------------------
# claim parsing + comparison (pure, so a mutated doc can be fed to it)
# --------------------------------------------------------------------------
def claimed_surface_count(readme: str, surface: str) -> int | None:
    match = re.search(
        rf"^\|\s*`{re.escape(surface)}`\s*\|\s*(\d+)\s*\|", readme, re.MULTILINE
    )
    return int(match.group(1)) if match else None


def claimed_tools(readme: str) -> tuple[int | None, list[str]]:
    match = _TOOLS_CLAIM.search(readme)
    if match is None:
        return None, []
    return int(match.group(1)), re.findall(r"`([a-z_]+)`", match.group(2))


def currency_violations(readme: str) -> list[str]:
    """A ``**Latest (DATE)**`` banner must carry the newest date in the document.

    Pure and text-only on purpose: no ``git log``. CI checks out at
    ``fetch-depth: 1``, so a commit-date oracle would be unavailable there and
    the check would degrade to "no history, therefore clean" -- a gate that
    passes because it cannot measure. Self-consistency needs no history: if the
    same file already talks about a later date, the banner is stale by its own
    evidence.
    """
    dates = _ISO_DATE.findall(readme)
    if not dates:
        return []
    newest = max(dates)
    return [
        f"stale-currency: '{word} ({claimed})' but this file already documents {newest}"
        for word, claimed in _CURRENCY_MARKER.findall(readme)
        if claimed < newest
    ]


def readme_violations(
    readme: str,
    surfaces: Mapping[str, int],
    snapshots: Mapping[str, int],
    policy_tests: int,
    tool_names: Sequence[str],
) -> list[str]:
    """Every disagreement between README's claims and the measured tree.

    A claim that cannot be FOUND is a violation too: a refactor that deletes the
    row must fail loudly rather than leave a gate quietly measuring nothing.
    """
    bad: list[str] = []

    for surface, measured in surfaces.items():
        claimed = claimed_surface_count(readme, surface)
        if claimed is None:
            bad.append(f"surface-row-missing: no `{surface}` count row in README")
        elif claimed != measured:
            bad.append(
                f"surface-count: `{surface}` claims {claimed}, measured {measured}"
            )

    split = _SPLIT_CLAIM.search(readme)
    if split is None:
        bad.append("split-missing: no '(N shared + M Claude-only)' claim in README")
    else:
        shared, claude_only = int(split.group(1)), int(split.group(2))
        if shared != surfaces["skills/"]:
            bad.append(f"split-shared: claims {shared}, measured {surfaces['skills/']}")
        if claude_only != surfaces["skills-claude-only/"]:
            bad.append(
                f"split-claude-only: claims {claude_only}, "
                f"measured {surfaces['skills-claude-only/']}"
            )

    snap = _SNAPSHOT_CLAIM.search(readme)
    if snap is None:
        bad.append(
            "snapshot-missing: no 'Codex (N MCPs), Claude (N MCPs), Gemini (N MCPs)' claim"
        )
    else:
        for platform, claimed_raw in zip(("Codex", "Claude", "Gemini"), snap.groups()):
            if int(claimed_raw) != snapshots[platform]:
                bad.append(
                    f"snapshot-mcps: {platform} claims {claimed_raw}, "
                    f"measured {snapshots[platform]}"
                )

    policy = _POLICY_CLAIM.search(readme)
    if policy is None:
        bad.append("policy-missing: no 'N offline policy/gate tests' claim in README")
    elif int(policy.group(1)) != policy_tests:
        bad.append(
            f"policy-tests: claims {policy.group(1)}, collector reports {policy_tests}"
        )

    claimed_count, claimed_names = claimed_tools(readme)
    if claimed_count is None:
        bad.append("tools-missing: no 'N tools: ...' claim in README")
    else:
        if claimed_count != len(tool_names):
            bad.append(
                f"tool-count: claims {claimed_count}, source declares {len(tool_names)}"
            )
        if sorted(claimed_names) != sorted(tool_names):
            bad.append(
                f"tool-names: README {sorted(claimed_names)} != source {sorted(tool_names)}"
            )
    return bad


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def surfaces() -> dict[str, int]:
    return measured_surface_counts()


@pytest.fixture(scope="module")
def snapshots() -> dict[str, int]:
    return measured_snapshot_mcp_counts()


@pytest.fixture(scope="module")
def policy_tests() -> int:
    return collected_policy_tests()


@pytest.fixture(scope="module")
def tool_names() -> list[str]:
    return measured_tool_names()


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------
def test_measurements_are_plausible(surfaces: dict[str, int]) -> None:
    """Detector integrity BEFORE the comparison: a collapsed count is loud."""
    for surface, floor in PLAUSIBILITY_FLOORS.items():
        assert surfaces[surface] >= floor, (
            f"{surface} measured {surfaces[surface]}, below the plausibility floor "
            f"{floor}. Fix the measurement, do not 'agree' with the doc."
        )
    assert surfaces["tools/web/"] == 0, (
        "tools/web/ is documented as a reserved, empty surface; it now has "
        f"{surfaces['tools/web/']} project(s), so README and docs/roadmap.md need updating"
    )


def test_policy_collector_actually_ran(policy_tests: int) -> None:
    assert policy_tests > 0, "the collector reported zero tests; that is a broken probe"


def test_tool_decorators_actually_found(tool_names: list[str]) -> None:
    assert len(tool_names) >= 5, f"AST found only {tool_names!r} @mcp.tool functions"


def test_readme_claims_match_measured_reality(
    readme: str,
    surfaces: dict[str, int],
    snapshots: dict[str, int],
    policy_tests: int,
    tool_names: list[str],
) -> None:
    violations = readme_violations(
        readme, surfaces, snapshots, policy_tests, tool_names
    )
    assert violations == [], (
        "README asserts numbers the tree contradicts:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_gate_is_line_ending_agnostic(
    readme: str,
    surfaces: dict[str, int],
    snapshots: dict[str, int],
    policy_tests: int,
    tool_names: list[str],
) -> None:
    """CRLF and LF forms of the same README must score identically.

    The blob is LF, a Windows working tree is CRLF, and CI checks out the LF
    form -- so a claim verified locally can be measured against different bytes
    than the ones CI reads (windows-shell 8b). This is not hypothetical here:
    ``_TOOLS_CLAIM`` ended in ``\\.\\n`` and reported ``tools-missing`` on the
    raw CRLF bytes of a README whose claim was present and correct.
    """
    lf = readme.replace("\r\n", "\n")
    crlf = lf.replace("\n", "\r\n")
    assert "\r\n" in crlf, "control precondition: the CRLF form has no CRLF"

    args = (surfaces, snapshots, policy_tests, tool_names)
    assert readme_violations(lf, *args) == readme_violations(crlf, *args), (
        "readme_violations disagrees between the LF and CRLF forms of the same "
        "document, so a local green does not imply a CI green"
    )
    assert currency_violations(lf) == currency_violations(crlf)


def test_currency_arm_has_something_to_measure(readme: str) -> None:
    """Fail-closed floor for the currency arm.

    ``currency_violations`` returns ``[]`` when the document contains no ISO
    date at all -- indistinguishable from "clean". Assert the input the arm
    depends on actually exists, so the arm can never pass by measuring nothing.

    The blind spot is PROVEN below rather than asserted, so the floor is
    visibly load-bearing instead of decorative. Honest limit, disclosed: the
    numeric threshold itself is not mutation-testable while the live README
    carries several dates -- ``>= 1`` and ``>= 0`` score the same on this
    input. That is inherent to a fail-closed floor (``PLAUSIBILITY_FLOORS`` has
    the same property) and is why the fail-closed BRANCH is mutation-tested
    instead, in ``docs/_lane_docs_r2_mutation_control.py``.
    """
    assert currency_violations("no dated events in this document at all") == [], (
        "the arm must return clean, not crash, on a dateless document -- this "
        "is the blind spot the floor below exists to guard"
    )
    dates = _ISO_DATE.findall(readme)
    assert len(dates) >= 1, (
        "README contains no ISO date, so the stale-banner arm has no baseline "
        "and would report clean regardless of what the file says"
    )


def test_readme_has_no_stale_currency_banner(readme: str) -> None:
    violations = currency_violations(readme)
    assert violations == [], (
        "README carries a currency banner older than its own newest dated "
        "event:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_control_currency_arm_distinguishes_stale_from_current(readme: str) -> None:
    """Two-hypothesis control: STALE must fire, CURRENT must not.

    A control that only proves "a marker was seen" would pass under both
    hypotheses and measure nothing but readability. This one is built from the
    file's own newest date, so it keeps discriminating as the README changes.
    """
    newest = max(_ISO_DATE.findall(readme))
    older = f"{int(newest[:4]) - 1}{newest[4:]}"

    stale = f"> **Latest ({older}):** injected control banner.\n\n{readme}"
    fired = currency_violations(stale)
    assert any("stale-currency" in v for v in fired), (
        f"control: the arm stayed silent on a banner dated {older} while the "
        f"document documents {newest}; violations were {fired!r}"
    )

    current = f"> **Latest ({newest}):** injected control banner.\n\n{readme}"
    assert currency_violations(current) == [], (
        "control: the arm fired on a banner carrying the newest date, so it "
        "flags the marker rather than its staleness"
    )

    for word in ("Current", "Updated", "As of"):
        variant = f"> **{word} ({older}):** injected control banner.\n\n{readme}"
        assert currency_violations(variant), f"control: '{word}' variant not covered"


def _mutate(readme: str, old: str, new: str) -> str:
    assert old in readme, f"control precondition failed: {old!r} not in README"
    return readme.replace(old, new, 1)


def test_control_gate_fires_on_every_stale_number(
    readme: str,
    surfaces: dict[str, int],
    snapshots: dict[str, int],
    policy_tests: int,
    tool_names: list[str],
) -> None:
    """Both-states control: each claim, individually falsified, must be caught.

    A probe that is silent in the broken state measures nothing. These mutations
    are built from the MEASURED values, so they keep working as the tree grows.
    """
    mutations: list[tuple[str, str, str, str]] = [
        (
            "surface-count",
            f"| `skills/` | {surfaces['skills/']} |",
            f"| `skills/` | {surfaces['skills/'] + 1} |",
            "`skills/` claims",
        ),
        (
            "split-shared",
            f"({surfaces['skills/']} shared + {surfaces['skills-claude-only/']} Claude-only)",
            f"({surfaces['skills/'] + 1} shared + {surfaces['skills-claude-only/']} Claude-only)",
            "split-shared",
        ),
        (
            "snapshot-mcps",
            f"Codex ({snapshots['Codex']} MCPs)",
            f"Codex ({snapshots['Codex'] + 1} MCPs)",
            "snapshot-mcps: Codex",
        ),
        (
            "policy-tests",
            f"# {policy_tests} offline policy/gate tests",
            f"# {policy_tests + 1} offline policy/gate tests",
            "policy-tests",
        ),
        (
            "tool-count",
            f"{len(tool_names)} tools: ",
            f"{len(tool_names) + 1} tools: ",
            "tool-count",
        ),
        (
            "tool-names",
            f"`{tool_names[0]}`",
            "`paper_nonexistent_tool`",
            "tool-names",
        ),
    ]
    for label, old, new, expected_substring in mutations:
        broken = _mutate(readme, old, new)
        found = readme_violations(broken, surfaces, snapshots, policy_tests, tool_names)
        assert any(expected_substring in v for v in found), (
            f"control {label}: the gate stayed silent on a falsified claim "
            f"(mutation {old!r} -> {new!r}); violations were {found!r}"
        )


def test_control_gate_fires_when_a_claim_is_deleted(
    readme: str,
    surfaces: dict[str, int],
    snapshots: dict[str, int],
    policy_tests: int,
    tool_names: list[str],
) -> None:
    """Deleting a claim must FAIL, not silently pass with nothing to compare."""
    stripped = _POLICY_CLAIM.sub("# tests", readme)
    found = readme_violations(stripped, surfaces, snapshots, policy_tests, tool_names)
    assert any("policy-missing" in v for v in found), (
        f"a deleted claim left the gate silent; violations were {found!r}"
    )

    row = f"| `skills/` | {surfaces['skills/']} |"
    without_row = _mutate(readme, row, "| `skills/` | many |")
    found = readme_violations(
        without_row, surfaces, snapshots, policy_tests, tool_names
    )
    assert any("surface-row-missing" in v for v in found), (
        f"an unparseable count row left the gate silent; violations were {found!r}"
    )


# --------------------------------------------------------------------------
# docs/roadmap.md: the skill-root projection claim
#
# Added round 3 after this lane's OWN round-1 edit was refuted. That edit called
# ``skills/`` "the generated projection of ``.agents/skills/``", said
# ``--strict-parity`` "holds the two in lockstep", and concluded it is "a
# permanent surface, not a temporary compatibility layer". It was written from a
# ONE-DIRECTIONAL count (how many names ``skills/`` has). Measured in BOTH
# directions the roots each hold names the other lacks, so a projection claim is
# false and the lockstep claim misreads the guard, whose own docstring says it is
# "intentionally a DIFF guard, not a tree-parity guard".
#
# The arm therefore pins the two ONE-SIDED counts -- not the shared count, which
# would change on every ordinary dual-written skill add and buy nothing: the
# claim only becomes wrong when a name is one-sided.
# --------------------------------------------------------------------------
_PROJECTION_CLAIM = re.compile(
    r"(\d+)\s+skill names live only in\s+`skills/`"
    r"\s+and\s+(\d+)\s+only in\s+`\.agents/skills/`"
)


def measured_skill_root_divergence() -> dict[str, int]:
    """Names present in exactly one skill root, measured in BOTH directions."""
    proj = {
        m.group(1)
        for f in _git_ls("skills")
        if (m := re.fullmatch(r"skills/([^/]+)/SKILL\.md", f))
    }
    canon = {
        m.group(1)
        for f in _git_ls(".agents/skills")
        if (m := re.fullmatch(r"\.agents/skills/([^/]+)/SKILL\.md", f))
    }
    return {
        "only_projection": len(proj - canon),
        "only_canonical": len(canon - proj),
        "projection_total": len(proj),
        "canonical_total": len(canon),
    }


def roadmap_violations(roadmap: str, divergence: Mapping[str, int]) -> list[str]:
    """Compare docs/roadmap.md's projection claim against the measured tree."""
    bad: list[str] = []
    match = _PROJECTION_CLAIM.search(roadmap)
    if match is None:
        bad.append(
            "projection-claim-missing: docs/roadmap.md no longer states how many "
            "skill names are one-sided. It must, while the roots diverge: "
            f"measured only-in-skills/={divergence['only_projection']}, "
            f"only-in-.agents/skills/={divergence['only_canonical']}."
        )
        return bad

    claimed_proj, claimed_canon = int(match.group(1)), int(match.group(2))
    if claimed_proj != divergence["only_projection"]:
        bad.append(
            f"projection-divergence: roadmap claims {claimed_proj} name(s) only in "
            f"`skills/`, measured {divergence['only_projection']}"
        )
    if claimed_canon != divergence["only_canonical"]:
        bad.append(
            f"canonical-divergence: roadmap claims {claimed_canon} name(s) only in "
            f"`.agents/skills/`, measured {divergence['only_canonical']}"
        )
    return bad


@pytest.fixture(scope="module")
def roadmap() -> str:
    return ROADMAP_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def divergence() -> dict[str, int]:
    return measured_skill_root_divergence()


def test_divergence_measurement_is_plausible(divergence: Mapping[str, int]) -> None:
    """Fail closed before comparing: a collapsed pathspec must not read as parity.

    Two empty sets differ by zero, which is exactly what a doc claiming perfect
    parity wants to hear. The floors make that state loud instead of agreeable.
    """
    assert divergence["projection_total"] >= 100, (
        f"skills/ measured {divergence['projection_total']} names; the pathspec "
        "is broken, not the tree"
    )
    assert divergence["canonical_total"] >= 100, (
        f".agents/skills/ measured {divergence['canonical_total']} names; the "
        "pathspec is broken, not the tree"
    )


def test_roadmap_projection_claim_matches_measured_divergence(
    roadmap: str, divergence: Mapping[str, int]
) -> None:
    assert roadmap_violations(roadmap, divergence) == []


def test_control_roadmap_arm_fires_on_every_stale_divergence_count(
    roadmap: str, divergence: Mapping[str, int]
) -> None:
    """Both-states control, built from the measured values so it cannot rot."""
    for label, shifted in (
        (
            "projection-divergence",
            {**divergence, "only_projection": divergence["only_projection"] + 1},
        ),
        (
            "canonical-divergence",
            {**divergence, "only_canonical": divergence["only_canonical"] + 1},
        ),
    ):
        found = roadmap_violations(roadmap, shifted)
        assert any(label in v for v in found), (
            f"control {label}: the arm stayed silent while the measured tree "
            f"disagreed with the doc; violations were {found!r}"
        )


def test_control_roadmap_arm_fires_when_the_claim_is_deleted_or_unparseable(
    roadmap: str, divergence: Mapping[str, int]
) -> None:
    """A gate that can no longer find its claim must go red, not measure nothing."""
    deleted = _PROJECTION_CLAIM.sub("the roots are in sync", roadmap)
    found = roadmap_violations(deleted, divergence)
    assert any("projection-claim-missing" in v for v in found), (
        f"deleting the claim left the arm silent; violations were {found!r}"
    )

    unparseable = _PROJECTION_CLAIM.sub(
        "a few skill names live only in `skills/` and some only in `.agents/skills/`",
        roadmap,
    )
    found = roadmap_violations(unparseable, divergence)
    assert any("projection-claim-missing" in v for v in found), (
        f"an unparseable claim left the arm silent; violations were {found!r}"
    )


def test_control_roadmap_arm_distinguishes_parity_from_divergence(
    divergence: Mapping[str, int],
) -> None:
    """The discriminating case: is the arm reading the CLAIM or just a number?

    H1 (arm compares doc to tree): the doc stating the measured counts must stay
    SILENT while a doc stating the WRONG counts must FIRE.
    H2 (arm merely notices digits): both look identical.
    Only H1 can produce the asymmetry asserted below.

    The wrong claim is chosen from the measured state so the control discriminates
    in BOTH states and cannot rot when the tree changes (the previous revision
    hard-coded the diverged state and told its maintainer to rewrite it at parity,
    which the 2026-08-28 fold made necessary):

    * roots diverge  -> a claim of perfect parity (0 and 0) is the wrong one;
    * roots at parity -> the pre-fold counts (3 and 12) are the wrong one.
    """
    truthful = (
        f"- `skills/` — {divergence['only_projection']} skill names live only in "
        f"`skills/` and {divergence['only_canonical']} only in "
        "`.agents/skills/`.\n"
    )
    assert roadmap_violations(truthful, divergence) == [], (
        "control: the arm fired on a doc that states the measured truth, so it "
        "flags the presence of numbers rather than their correctness"
    )

    at_parity = not (divergence["only_projection"] or divergence["only_canonical"])
    wrong_projection, wrong_canonical = (3, 12) if at_parity else (0, 0)
    assert (wrong_projection, wrong_canonical) != (
        divergence["only_projection"],
        divergence["only_canonical"],
    ), "control precondition: the chosen wrong claim coincides with the measured tree"
    wrong = (
        f"- `skills/` — {wrong_projection} skill names live only in `skills/` and "
        f"{wrong_canonical} only in `.agents/skills/`.\n"
    )
    found = roadmap_violations(wrong, divergence)
    assert found, (
        "control: a doc stating counts the tree contradicts did not fire -- the "
        "arm is not comparing the claim to reality"
    )
    assert any("projection-divergence" in v for v in found) or any(
        "canonical-divergence" in v for v in found
    ), f"control: fired, but not on the count mismatch; violations were {found!r}"
