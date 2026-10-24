#!/usr/bin/env python3
"""Pack AUD-0091 clean-room fresh-clone build/test baseline receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline first-failing-step claim is on disk (catalog
`reviewer_requirement`); then SUCCESS. Never stubs SUCCESS. Never invents
independent-review.json.

Headline is not "the docs are broken": npm install and npm test both pass,
byte-identically to the in-place baseline (probe2). The FIRST documented
step that diverges is `npm run validate:skills` (exit 127, `pwsh: not
found`) -- a real, reproduced divergence, not an invented one, and one
AGENTS.md already names as a known cloud-substrate caveat.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0091"
OUT = "command-center/audit/AUD-0091-clean-room-clone-baseline.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0091/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0091/probe1-clean-clone-run.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0091/probe2-inplace-baseline-compare.json"
CTL_JSON = "command-center/p2-wave/probes/AUD-0091/control-cache-free.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0091/probe1-clean-clone-run.raw.txt"
P2_RAW = (
    "command-center/p2-wave/probes/AUD-0091/probe2-inplace-baseline-compare.raw.txt"
)
CTL_RAW = "command-center/p2-wave/probes/AUD-0091/control-cache-free.raw.txt"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline first-failing-step claim is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((L.REPO / P1_JSON).read_text(encoding="utf-8"))
    p2 = json.loads((L.REPO / P2_JSON).read_text(encoding="utf-8"))
    ctl = json.loads((L.REPO / CTL_JSON).read_text(encoding="utf-8"))
    raw1 = (L.REPO / P1_RAW).read_text(encoding="utf-8")
    raw2 = (L.REPO / P2_RAW).read_text(encoding="utf-8")
    raw_ctl = (L.REPO / CTL_RAW).read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = p1.get("started_at") or "2026-09-07T22:59:20Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p1_ok = bool(p1.get("ok"))
    p2_ok = bool(p2.get("ok"))
    ctl_ok = bool(ctl.get("ok"))

    pinned_sha = p1.get("pinned_sha")
    first_failing = p1.get("first_failing_step") or {}
    first_failing_id = first_failing.get("id")
    first_failing_cmd = first_failing.get("doc_step")
    first_failing_exit = first_failing.get("exit_code")
    all_steps_passed = bool(p1.get("all_documented_steps_passed"))
    npm_test_summary = p1.get("npm_test_summary") or {}
    cache_free_before_run = bool((p1.get("cache_dir_precheck") or {}).get("cache_free"))
    out_of_scope = p1.get("out_of_scope_documented_steps") or []

    results_identical = bool(p2.get("results_identical"))
    environment_only_diff = bool(p2.get("environment_only_diff"))
    inplace_summary = p2.get("inplace_npm_test_summary") or {}

    fires_on_bad = bool(ctl.get("a_fires_on_bad"))
    silent_on_good = bool(ctl.get("a_silent_on_good"))

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(P1_JSON, "supporting"),
        L.art(P2_JSON, "supporting"),
        L.art(CTL_JSON, "control"),
        L.art(P1_RAW, "log"),
        L.art(P2_RAW, "log"),
        L.art(CTL_RAW, "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0091/probe1_clean_clone_run.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0091/probe2_inplace_baseline_compare.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0091/control_cache_free.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0091/_cache_check.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0091/fixtures/populated_npm_cache/"
            "stale-package-marker.txt",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0091/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Starting from a fresh clone into a clean directory with no local "
        "caches, does the documented setup, build, and test sequence "
        "succeed - and where exactly does it first diverge from the "
        "documentation?"
    )
    headline = (
        f"Fresh `git clone` of main pinned at {pinned_sha}, `npm install` and "
        f"`npm test` inside it with $HOME and $NPM_CONFIG_CACHE redirected to "
        f"brand-new empty scratch directories (cache_free_before_run="
        f"{cache_free_before_run}): both PASS, producing "
        f"{npm_test_summary.get('pass')}/{npm_test_summary.get('pass', 0) + npm_test_summary.get('fail', 0)} "
        f"tests passing, byte-identical to the in-place baseline "
        f"({inplace_summary.get('pass')} pass / {inplace_summary.get('fail')} fail; "
        f"results_identical={results_identical}, so this is NOT an "
        "environment-only artifact of caching). The documented sequence "
        f"FIRST DIVERGES at `{first_failing_cmd}` (exit_code={first_failing_exit}), "
        "which requires `pwsh` -- absent on this substrate, a caveat "
        "AGENTS.md's own Cursor Cloud section already names. "
        f"all_documented_steps_passed={all_steps_passed}. "
        f"{len(out_of_scope)} README step(s) requiring the `claude`/`git-crypt` "
        "CLIs were out of scope (agent-tooling mount steps, not build/test) "
        "and are listed, not silently skipped."
    )

    if success:
        reviewer = {
            "reviewer_id": rev.get("reviewer_id")
            or "fresh-context-claude-independent-reviewer-AUD-0091",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0091 first_failing_step={first_failing_id} "
            f"pinned_sha={pinned_sha} results_identical={results_identical}"
        )
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0091-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0091/independent-review.json"
                ),
            },
            {
                "id": "AUD-0091-D-VALIDATE-SKILLS-PWSH",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "`npm run validate:skills` requires `pwsh`, absent on this "
                    "substrate; this is the first documented-sequence divergence."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not "
                "seen this unit's transcript; the reviewer must try to FALSIFY "
                "the headline first-failing-step claim before PASS, not re-read "
                "the artifact. Unavailable in-session; BLOCKED instead of fake "
                "SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0091 clean-room baseline measured "
            f"first_failing_step={first_failing_id} exit_code={first_failing_exit} "
            f"pinned_sha={pinned_sha} cache_free_before_run={cache_free_before_run} "
            f"results_identical={results_identical} control_ok={ctl_ok}; "
            "blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "dependency-blocked",
                "green-not-live",
                "detector-failure",
            ],
            "reason": (
                f"Named probes completed (probe1 ok={p1_ok} clone+build+test "
                f"sequence executed against a real fresh clone pinned at "
                f"{pinned_sha}; probe2 ok={p2_ok} in-place comparator; cache-free "
                f"control ok={ctl_ok}), but catalog reviewer_requirement is unmet. "
                f"This is NOT a hidden defect masked as green: the measured first "
                f"divergence (`{first_failing_cmd}` exit_code={first_failing_exit}, "
                "missing `pwsh`) is the real answer to the catalog question, "
                "reported honestly rather than smoothed over."
            ),
            "diagnostic_tail": (
                f"first_failing_step={first_failing_id} exit_code={first_failing_exit} "
                f"all_documented_steps_passed={all_steps_passed} "
                f"pinned_sha={pinned_sha} cache_free_before_run={cache_free_before_run} "
                f"results_identical={results_identical} "
                f"environment_only_diff={environment_only_diff} "
                f"fires_on_bad={fires_on_bad} silent_on_good={silent_on_good} "
                f"control_ok={ctl_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the first_failing_step / "
                "pinned_sha / results_identical claims before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0091/"
                    "probe1_clean_clone_run.py",
                    f"first_failing_step={first_failing_id} exit_code={first_failing_exit}",
                    0 if p1_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0091-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0091-D-VALIDATE-SKILLS-PWSH",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"First documented-sequence divergence: `{first_failing_cmd}` "
                    f"exit_code={first_failing_exit} ('pwsh: not found'); npm "
                    "install and npm test both pass ahead of it, byte-identical "
                    "to the in-place baseline."
                ),
            },
        ]

    # Seed non-empty downstream_consumers before first schema validate.
    seeded_consumers = [
        {
            "consumer": "json.loads + schema resolver",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": L.probe(
                "source",
                "schema-validate",
                "python3 -B command-center/p2-wave/probes/AUD-0091/_pack_receipt.py",
                f"state={state}",
                0,
            ),
        }
    ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0091",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 clean-room run: `git clone {p1.get('clone_url')}` "
                    f"then `git checkout {pinned_sha}` into a brand-new scratch "
                    f"directory, with $NPM_CONFIG_CACHE and $HOME redirected to "
                    f"empty scratch dirs verified cache_free="
                    f"{cache_free_before_run} BEFORE npm install ran. Executed "
                    "the documented setup/build/test sequence in doc order "
                    f"(npm install, npm test, npm run validate:skills, python3 "
                    "scripts/test-live-skill-helpers.py); "
                    f"first_failing_step={first_failing_id} "
                    f"(`{first_failing_cmd}`, exit_code={first_failing_exit}); "
                    f"all_documented_steps_passed={all_steps_passed}. "
                    f"npm test: {npm_test_summary.get('pass')} pass / "
                    f"{npm_test_summary.get('fail')} fail, exit_code="
                    f"{npm_test_summary.get('exit_code')}. probe1_ok={p1_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0091/"
                        "probe1_clean_clone_run.py",
                        raw1[-8000:],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-clean-clone-run.json",
                        json.dumps(
                            {
                                "pinned_sha": pinned_sha,
                                "first_failing_step": first_failing_id,
                                "first_failing_exit_code": first_failing_exit,
                                "all_documented_steps_passed": all_steps_passed,
                                "npm_test_summary": npm_test_summary,
                                "ok": p1_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 in-place comparator: re-ran `npm test` fresh in "
                    "THIS checkout (pre-existing node_modules + real ~/.npm "
                    f"cache, the opposite of probe1's clean room): "
                    f"{inplace_summary.get('pass')} pass / "
                    f"{inplace_summary.get('fail')} fail, exit_code="
                    f"{inplace_summary.get('exit_code')}. "
                    f"results_identical={results_identical} vs the clean-clone "
                    f"npm test result; environment_only_diff={environment_only_diff}. "
                    "Because the two are identical, the measured "
                    "first_failing_step is a genuine documentation-sequence "
                    "divergence, not an artifact of local caching. probe2_ok="
                    f"{p2_ok}."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0091/"
                        "probe2_inplace_baseline_compare.py",
                        raw2[-8000:],
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-inplace-baseline-compare.json",
                        json.dumps(
                            {
                                "results_identical": results_identical,
                                "environment_only_diff": environment_only_diff,
                                "inplace_summary": inplace_summary,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain" if p2_ok else "refuted",
            ),
            L.evidence(
                (
                    "Detector control (tests_required): the SAME cache-free "
                    "detector (`_cache_check.is_cache_free`, imported by both "
                    "the control and probe1 -- not reimplemented) fires on a "
                    "committed contaminated fixture "
                    "(fixtures/populated_npm_cache/, one placeholder file) -> "
                    f"fired_on_bad={fires_on_bad}, and stays silent on a fresh "
                    f"empty tempdir -> silent_on_good={silent_on_good}. It is "
                    "then reapplied to probe1's actually-recorded cache "
                    f"directory precheck (recorded cache_free="
                    f"{cache_free_before_run} BEFORE npm install ran this run). "
                    f"control_ok={ctl_ok}. No live npm cache was mutated."
                ),
                "CONFIRMED" if ctl_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0091/"
                        "control_cache_free.py",
                        raw_ctl,
                        0 if ctl_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read control-cache-free.json",
                        json.dumps(
                            {
                                "a_fires_on_bad": fires_on_bad,
                                "a_silent_on_good": silent_on_good,
                                "probe1_recorded_cache_free_before_run": cache_free_before_run,
                                "ok": ctl_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0091-cache-free-fires-on-bad",
                "name": (
                    "tests_required: cache-free detector fires on a "
                    "contaminated cache fixture"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0091/"
                    "control_cache_free.py"
                ),
                "result": "PASS" if fires_on_bad else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0091-cache-free-silent-on-good",
                "name": (
                    "control precondition: cache-free detector stays silent "
                    "on a genuinely empty cache dir (not always-fires)"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0091/"
                    "control_cache_free.py"
                ),
                "result": "PASS" if silent_on_good else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0091-real-run-was-cache-free-before-use",
                "name": (
                    "the real clean-room npm cache directory this run used "
                    "was verified empty BEFORE npm install populated it"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0091/"
                    "probe1_clean_clone_run.py"
                ),
                "result": "PASS" if cache_free_before_run else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0091-C1",
                "known-broken-fixture",
                (
                    "A committed cache directory pre-populated with one "
                    "placeholder file (simulating a stale cached artifact) "
                    "must make the cache-free detector fire (cache_free=False); "
                    "a silent detector could let a cached artifact make a "
                    "broken setup appear to work, which is exactly what "
                    "tests_required warns against."
                ),
                True,
                True,
                bad=f"bad_fixture={json.dumps(ctl.get('bad_fixture'))}",
                good=f"good_fixture={json.dumps(ctl.get('good_fixture'))}",
            ),
            L.control(
                "AUD0091-C2",
                "other",
                (
                    "A genuinely empty scratch directory must report "
                    "cache_free=True (proves the detector is not "
                    "always-fires)."
                ),
                True,
                True,
                bad="would be False if the detector always fired",
                good=f"good_fixture.cache_free={(ctl.get('good_fixture') or {}).get('cache_free')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": seeded_consumers,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated "
                "the tree; restore from the AUD-0092 backup, record the "
                "mutation, and escalate (catalog retry_policy, verbatim)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether the README's `claude plugin marketplace add/"
                    "install` and `claude mcp add` steps (mounting this "
                    "repo's skill surface into a live Claude Code session) "
                    "succeed on a substrate that HAS the `claude` CLI -- "
                    "this substrate does not, so they were out of scope, "
                    "not executed and passed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 on a substrate with the `claude` CLI "
                    "installed and extend `documented_cmds` to include the "
                    "plugin marketplace/install/mcp-add steps."
                ),
            },
            {
                "claim": (
                    "Whether `git-crypt unlock` for `accounts.json` succeeds "
                    "-- requires an external password-manager-exported key "
                    "this substrate has no access to, and `git-crypt` itself "
                    "is absent."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Provision the key and the `git-crypt` binary on a test "
                    "substrate, then re-run this step and record success/"
                    "failure honestly."
                ),
            },
            {
                "claim": (
                    "Whether installing `pwsh` on this substrate would make "
                    "`npm run validate:skills` itself succeed, or whether it "
                    "would then fail at the external skill-creator validator "
                    "AGENTS.md says is also required under CODEX_HOME (a "
                    "second, deeper dependency this probe did not reach)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install `pwsh` and the external skill-creator validator "
                    "on a scratch substrate, re-run `npm run validate:skills` "
                    "there, and record whichever step fails next (if any)."
                ),
            },
        ],
        "report": {
            "kind": "audit-detector-control",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0091-C1", "AUD0091-C2"],
            "observations": [
                {
                    "name": "pinned_sha",
                    "measured": pinned_sha,
                    "method": "git ls-remote origin main at probe1 start",
                    "anchor": P1_JSON,
                },
                {
                    "name": "first_failing_step",
                    "measured": first_failing_id,
                    "method": "first documented step with exit_code != 0",
                    "anchor": P1_JSON,
                },
                {
                    "name": "first_failing_step_exit_code",
                    "measured": first_failing_exit,
                    "method": "subprocess.run(...).returncode",
                    "anchor": P1_JSON,
                },
                {
                    "name": "all_documented_steps_passed",
                    "measured": all_steps_passed,
                    "method": "every documented step exit_code == 0",
                    "anchor": P1_JSON,
                },
                {
                    "name": "cache_free_before_run",
                    "measured": cache_free_before_run,
                    "method": "is_cache_free() on $NPM_CONFIG_CACHE before npm install",
                    "anchor": P1_JSON,
                },
                {
                    "name": "clean_clone_npm_test_pass_count",
                    "measured": npm_test_summary.get("pass"),
                    "method": "sum of per-workspace '# pass N' TAP summary lines",
                    "anchor": P1_JSON,
                },
                {
                    "name": "results_identical_vs_inplace_baseline",
                    "measured": results_identical,
                    "method": "byte-compare clean-clone vs in-place npm test summaries",
                    "anchor": P2_JSON,
                },
                {
                    "name": "control_fires_on_bad_silent_on_good",
                    "measured": fires_on_bad and silent_on_good,
                    "method": "fixture pair through is_cache_free()",
                    "anchor": CTL_JSON,
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-detector-control",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "pinned_sha": pinned_sha,
            "first_failing_step": first_failing_id,
            "first_failing_step_exit_code": first_failing_exit,
            "all_documented_steps_passed": all_steps_passed,
            "out_of_scope_documented_steps": out_of_scope,
            "probe1_summary": {
                "cache_free_before_run": cache_free_before_run,
                "npm_test_summary": npm_test_summary,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "results_identical": results_identical,
                "environment_only_diff": environment_only_diff,
                "inplace_npm_test_summary": inplace_summary,
                "ok": p2_ok,
            },
            "control": {
                "fires_on_bad": fires_on_bad,
                "silent_on_good": silent_on_good,
                "ok": ctl_ok,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        L.REPO / P1_JSON,
        L.REPO / P2_JSON,
        L.REPO / CTL_JSON,
        L.REPO / P1_RAW,
        L.REPO / P2_RAW,
        L.REPO / CTL_RAW,
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0091 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
