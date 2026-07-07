#!/usr/bin/env python3
"""acceptance_review — the cross-model acceptance-reviewer harness.

The external-signal verifier that runs at the "done" boundary of an app change.
It gathers the objective evidence a fresh reviewer needs (the diff, the declared
golden-journeys, the reward-hack surface, and the on-disk artifacts proving the
journeys actually ran), builds an ADVERSARIAL review prompt, and dispatches an
INDEPENDENT reviewer — preferring a genuinely different model (Codex or Gemini
CLI) and degrading gracefully to a fresh-context Claude subagent when no
cross-model CLI is on PATH.

Why this exists (verifier separation): the same context that wrote the code is a
biased judge — intrinsic self-correction degrades (Huang, ICLR'24), verifier and
generator errors couple ("Verification Mirage"), and judges prefer their own
output (Panickssery, NeurIPS'24). The only trustworthy "does it actually work
end-to-end?" signal comes from an evaluator that did NOT write the code and
ideally is not the same model (VeriMAP / MetaGPT). Coverage and "tests pass" are
gameable proxies the implementer controls; this harness forbids trusting them and
demands the real artifact instead.

Design mirrors the journey-coverage hook: a PURE, testable core (evidence
correlation, reward-hack scan, reviewer routing, prompt build, verdict parse)
separated from thin IO/subprocess edges. Stdlib only. Fail-soft: the gather step
is advisory (exit 0) unless --strict is set with a dispatched BLOCK verdict.

Usage:
    python acceptance_review.py [--repo DIR] [--base REF] [--out DIR]
        [--reviewer auto|codex|gemini|claude] [--dispatch]
        [--model NAME] [--timeout SECS] [--strict] [--json]

Without --dispatch it writes the evidence bundle + rendered review prompt and
prints the routing decision (which reviewer, and the EXACT command / fresh-Claude
instruction to run it). With --dispatch it shells out to the chosen cross-model
CLI and prints the returned verdict; if the only available reviewer is a fresh
Claude subagent, it prints the Task-tool instruction for the orchestrator (a
Python process cannot spawn a Claude subagent itself).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Journey / E2E spec signatures (shared vocabulary with the journey-coverage    #
# hook so "declared journey" means the same thing across the gems).             #
# --------------------------------------------------------------------------- #
_SPEC_GLOBS = (
    "**/*golden*journey*.spec.*",
    "**/*golden-journey*.spec.*",
    "**/e2e/**/*.spec.*",
    "**/e2e/**/*.test.*",
    "**/*.e2e.spec.*",
    "**/*.e2e.test.*",
    "**/*journey*.spec.*",
    "**/cypress/e2e/**/*.cy.*",
    "**/tests/e2e/**/*.py",
    "**/playwright/**/*.spec.*",
)

# On-disk PROOF that a journey ran and produced a real artifact (not a green log).
_ARTIFACT_GLOBS = (
    "**/job.done",
    "**/*.mp4",
    "**/*.mov",
    "**/*.webm",
    "**/playwright-report/**/*",
    "**/test-results/**/*",
    "**/e2e/**/artifacts/**/*",
    "**/e2e/**/screenshots/**/*",
    "**/e2e/**/*.png",
    "**/reports/**/*.html",
    "**/reports/**/*.xml",
    "**/*.trace.zip",
)

# Dirs never worth scanning for journey SPECS (build output, deps, caches).
_SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "out",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

# Artifacts legitimately live in build-OUTPUT dirs (a rendered short in ``out/``,
# a Playwright HTML report in ``dist/``), so artifact discovery uses a much
# NARROWER skip set — deps and caches only, never the output dirs themselves.
_ARTIFACT_SKIP_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

# --------------------------------------------------------------------------- #
# Reward-hack surface: added lines in the diff that WEAKEN the exam or hide a    #
# broken journey. This is exactly where gaming hides (AGENTIC-REPAIR-           #
# RELIABILITY.md §2). Each pattern matches an *added* diff line ("+ ...").       #
# --------------------------------------------------------------------------- #
_REWARD_HACK_PATTERNS = (
    ("pragma_no_cover", re.compile(r"#\s*pragma:\s*no\s*cover", re.IGNORECASE)),
    ("xfail", re.compile(r"\bxfail\b", re.IGNORECASE)),
    (
        "skip_marker",
        re.compile(
            r"@?(?:pytest\.mark\.)?skip\b|\.skip\s*\(|\bit\.skip\b|\bdescribe\.skip\b"
            r"|\btest\.skip\b|\bxit\b|\bxdescribe\b",
            re.IGNORECASE,
        ),
    ),
    ("coverage_omit", re.compile(r"\bomit\s*=|collectCoverageFrom", re.IGNORECASE)),
    (
        "coverage_threshold_drop",
        re.compile(r"--cov-fail-under|coverageThreshold|fail_under", re.IGNORECASE),
    ),
    (
        "marker_deselect",
        re.compile(r"-m\s+['\"]?not\s+e2e|addopts|--ignore\b|--deselect\b", re.IGNORECASE),
    ),
    (
        "ci_trigger_edit",
        re.compile(r"if:\s*false|continue-on-error:\s*true|--no-verify", re.IGNORECASE),
    ),
)

_VERDICT_RE = re.compile(r"\bVERDICT\b\s*[:=]\s*\**\s*(SHIP|BLOCK)\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Pure core                                                                     #
# --------------------------------------------------------------------------- #
def scan_reward_hack(diff_text: str) -> list[dict]:
    """Return reward-hack findings from ADDED (``+``) diff lines only.

    Pure: operates on the unified-diff string, so it is trivially testable and
    can never touch the repo. Removed lines (``-``) and hunk headers (``+++``)
    are ignored — we only care about newly *introduced* exam-weakening.
    """
    findings: list[dict] = []
    for raw in diff_text.splitlines():
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        added = raw[1:]
        for name, pat in _REWARD_HACK_PATTERNS:
            if pat.search(added):
                findings.append({"kind": name, "line": added.strip()[:200]})
    return findings


def choose_reviewer(pref: str, available: dict[str, bool]) -> tuple[str, str]:
    """Route to the best independent reviewer, degrading gracefully.

    Preference order for a genuinely cross-model verifier: codex > gemini, and a
    fresh-context Claude subagent as the always-available floor. Returns
    ``(reviewer, reason)``. ``pref='auto'`` picks the best present CLI; an
    explicit pref is honoured when available, else falls through with a reason.
    """
    order = ["codex", "gemini"]
    if pref in ("codex", "gemini"):
        if available.get(pref):
            return pref, f"{pref} CLI present (explicit request)"
        # explicit but absent -> fall back down the chain, noting the miss
        for cli in order:
            if cli != pref and available.get(cli):
                return cli, f"{pref} absent; using {cli} (cross-model)"
        return "claude", f"{pref} absent and no other cross-model CLI; fresh Claude subagent"
    if pref == "claude":
        return "claude", "fresh Claude subagent (explicit request)"
    # auto
    for cli in order:
        if available.get(cli):
            return cli, f"{cli} CLI present (best available cross-model)"
    return "claude", "no cross-model CLI on PATH; fresh-context Claude subagent"


def parse_verdict(text: str) -> str | None:
    """Extract SHIP/BLOCK from a reviewer's structured reply, or None.

    Conservative: if the review never emits a parseable ``VERDICT: SHIP/BLOCK``
    token we return None (caller treats an unparseable verdict as inconclusive,
    NOT as a pass — never green-by-default).
    """
    m = _VERDICT_RE.search(text or "")
    return m.group(1).upper() if m else None


def _rel(p: Path, base: Path) -> str:
    try:
        return p.relative_to(base).as_posix()
    except ValueError:
        return p.as_posix()


# --------------------------------------------------------------------------- #
# IO edges: git + filesystem                                                    #
# --------------------------------------------------------------------------- #
def _run_git(repo: Path, args: list[str], timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.stdout if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def detect_base(repo: Path, explicit: str | None) -> str:
    """Resolve the diff base ref: explicit > merge-base with a mainline > HEAD~1."""
    if explicit:
        return explicit
    for mainline in ("origin/main", "main", "origin/master", "master", "develop"):
        mb = _run_git(repo, ["merge-base", "HEAD", mainline]).strip()
        if mb:
            return mb
    head1 = _run_git(repo, ["rev-parse", "HEAD~1"]).strip()
    return head1 or "HEAD"


def git_diff(repo: Path, base: str, max_diff_chars: int = 60000) -> dict:
    """Collect the change set: stat, changed files, and a (truncated) unified diff."""
    stat = _run_git(repo, ["diff", "--stat", f"{base}...HEAD"])
    if not stat:  # base may not be an ancestor (detached / no merge-base) -> two-dot
        stat = _run_git(repo, ["diff", "--stat", base, "HEAD"])
        two_dot = True
    else:
        two_dot = False
    rng = [base, "HEAD"] if two_dot else [f"{base}...HEAD"]
    files_raw = _run_git(repo, ["diff", "--name-only", *rng])
    changed = [f for f in files_raw.splitlines() if f.strip()]
    unified = _run_git(repo, ["diff", *rng])
    truncated = len(unified) > max_diff_chars
    return {
        "base": base,
        "stat": stat.strip(),
        "changed_files": changed,
        "unified_diff": unified[:max_diff_chars],
        "diff_truncated": truncated,
    }


def _walk_glob(repo: Path, globs: tuple[str, ...], skip: set[str]) -> list[Path]:
    found: set[Path] = set()
    for pattern in globs:
        for p in repo.glob(pattern):
            if not p.is_file():
                continue
            if any(part in skip for part in p.parts):
                continue
            found.add(p)
    return sorted(found)


def find_journey_specs(repo: Path) -> list[str]:
    """Declared journey/E2E spec files (repo-relative POSIX paths, sorted)."""
    return [_rel(p, repo) for p in _walk_glob(repo, _SPEC_GLOBS, _SKIP_DIRS)]


def find_artifacts(repo: Path, newer_than: float = 0.0, limit: int = 40) -> list[dict]:
    """On-disk artifacts that PROVE a journey ran, sorted newest-first.

    ``newer_than`` (epoch secs) flags whether the artifact post-dates the change
    under review — a stale artifact from last week is not evidence THIS change
    works. We report mtime + a ``fresh`` flag rather than silently dropping old
    ones, so the reviewer can weigh recency itself.
    """
    out: list[dict] = []
    for p in _walk_glob(repo, _ARTIFACT_GLOBS, _ARTIFACT_SKIP_DIRS):
        try:
            st = p.stat()
        except OSError:
            continue
        out.append(
            {
                "path": _rel(p, repo),
                "bytes": st.st_size,
                "mtime": int(st.st_mtime),
                "fresh": st.st_mtime >= newer_than if newer_than else None,
            }
        )
    out.sort(key=lambda d: d["mtime"], reverse=True)
    return out[:limit]


def probe_clis() -> dict[str, bool]:
    """Which independent-reviewer CLIs are actually on PATH (real availability)."""
    return {"codex": shutil.which("codex") is not None, "gemini": shutil.which("gemini") is not None}


# --------------------------------------------------------------------------- #
# Prompt construction (the adversarial IP)                                      #
# --------------------------------------------------------------------------- #
_PROMPT_HEADER = """\
You are an INDEPENDENT acceptance reviewer at the "done" boundary of an app change.
You did NOT write this code. Your one job: decide whether the real end-to-end user
journey actually WORKS, or whether this is green-but-broken (tests pass / coverage
high, but a button is dead, "shorts don't generate", the A->B->C flow is severed).

ADVERSARIAL STANCE — assume green-but-broken until an ARTIFACT proves otherwise:
  1. For EACH declared journey below, trace the real user path and name where it
     could fail at runtime (a mocked seam, an OS/path/permission edge, an unwired
     handler, a swallowed error). Be concrete about the failing step.
  2. DEMAND THE ARTIFACT. A journey is only proven if a real output exists on disk
     and post-dates this change (the produced .mp4 / screenshot / job.done / report
     that a human could open), NOT a unit test and NOT a coverage number.
  3. FORBIDDEN as proof: "coverage is 100%", "all tests pass", "the unit test for
     X passes". These are gameable proxies the implementer controls. Ignore them.
  4. INSPECT THE REWARD-HACK SURFACE. Net-new pragma:no-cover / xfail / skip /
     coverage-omit / marker-deselect / CI-disable in the diff is where gaming
     hides — treat any such change as suspect and call it out.
  5. If a journey spec EXISTS on disk but there is no artifact showing it ran this
     change, it is UNPROVEN — list it. Unproven != passing.

You MUST end your reply with EXACTLY this block, filled in (machine-parsed):

VERDICT: SHIP or BLOCK
UNPROVEN_JOURNEYS: comma-separated spec paths with no post-change artifact, or NONE
GAPS: the concrete runtime failures / severed steps you found, or NONE
REWARD_HACK_FINDINGS: exam-weakening diff changes, or NONE
DEMANDED_ARTIFACTS: the exact output files you require to flip BLOCK->SHIP
CONFIDENCE: 0.0-1.0
RATIONALE: 2-4 sentences. Do not cite coverage or "tests pass" as evidence.

Rule: SHIP only if EVERY declared journey has a real post-change artifact proving
the flow. If there are zero declared journeys, that itself is a BLOCK-worthy gap
(no held-out done-signal exists) — say so.
"""


def build_prompt(evidence: dict) -> str:
    """Render the full adversarial review prompt from the gathered evidence."""
    diff = evidence["diff"]
    journeys = evidence["journeys"]
    artifacts = evidence["artifacts"]
    hacks = evidence["reward_hack"]

    def _bullets(items: list[str], empty: str) -> str:
        return "\n".join(f"  - {i}" for i in items) if items else f"  ({empty})"

    journey_lines = _bullets(journeys, "NONE DECLARED — this is itself a gap")
    art_lines = (
        "\n".join(
            f"  - {a['path']}  ({a['bytes']} bytes, mtime={a['mtime']}"
            + (f", fresh={a['fresh']}" if a["fresh"] is not None else "")
            + ")"
            for a in artifacts
        )
        if artifacts
        else "  (NONE FOUND — no on-disk proof any journey produced output)"
    )
    hack_lines = (
        "\n".join(f"  - [{h['kind']}] {h['line']}" for h in hacks)
        if hacks
        else "  (none detected in the diff)"
    )
    diff_note = " (TRUNCATED — read files directly if you need more)" if diff["diff_truncated"] else ""

    return f"""{_PROMPT_HEADER}

================================================================================
CHANGE UNDER REVIEW  (base: {diff['base']})
================================================================================
Changed files:
{_bullets(diff['changed_files'], 'no files changed')}

Diffstat:
{diff['stat'] or '  (empty)'}

================================================================================
DECLARED JOURNEYS / E2E SPECS ON DISK
================================================================================
{journey_lines}

================================================================================
ARTIFACT EVIDENCE (on-disk proof the journeys ran)
================================================================================
{art_lines}

================================================================================
REWARD-HACK SURFACE (net-new exam-weakening in the diff — where gaming hides)
================================================================================
{hack_lines}

================================================================================
UNIFIED DIFF{diff_note}
================================================================================
{diff['unified_diff'] or '(no diff content)'}
"""


def build_reviewer_command(
    reviewer: str, prompt_file: Path, repo: Path, model: str | None
) -> list[str] | None:
    """Exact argv to run the chosen cross-model reviewer, or None for Claude.

    Codex and Gemini are driven in READ-ONLY mode (they may open the artifact to
    verify it, but never mutate the repo). The prompt is passed as a single argv
    element (subprocess list form — no shell quoting hazard). Returns None for the
    'claude' reviewer because a fresh Claude subagent must be spawned by the
    orchestrating agent via the Task tool, not by this process.
    """
    prompt = prompt_file.read_text(encoding="utf-8")
    if reviewer == "codex":
        argv = ["codex", "exec", "-s", "read-only", "-C", str(repo), "--skip-git-repo-check"]
        if model:
            argv += ["-m", model]
        argv.append(prompt)
        return argv
    if reviewer == "gemini":
        argv = ["gemini", "--approval-mode", "plan", "-o", "text"]
        if model:
            argv += ["-m", model]
        argv += ["-p", prompt]
        return argv
    return None


def dispatch_cli(argv: list[str], repo: Path, timeout: int) -> dict:
    """Run a cross-model reviewer CLI and capture its verdict text."""
    try:
        proc = subprocess.run(
            argv,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return {"returncode": proc.returncode, "output": out, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return {"returncode": None, "output": partial, "timed_out": True}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"returncode": None, "output": f"dispatch error: {exc}", "timed_out": False}


# --------------------------------------------------------------------------- #
# Orchestration                                                                 #
# --------------------------------------------------------------------------- #
def gather(repo: Path, base_ref: str | None) -> dict:
    """Collect the full evidence bundle for the reviewer."""
    base = detect_base(repo, base_ref)
    diff = git_diff(repo, base)
    # Freshness anchor: the mtime of the newest changed file (best-effort).
    newest = 0.0
    for f in diff["changed_files"]:
        try:
            newest = max(newest, (repo / f).stat().st_mtime)
        except OSError:
            continue
    return {
        "repo": str(repo),
        "diff": diff,
        "journeys": find_journey_specs(repo),
        "artifacts": find_artifacts(repo, newer_than=newest),
        "reward_hack": scan_reward_hack(diff["unified_diff"]),
        "clis": probe_clis(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cross-model acceptance-review harness.")
    ap.add_argument("--repo", default=os.getcwd(), help="Target repo (default: cwd).")
    ap.add_argument("--base", default=None, help="Diff base ref (default: auto merge-base).")
    ap.add_argument("--out", default=None, help="Output dir for evidence + prompt.")
    ap.add_argument(
        "--reviewer",
        default="auto",
        choices=["auto", "codex", "gemini", "claude"],
        help="Reviewer preference (default: auto = best cross-model CLI).",
    )
    ap.add_argument("--model", default=None, help="Model override for the reviewer CLI.")
    ap.add_argument("--dispatch", action="store_true", help="Actually run the CLI reviewer.")
    ap.add_argument("--timeout", type=int, default=240, help="Dispatch timeout secs.")
    ap.add_argument("--strict", action="store_true", help="Exit 20 on a dispatched BLOCK verdict.")
    ap.add_argument("--json", action="store_true", help="Print the evidence bundle as JSON.")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"acceptance-review: repo not a directory: {repo}\n")
        return 1

    evidence = gather(repo, args.base)
    reviewer, reason = choose_reviewer(args.reviewer, evidence["clis"])
    evidence["routing"] = {"reviewer": reviewer, "reason": reason}

    out_dir = Path(args.out).resolve() if args.out else repo / ".acceptance-review"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(evidence)
    prompt_file = out_dir / "review-prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    (out_dir / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(evidence, indent=2))

    # Human/orchestrator-facing routing summary.
    print("=" * 72)
    print("ACCEPTANCE-REVIEW  —  evidence gathered")
    print("=" * 72)
    print(f"repo            : {repo}")
    print(f"base            : {evidence['diff']['base']}")
    print(f"changed files   : {len(evidence['diff']['changed_files'])}")
    print(f"declared journeys: {len(evidence['journeys'])}  {evidence['journeys'] or '(NONE)'}")
    print(f"artifacts found : {len(evidence['artifacts'])}")
    print(f"reward-hack hits: {len(evidence['reward_hack'])}")
    print(f"CLIs on PATH    : codex={evidence['clis']['codex']} gemini={evidence['clis']['gemini']}")
    print(f"reviewer        : {reviewer}  ({reason})")
    print(f"prompt written  : {prompt_file}")
    print("=" * 72)

    cmd = build_reviewer_command(reviewer, prompt_file, repo, args.model)

    if reviewer == "claude" or cmd is None:
        print(
            "\nNO cross-model CLI available (or --reviewer claude): spawn a FRESH-CONTEXT\n"
            "Claude subagent (Task tool, general-purpose/Explore) whose ONLY input is the\n"
            "prompt file below — do NOT paste your own reasoning. The subagent must return\n"
            "the VERDICT block.\n"
            f"    prompt: {prompt_file}\n"
        )
        return 0

    if not args.dispatch:
        print("\nTo run the independent review, either re-run with --dispatch, or execute:")
        print("    " + " ".join(_shellish(a) for a in cmd[:-1]) + " <prompt-from-file>")
        print(f"(prompt is in {prompt_file}; pass it as the final argument)\n")
        return 0

    print(f"\nDispatching to {reviewer} (timeout {args.timeout}s)…\n")
    result = dispatch_cli(cmd, repo, args.timeout)
    verdict = parse_verdict(result["output"])
    print(result["output"])
    print("-" * 72)
    if result["timed_out"]:
        print(f"REVIEWER TIMED OUT after {args.timeout}s — verdict INCONCLUSIVE (treat as BLOCK).")
        verdict = verdict or "BLOCK"
    print(f"PARSED VERDICT  : {verdict or 'INCONCLUSIVE (no VERDICT token — treat as BLOCK)'}")
    (out_dir / "verdict.txt").write_text(result["output"], encoding="utf-8")

    if args.strict and (verdict == "BLOCK" or verdict is None):
        return 20
    return 0


def _shellish(arg: str) -> str:
    """Best-effort display quoting for the printed command (cosmetic only)."""
    return f'"{arg}"' if (" " in arg or not arg) else arg


if __name__ == "__main__":
    sys.exit(main())
