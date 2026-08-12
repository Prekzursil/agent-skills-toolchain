r"""CASUALTY lane integration guard -- the hermetic subset a CI runner can execute.

WHY THIS EXISTS. Build rounds 1 and 2 shipped two recovered receipts and six instruments into
`command-center/casualty/`. Every one of them was correct and every one of them was
UNREACHABLE: nothing in this repo called any of them, so the only thing keeping the lane from
rotting was somebody remembering it existed. An instrument that must be remembered is not
integrated -- it is a file. The same shape is already recorded against this estate twice:
`tools/detector-self-test/` (the gate-fabrication instrument) is wired into no CI job, no hook
and no skill, and `tools/measure-guard/` had no agent-facing surface at all.

WHAT IT GUARDS (six probes; the five structural ones each carry a both-states control under
--selftest, and P6 is itself the both-states answer to "does anything actually RUN"):

  P1 wiring        `.github/workflows/quality.yml` must INVOKE this file, not merely mention it.
                   The matcher strips comment lines first, so a path named in prose cannot
                   satisfy it -- use-vs-mention produced four false findings in one wave here.
  P2 inventory     Every shipped instrument carries a disposition (EXECUTED / TESTED / EXEMPT
                   with a written reason) and every disposition names a file that exists.
                   Fail-closed in BOTH directions, so a new instrument cannot arrive ungated and
                   an exemption cannot outlive the file it excuses.
  P3 receipts      Both recovered receipts still reproduce their published elided sha256 and
                   their declared byte count. Cross-checked against the lane's own
                   `verify_elided_digest.py` run as a subprocess: if this file and that one ever
                   disagree, the guard FAILS rather than picking a winner.
  P4 no-lost-work  For each recovered unit, a SUBSTANTIVE artifact must exist somewhere in the
                   repo. Deliberately location-agnostic: the lane copy is authoritative today,
                   but an orchestrator may promote it to the canonical `adversarial/` path, and
                   a guard that pinned the location would fail on the very act of finishing the
                   job. It fails only if the substantive artifact is GONE from both.
  P5 banners       The two superseded round-1 outputs keep their `_DO_NOT_CITE` banner. Those
                   files hold eight CASUALTY verdicts of which SIX were false; stripping the
                   banner silently resurrects them.

WHAT IT DELIBERATELY DOES NOT RUN, and why an exemption is not a shrug. `r2_verify_all.py` is
the full local reviewer runner: it shells to Git Bash, makes a real clone, and reads agent
transcripts that exist only on the box that ran the wave. `recover_failed_agents_v2.py
--selftest` needs those same transcripts. `census_v2.py` reads `command-center/adversarial/`,
which a LIVE sibling wave is still writing; pinning its control pairs in CI would turn an
unrelated sibling commit into a red build, and a gate that fails on every unrelated PR gets
deleted. Each of those is TESTED instead -- `command-center/casualty/tests/` exercises the same
logic against fixtures -- and the exemption table below is itself gated by P2.

usage:
    python command-center/casualty/casualty_guard.py            # the gate (CI runs this)
    python command-center/casualty/casualty_guard.py --selftest # both-states control per probe
    python command-center/casualty/casualty_guard.py --json     # machine-readable result

Terminal: SUCCESS:casualty-guard / FAILED:casualty-guard <failing probe ids>
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# INTEGRATE: repo root derived from THIS file, never hardcoded -- a guard that only runs from one
# absolute path cannot run on a CI runner, which is the whole point of it.
REPO = Path(os.environ.get("CASUALTY_REPO") or Path(__file__).resolve().parents[2])
LANE_REL = "command-center/casualty"
GUARD_REL = f"{LANE_REL}/casualty_guard.py"
WORKFLOW_REL = ".github/workflows/quality.yml"

#: The two units whose builders died mid-wave. Filename under the lane; the canonical
#: `command-center/adversarial/` path holds the 2 KB write-as-you-go skeleton they left behind.
UNITS: dict[str, str] = {
    "ADV-0021": "ADV-0021-install-path-stride-threat-model.json",
    "ADV-0022": "ADV-0022-declared-permission-escape.json",
}

#: Round-1 outputs retained as evidence of a defect rather than deleted. Deleting the evidence of
#: a defect is how the defect comes back, so they stay -- banner-stamped.
SUPERSEDED: tuple[str, ...] = (
    "ADV-LIVENESS.json",
    "ADV-COMPLETENESS-CENSUS.json",
)
BANNER_KEYS = ("_DO_NOT_CITE", "_SUPERSEDED_BY")

#: Disposition of every shipped instrument. Four kinds, and the distinction between the first two
#: is not pedantry -- it is a recursion guard:
#:   EXECUTED     this guard runs it, in P3 or P6.
#:   CI-EXECUTED  the WORKFLOW runs it directly, alongside this guard. `integration_redproof.py`
#:                must be CI-EXECUTED and never EXECUTED: it runs the guard, so a guard that ran
#:                it back would recurse until the runner died.
#:   TESTED       covered by `command-center/casualty/tests/` against fixtures.
#:   EXEMPT       cannot run hermetically, with the reason written out.
#: P2 gates this table in both directions.
INSTRUMENTS: dict[str, str] = {
    "casualty_guard.py": "EXECUTED: this file",
    "verify_elided_digest.py": "EXECUTED: pure, stdlib-only, carries its own mutated-state control",
    "verify_blob_parity.py": (
        "EXECUTED: needs only git and two tracked blobs; --fresh-clone is EXEMPT (clones the repo)"
    ),
    "liveness_v2.py": "EXECUTED: --selftest builds synthetic fixtures in a temp dir",
    "census_v2.py": (
        "TESTED: reads command-center/adversarial/, which a LIVE sibling wave writes. Pinning its "
        "control pairs in CI makes an unrelated sibling commit a red build; the separation logic "
        "is exercised against fixtures in tests/test_casualty_guard.py instead."
    ),
    "recover_failed_agents_v2.py": (
        "EXEMPT: --selftest reads agent transcripts under ~/.claude/projects, which exist only on "
        "the box that ran the wave. Fabricating a fixture for them would be a gate measuring its "
        "own fixture."
    ),
    "integration_redproof.py": (
        "CI-EXECUTED: the both-states control for the integration itself -- runs this guard "
        "against a tree with the CI line deleted and requires the red. A gate that has never "
        "gone red is indistinguishable from a no-op, so CI carries the proof that it can. NOT "
        "EXECUTED by this guard: it invokes the guard, so that would recurse."
    ),
    "r2_verify_all.py": (
        "EXEMPT: the full local reviewer runner -- shells to Git Bash, makes a real clone, reads "
        "the same machine-local transcripts. It is the thing a human runs, not a per-PR gate."
    ),
}


@dataclass
class Result:
    """One probe outcome. `ok=False` is the only thing that fails the gate."""

    probe: str
    ok: bool
    detail: str
    facts: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- shared helpers


def _read_text(path: Path) -> str:
    """Read with newline='' so byte-for-byte content survives; CRLF is normalised by callers."""
    return io.open(path, encoding="utf-8", newline="").read()


def _strip_comment_lines(text: str) -> list[tuple[int, str]]:
    """Drop whole-line YAML comments so a MENTION cannot satisfy a USE check.

    Counting the document instead of the field is the measured failure here: four false findings
    in one wave came from a path being NAMED in prose and read as a dependency.

    Returns (1-based ORIGINAL line number, text) pairs. Carrying the original number matters: the
    first version returned bare strings and reported the index within the stripped list, so it
    told a reviewer "line 176" for an invocation that sits at line 411 of the real file. A gate
    that prints a plausible-but-wrong locator costs exactly the debugging it exists to save.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if line.lstrip().startswith("#"):
            continue
        out.append((i, line))
    return out


def _git(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


def _elide(text: str, declared: str) -> str:
    """The family self-digest recipe: blank artifacts[0].sha256 to 64 zeros, exactly once.

    Mirrors verify_elided_digest.py:41-43. P3 cross-checks the two against each other rather
    than trusting that this copy stayed in step.
    """
    return re.sub(re.escape(declared), "0" * 64, text, count=1)


def _load_scorer():
    """Import the control-proven structural scorer instead of writing a second one.

    Six axes, already shown to separate a complete artifact from a skeleton on six pairs. The
    scorer is the INSTRUMENT, so it is always loaded from the real lane even when a probe is
    aimed at a mutated copy -- the instrument stays fixed, the data varies.
    """
    src = REPO / LANE_REL / "_probe_census.py"
    spec = importlib.util.spec_from_file_location("_casualty_scorer", src)
    if (
        spec is None or spec.loader is None
    ):  # pragma: no cover - unreachable with a real file
        raise RuntimeError(f"cannot load the scorer from {src}")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: on Python 3.14 a `@dataclass` in a path-loaded module resolves its
    # own `__module__` through sys.modules and dies with a bare AttributeError inside dataclasses
    # if it is absent. _probe_census has no dataclass today, so this is prophylactic -- it cost a
    # real failure in integration_redproof.py loading suitefloor.py, which does.
    sys.modules.setdefault("_casualty_scorer", mod)
    spec.loader.exec_module(mod)
    return mod.score


# --------------------------------------------------------------------------- P1 wiring


def probe_wiring(root: Path, *, allow_uncommitted: bool = False) -> Result:
    """quality.yml must INVOKE this guard from a run: block, not name it in a comment."""
    wf = root / WORKFLOW_REL
    if not wf.is_file():
        return Result("P1-wiring", False, f"no workflow at {wf}")

    raw = _read_text(wf)
    lines = _strip_comment_lines(raw)
    invoke = re.compile(r"^\s*python\s+" + re.escape(GUARD_REL) + r"\s*$")
    hits = [n for n, line in lines if invoke.match(line)]
    mentions = raw.replace("\r\n", "\n").count(GUARD_REL)

    facts = {
        "invocation_lines": hits,
        "mentions_anywhere": mentions,
        "workflow": WORKFLOW_REL,
    }

    if not hits:
        return Result(
            "P1-wiring",
            False,
            (
                f"{WORKFLOW_REL} does not INVOKE {GUARD_REL} "
                f"(mentioned {mentions}x anywhere, invoked 0x). The lane is not wired into CI."
            ),
            facts,
        )

    # Second, mechanically independent signal: the COMMITTED blob, read via `git cat-file -p`
    # (never `git archive`, which hands back CRLF worktree bytes on Windows). In CI the checkout
    # IS the blob, so the two can only disagree on a dev box with an uncommitted edit.
    rc, blob = _git(root, "cat-file", "-p", f"HEAD:{WORKFLOW_REL}")
    blob_hits = (
        [n for n, line in _strip_comment_lines(blob) if invoke.match(line)]
        if rc == 0
        else []
    )
    facts["blob_invocation_lines"] = blob_hits
    facts["blob_readable"] = rc == 0

    if rc == 0 and not blob_hits:
        if not allow_uncommitted:
            return Result(
                "P1-wiring",
                False,
                (
                    "the worktree invokes the guard but the COMMITTED blob does not -- the wiring "
                    "is uncommitted, so a fresh clone (and therefore CI) would not run it. Pass "
                    "--allow-uncommitted-wiring only for a deliberate pre-commit dry run."
                ),
                facts,
            )
        return Result(
            "P1-wiring",
            True,
            f"invoked at line(s) {hits} (WARNING: uncommitted -- blob does not carry it yet)",
            facts,
        )

    return Result(
        "P1-wiring",
        True,
        f"invoked at worktree line(s) {hits}, blob line(s) {blob_hits}",
        facts,
    )


# --------------------------------------------------------------------------- P2 inventory


def probe_inventory(root: Path) -> Result:
    """Two-directional: no ungated instrument, no exemption for a file that is gone."""
    lane = root / LANE_REL
    if not lane.is_dir():
        return Result("P2-inventory", False, f"no lane directory at {lane}")

    # `_`-prefixed files are the round-1/round-2 derivation trail (scratch), not shipped
    # instruments; tests/ and probes/ are covered by their own suites. An empty walk is a
    # detector failure, never a pass.
    shipped = sorted(p.name for p in lane.glob("*.py") if not p.name.startswith("_"))
    if not shipped:
        return Result(
            "P2-inventory",
            False,
            f"walked {lane} and found ZERO instruments -- an empty walk is a path bug, not a pass",
        )

    ungated = [n for n in shipped if n not in INSTRUMENTS]
    orphaned = [n for n in INSTRUMENTS if not (lane / n).is_file()]
    unparseable = []
    for name in shipped:
        try:
            ast.parse(_read_text(lane / name))
        except SyntaxError as exc:  # pragma: no cover - exercised by --selftest
            unparseable.append(f"{name}: {exc}")

    facts = {
        "shipped": shipped,
        "ungated": ungated,
        "orphaned_dispositions": orphaned,
        "unparseable": unparseable,
        "dispositions": {k: v.split(":", 1)[0] for k, v in INSTRUMENTS.items()},
    }
    problems = []
    if ungated:
        problems.append(f"instrument(s) with NO disposition: {ungated}")
    if orphaned:
        problems.append(f"disposition(s) naming a missing file: {orphaned}")
    if unparseable:
        problems.append(f"unparseable: {unparseable}")

    if problems:
        return Result("P2-inventory", False, "; ".join(problems), facts)
    return Result(
        "P2-inventory",
        True,
        f"{len(shipped)} instrument(s), all dispositioned and parseable",
        facts,
    )


# --------------------------------------------------------------------------- P3 receipts


def _digest_facts(path: Path) -> dict:
    raw = _read_text(path)
    doc = json.loads(raw)
    declared = doc["artifacts"][0]["sha256"]
    declared_bytes = doc["artifacts"][0]["bytes"]
    on_disk = len(raw.encode("utf-8"))
    recomputed = hashlib.sha256(_elide(raw, declared).encode("utf-8")).hexdigest()
    return {
        "declared": declared,
        "recomputed": recomputed,
        "digest_match": recomputed == declared,
        "declared_bytes": declared_bytes,
        "on_disk_bytes": on_disk,
        "bytes_match": declared_bytes == on_disk,
    }


def probe_receipts(root: Path, *, cross_check: bool = True) -> Result:
    """Both receipts reproduce their published elided digest and declared byte count."""
    lane = root / LANE_REL
    facts: dict = {}
    bad: list[str] = []
    for unit, fname in UNITS.items():
        path = lane / fname
        if not path.is_file():
            bad.append(f"{unit}: missing at {path}")
            facts[unit] = {"present": False}
            continue
        try:
            f = _digest_facts(path)
        except (ValueError, KeyError, IndexError) as exc:
            bad.append(f"{unit}: unreadable receipt ({exc})")
            facts[unit] = {"present": True, "parse_error": str(exc)}
            continue
        facts[unit] = {"present": True, **f}
        if not f["digest_match"]:
            bad.append(f"{unit}: elided digest does not reproduce")
        if not f["bytes_match"]:
            bad.append(
                f"{unit}: declared {f['declared_bytes']} B, on disk {f['on_disk_bytes']} B"
            )

    # CROSS-CHECK, not duplication. `_elide` above restates verify_elided_digest.py's rule; two
    # copies of a rule drift. Rather than trust that they stayed in step, execute the other one
    # and require agreement. A disagreement fails the gate -- it is a detector conflict, and a
    # self-contradicting output is a detector failure, not a finding.
    if cross_check and not bad:
        checker = root / LANE_REL / "verify_elided_digest.py"
        args = [sys.executable, str(checker)] + [
            str(lane / f) for f in UNITS.values() if (lane / f).is_file()
        ]
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        agree = proc.returncode == 0
        facts["cross_check"] = {
            "tool": "verify_elided_digest.py",
            "returncode": proc.returncode,
            "agrees": agree,
        }
        if not agree:
            bad.append(
                "verify_elided_digest.py disagrees with this guard "
                f"(rc={proc.returncode}); two detectors in conflict is a detector failure"
            )

    if bad:
        return Result("P3-receipts", False, "; ".join(bad), facts)
    return Result(
        "P3-receipts",
        True,
        f"{len(UNITS)} receipt(s) reproduce their published digest and byte count",
        facts,
    )


# --------------------------------------------------------------------------- P4 no-lost-work


#: Non-instrument files the guard itself DEPENDS on. `_`-prefixed files are the round-1/round-2
#: derivation trail and are deliberately outside the instrument inventory, but the scorer is a
#: hard dependency of P4 -- deleting it must produce a named FAILED marker, not a traceback.
REQUIRED_DEPS: tuple[str, ...] = ("_probe_census.py",)


def probe_no_lost_work(root: Path, *, floor: int = 5) -> Result:
    """A substantive artifact for each recovered unit must exist SOMEWHERE in the repo.

    Location-agnostic on purpose. The lane copy is authoritative today because this lane was
    forbidden from writing into `command-center/adversarial/` while a sibling wave was live; an
    orchestrator promoting it to the canonical path is the intended END state, and a guard that
    pinned the location would go red on the act of finishing the job.
    """
    missing_deps = [d for d in REQUIRED_DEPS if not (REPO / LANE_REL / d).is_file()]
    if missing_deps:
        return Result(
            "P4-no-lost-work",
            False,
            f"the scorer this probe depends on is gone: {missing_deps}. Without it there is no "
            "measurement, and no measurement is a FAILURE, never a pass.",
            {"missing_dependencies": missing_deps},
        )
    try:
        score = _load_scorer()
    except (OSError, RuntimeError, SyntaxError) as exc:
        return Result(
            "P4-no-lost-work",
            False,
            f"the scorer failed to load: {exc}",
            {"load_error": str(exc)},
        )
    lane = root / LANE_REL
    canon = root / "command-center" / "adversarial"
    facts: dict = {}
    bad: list[str] = []

    for unit, fname in UNITS.items():
        best = -1
        where = None
        seen: dict[str, int] = {}
        for label, base in (("lane", lane), ("canonical", canon)):
            path = base / fname
            if not path.is_file():
                seen[label] = -1
                continue
            try:
                doc = json.loads(_read_text(path))
                s = score(doc, path.stat().st_size)["substance_score"]
            except (ValueError, KeyError, TypeError):
                s = -1
            seen[label] = s
            if s > best:
                best, where = s, label
        facts[unit] = {"scores": seen, "best": best, "best_location": where}
        if best < floor:
            bad.append(
                f"{unit}: no substantive artifact anywhere (best score {best}/6 < floor {floor}) "
                f"-- the recovered work is LOST, not merely moved"
            )

    if bad:
        return Result("P4-no-lost-work", False, "; ".join(bad), facts)
    return Result(
        "P4-no-lost-work",
        True,
        "; ".join(
            f"{u} substantive at {facts[u]['best_location']} ({facts[u]['best']}/6)"
            for u in UNITS
        ),
        facts,
    )


# --------------------------------------------------------------------------- P5 banners


def probe_banners(root: Path) -> Result:
    """The superseded round-1 outputs keep their do-not-cite banner.

    ADV-LIVENESS.json carries eight CASUALTY verdicts, SIX of them false (complete 6/6 artifacts
    of 40-166 KB read as dead because the liveness gate scored them from an eight-hour-stale
    census file). They are kept as defect evidence; the banner is what stops them being cited.
    """
    lane = root / LANE_REL
    facts: dict = {}
    bad: list[str] = []
    for name in SUPERSEDED:
        path = lane / name
        if not path.is_file():
            facts[name] = {"present": False}
            bad.append(
                f"{name}: missing -- deleting the evidence of a defect is how it returns"
            )
            continue
        text = _read_text(path)
        found = [k for k in BANNER_KEYS if k in text]
        facts[name] = {"present": True, "banners": found}
        if not found:
            bad.append(
                f"{name}: no {' / '.join(BANNER_KEYS)} banner -- it reads as citable"
            )

    if bad:
        return Result("P5-banners", False, "; ".join(bad), facts)
    return Result(
        "P5-banners",
        True,
        f"{len(SUPERSEDED)} superseded output(s) banner-stamped",
        facts,
    )


# --------------------------------------------------------------------------- executed instruments


def probe_executed_instruments(root: Path) -> Result:
    """Actually RUN the instruments marked EXECUTED. Checking bytes is not running a program.

    This is the `launchpath` lesson from this repo, restated: vendordrift proves every copy is
    byte-identical and the registry tests prove each path is tracked, and none of them would
    notice a program that exits 0 without doing anything -- the silent-no-op shape that once
    turned `ui-audit` into a vacuous pass.
    """
    lane = root / LANE_REL
    runs = [
        (
            "liveness_v2 --selftest",
            [sys.executable, str(lane / "liveness_v2.py"), "--selftest"],
            "SUCCESS:liveness-v2-selftest",
        ),
        (
            "verify_blob_parity",
            [sys.executable, str(lane / "verify_blob_parity.py")],
            "SUCCESS:blob-parity",
        ),
    ]
    facts: dict = {}
    bad: list[str] = []
    for label, argv, needle in runs:
        proc = subprocess.run(
            argv, cwd=str(root), capture_output=True, text=True, check=False
        )
        out = proc.stdout + proc.stderr
        ok = proc.returncode == 0 and needle in out
        facts[label] = {
            "returncode": proc.returncode,
            "needle": needle,
            "needle_seen": needle in out,
        }
        if not ok:
            bad.append(f"{label}: rc={proc.returncode} needle_seen={needle in out}")
    if bad:
        return Result("P6-executed", False, "; ".join(bad), facts)
    return Result(
        "P6-executed",
        True,
        f"{len(runs)} instrument(s) executed and emitted their marker",
        facts,
    )


PROBES = (
    "P1-wiring",
    "P2-inventory",
    "P3-receipts",
    "P4-no-lost-work",
    "P5-banners",
    "P6-executed",
)


def run_all(
    root: Path, *, allow_uncommitted: bool = False, skip_executed: bool = False
) -> list[Result]:
    results = [
        probe_wiring(root, allow_uncommitted=allow_uncommitted),
        probe_inventory(root),
        probe_receipts(root),
        probe_no_lost_work(root),
        probe_banners(root),
    ]
    if not skip_executed:
        results.append(probe_executed_instruments(root))
    return results


# --------------------------------------------------------------------------- both-states control


def _mirror(root: Path, dest: Path) -> Path:
    """Copy just enough of the repo to run the probes against a mutated tree."""
    (dest / LANE_REL).mkdir(parents=True, exist_ok=True)
    (dest / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / WORKFLOW_REL, dest / WORKFLOW_REL)
    lane = root / LANE_REL
    for name in [*INSTRUMENTS, *SUPERSEDED, *UNITS.values(), "_probe_census.py"]:
        src = lane / name
        if src.is_file():
            shutil.copy2(src, dest / LANE_REL / name)
    return dest


def selftest() -> int:
    """Every probe must FAIL against a deliberately broken copy.

    A probe that is silent in both states measures nothing. Eight detector failures were measured
    in one program on this estate, three of them inside instruments built to catch detector
    failures -- including an UNKNOWN-sentinel grep that scored identically on a complete 162 KB
    artifact and a 1.8 KB skeleton. So: break it, and require the red.
    """
    tmp = Path(tempfile.mkdtemp(prefix="casualty_guard_selftest_"))
    rows: list[tuple[str, str, bool, str]] = []

    def record(probe: str, mutation: str, res: Result) -> None:
        rows.append((probe, mutation, not res.ok, res.detail[:110]))

    # --- P1: strip the invocation, leaving only a COMMENT that names the path.
    base = _mirror(REPO, tmp / "p1")
    wf = base / WORKFLOW_REL
    text = _read_text(wf).replace("\r\n", "\n")
    stripped = "\n".join(
        line
        for line in text.split("\n")
        if not re.match(r"^\s*python\s+" + re.escape(GUARD_REL), line)
    )
    stripped += f"\n# see {GUARD_REL} for the casualty lane guard\n"
    wf.write_text(stripped, encoding="utf-8", newline="")
    record(
        "P1-wiring",
        "invocation removed, path left in a comment (use-vs-mention)",
        probe_wiring(base, allow_uncommitted=True),
    )

    # --- P1 positive control: the UNMUTATED copy must still pass, or the mutation proved nothing.
    base_ok = _mirror(REPO, tmp / "p1ok")
    p1ok = probe_wiring(base_ok, allow_uncommitted=True)
    rows.append(
        (
            "P1-wiring",
            "POSITIVE CONTROL: unmutated copy must PASS",
            p1ok.ok,
            p1ok.detail[:110],
        )
    )

    # --- P2 direction A: an instrument with no disposition.
    base = _mirror(REPO, tmp / "p2a")
    (base / LANE_REL / "brand_new_tool.py").write_text("x = 1\n", encoding="utf-8")
    record(
        "P2-inventory",
        "a new instrument arrives with no disposition",
        probe_inventory(base),
    )

    # --- P2 direction B: a disposition whose file is gone.
    base = _mirror(REPO, tmp / "p2b")
    (base / LANE_REL / "verify_blob_parity.py").unlink()
    record(
        "P2-inventory",
        "a disposition outlives the file it excuses",
        probe_inventory(base),
    )

    # --- P3: one byte changed in a receipt.
    base = _mirror(REPO, tmp / "p3")
    victim = base / LANE_REL / UNITS["ADV-0021"]
    raw = _read_text(victim)
    victim.write_text(
        raw.replace('"schema_version": 1', '"schema_version": 2', 1),
        encoding="utf-8",
        newline="",
    )
    record(
        "P3-receipts",
        "one byte of ADV-0021 mutated",
        probe_receipts(base, cross_check=False),
    )

    # --- P4: the substantive receipt replaced by a skeleton, in BOTH locations.
    base = _mirror(REPO, tmp / "p4")
    skeleton = json.dumps(
        {
            "unit_id": "ADV-0021",
            "status": "in-progress",
            "evidence": [],
            "tests": [],
            "negative_controls": [],
        },
        indent=2,
    )
    (base / LANE_REL / UNITS["ADV-0021"]).write_text(
        skeleton, encoding="utf-8", newline=""
    )
    record(
        "P4-no-lost-work",
        "the only substantive copy replaced by a skeleton",
        probe_no_lost_work(base),
    )

    # --- P5: the do-not-cite banner stripped.
    base = _mirror(REPO, tmp / "p5")
    victim = base / LANE_REL / SUPERSEDED[0]
    text = _read_text(victim)
    for key in BANNER_KEYS:
        text = text.replace(key, "_retired_note")
    victim.write_text(text, encoding="utf-8", newline="")
    record(
        "P5-banners",
        "the _DO_NOT_CITE banner stripped from ADV-LIVENESS.json",
        probe_banners(base),
    )

    print("BOTH-STATES CONTROL for casualty_guard")
    print(f"  {'probe':<16} {'fires':<6} mutation")
    ok = True
    for probe, mutation, fired, detail in rows:
        ok = ok and fired
        print(f"  {probe:<16} {'PASS' if fired else 'FAIL':<6} {mutation}")
        print(f"  {'':<16} {'':<6}   -> {detail}")
    shutil.rmtree(tmp, ignore_errors=True)
    print("SUCCESS:casualty-guard-selftest" if ok else "FAILED:casualty-guard-selftest")
    return 0 if ok else 1


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--selftest", action="store_true", help="prove each probe fires when broken"
    )
    ap.add_argument(
        "--json", action="store_true", help="emit the result vector as JSON"
    )
    ap.add_argument(
        "--allow-uncommitted-wiring",
        action="store_true",
        help="pre-commit dry run only: tolerate a wiring edit that is not yet in a blob",
    )
    ap.add_argument(
        "--skip-executed",
        action="store_true",
        help="skip P6 (running the EXECUTED instruments); for a fast structural-only pass",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    results = run_all(
        REPO,
        allow_uncommitted=args.allow_uncommitted_wiring,
        skip_executed=args.skip_executed,
    )
    if not results:  # fail closed: an empty probe set must never read as success
        print("FAILED:casualty-guard no probes ran")
        return 1

    if args.json:
        print(
            json.dumps(
                {"repo": str(REPO), "results": [r.__dict__ for r in results]},
                indent=2,
                default=str,
            )
        )
    else:
        for r in results:
            print(f"  {'OK  ' if r.ok else 'FAIL'} {r.probe}: {r.detail}")

    failed = [r.probe for r in results if not r.ok]
    if failed:
        print(f"FAILED:casualty-guard {','.join(failed)}")
        return 1
    print(f"SUCCESS:casualty-guard {len(results)} probe(s) green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
