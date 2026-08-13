#!/usr/bin/env python3
r"""The gate the repo->live hook deploy has never had.

Every round of this audit named the same hole: the deploy step from `hooks/` (repo SSOT) into
`~/.claude/hooks` (what actually runs) has NO checker. `probe_hook_manifest_drift.py` covers one
axis -- which hooks are WIRED -- and its conclusion, "deploying repo->live is SAFE, nothing live
would be lost", is scoped to manifest ENTRIES. Round 5 measured the layer underneath and found 43
of 235 shared files differ, 12 of them wired. Round 6 (`_b1_direction.py`) classified those 12 by
line-set membership: **all twelve are DIVERGED**, both sides holding content the other lacks. The
deploy plan's Step 1 ("copy the two hook trees if absent") is therefore safe only for the ABSENT
case it names, and a wider tree copy would delete live behaviour in every wired hook it touched.

That is the exact failure fan-out-contract C4 measured: six Opus agents classified 338 files, got
86% right, and **100% of the 47 errors pointed at data loss** -- every one a DIVERGED file read as
deploy-safe, because a one-directional read cannot see two-directional divergence. C4's own
conclusion is this file: the classification is answerable by an exact algorithm, so write the
algorithm and reserve judgement for what the divergent content MEANS.

AXES
  A  manifest entries      repo/live `_dispatch/manifest.json`, both directions
  B  wired script bodies   direction per file (EQUAL / REPO-AHEAD / LIVE-AHEAD / DIVERGED)
  C  capability markers    for DIVERGED bodies, which behaviour markers exist ONLY live
  D  settings hooks        repo `agent-self/config/settings.json` vs live, both directions
  L1 `if` on a non-tool event   -- vendor evaluates `if` ONLY on tool events, so elsewhere the
                                   hook silently never runs
  L2 check timeout above its event's settings_timeout -- the surplus is unreachable

WHY IT CANNOT BE A GITHUB JOB. Axes B/C/D and the manifest LIVE side read `~/.claude`, which does
not exist on a runner. This is a LOCAL pre-deploy gate. `check_citations.py` is the CI-shaped
sibling; this one is the thing you run before touching the live tree.

EXIT CODES
  0  no HAZARD
  1  at least one HAZARD (a deploy in the stated direction would lose live behaviour, or a hook is
     inert by construction)
  2  a CONTROL failed -- the gate could not measure, and says so instead of reporting clean.
     Fail-closed is the whole point: this program's ancestors reported parity four times running
     off `manifest["events"][ev]`, which is a DICT, so `len()` returned 3 on both sides.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _g5_vendorcaps as vendor  # noqa: E402  vendor doc facts, single-sourced

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_ROOT = Path(os.environ.get("CLAUDE_LIVE_ROOT", Path.home() / ".claude"))

REPO_HOOKS = REPO_ROOT / "hooks"
LIVE_HOOKS = LIVE_ROOT / "hooks"
REPO_MANIFEST = REPO_HOOKS / "_dispatch" / "manifest.json"
LIVE_MANIFEST = LIVE_HOOKS / "_dispatch" / "manifest.json"
REPO_SETTINGS = REPO_ROOT / "agent-self" / "config" / "settings.json"
LIVE_SETTINGS = LIVE_ROOT / "settings.json"

#: Below this, assume the reader is looking at the wrong collection rather than at a genuinely
#: tiny fleet. Round 5 measured 25 live checks; a reading of 0-4 means the shape moved.
MIN_PLAUSIBLE_CHECKS = 5

#: Manifest fields whose difference changes behaviour. `comment` is prose, reported separately.
BEHAVIOUR_FIELDS = (
    "script",
    "args",
    "matcher",
    "timeout",
    "isolate",
    "side_effect",
    "emits",
)

SKIP_DIRS = {"__pycache__", "_fleet-backups", ".pytest_cache", ".mypy_cache"}

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{3,}$")
_PATHISH = re.compile(r"[\\/]|^\.[A-Za-z]")
#: Constructs that only appear in a regex, never in a path. Checked BEFORE _PATHISH because a
#: pattern like r"(?:def|class)\s+" contains a backslash and would otherwise read as a path.
_REGEX_META = re.compile(r"\(\?[:=!P<]|\\[sdwbSDWB]|\[\^|\{\d+,|\.\*|\.\+|\|\w+\)")
#: A concrete artifact path under the harness home. Its presence is the second signal that turns
#: a hook NAME in prose into a documented DEPENDENCY on that hook's output (use-vs-mention).
_ARTIFACT_PATH = re.compile(r"[~.]?[\\/]?\.claude[\\/][\w.<>/\\-]+")


# --------------------------------------------------------------------------- findings


@dataclass
class Finding:
    axis: str
    severity: str  # HAZARD | WARN | INFO
    subject: str
    detail: str

    def line(self) -> str:
        return f"[{self.severity:<6}] {self.axis:<3} {self.subject}: {self.detail}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    controls: dict[str, bool] = field(default_factory=dict)
    stats: dict[str, object] = field(default_factory=dict)

    def add(self, axis: str, severity: str, subject: str, detail: str) -> None:
        self.findings.append(Finding(axis, severity, subject, detail))

    def hazards(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "HAZARD"]


# --------------------------------------------------------------------------- readers


def manifest_checks(doc: dict, event: str) -> dict[str, dict]:
    """Hooks live at events[<event>]["checks"].

    events[<event>] is a DICT of {settings_matcher, settings_timeout, checks}. Iterating it
    yields three KEY NAMES and `len()` returns 3 for every event on both sides -- the false
    parity that survived four successive probes. An older flat list shape is tolerated rather
    than crashed on, because crashing on it would look like "no drift" to a caller that only
    reads the exit code.
    """
    node = (doc.get("events") or {}).get(event) or {}
    items = node if isinstance(node, list) else (node.get("checks") or [])
    return {c.get("name", json.dumps(c)[:60]): c for c in items if isinstance(c, dict)}


def settings_hooks(path: Path) -> dict[str, list[dict]]:
    """Return {event: [entry, ...]} from a settings file's `hooks` subtree ONLY.

    SECURITY: the live settings.json holds real credentials. Nothing outside `hooks` is read,
    and callers must print only event names, matchers, timeouts and command BASENAMES.
    """
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for event, groups in (doc.get("hooks") or {}).items():
        entries: list[dict] = []
        for group in groups if isinstance(groups, list) else []:
            for hook in group.get("hooks") or []:
                entries.append(
                    {
                        "matcher": group.get("matcher"),
                        "if": group.get("if", hook.get("if")),
                        "timeout": hook.get("timeout"),
                        "script": _command_script(str(hook.get("command", ""))),
                    }
                )
        out[event] = entries
    return out


def _command_script(command: str) -> str:
    """The hooks-relative script path a settings command runs, or its basename.

    Returns only the portion at or below `hooks/` -- never the full command line, which can
    carry an env-var prefix, and never a value from any other settings key.

    This exists because the first version of this gate derived "is it wired?" from the manifest
    alone. That silently under-reported severity for every hook registered DIRECTLY in
    settings.json -- which is where both blocking security hooks (no-force-push, test-tamper-
    guard) live. A gate that mis-scores exactly the hooks whose loss matters most is worse than
    no gate, so wiredness is now the UNION of both registries.
    """
    tokens = re.split(r'["\s]+', command.strip())
    for token in reversed(tokens):
        if token.endswith((".py", ".ps1", ".sh", ".cmd", ".mjs", ".js")):
            posix = token.replace("\\", "/")
            marker = "/hooks/"
            if marker in posix:
                return posix.split(marker, 1)[1]
            return os.path.basename(posix)
    return os.path.basename(tokens[-1].replace("\\", "/")) if tokens else ""


def walk_hooks(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith((".py", ".ps1", ".sh", ".json")):
                full = Path(dirpath) / name
                out[full.relative_to(root).as_posix()] = full
    return out


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- comparators


def sig_lines(text: str) -> set[str]:
    """The comparable line set: LF-normalised, right-stripped, no blanks, no whole-line comments.

    Indentation is KEPT -- moving a block under an `if` changes behaviour. CRLF is normalised
    away because it is not drift (windows-shell 8b); counting it manufactures a flood and trains
    the reader to ignore the report, which is one of this audit's own findings.
    """
    out: set[str] = set()
    for raw in text.replace("\r\n", "\n").split("\n"):
        stripped = raw.rstrip()
        if stripped.strip() and not stripped.lstrip().startswith("#"):
            out.add(stripped)
    return out


def classify_direction(repo_text: str, live_text: str) -> str:
    """EQUAL / REPO-AHEAD / LIVE-AHEAD / DIVERGED by line-set membership.

    Order-insensitive on purpose. Known and disclosed weakness: a purely MOVED line reads as
    EQUAL, so this UNDER-reports reordering. That bias is the safe direction for a gate whose
    failure mode is data loss -- it can never report "safe" for a file with live-only content.
    """
    repo, live = sig_lines(repo_text), sig_lines(live_text)
    repo_only, live_only = repo - live, live - repo
    if not repo_only and not live_only:
        return "EQUAL"
    if not live_only:
        return "REPO-AHEAD"
    if not repo_only:
        return "LIVE-AHEAD"
    return "DIVERGED"


def markers(text: str) -> set[str]:
    """Behaviour markers: what this program can DO, independent of how it is written.

    Line-set drift answers "do the bytes differ"; a refactor makes that noisy. Markers answer the
    question the deploy actually poses -- "would this capability disappear" -- and survive
    reformatting, renaming and extraction into a helper.

      ENV:<NAME>    an environment variable the hook reads (opt-outs, budgets, kill switches)
      PATH:<frag>   a path literal (a `.disabled` file, an index, a spool dir)
      EXIT2:<n>     how many blocking exit-2 sites exist
      MSG:<text>    a long message literal -- the user-visible surface
    """
    out: set[str] = set()
    try:
        tree = ast.parse(text.replace("\r\n", "\n"))
    except SyntaxError:
        return {"UNPARSEABLE"}
    exit2 = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            kind = classify_literal(node.value.strip())
            if kind:
                out.add(kind)
        elif _is_exit2(node):
            exit2 += 1
    out.add(f"EXIT2:{exit2}")
    return out


def classify_literal(value: str) -> str:
    """Label one string literal, or return "" for one that carries no capability signal.

    The regex-vs-path split is the fiddly part and the first version got it wrong: `_PATHISH`
    matched any backslash, so a REGEX containing `\\s` was reported as a lost PATH. That is a
    self-contradicting label -- `PATH:(?:def|class|...)\\s+` is visibly not a path -- and a
    label the reader can see is wrong discredits the findings next to it, which are real.
    """
    if _ENV_NAME.match(value):
        return f"ENV:{value}"
    if _REGEX_META.search(value):
        return f"RE:{value[:80]}" if len(value) >= 12 else ""
    if _PATHISH.search(value) and 3 < len(value) < 120:
        return f"PATH:{value}"
    if len(value) >= 40:
        return f"MSG:{' '.join(value.split())[:80]}"
    return ""


def _is_exit2(node: ast.AST) -> bool:
    if isinstance(node, ast.Return):
        return isinstance(node.value, ast.Constant) and node.value.value == 2
    if isinstance(node, ast.Call):
        name = getattr(node.func, "attr", getattr(node.func, "id", ""))
        if name in {"exit", "_exit"} and node.args:
            arg = node.args[0]
            return isinstance(arg, ast.Constant) and arg.value == 2
    return False


# --------------------------------------------------------------------------- axes


def axis_manifest(report: Report) -> set[str]:
    """Axis A. Returns the set of scripts wired on EITHER side (input to axes B/C)."""
    if not REPO_MANIFEST.is_file() or not LIVE_MANIFEST.is_file():
        report.add("A", "HAZARD", "manifest", "one side missing -- cannot compare")
        return set()
    live = json.loads(read_text(LIVE_MANIFEST))
    repo = json.loads(read_text(REPO_MANIFEST))
    events = sorted(set(live.get("events", {})) | set(repo.get("events", {})))

    wired: set[str] = set()
    live_total = 0
    for event in events:
        live_checks, repo_checks = (
            manifest_checks(live, event),
            manifest_checks(repo, event),
        )
        live_total += len(live_checks)
        for name in sorted(set(live_checks) | set(repo_checks)):
            entry = live_checks.get(name) or repo_checks.get(name) or {}
            if entry.get("script"):
                wired.add(str(entry["script"]))
            if name not in live_checks:
                report.add(
                    "A",
                    "WARN",
                    f"{event}/{name}",
                    "in repo, NOT deployed -- the live harness does not run it",
                )
            elif name not in repo_checks:
                report.add(
                    "A",
                    "HAZARD",
                    f"{event}/{name}",
                    "live-only -- a repo->live manifest deploy would UNWIRE it",
                )
            else:
                _diff_fields(report, event, name, repo_checks[name], live_checks[name])
    report.stats["live_manifest_checks"] = live_total
    report.stats["manifest_events"] = len(events)
    return wired


def _diff_fields(report: Report, event: str, name: str, repo: dict, live: dict) -> None:
    for key in BEHAVIOUR_FIELDS:
        if repo.get(key) != live.get(key):
            report.add(
                "A",
                "WARN",
                f"{event}/{name}",
                f"{key}: repo={repo.get(key)!r} live={live.get(key)!r}",
            )


def _body_severity(rel: str, is_wired: bool) -> tuple[str, str]:
    """Severity ladder for a drifted file, and why.

    Not everything under `hooks/` is a program the harness runs. A drifted runtime index or a
    live-only test file is not a behaviour fork, and reporting it at the same volume as a wired
    security hook is how a report earns the ignore it then gets -- "hooks so noisy they are
    ignored" is one of this audit's own axes, so the gate must not commit it.
    """
    if is_wired:
        return "HAZARD", "WIRED LIVE -- the live harness runs this file today"
    if rel.rsplit("/", 1)[-1].startswith("test_"):
        return (
            "INFO",
            "test file -- the live tree's copy is never executed by the harness",
        )
    if rel.endswith(".json"):
        return "INFO", "data/state file -- differing content is not a behaviour fork"
    return "WARN", "present in the tree but not wired to any event"


def axis_bodies_and_markers(report: Report, wired: set[str]) -> None:
    """Axes B and C over every file present in BOTH trees."""
    repo_files, live_files = walk_hooks(REPO_HOOKS), walk_hooks(LIVE_HOOKS)
    shared = sorted(set(repo_files) & set(live_files))
    report.stats["shared_files"] = len(shared)
    report.stats["repo_only_files"] = len(set(repo_files) - set(live_files))
    report.stats["live_only_files"] = len(set(live_files) - set(repo_files))
    report.stats["wired_scripts"] = len(wired)

    tally: dict[str, int] = {}
    for rel in shared:
        verdict = classify_direction(
            read_text(repo_files[rel]), read_text(live_files[rel])
        )
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict in {"EQUAL", "REPO-AHEAD"}:
            continue
        is_wired = rel in wired
        severity, why = _body_severity(rel, is_wired)
        report.add(
            "B",
            severity,
            rel,
            f"{verdict} ({why}) -- repo->live copy would lose live content",
        )
        if rel.endswith(".py"):
            _report_lost_markers(
                report, rel, repo_files[rel], live_files[rel], is_wired
            )
    report.stats["direction_tally"] = tally


def _report_lost_markers(
    report: Report, rel: str, repo_path: Path, live_path: Path, is_wired: bool
) -> None:
    lost = markers(read_text(live_path)) - markers(read_text(repo_path))
    hard = sorted(
        m for m in lost if m.split(":", 1)[0] in {"ENV", "PATH", "EXIT2", "RE"}
    )
    soft = sorted(m for m in lost if m.startswith("MSG:"))
    if hard:
        report.add(
            "C",
            "HAZARD" if is_wired else "WARN",
            rel,
            f"{len(hard)} capability marker(s) exist ONLY live: {'; '.join(hard[:6])}",
        )
    if soft:
        report.add("C", "INFO", rel, f"{len(soft)} live-only message literal(s)")


def axis_settings(report: Report) -> None:
    """Axis D. A repo->live settings deploy DELETES any event the repo lacks."""
    live, repo = settings_hooks(LIVE_SETTINGS), settings_hooks(REPO_SETTINGS)
    report.stats["live_settings_events"] = len(live)
    report.stats["repo_settings_events"] = len(repo)
    for event in sorted(set(live) | set(repo)):
        live_tails = sorted(e["script"] for e in live.get(event, []))
        repo_tails = sorted(e["script"] for e in repo.get(event, []))
        if event not in repo:
            report.add(
                "D",
                "HAZARD",
                event,
                f"live-only event ({len(live_tails)} hook(s): {', '.join(live_tails)}) -- "
                "a repo->live settings deploy would DELETE it",
            )
        elif event not in live:
            report.add(
                "D", "WARN", event, "repo-only event -- declared but not deployed"
            )
        elif live_tails != repo_tails:
            report.add("D", "WARN", event, f"repo={repo_tails} live={live_tails}")


def axis_promises(
    report: Report,
    docs: dict[str, str],
    wired: set[str],
    hook_dirs: set[str],
    age_fn: Callable[[str], float | None] | None = None,
    stale_hours: float | None = None,
) -> None:
    """Axis P. A command that promises a capability no LIVE hook produces.

    This is the /rollback gap, generalised. `commands/rollback.md` opens by stating that the
    `edit-checkpoints` PreToolUse hook "snapshots the pre-edit state once per turn", and then
    tells the reader to restore from an index at `~/.claude/checkpoints/<id>/index.ndjson`.
    That producer is declared in the repo manifest and deployed NOWHERE, and the index's newest
    record is 26.7 days old. The command has been promising a capability the harness cannot
    deliver for close to a month, silently, because nothing checks the pairing.

    A deploy plan for it already exists and is not re-litigated here. What did not exist is a
    way for the gap to FAIL rather than sit in a document, and for a future unwiring of any
    producer to be caught the same way.

    TWO SIGNALS, AND-GATED. The first version of this axis fired on the CONFIG alone -- "the doc
    names a hooks/ directory that is not wired live" -- and immediately produced a false positive
    it could not have caught by reading itself: `commands/sentinel.md` names `event-ledger`, no
    script under `hooks/event-ledger/` is wired in either live registry, and yet
    `~/.claude/event-ledger/` holds 375 files whose newest write is 0.6 h old. Something wired
    under a DIFFERENT directory name produces it. Inferring the producer from a name match is
    the use-vs-mention trap wearing new clothes: it counted the directory name, not the
    producing field.

    So a finding now needs the config signal AND an independent BEHAVIOURAL one -- the artifact
    the doc points at is absent, or has not been written in `stale_hours`. On the real tree those
    two separate cleanly: checkpoints 642 h (26.7 days) stale, event-ledger 0.6 h fresh.

    Residuals, disclosed: the artifact-path and hook-name tests are both document-scoped rather
    than proximity-scoped, and an artifact that is legitimately written rarely would read as
    stale. `HOOK_GATE_STALE_HOURS` tunes the threshold; the tightening, if it ever misfires, is
    proximity between the hook name and the path.
    """
    limit = (
        stale_hours
        if stale_hours is not None
        else float(os.environ.get("HOOK_GATE_STALE_HOURS", "168"))
    )
    cache: dict[str, float | None] = {}

    def age_of(root: str) -> float | None:
        if root not in cache:
            cache[root] = (
                age_fn(root)
                if age_fn
                else _newest_age_hours(root, fresh_before_hours=limit)
            )
        return cache[root]

    wired_dirs = {script.split("/", 1)[0] for script in wired}
    for name, text in sorted(docs.items()):
        roots = artifact_roots(text)
        unwired = sorted(h for h in hook_dirs if h in text and h not in wired_dirs)
        if not roots or not unwired:
            continue
        for root in sorted(roots):
            age = age_of(root)
            if age is None:
                state = "produces nothing -- the path does not exist"
            elif age > limit:
                state = f"was last written {age / 24:.1f} days ago"
            else:
                continue
            report.add(
                "P",
                "HAZARD",
                name,
                f"points the reader at ~/.claude/{root}, which {state}; the doc also names "
                f"unwired hook(s) {', '.join(unwired)}. The pairing is document-scoped -- the "
                "load-bearing claim is the dead artifact, not that those hooks produce it",
            )


def artifact_roots(text: str) -> set[str]:
    """The first path segment under `.claude/` for every artifact path a doc cites."""
    roots: set[str] = set()
    for match in _ARTIFACT_PATH.finditer(text):
        tail = re.split(r"[\\/]", match.group(0).split(".claude", 1)[1].lstrip("\\/"))
        if tail and tail[0]:
            roots.add(tail[0])
    return roots


def _newest_age_hours(
    root: str, fresh_before_hours: float | None = None
) -> float | None:
    """Hours since the newest write anywhere under `~/.claude/<root>`, or None if absent.

    mtime distinguishes "written in the last T" and nothing else -- never stalled-vs-done. That
    is exactly and only what is asked of it here: is anything still PRODUCING this artifact.

    `fresh_before_hours` stops the walk the moment any file is younger than it. That is not an
    optimisation detail, it is what makes the gate runnable: `~/.claude/plugins` is cited by a
    command, took **109 seconds** to walk exhaustively, and is 0.3 h fresh -- so the entire walk
    was spent re-proving a verdict the first file already settled. The whole suite ran in 180 s
    because of that one root. A gate slow enough to skip is a gate nobody runs.

    Honesty about the return value: with the early exit the number is an UPPER BOUND on the true
    age, not necessarily the newest write. The only consumer compares it against that same
    threshold, so the verdict is unaffected; callers wanting the exact age omit the argument.
    """
    base = LIVE_ROOT / root
    if not base.exists():
        return None
    if base.is_file():
        # A cited artifact can be a FILE, not a directory. Walking a file yields nothing, so the
        # first version returned None and reported `~/.claude/settings.json` as "produces
        # nothing" -- about a file that plainly exists. A claim the reader can falsify by
        # looking discredits the true findings printed beside it.
        return (time.time() - base.stat().st_mtime) / 3600.0
    now = time.time()
    cutoff = None if fresh_before_hours is None else now - fresh_before_hours * 3600.0
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            try:
                newest = max(newest, (Path(dirpath) / filename).stat().st_mtime)
            except OSError:
                continue
            if cutoff is not None and newest > cutoff:
                return (now - newest) / 3600.0
    if newest == 0.0:
        return None
    return (now - newest) / 3600.0


def lint_if_on_non_tool_event(report: Report, sources: dict[str, dict]) -> None:
    """L1. The vendor evaluates `if` ONLY on tool events; anywhere else the hook never runs.

    Nothing violates this today (0 of 42 entries use `if`, re-confirmed three rounds running).
    That is exactly why it is worth one function: this is a tripwire for the FIRST author to
    reach for `if`, and the failure it prevents is silent -- the hook simply stops firing, with
    no error anywhere.
    """
    for origin, events in sources.items():
        for event, entries in events.items():
            for entry in entries:
                if entry.get("if") in (None, ""):
                    continue
                if event in vendor.IF_EVALUATED_EVENTS:
                    report.add(
                        "L1",
                        "INFO",
                        f"{origin}:{event}",
                        "`if` on a tool event -- valid",
                    )
                else:
                    report.add(
                        "L1",
                        "HAZARD",
                        f"{origin}:{event}/{entry.get('script')}",
                        f"carries `if`={entry['if']!r} on a NON-tool event -- never evaluated, "
                        "so the hook silently never runs",
                    )


def lint_budget_ceiling(report: Report) -> None:
    """L2. A check timeout above its event's settings_timeout is unreachable surplus.

    Round 4 measured this by hand (Stop/git-hygiene 90 s inside a 35 s event = 55 s that cannot
    be used, in BOTH trees). Encoding it here is what stops it regressing silently, and the
    vendor doc supplies the mechanism round 4 lacked: `timeout` is per-hook-COMMAND, and our
    dispatcher is registered as ONE command holding N checks, so the cancellation lands on the
    whole dispatcher and every check on that event loses its output together.
    """
    for label, path in (("repo", REPO_MANIFEST), ("live", LIVE_MANIFEST)):
        if not path.is_file():
            continue
        doc = json.loads(read_text(path))
        for event, node in (doc.get("events") or {}).items():
            ceiling = node.get("settings_timeout") if isinstance(node, dict) else None
            if not isinstance(ceiling, (int, float)):
                continue
            for name, check in manifest_checks(doc, event).items():
                declared = check.get("timeout")
                if isinstance(declared, (int, float)) and declared > ceiling:
                    report.add(
                        "L2",
                        "WARN",
                        f"{label}:{event}/{name}",
                        f"declares {declared}s inside a {ceiling}s event budget -- "
                        f"{declared - ceiling}s unreachable",
                    )


# --------------------------------------------------------------------------- controls


def run_controls(report: Report) -> None:
    """Both-states controls. A silence only counts once the probe has FIRED on a broken state."""
    equal = classify_direction("def f():\n    return 1\n", "def f():\n    return 1\n")
    ahead = classify_direction(
        "def f():\n    pass\ndef g():\n    pass\n", "def f():\n    pass\n"
    )
    behind = classify_direction(
        "def f():\n    pass\n", "def f():\n    pass\ndef g():\n    pass\n"
    )
    diverged = classify_direction(
        "def f():\n    pass\ndef g():\n    pass\n",
        "def f():\n    pass\ndef h():\n    pass\n",
    )
    report.controls["C1_direction_equal"] = equal == "EQUAL"
    report.controls["C2_direction_repo_ahead"] = ahead == "REPO-AHEAD"
    report.controls["C3_direction_live_ahead"] = behind == "LIVE-AHEAD"
    report.controls["C4_direction_diverged"] = diverged == "DIVERGED"

    base = 'import os\nX = os.environ.get("KEEP_ME")\n'
    report.controls["C5_marker_loss_detected"] = "ENV:KEEP_ME" in (
        markers(base) - markers("import os\n")
    )
    report.controls["C6_marker_no_false_loss"] = not (markers(base) - markers(base))
    report.controls["C6b_regex_not_labelled_path"] = classify_literal(
        r"(?:def|class)\s+([A-Za-z_]\w{2,})"
    ).startswith("RE:")
    report.controls["C6c_path_still_labelled_path"] = classify_literal(
        ".claude/hooks/_dispatch"
    ).startswith("PATH:")

    lint = Report()
    lint_if_on_non_tool_event(
        lint,
        {
            "synthetic": {"Stop": [{"if": "Edit(*.ts)", "script": "broken.py"}]},
        },
    )
    report.controls["C7_if_lint_fires_on_broken"] = bool(lint.hazards())
    clean = Report()
    lint_if_on_non_tool_event(
        clean,
        {
            "synthetic": {"PreToolUse": [{"if": "Edit(*.ts)", "script": "ok.py"}]},
        },
    )
    report.controls["C8_if_lint_silent_on_valid"] = not clean.hazards()

    doc = {"d.md": "the ghost-hook writes ~/.claude/ghost/index.ndjson"}

    def _promise(
        wired_set: set[str], age: float | None, text: dict[str, str] | None = None
    ) -> Report:
        out = Report()
        axis_promises(
            out,
            text or doc,
            wired_set,
            {"ghost-hook"},
            age_fn=lambda _root: age,
            stale_hours=168.0,
        )
        return out

    report.controls["C11_promise_fires_on_stale_artifact"] = bool(
        _promise(set(), 700.0).hazards()
    )
    report.controls["C11b_promise_fires_on_absent_artifact"] = bool(
        _promise(set(), None).hazards()
    )
    # The regression control for a false positive this axis actually produced: `event-ledger` is
    # named by a command, is not wired under its own directory name, and is 0.6 h fresh because
    # something else writes it. Config alone must NOT be enough to raise a hazard.
    report.controls["C12_promise_silent_when_artifact_is_fresh"] = not _promise(
        set(), 0.6
    ).hazards()
    report.controls["C13_promise_silent_when_producer_wired"] = not _promise(
        {"ghost-hook/hook.py"}, 700.0
    ).hazards()
    report.controls["C14_promise_silent_on_bare_mention"] = not _promise(
        set(), 700.0, {"d.md": "see also the ghost-hook, unrelated to this command"}
    ).hazards()

    found = report.stats.get("live_manifest_checks", 0)
    report.controls["C9_manifest_reader_plausible"] = (
        isinstance(found, int) and found >= MIN_PLAUSIBLE_CHECKS
    )
    report.controls["C10_settings_reader_nonempty"] = bool(
        report.stats.get("live_settings_events")
    ) and bool(report.stats.get("repo_settings_events"))


# --------------------------------------------------------------------------- main


def wired_live(report: Report) -> set[str]:
    """Every script the LIVE harness actually runs, from BOTH of its registries.

    Two corrections are baked into this one function, both caught by running the gate against
    reality rather than by reading it:

    1. A hook reaches the harness by two independent routes -- the dispatcher manifest, or a
       command registered directly in settings.json -- and the second route is where BOTH
       blocking security hooks live. Reading only the manifest (this gate's first version)
       scored `no-force-push/hook.py` and `test-tamper-guard/guard.py` as unwired: it
       under-reported exactly the two files whose loss matters most.
    2. Wiredness must be measured on the LIVE side alone. A union across both trees pulled in
       `mcp-liveness/liveness.py`, which is declared in the repo manifest and NOT deployed, and
       the gate then printed "the live harness runs this file" about a file the live harness
       does not run. The hazard being measured is "a deploy destroys behaviour that runs today",
       so the denominator is what runs today. The repo-declared-but-undeployed case is a
       different finding and axis A already reports it.
    """
    # Emits the manifest findings as a side effect; its own union is NOT the live set.
    axis_manifest(report)
    live: set[str] = set()
    if LIVE_MANIFEST.is_file():
        doc = json.loads(read_text(LIVE_MANIFEST))
        for event in doc.get("events", {}):
            for check in manifest_checks(doc, event).values():
                if check.get("script"):
                    live.add(str(check["script"]))
    for entries in settings_hooks(LIVE_SETTINGS).values():
        for entry in entries:
            if entry.get("script"):
                live.add(str(entry["script"]))
    return live


def hook_dir_names() -> set[str]:
    if not REPO_HOOKS.is_dir():
        return set()
    return {
        p.name
        for p in REPO_HOOKS.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }


def command_docs() -> dict[str, str]:
    root = REPO_ROOT / "commands"
    if not root.is_dir():
        return {}
    return {f"commands/{p.name}": read_text(p) for p in sorted(root.glob("*.md"))}


def build_report() -> Report:
    report = Report()
    wired = wired_live(report)
    axis_bodies_and_markers(report, wired)
    axis_promises(report, command_docs(), wired, hook_dir_names())
    axis_settings(report)
    lint_if_on_non_tool_event(
        report,
        {
            "repo-settings": settings_hooks(REPO_SETTINGS),
            "live-settings": settings_hooks(LIVE_SETTINGS),
        },
    )
    lint_budget_ceiling(report)
    run_controls(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="also write the full report here")
    parser.add_argument("--quiet", action="store_true", help="findings summary only")
    args = parser.parse_args(argv)

    report = build_report()
    failed = [k for k, ok in report.controls.items() if not ok]

    print(
        "  controls: "
        + ", ".join(
            f"{k}={'ok' if v else 'FAIL'}" for k, v in sorted(report.controls.items())
        )
    )
    print("  stats: " + json.dumps(report.stats, sort_keys=True))
    if not args.quiet:
        for finding in sorted(
            report.findings, key=lambda f: (f.severity, f.axis, f.subject)
        ):
            print("  " + finding.line())

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "controls": report.controls,
                    "stats": report.stats,
                    "findings": [f.__dict__ for f in report.findings],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
            newline="\n",
        )

    if failed:
        print(f"FAILED:hook-predeploy-gate controls failed: {', '.join(failed)}")
        return 2
    hazards = report.hazards()
    if hazards:
        print(
            f"FAILED:hook-predeploy-gate {len(hazards)} HAZARD(s) of {len(report.findings)} findings"
        )
        return 1
    print(f"SUCCESS:hook-predeploy-gate 0 hazards of {len(report.findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
