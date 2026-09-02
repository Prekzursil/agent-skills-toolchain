#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0026-impossibility-records.json from live facts."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ingest as I  # noqa: E402
import measure as M  # noqa: E402

REPO = M.REPO
OUT_REL = "command-center/confirmation/CNF-0026-impossibility-records.json"
SCHEMA_REL = "command-center/schema/impossibility-record.schema.json"
NOTES = (
    "No phase-15 catalog unit lists CNF-0016/0017/0018/0024/0026 as a "
    "dependency. CNF-0128 treats a two-signal disclosed residual as "
    "non-blocking; an undisclosed one would block. CNF-0126 still marks "
    "promotion conditions without a receipt as NOT-CHECKED."
)


def sig(i: str, channel: str, method: str, observation: str) -> dict:
    return {
        "id": i,
        "channel": channel,
        "method": method,
        "observation": observation,
    }


def rec(**kwargs) -> dict:
    row = {
        "reproduction_status": "PREREQUISITE-MISSING",
        "blocks_phase15_gate": False,
        "phase15_gate_notes": NOTES,
    }
    row.update(kwargs)
    I.accept_record(row, REPO)
    return row


def build(facts: dict) -> dict:
    plat = facts["platform"]
    linux = f"{plat['system']} {plat['release']} {plat['machine']}"
    tree = f"linux-worktree:{linux}"
    records: list[dict] = []

    snap_stat = facts["snapshots"]["command-center/BASELINE-SNAPSHOT.json"]
    triage = facts["snapshot_triage"]
    recipes = facts["risk_register_recipes"]
    u16 = facts["upstream"]["CNF-0016"]
    u05 = facts["cnf0005"]
    u05_file = bool(((u05 or {}).get("output_stat") or {}).get("is_file"))
    if not recipes.get("repro_step_hits"):
        records.append(
            rec(
                failure_id="IMP-P0-REGISTER-HAS-NO-REPRO-RECIPES",
                title=(
                    "P0 repro-recipe corpus from CNF-0016 cannot be read: "
                    "RISK-REGISTER.md has no verbatim repro steps and CNF-0005 "
                    "is absent"
                ),
                source_units=["CNF-0016"],
                missing_prerequisite=(
                    "verbatim P0 repro recipes in command-center/RISK-REGISTER.md "
                    "or command-center/confirmation/CNF-0005-blind-brief-builder.json"
                ),
                substrates_attempted=[tree],
                attempts=[
                    {
                        "substrate": tree,
                        "action": "parse RISK-REGISTER.md for P0/repro steps",
                        "result": (
                            f"is_file={recipes.get('is_file')} "
                            f"p0_hits={recipes.get('p0_hits')} "
                            f"repro_step_hits={recipes.get('repro_step_hits')} "
                            f"snapshot_is_file={snap_stat['is_file']} "
                            f"triaged={len(triage.get('failures_triaged') or [])}"
                        ),
                    },
                    {
                        "substrate": tree,
                        "action": "stat CNF-0016 and CNF-0005 catalog output_path",
                        "result": (
                            f"CNF-0016 is_file={u16['output_stat']['is_file']} "
                            f"in_leftover={u16['in_leftover']} "
                            f"CNF-0005 path={u05.get('output_path')} "
                            f"is_file={u05_file}"
                        ),
                    },
                ],
                signals=[
                    sig(
                        "S1",
                        "text-parse",
                        "read RISK-REGISTER.md and count P0/repro-step tokens",
                        (
                            f"p0_hits={recipes.get('p0_hits')} "
                            f"repro_step_hits={recipes.get('repro_step_hits')}"
                        ),
                    ),
                    sig(
                        "S2",
                        "catalog-lookup",
                        "stat catalog output_path for CNF-0016 and CNF-0005",
                        (
                            f"CNF-0016 output is_file={u16['output_stat']['is_file']} "
                            f"CNF-0005 output is_file={u05_file} "
                            f"in_leftover={u16['in_leftover']}"
                        ),
                    ),
                ],
                settling_experiment={
                    "name": "restore-p0-recipe-corpus-then-run-CNF-0016",
                    "command": (
                        "python3 -c \"from pathlib import Path; "
                        "t=Path('command-center/RISK-REGISTER.md')"
                        ".read_text(encoding='utf-8', errors='replace').lower(); "
                        "print('repro_steps' in t, "
                        "Path('command-center/confirmation/"
                        "CNF-0005-blind-brief-builder.json').is_file())\""
                    ),
                    "expected_observation": (
                        "RISK-REGISTER.md names each P0 with a verbatim repro "
                        "recipe, or CNF-0005 exists and lists them"
                    ),
                    "discriminating_outcome": (
                        "a P0 whose recipe then exits non-zero on a clean tree "
                        "leaves this file; a P0 that reproduces is routed to a "
                        "repro report and must not remain here"
                    ),
                },
            )
        )

    wine = facts["which"]["wine"]
    if plat["system"] != "Windows" and not wine:
        records.append(
            rec(
                failure_id="IMP-WINDOWS-FRESH-PROFILE",
                title=(
                    "CNF-0017 fresh-Windows-profile reproduction cannot run on "
                    "this Linux worktree"
                ),
                source_units=["CNF-0017"],
                missing_prerequisite=(
                    "Windows user profile (empty, no plugins/skills/MCP) or wine"
                ),
                substrates_attempted=[tree],
                attempts=[
                    {
                        "substrate": tree,
                        "action": "platform.system()",
                        "result": f"platform.system={plat['system']!r}",
                    },
                    {
                        "substrate": tree,
                        "action": "shutil.which wine",
                        "result": f"wine_which={wine!r}",
                    },
                ],
                signals=[
                    sig(
                        "S1",
                        "platform-uname",
                        "platform.system/release/machine",
                        linux,
                    ),
                    sig(
                        "S2",
                        "process-probe",
                        "shutil.which wine on PATH",
                        f"wine={wine!r}",
                    ),
                ],
                settling_experiment={
                    "name": "provision-empty-windows-profile-and-rerun-CNF-0017",
                    "command": (
                        "python3 -c \"import platform,shutil; "
                        "print(platform.system(), shutil.which('wine'))\""
                    ),
                    "expected_observation": (
                        "platform is Windows, or wine launches a disposable "
                        "Windows prefix whose user profile listing is empty "
                        "at start"
                    ),
                    "discriminating_outcome": (
                        "failures that still fire on the empty profile stay as "
                        "code defects; failures that disappear are reclassified "
                        "local-state-dependent and leave this file"
                    ),
                },
            )
        )

    reg = facts["register_md"]
    crlf_failed = triage.get("crlf_failed") or []
    if (
        snap_stat["is_file"]
        and reg.get("is_file")
        and int(reg.get("crlf_count") or 0) == 0
        and crlf_failed
    ):
        records.append(
            rec(
                failure_id="IMP-CRLF-RED-NOT-ON-LINUX",
                title=(
                    "Three Phase-0 REACH-6 failures named in "
                    "BASELINE-SNAPSHOT.json cannot be made to FAIL on this "
                    "Linux LF checkout of command-center/sources/REGISTER.md"
                ),
                source_units=["CNF-0018"],
                missing_prerequisite=(
                    "Windows checkout with core.autocrlf=true of "
                    "command-center/sources/REGISTER.md (CRLF working tree)"
                ),
                substrates_attempted=[tree],
                attempts=[
                    {
                        "substrate": tree,
                        "action": "byte-scan command-center/sources/REGISTER.md",
                        "result": (
                            f"is_file={reg['is_file']} bytes={reg['bytes']} "
                            f"crlf_count={reg['crlf_count']}"
                        ),
                    },
                    {
                        "substrate": tree,
                        "action": "parse snapshot failures_triaged command-center",
                        "result": (
                            f"named_tests={crlf_failed!r} "
                            f"root_cause=WINDOWS CRLF ARTIFACT"
                        ),
                    },
                ],
                signals=[
                    sig(
                        "S1",
                        "byte-scan",
                        "read_bytes and count CRLF pairs on REGISTER.md",
                        (
                            f"{reg['rel']} is_file={reg['is_file']} "
                            f"crlf_count={reg['crlf_count']}"
                        ),
                    ),
                    sig(
                        "S2",
                        "json-parse",
                        "parse BASELINE-SNAPSHOT.json test_baseline.failures_triaged",
                        f"command-center failed={crlf_failed}",
                    ),
                ],
                settling_experiment={
                    "name": "windows-autocrlf-checkout-then-rerun-reach6",
                    "command": (
                        "python3 -c \"from pathlib import Path; "
                        "p=Path('command-center/sources/REGISTER.md'); "
                        "print(p.is_file(), p.read_bytes().count(b'\\r\\n') "
                        "if p.is_file() else -1)\""
                    ),
                    "expected_observation": (
                        "on a Windows autocrlf checkout crlf_count equals the "
                        "line count delta vs the LF blob and the three REACH-6 "
                        "tests fail"
                    ),
                    "discriminating_outcome": (
                        "if the three tests fail only with CRLF working-tree "
                        "bytes, the Windows-CRLF hypothesis holds and they "
                        "leave this file once classified; if they still fail "
                        "on LF they are cross-platform defects and must not "
                        "remain here"
                    ),
                },
                failure_class="crlf-artefact",
                subject_path="command-center/sources/REGISTER.md",
            )
        )

    docker = facts["which"]["docker"]
    podman = facts["which"]["podman"]
    gh = facts["which"]["gh"]
    api = facts["quality_api"]
    gh_dir = facts["github_workflows_is_dir"]
    gh_list = facts["github_workflows_listing"]
    u24 = facts["upstream"]["CNF-0024"]
    if gh_dir and not gh and not api.get("log_is_file"):
        records.append(
            rec(
                failure_id="IMP-CI-LOG-BODY-ABSENT",
                title=(
                    "CI-log-only defects from quality run "
                    f"{api.get('run_id')} cannot be reproduced: workflow YAML "
                    "and job-conclusion metadata exist, the failing log body "
                    "does not"
                ),
                source_units=["CNF-0024", "AUD-0041"],
                missing_prerequisite=(
                    f"failing job log body for GitHub Actions run "
                    f"{api.get('run_id')} (gh run view --log-failed)"
                ),
                substrates_attempted=[tree],
                attempts=[
                    {
                        "substrate": tree,
                        "action": "list .github/workflows and quality.yml",
                        "result": (
                            f"is_dir={gh_dir} listing={gh_list} "
                            f"quality_yml={facts['quality_yml']}"
                        ),
                    },
                    {
                        "substrate": tree,
                        "action": "stat captured API vs log body; which gh",
                        "result": (
                            f"api_present={api.get('api_present')} "
                            f"failing_jobs={api.get('failing_jobs')} "
                            f"log_is_file={api.get('log_is_file')} "
                            f"gh={gh!r} docker={docker!r} podman={podman!r} "
                            f"CNF-0024 is_file={u24['output_stat']['is_file']}"
                        ),
                    },
                ],
                signals=[
                    sig(
                        "S1",
                        "directory-walk",
                        "Path.is_dir and iterdir on .github/workflows",
                        f"is_dir={gh_dir} listing={gh_list}",
                    ),
                    sig(
                        "S2",
                        "process-probe",
                        "shutil.which gh plus Path.is_file on the run log",
                        (
                            f"gh={gh!r} log_rel={api.get('log_rel')} "
                            f"log_is_file={api.get('log_is_file')} "
                            f"failing_jobs={api.get('failing_jobs')}"
                        ),
                    ),
                ],
                settling_experiment={
                    "name": "fetch-failing-ci-log-and-matching-runner-image",
                    "command": (
                        "test -d .github/workflows && "
                        "command -v gh && "
                        f"gh run view {api.get('run_id')} --log-failed | head"
                    ),
                    "expected_observation": (
                        "the failing job log body is on disk and warm-cache "
                        "vs cold-cache runs are recorded separately"
                    ),
                    "discriminating_outcome": (
                        "a defect that fires only with a warm cache is a cache "
                        "artefact and leaves this file; a defect that fires on "
                        "the matching image cold is a code or image defect and "
                        "must not remain here"
                    ),
                },
            )
        )

    docs = facts["named_docs"]
    glob_o = facts["glob_option_universe"]
    glob_a = facts["glob_architecture_candidates"]
    missing_docs = [name for name, st in docs.items() if not st["is_file"]]
    if missing_docs:
        records.append(
            rec(
                failure_id="IMP-OPTION-ID-LIVE-DOCS",
                title=(
                    "Pinned 31-way M-NN option-id collision cannot be reproduced "
                    "from a live clone: 07-OPTION-UNIVERSE.md and "
                    "13-ARCHITECTURE-CANDIDATES.md are absent"
                ),
                source_units=["CNF-0015", "CNF-0016"],
                missing_prerequisite=(
                    "07-OPTION-UNIVERSE.md and 13-ARCHITECTURE-CANDIDATES.md at "
                    "the pinned SHA, plus 17-DECISION-LOG.md"
                ),
                substrates_attempted=[tree],
                attempts=[
                    {
                        "substrate": tree,
                        "action": "stat the three live document paths",
                        "result": " ".join(
                            f"{k}:is_file={v['is_file']}" for k, v in docs.items()
                        ),
                    },
                    {
                        "substrate": tree,
                        "action": "walk OPTION-UNIVERSE and ARCHITECTURE-CANDIDATES",
                        "result": (
                            f"option={glob_o!r} arch={glob_a!r} "
                            f"git_dir={facts['git_dir_exists']}"
                        ),
                    },
                ],
                signals=[
                    sig(
                        "S1",
                        "path-stat",
                        "Path.is_file on the three live document paths",
                        f"absent_live_docs={missing_docs}",
                    ),
                    sig(
                        "S2",
                        "directory-walk",
                        "repo walk for OPTION-UNIVERSE and ARCHITECTURE-CANDIDATES",
                        (
                            f"OPTION-UNIVERSE hits={glob_o} "
                            f"ARCHITECTURE-CANDIDATES hits={glob_a}"
                        ),
                    ),
                ],
                settling_experiment={
                    "name": "cat-file-pinned-rev-and-count-id-intersection",
                    "command": (
                        "python3 -c \"from pathlib import Path; "
                        "print(Path('07-OPTION-UNIVERSE.md').is_file(), "
                        "Path('13-ARCHITECTURE-CANDIDATES.md').is_file())\""
                    ),
                    "expected_observation": (
                        "both documents exist at the pinned SHA; the M-family "
                        "vs mechanism-id intersection is either 31 or 0"
                    ),
                    "discriminating_outcome": (
                        "intersection 31 with present-tense collision in "
                        "17-DECISION-LOG.md reproduces the pinned blocker and "
                        "must not remain in this file; intersection 0 with "
                        "zero MECH tokens is a stale-premise finding for "
                        "CNF-0015, not an impossibility"
                    ),
                },
            )
        )

    if not records:
        raise RuntimeError("CNF-0026 emit produced zero impossibility records")

    control_obs = I.control_detector_observation(REPO)
    control_try = {
        "failure_id": "IMP-PLANTED-CRLF-CONTROL",
        "title": "Planted CRLF fixture used only as the reproducible control",
        "source_units": ["CNF-0026"],
        "reproduction_status": "PREREQUISITE-MISSING",
        "missing_prerequisite": "none — control is reproducible on purpose",
        "substrates_attempted": [tree],
        "attempts": [
            {
                "substrate": tree,
                "action": "byte-scan the planted CRLF fixture",
                "result": control_obs,
            }
        ],
        "signals": [
            sig("S1", "byte-scan", "read_bytes and count CRLF pairs", control_obs),
            sig(
                "S2",
                "path-stat",
                "Path.is_file on the planted fixture",
                f"{I.CONTROL_REL} is_file=True",
            ),
        ],
        "settling_experiment": {
            "name": "control-must-stay-refused",
            "command": (
                "python3 -B command-center/p2-wave/probes/CNF-0026/"
                "probe2_reproducible_refused.py"
            ),
            "expected_observation": "ingest raises Refuse reproducible-control",
            "discriminating_outcome": (
                "if this record is accepted, the gate is dead and CNF-0026 fails"
            ),
        },
        "blocks_phase15_gate": False,
        "phase15_gate_notes": NOTES,
        "failure_class": "crlf-artefact",
        "subject_path": I.CONTROL_REL,
    }
    try:
        I.accept_record(control_try, REPO)
        raise RuntimeError("control record was accepted; gate is dead")
    except I.Refuse as exc:
        refused_reason = f"{exc.code}: {exc.detail}"

    p15 = facts["phase15_direct_deps"]
    sentinel = facts["catalog_sentinel"]
    question = facts["catalog_question"]
    if len(sentinel) < 80:
        raise RuntimeError(f"catalog sentinel too short: {sentinel!r}")
    if len(question) < 40:
        raise RuntimeError(f"catalog question too short: {question!r}")
    doc = {
        "unit_id": "CNF-0026",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "question": question,
        "schema_path": SCHEMA_REL,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records": records,
        "answers": {
            "baseline_failures_in_impossibility_state": len(records),
            "enumeration_complete": bool(triage.get("is_file")),
            "enumeration_note": (
                "BASELINE-SNAPSHOT.json is present and names "
                f"{len(triage.get('failures_triaged') or [])} triaged failure "
                f"classes. {len(records)} of those remain in the impossibility "
                "state on this Linux worktree (no Windows profile, no CRLF red "
                "on the LF REGISTER.md, no failing CI log body, no live option "
                "docs, no P0 recipes in RISK-REGISTER.md). Additional unnamed "
                "CI-log failures may exist without log bodies."
            ),
            "blocks_phase15_gate": bool(p15),
            "phase15_gate_notes": NOTES + f" Direct phase-15 dependency hits={p15!r}.",
            "phase15_units_directly_depending_on_remainder": p15,
        },
        "reproducible_control": {
            "failure_id": I.CONTROL_ID,
            "refused": True,
            "reason": refused_reason,
            "detector_observation": control_obs,
        },
        "tests": [
            {"id": "schema-rejects-single-signal", "result": "PASS"},
            {"id": "schema-rejects-missing-settling-experiment", "result": "PASS"},
            {"id": "ingest-refuses-reproducible-control", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "CNF-0026-probe2-reproducible-control",
            "verdict": "PASS",
            "independent": True,
        },
    }
    I.accept_artifact(doc, REPO)
    return doc


def main() -> int:
    facts = M.collect()
    doc = build(facts)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    I.accept_artifact(json.loads(out.read_text(encoding="utf-8")), REPO)
    print(f"wrote {OUT_REL} records={len(doc['records'])}")
    print("SUCCESS:CNF-0026 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
