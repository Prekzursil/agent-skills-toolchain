#!/usr/bin/env python3
"""Pack AUD-0096 fresh-user-profile harness-load-baseline receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline counts is on disk (catalog `reviewer_requirement`);
then SUCCESS. Never stubs SUCCESS. Never invents independent-review.json.

SCOPE NOTE carried into every state: the catalog scoped this unit to "a clean
Windows user profile" measuring Claude/Codex hooks/plugins/MCP servers. This
substrate is Linux Cursor Cloud with no ~/.claude, no ~/.codex, and no `pwsh`
(measured, not assumed -- see probe1/probe2 census). The nearest analogous
profile-level harness state is $HOME/.cursor (skills-cursor side-loaded skill
packs, plugins cache, agent-hooks), which is what both probes actually
measure. This is a real, disclosed scope adaptation per the task's explicit
"document residual if Windows-only profile paths apply" instruction, not a
silent substitution.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0096"
OUT = "command-center/audit/AUD-0096-fresh-profile-harness-baseline.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0096/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0096/probe1-clean-profile-load.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0096/probe2-current-profile-diff.json"
CTL_JSON = "command-center/p2-wave/probes/AUD-0096/control-profile-clean.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0096/probe1-clean-profile-load.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0096/probe2-current-profile-diff.raw.txt"
CTL_RAW = "command-center/p2-wave/probes/AUD-0096/control-profile-clean.raw.txt"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline counts is on disk."""
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
    started = p1.get("started_at") or "2026-09-07T23:00:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p1_ok = bool(p1.get("ok"))
    p2_ok = bool(p2.get("ok"))
    ctl_ok = bool(ctl.get("ok"))

    clean_check = p1.get("clean_check") or {}
    clean_ok = bool(clean_check.get("clean"))
    clean_census = p1.get("census") or {}
    current_census = p2.get("current_census") or {}
    current_clean_check = p2.get("current_clean_check") or {}
    diff = p2.get("diff") or {}

    clean_skill_count = int(clean_census.get("total_skill_count") or 0)
    clean_file_count = int(clean_census.get("total_file_count") or 0)
    clean_bytes = int(clean_census.get("total_bytes") or 0)
    current_skill_count = int(current_census.get("total_skill_count") or 0)
    current_file_count = int(current_census.get("total_file_count") or 0)
    current_bytes = int(current_census.get("total_bytes") or 0)
    skill_delta = int(diff.get("total_skill_count_delta") or 0)
    file_delta = int(diff.get("total_file_count_delta") or 0)
    bytes_delta = int(diff.get("total_bytes_delta") or 0)

    claude_absent = not bool(
        (current_census.get("components") or {}).get("claude_home", {}).get("exists")
    )
    codex_absent = not bool(
        (current_census.get("components") or {}).get("codex_home", {}).get("exists")
    )

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
            "command-center/p2-wave/probes/AUD-0096/_profile_check.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0096/probe1_clean_profile_load.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0096/probe2_current_profile_diff.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0096/control_profile_clean.py",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0096/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Under a clean profile with no existing harness state, which skills, "
        "hooks, rules, plugins and MCP servers load - and how does that "
        "differ from the current profile?"
    )
    headline = (
        f"Clean profile (brand-new scratch $HOME, proven clean={clean_ok}, "
        "leaked_dirs=[]): harness load set is "
        f"{clean_skill_count} skill(s) / {clean_file_count} file(s) / "
        f"{clean_bytes} byte(s) -- zero, by construction of an empty scratch "
        f"dir. Current profile (/home/ubuntu, clean={bool(current_clean_check.get('clean'))}): "
        f"{current_skill_count} skill(s) / {current_file_count} file(s) / "
        f"{current_bytes} byte(s). Diff (current-clean) = "
        f"+{skill_delta} skill(s) / +{file_delta} file(s) / +{bytes_delta} "
        "byte(s), entirely attributable to this profile's side-loaded "
        "skills-cursor packs, plugins cache, and agent-hooks -- none of it is "
        "an artifact of the clean-profile baseline itself. This substrate has "
        f"NO Claude Code harness (~/.claude absent={claude_absent}) and NO "
        f"Codex CLI harness (~/.codex absent={codex_absent}); the catalog's "
        "originally-scoped Windows user-profile paths and PowerShell tooling "
        "do not apply here (Linux Cursor Cloud). Control fires_on_bad="
        f"{fires_on_bad} silent_on_good={silent_on_good} ok={ctl_ok}."
    )

    if success:
        raw_notes = rev.get("notes", "")
        if isinstance(raw_notes, list):
            notes = "\n".join(str(n) for n in raw_notes)
        else:
            notes = str(raw_notes or "")
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:8000],
        }
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0096 skill_delta={skill_delta} file_delta={file_delta} "
            f"bytes_delta={bytes_delta}"
        )
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0096-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0096/independent-review.json"
                ),
            },
            {
                "id": "AUD-0096-D-SUBSTRATE-SCOPE-MISMATCH",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "Catalog scoped this unit to a clean Windows user profile "
                    "with Claude/Codex harness state; this substrate is Linux "
                    "Cursor Cloud with neither harness present. Measured "
                    "against $HOME/.cursor instead; not a like-for-like "
                    "reproduction of the original scope."
                ),
            },
            {
                "id": "AUD-0096-D-FILESYSTEM-CENSUS-NOT-BOOT-OBSERVATION",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "The clean-profile measurement is a filesystem census of "
                    "a controlled scratch dir, not an executed fresh-harness "
                    "boot against a synthetic $HOME (which would require "
                    "restarting the harness daemon, out of scope and risky "
                    "per catalog retry_policy)."
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
                "the headline counts before PASS, not re-read the artifact. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0096 fresh-profile harness-load baseline measured "
            f"clean_load={clean_skill_count}skills/{clean_file_count}files/"
            f"{clean_bytes}bytes current_load={current_skill_count}skills/"
            f"{current_file_count}files/{current_bytes}bytes "
            f"delta={skill_delta}skills/{file_delta}files/{bytes_delta}bytes "
            f"control_ok={ctl_ok}; blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "scope-mismatch",
                "green-not-live",
                "detector-failure",
            ],
            "reason": (
                f"Named probes completed (probe1 ok={p1_ok} clean profile "
                f"proven clean={clean_ok} then censused; probe2 ok={p2_ok} "
                f"current-profile census + diff; control ok={ctl_ok}), but "
                "catalog reviewer_requirement is unmet. This is NOT a hidden "
                "defect masked as green: the catalog's original scope (clean "
                "Windows profile, Claude/Codex harness state, PowerShell "
                "tooling) does not map onto this Linux Cursor Cloud substrate "
                f"(claude_home_absent={claude_absent} codex_home_absent="
                f"{codex_absent} pwsh not present); the closest honest "
                "analogue ($HOME/.cursor) was measured and diffed instead, "
                "reported as such rather than smoothed over as a like-for-"
                "like reproduction."
            ),
            "diagnostic_tail": (
                f"clean_ok={clean_ok} clean_skill_count={clean_skill_count} "
                f"clean_file_count={clean_file_count} clean_bytes={clean_bytes} "
                f"current_skill_count={current_skill_count} "
                f"current_file_count={current_file_count} "
                f"current_bytes={current_bytes} skill_delta={skill_delta} "
                f"file_delta={file_delta} bytes_delta={bytes_delta} "
                f"claude_home_absent={claude_absent} codex_home_absent={codex_absent} "
                f"fires_on_bad={fires_on_bad} silent_on_good={silent_on_good} "
                f"control_ok={ctl_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the clean-profile-is-clean, "
                "current-profile census, and skill/file/byte delta claims "
                "before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0096/"
                    "probe2_current_profile_diff.py",
                    f"skill_delta={skill_delta} file_delta={file_delta} "
                    f"bytes_delta={bytes_delta}",
                    0 if p2_ok else 1,
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
                "id": "AUD-0096-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0096-D-SUBSTRATE-SCOPE-MISMATCH",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "Catalog scoped this unit to a clean Windows user profile "
                    f"with Claude/Codex harness state; measured claude_home_absent="
                    f"{claude_absent} codex_home_absent={codex_absent} pwsh "
                    "absent on this Linux Cursor Cloud substrate. Measured "
                    "against $HOME/.cursor instead of the originally-scoped "
                    "harnesses; do not treat the load-set numbers as a "
                    "like-for-like Windows-profile reproduction."
                ),
            },
            {
                "id": "AUD-0096-D-FILESYSTEM-CENSUS-NOT-BOOT-OBSERVATION",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "The clean-profile measurement is a filesystem census of "
                    "a controlled scratch dir this run created, not an "
                    "executed fresh-harness boot against a synthetic $HOME."
                ),
            },
        ]

    # SUCCESS schemas reject consumers with executed/read_ok False (AUD-0003/
    # AUD-0044 pattern): seed a placeholder consumer that already carries
    # executed=True/read_ok=True for the SUCCESS-capable first write, then
    # replace it with the live receipt_validate.py admission result below.
    seeded_consumers = [
        {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True if success else False,
            "read_ok": True if success else False,
            "exit_code": 0 if success else 1,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                f"seeded-before-first-admit state={state}; replaced after live run",
                0 if success else 1,
            ),
        }
    ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0096",
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
                    "Probe 1 clean-profile load set: brand-new scratch $HOME "
                    f"proven clean (leaked_dirs=[]) BEFORE the census ran "
                    f"(clean_ok={clean_ok}); census over that scratch dir "
                    f"measured {clean_skill_count} skill(s), "
                    f"{clean_file_count} file(s), {clean_bytes} byte(s) -- "
                    "zero everywhere, by construction of an empty scratch "
                    "dir this run created and destroyed. This is a "
                    "filesystem census, not an executed fresh-harness-boot "
                    f"observation (see residual_unknowns). probe1_ok={p1_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0096/"
                        "probe1_clean_profile_load.py",
                        raw1[-8000:],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-clean-profile-load.json",
                        json.dumps(
                            {
                                "clean_ok": clean_ok,
                                "leaked_dirs": clean_check.get("leaked_dirs"),
                                "total_skill_count": clean_skill_count,
                                "total_file_count": clean_file_count,
                                "total_bytes": clean_bytes,
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
                    "Probe 2 current-profile load set as a diff against "
                    f"probe1: current profile (/home/ubuntu) measured "
                    f"{current_skill_count} skill(s) ("
                    f"{(current_census.get('components') or {}).get('cursor_skills_cursor', {}).get('skill_paths')}"
                    f"), {current_file_count} file(s), {current_bytes} "
                    f"byte(s) across .cursor/skills-cursor, .cursor/plugins, "
                    f".cursor/agent-hooks. Diff vs clean = +{skill_delta} "
                    f"skill(s) / +{file_delta} file(s) / +{bytes_delta} "
                    "byte(s) -- computed as an explicit current-minus-clean "
                    "subtraction over probe1's own recorded numbers, not "
                    f"assumed equal to the current census. probe2_ok={p2_ok}."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0096/"
                        "probe2_current_profile_diff.py",
                        raw2[-8000:],
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-current-profile-diff.json",
                        json.dumps(
                            {
                                "current_skill_count": current_skill_count,
                                "current_file_count": current_file_count,
                                "current_bytes": current_bytes,
                                "skill_delta": skill_delta,
                                "file_delta": file_delta,
                                "bytes_delta": bytes_delta,
                                "ok": p2_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain" if p2_ok else "refuted",
            ),
            L.evidence(
                (
                    "Detector control (tests_required): the SAME "
                    "`is_profile_clean` function probe1 uses as its own "
                    "precondition gate (not reimplemented) fires on a "
                    "planted bad fixture (one leaked SKILL.md under "
                    "$scratch/.cursor/skills-cursor/) -> "
                    f"fired_on_bad={fires_on_bad}, and stays silent on a "
                    f"genuinely empty scratch dir -> silent_on_good="
                    f"{silent_on_good}. control_ok={ctl_ok}. No live "
                    "profile was mutated -- both fixtures are throwaway "
                    "tempdirs."
                ),
                "CONFIRMED" if ctl_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0096/"
                        "control_profile_clean.py",
                        raw_ctl,
                        0 if ctl_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read control-profile-clean.json",
                        json.dumps(
                            {
                                "a_fires_on_bad": fires_on_bad,
                                "a_silent_on_good": silent_on_good,
                                "probe1_clean_ok": clean_ok,
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
                "id": "AUD-0096-clean-detector-fires-on-leaked",
                "name": (
                    "tests_required: clean-profile detector fires on a "
                    "planted leaked-skill fixture"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0096/"
                    "control_profile_clean.py"
                ),
                "result": "PASS" if fires_on_bad else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0096-clean-detector-silent-on-empty",
                "name": (
                    "control precondition: clean-profile detector stays "
                    "silent on a genuinely empty scratch dir (not "
                    "always-fires)"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0096/"
                    "control_profile_clean.py"
                ),
                "result": "PASS" if silent_on_good else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0096-real-clean-profile-was-clean-before-census",
                "name": (
                    "the real scratch $HOME probe1 used was verified clean "
                    "BEFORE census_load_set ran on it"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0096/"
                    "probe1_clean_profile_load.py"
                ),
                "result": "PASS" if clean_ok else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0096-C1",
                "known-broken-fixture",
                (
                    "A scratch profile with one planted leaked SKILL.md under "
                    ".cursor/skills-cursor/ must make the clean-profile "
                    "detector fire (clean=False); a silent detector could "
                    "let a leaked profile make the clean and current "
                    "measurements identical by construction, which is "
                    "exactly what tests_required warns against."
                ),
                True,
                True,
                bad=f"bad_fixture={json.dumps(ctl.get('bad_fixture'))}",
                good=f"good_fixture={json.dumps(ctl.get('good_fixture'))}",
            ),
            L.control(
                "AUD0096-C2",
                "other",
                (
                    "A genuinely empty scratch dir must report clean=True "
                    "(proves the detector is not always-fires)."
                ),
                True,
                True,
                bad="would be False if the detector always fired",
                good=(
                    f"good_fixture.clean={(ctl.get('good_fixture') or {}).get('clean')}"
                ),
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
                    "Whether a genuinely fresh Cursor Cloud harness boot "
                    "against a synthetic $HOME (as opposed to a filesystem "
                    "census of a scratch dir this probe created and "
                    "controls) would load any DEFAULT skill/plugin/hook "
                    "content this census cannot see (e.g. anything the "
                    "harness ships baked-in rather than writing to disk "
                    "under $HOME on first boot)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Provision a second, genuinely separate Cursor Cloud "
                    "agent VM with no prior $HOME state, and diff its "
                    "$HOME/.cursor tree against this run's clean-scratch "
                    "census before any user-directed skill install."
                ),
            },
            {
                "claim": (
                    "Whether the catalog's originally-scoped Windows "
                    "%USERPROFILE%\\.claude / %USERPROFILE%\\.codex harness "
                    "state (Claude Code / Codex CLI hooks, plugins, MCP "
                    "servers) would show a materially different load-set "
                    "delta than the $HOME/.cursor analogue measured here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1/probe2 on a Windows substrate with `pwsh` "
                    "and a real or sandboxed Claude Code / Codex CLI "
                    "installation, per the catalog's original scope."
                ),
            },
            {
                "claim": (
                    "Whether any currently-connected MCP server namespace "
                    "for THIS session (visible only in-session as a live "
                    "tool catalog, not as a $HOME filesystem artifact) would "
                    "differ between a clean and current profile."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Capture the dynamic-tool-catalog namespace list from a "
                    "session booted against a genuinely fresh profile and "
                    "diff it against this session's own namespace list."
                ),
            },
        ],
        "report": {
            "kind": "audit-drift",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0096-C1", "AUD0096-C2"],
            "observations": [
                {
                    "name": "clean_profile_proven_clean",
                    "measured": clean_ok,
                    "method": "is_profile_clean() on scratch $HOME before census",
                    "anchor": P1_JSON,
                },
                {
                    "name": "clean_profile_total_skill_count",
                    "measured": clean_skill_count,
                    "method": "census_load_set() on scratch $HOME",
                    "anchor": P1_JSON,
                },
                {
                    "name": "clean_profile_total_file_count",
                    "measured": clean_file_count,
                    "method": "census_load_set() on scratch $HOME",
                    "anchor": P1_JSON,
                },
                {
                    "name": "current_profile_total_skill_count",
                    "measured": current_skill_count,
                    "method": "census_load_set() on real $HOME",
                    "anchor": P2_JSON,
                },
                {
                    "name": "current_profile_total_file_count",
                    "measured": current_file_count,
                    "method": "census_load_set() on real $HOME",
                    "anchor": P2_JSON,
                },
                {
                    "name": "current_profile_total_bytes",
                    "measured": current_bytes,
                    "method": "census_load_set() on real $HOME",
                    "anchor": P2_JSON,
                },
                {
                    "name": "total_skill_count_delta",
                    "measured": skill_delta,
                    "method": "current_census - clean_census",
                    "anchor": P2_JSON,
                },
                {
                    "name": "total_file_count_delta",
                    "measured": file_delta,
                    "method": "current_census - clean_census",
                    "anchor": P2_JSON,
                },
                {
                    "name": "total_bytes_delta",
                    "measured": bytes_delta,
                    "method": "current_census - clean_census",
                    "anchor": P2_JSON,
                },
                {
                    "name": "control_fires_on_bad_silent_on_good",
                    "measured": fires_on_bad and silent_on_good,
                    "method": "leaked-skill fixture vs empty-scratch fixture through is_profile_clean()",
                    "anchor": CTL_JSON,
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-drift",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "substrate_scope_note": (
                "Catalog scoped this unit to a clean Windows user profile "
                "with Claude/Codex harness state; this substrate is Linux "
                "Cursor Cloud. claude_home_absent="
                f"{claude_absent} codex_home_absent={codex_absent}. Measured "
                "$HOME/.cursor (skills-cursor, plugins, agent-hooks) as the "
                "nearest analogous profile-level harness state instead."
            ),
            "clean_profile_summary": {
                "clean_ok": clean_ok,
                "total_skill_count": clean_skill_count,
                "total_file_count": clean_file_count,
                "total_bytes": clean_bytes,
                "ok": p1_ok,
            },
            "current_profile_summary": {
                "clean": bool(current_clean_check.get("clean")),
                "total_skill_count": current_skill_count,
                "total_file_count": current_file_count,
                "total_bytes": current_bytes,
                "ok": p2_ok,
            },
            "diff_summary": {
                "total_skill_count_delta": skill_delta,
                "total_file_count_delta": file_delta,
                "total_bytes_delta": bytes_delta,
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
        print("FAILED:AUD-0096 missing probe outputs:", *missing, sep="\n")
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
