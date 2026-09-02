"""P13: emit the missing blindspot-register receipt and validate it with the
repo's OWN schema resolver (platform/lib/schema_resolver.validate_artifact).

Seven phase-13 units declare command-center/schema/blindspot-register.schema.json
as output_schema and NONE ran, so no instance of that artifact class has ever
existed. This emits BLD-0023 (suppressed-failure construct census), the unit this
review's measurements actually cover.

The receipt is only written if it VALIDATES. A receipt that does not validate is
reported as FAILED and not persisted -- otherwise this script would itself be the
"guard that converts a bug into a green".
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
RECEIPTS = CC / "receipts"
OUT = RECEIPTS / "BLD-0023.json"
SCHEMA = "command-center/schema/blindspot-register.schema.json"
TS = "2026-08-10T12:00:00Z"


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load schema_resolver")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def art(rel: str) -> dict:
    p = REPO / rel
    exists = p.is_file()
    data = p.read_bytes() if exists else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest() if exists else ("0" * 64),
        "exists": exists,
    }


def probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw,
        "fingerprint": hashlib.sha256(f"{command}\n{raw}".encode()).hexdigest()[:32],
    }


def build() -> dict:
    return {
        "schema_version": 1,
        "unit_id": "BLD-0023",
        # NOT "SUCCESS". The schema enforces that a SUCCESS receipt carries zero
        # open P0/P1 defects, an INDEPENDENT reviewer verdict of PASS, a failing-test
        # count of zero and manifest_registration.registered=true. This unit measured
        # correctly and therefore has 8 open defects, a failing Linux suite, and no
        # independent review -- so SUCCESS is unavailable to it by construction.
        # BLOCKED is the honest terminal state: the remaining gate is an owner
        # decision plus an independent review, neither of which an agent can grant.
        "state": "BLOCKED",
        "sentinel": "SENTINEL:BLD-0023:BLOCKED-ON-OWNER-DECISION-AND-INDEPENDENT-REVIEW blind-spot census measured with both-states controls on every pattern",
        "failure": {
            "classification": [
                "blocked-on-owner-decision",
                "blocked-on-independent-review",
            ],
            "reason": (
                "The census itself completed and every claim carries a source+verifier probe "
                "pair. The receipt cannot be SUCCESS because the schema forbids that state "
                "while any P0/P1 defect is open, while any test result is FAIL, and until an "
                "INDEPENDENT reviewer records PASS. This unit found 2 open P0 defects and a "
                "failing Linux suite, so a SUCCESS receipt would be a false green."
            ),
            "blocked_on": (
                "owner decisions BS-02 (unapproved 2,048->few-dozen scope substitution, OQ-4), "
                "BS-07 (release mode, OQ-3), BS-08 (27 open owner questions, 3 literal spec "
                "placeholders) and BS-11 (239/261 mcp__ units unapproved); plus one "
                "cross-vendor refuter to re-derive the 1-of-2007 and zero-CI findings from the "
                "raw tree rather than from this receipt."
            ),
            "diagnostic_tail": (
                "Structural observation worth escalating: the receipt predicate cannot express "
                "'an audit unit that correctly did its job and found defects'. For the 144 "
                "phase-12 adversarial units and the 7 phase-13 blindspot units, FINDING a P0 "
                "is mission success, yet any open P0 makes SUCCESS unreachable. Phase 12/13 "
                "units are therefore structurally unable to emit a SUCCESS receipt, which is "
                "one plausible contributor to why zero receipts of any kind exist."
            ),
            "two_signal_proof": [
                probe(
                    "source",
                    "file-read",
                    "read platform/schema/receipt.schema.json#/$defs/receipt_core/allOf[0]",
                    "IF state==SUCCESS THEN: defects must NOT contain {severity in [P0,P1], status: open}; reviewer.verdict==PASS; reviewer.independent==true; manifest_registration.registered==true; tests must NOT contain {result in [FAIL,ERROR,SKIP,NOT-RUN]}; evidence minItems 2 with a source and a verifier probe.",
                ),
                probe(
                    "verifier",
                    "schema-validate",
                    "python command-center/p13_emit_receipt.py with state=SUCCESS",
                    "FAILED:p13-receipt 7 validation error(s) - NOT writing the receipt. The 7 named exactly: the P0/P1-open defect clause, manifest_registration/registered True expected, two negative_controls clauses, reviewer/independent True expected, reviewer/verdict PASS expected, and the failing-test clause. An empirical refusal, not a reading of the schema.",
                ),
            ],
        },
        "spec_anchor": "_USER-PROMPTS.md:11066-11082",
        "min_bytes_threshold": 2048,
        "artifacts": [
            art("command-center/P13-BLINDSPOT-REVIEW.md"),
            art("command-center/P13-SUPPRESSION-CENSUS.json"),
            art("command-center/P13-EXECUTION-GAP.json"),
            art("command-center/P13-ORPHAN-PLAN.json"),
            art("command-center/P13-LINUX-SUITE.json"),
        ],
        "evidence": [
            {
                "claim": "1 of 2,007 catalogued work units produced the artifact it declared; the catalog has no execution-state field, so plan and delivery cannot be reconciled by anything in the repo",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/P13-EXECUTION-GAP.json#/totals",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python command-center/p13_execution_gap.py",
                        "detector controls: PASS (present-file, present-dir, absent-path, present-but-empty all correct)\ncatalogued=2007 produced=1 missing=2006",
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "python command-center/p13_orphan_plan.py",
                        "declared_output_paths_distinct: 2007\nvs ARTIFACT-MANIFEST paths : 0\nvs git-tracked files (8911): 1\nvs on-disk command-center   : 1",
                    ),
                ],
            },
            {
                "claim": "The entire platform/ tree has zero CI coverage: platform/ appears 0 times across all 7 workflow files, and ci/ contains no reference either",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": ".github/workflows/",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "grep -rcE 'platform/' .github/workflows/*.yml",
                        "autofix-models.yml:0 codex-runner.yml:0 dependabot-auto-merge.yml:0 no-runtime-junk.yml:0 quality.yml:0 routing-benchmark.yml:0 skill-dual-write.yml:0",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "positive control: grep -rhoF <known-present> .github/workflows/*.yml | wc -l",
                        "command-center -> 5 hits; monitorcore -> 22 hits; mcpctl -> 28 hits; platform/ -> 0 hits. The detector finds known-present strings, so the zero is real and not a broken matcher.",
                    ),
                ],
            },
            {
                "claim": "The platform suite fails on Linux (24 failed / 3875 passed / 37 skipped) while Windows reports 0 failed / 3847 passed / 14 skipped; 21 of the 24 failures are platform/routing",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/P13-LINUX-SUITE.json#/summary",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "wsl python3 -m pytest platform -q -p no:cacheprovider",
                        "24 failed, 3875 passed, 37 skipped in 706.79s (0:11:46)  EXIT=1",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "wsl python3 -m pytest platform/plugin -q",
                        "252 passed in 118.98s -- a disjoint subpackage passes cleanly on the SAME Linux interpreter, so the 24 failures are localised, not an environment-wide import failure. This REFUTES a blanket 'it breaks on Linux'.",
                    ),
                ],
            },
            {
                "claim": "The Linux routing failures are environment coupling, not portability: platform/routing indexes the operator's LIVE ~/.claude harness, so the Phase 8 numbers are not reproducible off this one machine and no CI runner could ever pass those tests",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "platform/routing/index.py:55",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "read platform/routing/index.py:55,93-97",
                        "HOME = Path(os.environ.get('ROUTING_HOME') or Path.home())  # then skills=[HOME/.agents/skills, HOME/.claude/skills], agents=HOME/.claude/agents, commands=HOME/.claude/commands",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "count ~/.claude/{agents,commands,skills} on both platforms",
                        "Windows: agents=27 commands=71 skills=79. WSL Linux ($HOME=/home/prekzursil): agents=0 commands=0 skills=0. Linux indexed 383 records and the test's own positive-form guard fired: 'corpus implausibly small (383); the walk is probably broken' (assert 383 > 800).",
                    ),
                ],
            },
            {
                "claim": "routing-benchmark.yml gates hooks/semantic-router (the pre-existing router), not platform/routing (the Phase 8 deliverable), and its regression probe is continue-on-error: true",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": ".github/workflows/routing-benchmark.yml:95-97",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "grep -nE 'run:|continue-on-error' .github/workflows/routing-benchmark.yml",
                        "53: hooks/harness-bench/test_bench.py  54: hooks/harness-bench/test_gate.py  55: hooks/semantic-router/test_eval.py  96: continue-on-error: true  97: python hooks/harness-bench/gate.py --runs 5",
                    ),
                    probe(
                        "verifier",
                        "manual-inspection",
                        "cross-check the register's own Phase 8 completion evidence",
                        "WORK-UNIT-CATALOG items[] T-13 disposition_evidence names hooks/semantic-router/{route,embed,build_index,eval,intents,observe,success}.py -- i.e. the DONE-VERIFIED Phase 8 claim points at hooks/, a different implementation from platform/routing. Two routers exist; CI gates the older one, fail-open.",
                    ),
                ],
            },
            {
                "claim": "488 failure-suppression constructs exist across 355 in-scope deliverable files; the largest classes are 112 '# pragma: no cover' and 33 pytest.skip() absence guards",
                "verdict": "CONFIRMED",
                "confidence": "likely",
                "anchor": "command-center/P13-SUPPRESSION-CENSUS.json#/totals",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "python command-center/p13_suppression_census.py",
                        "detector controls: PASS (13 patterns, both-states each)\nfiles_scanned=355 scratch_excluded=321\n112 pragma_no_cover / 33 pytest_skip_call / 16 shell_or_true / 8 stderr_to_null / 7 shell_or_echo / 6 ci_continue_on_error / 5 contextlib_suppress / 488 TOTAL",
                    ),
                    probe(
                        "verifier",
                        "manual-inspection",
                        "narrow the two over-broad classes by re-reading each hit",
                        "except-clause pattern matched 290 lines but matches CORRECT handlers too; requiring the body to be pass/.../continue gives 29, mostly in scratch wave3_* scripts and ci/harness/ledger.py. continue-on-error matched 3 but 2 are inside YAML comments (codex-runner.yml:319,323); exactly 1 is live (routing-benchmark.yml:96, a step self-labelled shadow). Both of my own counts corrected DOWNWARD.",
                    ),
                ],
                "unverified": False,
            },
            {
                "claim": "The absence-is-skip guard is a LATENT mask, not a live one: no such guard currently fires",
                "verdict": "PARTIAL",
                "confidence": "almost-certain",
                "anchor": "platform/lib/wfdsl/test_catalog_conformance.py:33-34",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "read platform/lib/wfdsl/test_catalog_conformance.py:31-35",
                        "if not CATALOG.is_file():  # pragma: no cover - environment guard\n    pytest.skip(f'catalog not present at {CATALOG}')",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "python -m pytest <the guarded modules> -q -rs",
                        "221 passed in 51.60s -- 0 skipped, so zero absence guards are live today. The mask is latent. It compounds with the zero-CI finding: the guard branch is '# pragma: no cover' so coverage cannot see it either.",
                    ),
                ],
                "unverified": False,
                "settling_experiment": "delete WORK-UNIT-CATALOG.json in a throwaway clone and re-run; deliberately NOT run against the working tree",
            },
            {
                "claim": "All three owner-input slots in the governing spec are still literal placeholders and all 27 owner questions are OPEN, so release mode was never selected by the owner",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/OWNER-DECISIONS.md:5,32",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "grep -n PASTE _USER-PROMPTS.md",
                        "10516: `[PASTE SELECTED OPTION IDS HERE]`   10520: `[PASTE OWNER OVERRIDES HERE]`   and the release-mode line reads `[PR-ONLY / PRIVATE CANARY / PUBLIC MARKETPLACE RELEASE - choose or ask when required]`",
                    ),
                    probe(
                        "verifier",
                        "schema-validate",
                        "state census over WORK-UNIT-CATALOG.json#/owner_questions",
                        "27 of 27 state=OPEN. OWNER-DECISIONS.md:5 '27 open of 27'. OQ-3 records that Phase 15 branches entirely on release mode; no owner decision record exists anywhere in command-center/. The wave brief's 'PR-ONLY is binding' is therefore an EXECUTOR assumption.",
                    ),
                ],
            },
            {
                "claim": "0 of 103 register items have the receipt their output_path contract declares, and 26 items marked DONE-VERIFIED have none - though each does carry inline file:line evidence, so this is a verifiability gap, not fabrication",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/P13-ORPHAN-PLAN.json#/register_receipt_contract",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "stat() over items[].output_path for all 103 register items",
                        "receipts dir exists: False. items with existing receipt: 0/103. DONE-VERIFIED: 26. DONE-VERIFIED without receipt: 26 (T-01..T-26).",
                    ),
                    probe(
                        "verifier",
                        "manual-inspection",
                        "read disposition_evidence for T-01, T-13, T-26",
                        "Each carries concrete inline anchors (e.g. T-26: 'tools/mcpctl/mcpctl/safety.py:190 on origin/main now reads return redact_text(strip_controls(text))'). The evidence is real prose; what is missing is the schema-valid machine-checkable receipt. Scoped as a contract gap, NOT as a false completion.",
                    ),
                ],
            },
            {
                "claim": "No STRIDE threat model exists and all 14 required Phase-12 refuter lenses are unexecuted",
                "verdict": "CONFIRMED",
                "confidence": "likely",
                "anchor": "_USER-PROMPTS.md:11044-11060",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "repo-wide search for STRIDE",
                        "hits only in command-center/catalog-slices/{ADV-1,BLD-1}.json, the catalog itself, wave4 probe scripts, and agent-self/config/commands/review-design.md -- i.e. DECLARATIONS and one unrelated command, never a produced threat-model artifact.",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "output-existence over the 144 phase-12 ADV units",
                        "phase 12: 129 catalogued / 0 produced / 129 missing (plus ADV-2 slice). command-center/adversarial/ does not exist. So every one of the 14 named lenses -- including the 'cross-platform behavior' refuter that would have caught the Linux failures -- never ran.",
                    ),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-01",
                "kind": "known-broken-fixture",
                "description": "Each of the 13 suppression regexes was run against a hand-written line that MUST match and one that MUST NOT (e.g. 'continue-on-error: true' vs 'continue-on-error: false'). All 13 fired on the positive and stayed silent on the negative before any count was emitted.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "control_pass=True for all 13 patterns",
                "good_state_output": "fires_on_known_negative=False for all 13 patterns",
            },
            {
                "id": "NC-02",
                "kind": "absent-input",
                "description": "The output-existence detector was shown a deliberately absent path and a deliberately present-but-EMPTY file; both must be reported MISSING, and a known-present file plus a known-present directory must be reported PRESENT.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "negative_absent.reported_present=false; negative_empty.reported_present=false (bytes=0)",
                "good_state_output": "positive_file.reported_present=true (5356178 B); positive_dir.reported_present=true",
            },
            {
                "id": "NC-03",
                "kind": "mutation",
                "description": "CI-grep positive control: the same grep that returned 0 for platform/ was shown three strings known to be present in the workflow files.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "command-center=5, monitorcore=22, mcpctl=28",
                "good_state_output": "platform/=0",
            },
            {
                "id": "NC-04",
                "kind": "other",
                "description": "DETECTOR FAILURE RETAINED, not deleted: my first attempt to prove the skip mask by in-process monkeypatching reported masks_found=0. That zero was an artefact -- platform/ shadows the stdlib platform module so the dotted import never resolved. Recorded so the false zero cannot be cited as evidence of absence.",
                "fired_on_bad_state": False,
                "silent_on_good_state": False,
                "bad_state_output": "No module named 'platform.lib'; 'platform' is not a package -> masks_found=0",
                "good_state_output": "superseded by a source read plus a real 221-passed/0-skipped pytest run",
            },
        ],
        "tests": [
            {
                "id": "T-LINUX-FULL",
                "name": "platform suite on Ubuntu 24.04 / python 3.12.3 under WSL (measured by this unit)",
                "command": "wsl python3 -m pytest platform -q -p no:cacheprovider",
                "result": "FAIL",
                "duration_seconds": 706.79,
                "output_tail": "24 failed, 3875 passed, 37 skipped in 706.79s (0:11:46)",
            },
            {
                "id": "T-LINUX-PLUGIN",
                "name": "platform/plugin subpackage on Linux (disjoint control)",
                "command": "wsl python3 -m pytest platform/plugin -q",
                "result": "PASS",
                "duration_seconds": 118.98,
                "output_tail": "252 passed in 118.98s",
            },
            {
                "id": "T-SKIP-LIVENESS",
                "name": "guarded-module targeted run: are any absence guards live?",
                "command": "python -m pytest platform/lib/foundry platform/lib/workflows/test_workflow_id_uniqueness.py platform/lib/test_schema_resolver.py platform/lib/wfdsl/test_catalog_conformance.py -q -rs",
                "result": "PASS",
                "output_tail": "221 passed in 51.60s (0 skipped)",
            },
            {
                "id": "T-WINDOWS-BASELINE",
                "name": "platform suite on Windows (pinned baseline, NOT re-run by this unit)",
                "command": "python -m pytest platform -q",
                "result": "NOT-RUN",
                "output_tail": "carried figure: 3847 passed / 14 skipped / 0 failed",
            },
        ],
        "defects": [
            {
                "id": "P13-D01",
                "severity": "P0",
                "status": "open",
                "summary": "2,006 of 2,007 catalogued work units produced no artifact; the catalog carries no execution-state field and its declared output paths intersect the program's own ARTIFACT-MANIFEST in 0 places, so plan and delivery cannot be reconciled. Anchor: command-center/WORK-UNIT-CATALOG.json#/work_units.",
            },
            {
                "id": "P13-D02",
                "severity": "P0",
                "status": "open",
                "summary": "The entire platform/ tree has zero CI coverage on any OS (platform/ appears 0 times in all 7 workflow files), so the ~3,847-test green is a hand-run single-machine figure no gate reproduces. Anchor: .github/workflows/.",
            },
            {
                "id": "P13-D03",
                "severity": "P1",
                "status": "open",
                "summary": "platform/routing tests index the operator's live ~/.claude harness, which structurally prevents any CI runner from passing them and makes the Phase 8 capability count machine-specific. A ROUTING_HOME env seam already exists and no test uses it. Anchor: platform/routing/index.py:55.",
            },
            {
                "id": "P13-D04",
                "severity": "P1",
                "status": "open",
                "summary": "routing-benchmark.yml gates hooks/semantic-router, not platform/routing, and its regression probe is continue-on-error: true -- so the one CI job named for routing tests a different implementation, fail-open. Anchor: .github/workflows/routing-benchmark.yml:95-97.",
            },
            {
                "id": "P13-D05",
                "severity": "P1",
                "status": "open",
                "summary": "All 13 CI jobs are runs-on: ubuntu-latest. Windows (the sole development platform) and macOS (declared in the plugin platforms enum) are ungated by any route. Anchor: .github/workflows/quality.yml:76.",
            },
            {
                "id": "P13-D06",
                "severity": "P1",
                "status": "open",
                "summary": "0 of 103 register items have the receipt their output_path declares and command-center/receipts/ does not exist, including for 26 DONE-VERIFIED items. Their inline evidence is real, so this is a machine-verifiability gap rather than a false completion. Anchor: command-center/P13-ORPHAN-PLAN.json#/register_receipt_contract.",
            },
            {
                "id": "P13-D07",
                "severity": "P2",
                "status": "open",
                "summary": "platform/ shadows the Python stdlib platform module; survivable only because no __init__.py exists. Adding one would shadow stdlib platform process-wide. Anchor: platform/.",
            },
            {
                "id": "P13-D08",
                "severity": "P2",
                "status": "open",
                "summary": "33 pytest.skip() absence guards convert a missing artifact into a non-failure, and the guard branches carry '# pragma: no cover' so coverage tooling cannot see them. Latent today (221 passed / 0 skipped) but unprotected because platform/ has no CI. Anchor: platform/lib/wfdsl/test_catalog_conformance.py:33-34.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Which files inside declared scope no agent ever opened (BLD-0001). No transcript read-ledger was built, so Q01 is reported NOT-CHECKED rather than approximated.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "extract every Read/Grep/Glob/Bash-cat input path from the session JSONL transcripts for the whole program and diff against the declared scope file list",
            },
            {
                "claim": "Whether deleting a catalogued artifact leaves the suite green -- the LIVE form of the skip mask.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "delete WORK-UNIT-CATALOG.json in a throwaway clone and re-run the guarded modules; deliberately not run against the working tree",
            },
            {
                "claim": "Whether all 24 Linux failures share the live-home root cause. 21 are platform/routing and consistent with it, but test_docs.py::test_every_resolution_source_anchor_points_at_a_real_file, test_leases.py::test_backslash_and_case_fold_on_windows and the routing test_descriptions corpus-stats failure were not individually triaged.",
                "verdict": "PARTIAL",
                "settling_experiment": "re-run the Linux suite with ROUTING_HOME pointed at a committed fixture and re-count the residual failures",
            },
            {
                "claim": "Whether only 7 of 46 named failure classes are seeded as regressions (UNKNOWNS-REGISTER U-4). Carried forward from that register, NOT re-verified by this unit.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "populate TEST-REGISTRY.json per failure class and run each",
            },
            {
                "claim": "Collected test counts differ between platforms (Windows 3861 vs Linux 3936 collected) and the cause was not investigated; parametrisation over discovered files is the likely driver.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "pytest --collect-only -q on both platforms and diff the node id lists",
            },
            {
                "claim": "Whether the 5.36 MB monolithic catalog degrades consumers at 10x scale. Structural facts were read (full json.loads on every consumer path, no index, no streaming) but no load test was run.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "synthesise a 20,070-unit catalog and time the conformance suite, schema resolver and renderer against it",
            },
        ],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.validate_artifact",
                "artifact_path": "command-center/receipts/BLD-0023.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "schema_resolver.validate_artifact(receipt, 'command-center/schema/blindspot-register.schema.json')",
                    "0 validation errors -- the receipt is accepted by the repo's own resolver, which resolves the shim through platform/schema/artifact-class-profiles.schema.json#/$defs/blindspot-register to receipt.schema.json#/$defs/generic_report. This receipt is only written when that returns empty.",
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "NONE",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "notes": "This unit was NOT independently reviewed. Per the estate default a cross-vendor refuter in a fresh context should re-derive the 1-of-2007 figure and the zero-CI claim from the raw tree, not from this receipt.",
        },
        "timestamps": {"started_at": TS, "ended_at": TS},
        "retry": {
            "count": 2,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
            "pivot_alternatives": [
                "source-read the guard plus a real pytest -rs run (CHOSEN)",
                "delete the artifact in a throwaway clone and re-run (rejected: mutates a tree another lane may read)",
            ],
        },
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "blindspot-reviewer",
            "execution_substrate": "local-windows-pwsh7",
        },
        "report": {
            "kind": "blindspot-register",
            "observations": [
                {
                    "name": "catalogued_work_units",
                    "measured": 2007,
                    "method": "len(WORK-UNIT-CATALOG.json#/work_units)",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json#/work_units_meta/work_unit_count",
                },
                {
                    "name": "declared_outputs_present_on_disk",
                    "measured": 1,
                    "method": "stat()+non-emptiness per output_path; 4 detector controls passed first",
                    "anchor": "command-center/P13-EXECUTION-GAP.json#/totals/output_present",
                },
                {
                    "name": "declared_paths_intersecting_artifact_manifest",
                    "measured": 0,
                    "method": "set intersection, mechanically independent of stat()",
                    "anchor": "command-center/P13-ORPHAN-PLAN.json#/intersections",
                },
                {
                    "name": "expected_output_dirs_never_created",
                    "measured": 25,
                    "method": "dir-existence over the distinct parent dirs of all 2007 output paths",
                    "anchor": "command-center/P13-EXECUTION-GAP.json#/expected_output_dirs",
                },
                {
                    "name": "units_expecting_the_absent_receipts_dir",
                    "measured": 1021,
                    "method": "same",
                    "anchor": "command-center/P13-EXECUTION-GAP.json#/expected_output_dirs",
                },
                {
                    "name": "register_receipts_existing",
                    "measured": 0,
                    "method": "stat() over items[].output_path for all 103 register items",
                    "anchor": "command-center/P13-ORPHAN-PLAN.json#/register_receipt_contract",
                },
                {
                    "name": "items_done_verified_without_receipt",
                    "measured": 26,
                    "method": "disposition==DONE-VERIFIED AND receipt path absent",
                    "anchor": "command-center/P13-ORPHAN-PLAN.json#/register_receipt_contract",
                },
                {
                    "name": "workflow_files_referencing_platform",
                    "measured": 0,
                    "method": "grep over 7 workflow files; positive control command-center=5 monitorcore=22 mcpctl=28",
                    "anchor": ".github/workflows/",
                },
                {
                    "name": "ci_jobs_on_ubuntu_latest",
                    "measured": 13,
                    "method": "grep runs-on across all workflows; zero windows-latest, zero macos-latest, no matrix",
                    "anchor": ".github/workflows/quality.yml:76",
                },
                {
                    "name": "linux_suite_failures",
                    "measured": 24,
                    "method": "full platform suite, Ubuntu 24.04 / python 3.12.3 under WSL",
                    "anchor": "command-center/P13-LINUX-SUITE.json#/summary",
                },
                {
                    "name": "linux_suite_failures_in_platform_routing",
                    "measured": 21,
                    "method": "classify the 24 FAILED node ids by package",
                    "anchor": "command-center/P13-LINUX-SUITE.json#/failures",
                },
                {
                    "name": "linux_suite_skips",
                    "measured": 37,
                    "method": "same run; Windows reports 14, so 23 more tests are inert on Linux",
                    "anchor": "command-center/P13-LINUX-SUITE.json#/summary",
                },
                {
                    "name": "linux_home_harness_capabilities_indexed",
                    "measured": 383,
                    "method": "the routing index's own walk under $HOME on Linux; its positive-form guard demands >800",
                    "anchor": "platform/routing/test_index.py:146",
                },
                {
                    "name": "windows_home_harness_agents_commands_skills",
                    "measured": "27/71/79",
                    "method": "directory listing of ~/.claude/{agents,commands,skills} on Windows vs 0/0/0 on Linux",
                    "anchor": "platform/routing/index.py:93-97",
                },
                {
                    "name": "suppression_constructs_total",
                    "measured": 488,
                    "method": "13 both-states-controlled regex patterns over 355 in-scope files",
                    "anchor": "command-center/P13-SUPPRESSION-CENSUS.json#/grand_total",
                },
                {
                    "name": "pragma_no_cover_occurrences",
                    "measured": 112,
                    "method": "same census",
                    "anchor": "command-center/P13-SUPPRESSION-CENSUS.json#/totals",
                },
                {
                    "name": "pytest_skip_absence_guards",
                    "measured": 33,
                    "method": "same census",
                    "anchor": "command-center/P13-SUPPRESSION-CENSUS.json#/totals",
                },
                {
                    "name": "true_swallowing_except_handlers",
                    "measured": 29,
                    "method": "narrowed from an over-broad 290 by requiring the handler body to be pass/.../continue - my own count corrected downward",
                    "anchor": "command-center/P13-BLINDSPOT-REVIEW.md",
                },
                {
                    "name": "live_ci_continue_on_error_steps",
                    "measured": 1,
                    "method": "narrowed from 3 by discarding 2 occurrences inside YAML comments (use-vs-mention)",
                    "anchor": ".github/workflows/routing-benchmark.yml:96",
                },
                {
                    "name": "owner_questions_open",
                    "measured": 27,
                    "method": "state census over WORK-UNIT-CATALOG.json#/owner_questions",
                    "anchor": "command-center/OWNER-DECISIONS.md:5",
                },
                {
                    "name": "spec_owner_input_placeholders_still_literal",
                    "measured": 3,
                    "method": "grep PASTE plus the release-mode line in the governing spec",
                    "anchor": "_USER-PROMPTS.md:10516,10520,10524",
                },
                {
                    "name": "unknowns_on_register_none_retired",
                    "measured": 13,
                    "method": "row count of UNKNOWNS-REGISTER.md U-1..U-13",
                    "anchor": "command-center/UNKNOWNS-REGISTER.md",
                },
                {
                    "name": "blindspot_register_instances_before_this_unit",
                    "measured": 0,
                    "method": "repo-wide search for any instance of the 3 register schemas; only catalog declarations and the schema shims exist",
                    "anchor": "command-center/schema/blindspot-register.schema.json",
                },
                {
                    "name": "phase13_units_declaring_this_artifact_class",
                    "measured": 7,
                    "method": "catalog scan for output_schema==blindspot-register",
                    "anchor": "command-center/schema/blindspot-register.schema.json#/x-catalog-reference-count",
                },
                {
                    "name": "tested_install_clients",
                    "measured": 1,
                    "method": "client token census over platform/plugin and platform/marketplace: claude-code 12, antigravity 1, no test for any non-claude-code client",
                    "anchor": "platform/plugin/schemas.py:709-716",
                },
                {
                    "name": "stride_threat_model_artifacts",
                    "measured": 0,
                    "method": "repo-wide STRIDE search; every hit is a catalog declaration",
                    "anchor": "command-center/catalog-slices/ADV-1.json",
                },
                {
                    "name": "phase12_adversarial_outputs_produced",
                    "measured": 0,
                    "method": "output-existence over the phase-12 units; all 14 required refuter lenses unexecuted",
                    "anchor": "command-center/P13-EXECUTION-GAP.json#/by_phase",
                },
                {
                    "name": "catalog_bytes_parsed_whole_per_consumer",
                    "measured": 5356178,
                    "method": "stat() of the single JSON blob every consumer json.loads in full",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json",
                },
                {
                    "name": "declared_target_shortfall_never_closed",
                    "measured": 41,
                    "method": "work_units_meta target 2048 minus work_unit_count 2007",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json#/work_units_meta/shortfall",
                },
                {
                    "name": "blind_spots_registered_by_this_unit",
                    "measured": 20,
                    "method": "row count of the BS-01..BS-20 table, each dispositioned as work unit, owner decision, or accepted risk",
                    "anchor": "command-center/P13-BLINDSPOT-REVIEW.md",
                },
            ],
            "control_ids": ["NC-01", "NC-02", "NC-03", "NC-04"],
        },
    }


def main() -> int:
    sr = load_resolver()
    receipt = build()
    errors = sr.validate_artifact(receipt, SCHEMA)
    if errors:
        print(
            f"FAILED:p13-receipt {len(errors)} validation error(s) - NOT writing the receipt"
        )
        for e in errors[:25]:
            print(f"  - {e}")
        return 1
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"receipt VALIDATES against {SCHEMA} (0 errors from the repo's own resolver)")
    print(f"  observations:  {len(receipt['report']['observations'])}")
    print(f"  evidence pairs:{len(receipt['evidence'])}")
    print(f"  neg controls:  {len(receipt['negative_controls'])}")
    print(f"  defects:       {len(receipt['defects'])}")
    print(f"  unknowns:      {len(receipt['residual_unknowns'])}")
    print(f"SUCCESS:BLD-0023 wrote {OUT} ({OUT.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
