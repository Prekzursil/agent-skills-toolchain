#!/usr/bin/env python3
"""Generator for catalog slice TST-1 (units TST-0001..TST-0128).

Bucket: "testing, benchmark, mutation, fuzz, chaos, deliberation-calibration"
(spec _USER-PROMPTS.md:10561, bucket total 352). This is slice 1 of 3.

DECLARED SLICE-1 SCOPE (so slices 2 and 3 do not collide):
  the test PLATFORM itself + Phase-4 executable contract conformance
  + Phase-5/10 plugin-lifecycle + the artifact/monitor/dispatch/parser/shell/path
  reliability subset of the spec's "Known failure classes" list (:11300-11347).
EXPLICITLY LEFT TO SLICES 2/3:
  council + deliberation calibration (:11227-11244, :11335-11344);
  workflow-foundry benchmark/tournament/fusion/lineage tests (:11163-11165, :11331-11334);
  security / privacy / legal / supply-chain / marketplace-abuse lanes
  (:11018-11020, :11345-11347);
  per-target mutation / fuzz / chaos CAMPAIGNS (slice 1 ships only the
  infrastructure those campaigns run on).

Every unit carries the 19 fields the spec enumerates at :10607-10625.
"""

import json
import pathlib

# ---------------------------------------------------------------- presets ----
# tool_permissions: least-privilege classes (spec Phase 4 "permission model")
TOOLS = {
    "ANALYZE": ["Read", "Grep", "Glob", "Bash"],
    "TEST": ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    "TESTWIN": ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell"],
    "FAULT": ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell", "Monitor"],
    "XVENDOR": ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "mcp__codex__codex"],
    "GH": ["Read", "Grep", "Glob", "Bash", "mcp__github__list_commits",
           "mcp__github__get_file_contents", "mcp__github__pull_request_read"],
}

SCHEMAS = {
    "R": "command-center/schema/receipt.schema.json",
    "T": "command-center/schema/test-receipt.schema.json",
    "C": "command-center/schema/conformance-report.schema.json",
    "D": "command-center/schema/detector-control.schema.json",
    "F": "command-center/schema/fault-injection-receipt.schema.json",
    "B": "command-center/schema/benchmark-receipt.schema.json",
}

# retry policies
RP = {
    "2S": "two strikes then pivot: after the 2nd failure on the same error-fingerprint, "
          "enumerate >=2 alternative approaches before a 3rd attempt (AGENTS.md 4b)",
    "NONE": "NO retry. A retry masks the exact instability this unit exists to measure; "
            "a failed run is the datum, re-run only with a changed hypothesis recorded first",
    "NET3": "3 attempts with jittered exponential backoff (base 2s, cap 60s, full jitter), "
            "then FAILED:timeout-<n>s with the last response headers attached",
    "1S": "single attempt then escalate to the owner; this unit mutates a live shared "
          "surface and a blind retry can compound the damage",
    "SEED": "unlimited re-runs ONLY with a new recorded seed; re-running the same seed is "
            "not a retry, it is a reproduction and must produce the identical verdict",
}

FC = {
    "CORE": ["detector-failure", "overclaim", "schema-invalid", "dependency-blocked"],
    "GREEN": ["green-not-live", "overclaim", "detector-failure", "uncontrolled-silence"],
    "WIN": ["platform-specific-only", "detector-failure", "green-not-live", "transport-mangled"],
    "DIST": ["severed-stream", "timeout-<n>s", "uncontrolled-silence", "duplicate-dispatch",
             "partial-artifact"],
    "PKG": ["packaging-gap", "green-not-live", "stale-cache", "dependency-blocked"],
    "BENCH": ["measured-nothing", "benchmark-gaming", "variance-unbanded", "overclaim"],
    "GOV": ["false-coverage", "overclaim", "detector-failure", "owner-blocked"],
    "OWNER": ["owner-blocked", "irreversible-refused", "dependency-blocked"],
}

# bucket codes used in `dependencies` (mapped from the spec allocation, :10554-10566)
# BKT-CMD command-center/corpus-control 24 | BKT-AUD current-state audit 96
# BKT-RES deep-research/gem-hunt 224      | BKT-WFA workflow archaeology 160
# BKT-CNL council design 128              | BKT-ARC architecture/spec 112
# BKT-IMP implementation 480              | BKT-TST testing 352
# BKT-CNF independent confirmation 192    | BKT-ADV adversarial/security 144
# BKT-BLD completeness/blind-spot 64      | BKT-SYN synthesis 48
# BKT-REL release/canary/rollback 24

SPEC = "_USER-PROMPTS.md"


def U(n, title, phase, qot, inputs, deps, mvr, tools, sub, timeout, schema,
      evidence, tests, reviewer, retry, failclass, owner=False):
    model, vendor, role = mvr
    uid = "TST-%04d" % n
    return {
        "id": uid,
        "title": title,
        "phase": phase,
        "question_or_target": qot,
        "inputs": inputs,
        "dependencies": deps,
        "assigned_model_vendor_role": {"model": model, "vendor": vendor, "role": role},
        "tool_permissions": TOOLS[tools],
        "execution_substrate": sub,
        "timeout_seconds": timeout,
        "output_path": "command-center/receipts/%s.json" % uid,
        "output_schema": SCHEMAS[schema],
        "evidence_requirement": evidence,
        "tests_required": tests,
        "reviewer_requirement": reviewer,
        "completion_sentinel": "SUCCESS:%s" % uid,
        "retry_policy": RP[retry],
        "failure_classification": FC[failclass],
        "owner_approval_required": owner,
    }


OPUS = ("opus", "anthropic", "test-architect")
OPUS_CE = ("opus", "anthropic", "conformance-engineer")
OPUS_DA = ("opus", "anthropic", "detector-auditor")
OPUS_FI = ("opus", "anthropic", "fault-injection-engineer")
OPUS_PT = ("opus", "anthropic", "platform-test-engineer")
OPUS_BE = ("opus", "anthropic", "benchmark-engineer")
OPUS_GA = ("opus", "anthropic", "test-governance-auditor")
OPUS_RE = ("opus", "anthropic", "release-test-engineer")
OPUS_DX = ("opus", "anthropic", "docs-test-engineer")
CDX_CE = ("gpt-5-codex", "openai", "conformance-engineer")
CDX_FI = ("gpt-5-codex", "openai", "fault-injection-engineer")
CDX_PT = ("gpt-5-codex", "openai", "platform-test-engineer")
CDX_DA = ("gpt-5-codex", "openai", "detector-auditor")
CDX_GA = ("gpt-5-codex", "openai", "test-governance-auditor")

XV = "one fresh-context adversarial reviewer from the OTHER vendor than the author " \
     "(Claude author -> Codex reviewer, and the reverse); a same-vendor reviewer " \
     "inherits the author's blind spots"
XV_SEC = "two fresh-context reviewers: one cross-vendor correctness refuter and one " \
         "security refuter; both default to REFUTED when evidence is insufficient (:11062)"
XV_WIN = "two fresh-context reviewers: one cross-vendor refuter and one Windows-platform " \
         "specialist who re-runs the probe in the OTHER shell (PowerShell 7 vs Git Bash)"
XV_OWN = "one cross-vendor refuter plus explicit owner sign-off recorded in " \
         "command-center/OWNER-DECISIONS.md before the unit may close"
XV_STAT = "one cross-vendor refuter plus one statistics reviewer who re-derives the " \
          "variance band from the raw per-run numbers, not from the summary"

units = []
A = units.append

# =========================================================================
# G1 - Shared completion predicate and fan-in reducer (TST-0001..0012)
#     spec: "One completion predicate everywhere" :10627-10648
# =========================================================================
A(U(1, "Executable conformance harness and reference oracle for the 12-condition completion predicate",
    "4",
    "Build a reference oracle that implements conditions 1-12 of the unit completion predicate "
    "(_USER-PROMPTS.md:10631-10644) as 12 independently-addressable boolean checks, and a harness "
    "that runs any candidate reducer against it. Target: the production reducer and the oracle "
    "return byte-identical verdict objects (verdict + failing-condition-id + reason) on every "
    "receipt in the conformance corpus. Does any condition of the 12 lack a distinguishable "
    "failing-condition-id in the production reducer?",
    [SPEC + ":10627-10648", "command-center/COMPLETION-GATES.json#gate_a_unit_completion_predicate",
     "command-center/WORK-UNIT-CATALOG.json"],
    ["BKT-CMD", "BKT-IMP"],
    OPUS_CE, "TEST", "local-parallel", 3600, "C",
    "the oracle source at file:line, plus a captured diff showing oracle-vs-reducer verdicts "
    "agreeing on all corpus rows; agreement asserted per-condition, not on the aggregate boolean",
    ["test_oracle_has_12_distinguishable_conditions",
     "test_reducer_matches_oracle_on_full_corpus",
     "negative control: a reducer stubbed to return True always must FAIL this harness"],
    XV, "2S", "CORE"))

A(U(2, "Twelve-row negative corpus: one receipt per predicate condition, each violating exactly one",
    "4",
    "Construct 12 fixture receipts where receipt[k] violates ONLY condition k and satisfies the "
    "other 11. Target: the reducer returns FAILED with failing-condition-id == k for each, and "
    "PASS for the single all-satisfied control row. Which conditions cannot be violated in "
    "isolation because the artifact format couples them?",
    [SPEC + ":10631-10644", "command-center/COMPLETION-GATES.json"],
    ["TST-0001", "BKT-CMD"],
    CDX_CE, "TEST", "local-parallel", 2700, "C",
    "the 13 fixture files committed under tests/fixtures/completion/, plus the parametrised run "
    "output showing 12 distinct failing-condition-ids and 1 PASS",
    ["test_each_condition_fails_in_isolation[1..12]",
     "test_all_satisfied_row_passes",
     "coupling report: any condition pair that cannot be separated is recorded as a contract defect"],
    XV, "2S", "CORE"))

A(U(3, "Seven-call-site parity differential for the shared reducer",
    "10",
    "The spec names seven consumers of the same reducer: local runners, cloud dispatchers, "
    "monitors, harvesters, workflow fan-in, cross-vendor adapters, final synthesis (:10648). "
    "Target: replay the full conformance corpus through all seven call sites and assert the "
    "verdict objects are byte-identical. Do any two call sites disagree on any row?",
    [SPEC + ":10648", "TST-0002 corpus", "command-center/PHASE-GRAPH.json"],
    ["TST-0002"],
    OPUS, "TEST", "local-parallel", 3600, "T",
    "a 7xN verdict matrix committed as an artifact plus the hash of each column; equality proven "
    "by hash comparison, not by eyeballing the table",
    ["test_all_seven_call_sites_agree_per_row",
     "negative control: patch ONE call site to skip condition 8 and assert the differential goes red"],
    XV, "2S", "CORE"))

A(U(4, "Exit-code-zero with a missing artifact must classify FAILED",
    "10",
    "Spec: 'Exit code zero alone is never success' (:10646) and failure class 'exit zero with "
    "missing artifact' (:11311). Target: a dispatched unit that exits 0 and writes nothing is "
    "classified FAILED at condition 2, never SUCCESS. Does any existing runner short-circuit on "
    "returncode == 0 before the artifact check?",
    [SPEC + ":10646", SPEC + ":11311", "rules/common/cross-vendor-dispatch.md"],
    ["TST-0001"],
    OPUS_FI, "TEST", "local-parallel", 1800, "F",
    "a grep census of every `returncode == 0` / `$LASTEXITCODE -eq 0` site in the runner tree with "
    "a verdict per site, plus the injected-run transcript showing FAILED",
    ["test_exit0_no_artifact_is_failed",
     "test_exit0_with_valid_artifact_is_success (the both-states pair)"],
    XV, "2S", "DIST"))

A(U(5, "A plausible digest must not satisfy a fan-in barrier",
    "10",
    "Spec: 'A plausible digest is not a receipt' (:10646); measured on this estate, 3/3 Codex "
    "agents returned plausible digests for files that do not exist. Target: the fan-in barrier "
    "Test-Path-checks every contracted output BEFORE parsing any digest, and rejects a "
    "well-formed prose digest whose artifact is absent.",
    [SPEC + ":10646", "rules/common/fan-out-contract.md#B1"],
    ["TST-0001"],
    OPUS_FI, "TEST", "local-parallel", 1800, "F",
    "the barrier source line performing the existence check before the parse, plus a run where a "
    "hand-written convincing digest for an absent path is rejected",
    ["test_digest_without_artifact_rejected",
     "test_digest_with_artifact_accepted",
     "test_rejection_message_names_the_absent_path"],
    XV, "2S", "DIST"))

A(U(6, "A file path appearing in agent text is not proof the file exists",
    "10",
    "Spec: 'A file path in text is not proof the file exists' (:10646). Target: a linter over "
    "agent result payloads that extracts every path-shaped token, stats it, and downgrades the "
    "result to UNVERIFIED-PATH when a cited path is absent. What is the false-positive rate on "
    "paths that are legitimately illustrative (documentation examples)?",
    [SPEC + ":10646", "command-center/ARTIFACT-MANIFEST.json"],
    ["TST-0005"],
    CDX_CE, "TEST", "local-parallel", 2700, "T",
    "precision/recall measured against a hand-labelled sample of 100 real agent payloads drawn "
    "from the corpus, with the labels committed",
    ["test_absent_path_downgrades_result",
     "test_illustrative_path_in_fenced_code_is_not_flagged (use-vs-mention control)"],
    XV, "2S", "CORE"))

A(U(7, "Calibrate the meaningful-minimum-size threshold and prove the default is exercised",
    "10",
    "Predicate condition 3 requires the artifact to exceed 'a meaningful minimum size' (:10635). "
    "Target: derive the threshold from the measured size distribution of real receipts rather "
    "than a guessed constant, AND prove the DEFAULT is exercised by tests. Ledger precedent: "
    "reverting DEFAULT_MIN_BYTES 1024->512 left 15/15 tests green because every case passed "
    "min_bytes explicitly. Does at least one test call the API without the size argument?",
    [SPEC + ":10635", "rules/common/single-signal-verification.md"],
    ["TST-0001", "TST-0015"],
    OPUS_DA, "TEST", "local-parallel", 2700, "T",
    "the size histogram over >=200 real receipts, the chosen threshold with its percentile, and a "
    "mutation run showing the suite goes RED when the default is changed",
    ["test_default_min_bytes_is_exercised_without_explicit_arg",
     "mutation control: flip the default and require at least one test to fail"],
    XV, "2S", "GREEN"))

A(U(8, "Sentinel detection must distinguish a real sentinel from a sentinel quoted inside a payload",
    "10",
    "Predicate condition 5 requires the sentinel present (:10636). The use-vs-mention class has "
    "hit this estate ~8 times, including inside the verification probes themselves. Target: the "
    "sentinel check keys on the semantic ROLE (a terminal line in the receipt's status field), "
    "not on a substring match anywhere in the payload. Does a document that merely DESCRIBES "
    "'SUCCESS:TST-0008' satisfy the check?",
    [SPEC + ":10636", SPEC + ":11323", "rules/common/single-signal-verification.md"],
    ["TST-0001", "TST-0017"],
    OPUS_DA, "TEST", "local-parallel", 2700, "T",
    "the checker reading a typed field rather than scanning free text, plus a fixture whose BODY "
    "quotes a valid sentinel while its status field is empty, asserted FAILED",
    ["test_sentinel_in_body_does_not_satisfy",
     "test_sentinel_in_status_field_satisfies",
     "test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy"],
    XV, "2S", "CORE"))

A(U(9, "Evidence-anchor resolvability validator: every anchor must actually resolve",
    "4",
    "Predicate condition 6 requires 'required evidence anchors exist' (:10637). Target: a "
    "validator that resolves each anchor by KIND - file:line (the file exists AND has that many "
    "lines), a command (re-executes it and compares the recorded exit code), or an explicit "
    "'inferred from X'. How many anchors in the existing corpus fail to resolve today?",
    [SPEC + ":10637", "command-center/CLAIM-REGISTRY.json"],
    ["TST-0001"],
    OPUS_CE, "TEST", "local-parallel", 3600, "C",
    "a per-anchor resolution table over the whole existing claim registry with counts by kind and "
    "by outcome; a line number beyond EOF counts as unresolved",
    ["test_file_line_beyond_eof_is_unresolved",
     "test_command_anchor_reexecutes",
     "test_inferred_anchor_requires_a_named_source"],
    XV, "2S", "CORE"))

A(U(10, "Open P0/P1 defect attachment must block completion",
    "10",
    "Predicate condition 10: 'no unresolved P0/P1 defect is attached' (:10642). Target: a unit "
    "with an OPEN P1 in the defect ledger cannot reach SUCCESS even when all other 11 conditions "
    "hold, and the block names the defect id. Can a defect be silently downgraded from P1 to P2 "
    "to unblock, without an audit entry?",
    [SPEC + ":10642", "command-center/RISK-REGISTER.md"],
    ["TST-0001"],
    CDX_CE, "TEST", "local-parallel", 1800, "T",
    "the blocked run transcript naming the defect id, plus the append-only audit row generated by "
    "a severity downgrade",
    ["test_open_p1_blocks_success",
     "test_severity_downgrade_writes_an_audit_row",
     "test_closed_p1_does_not_block"],
    XV, "2S", "GOV"))

A(U(11, "Artifact-manifest registration round-trip",
    "10",
    "Predicate condition 11: 'output was registered in the artifact manifest' (:10643). Target: "
    "closing a unit writes a manifest row containing path, sha256 and producing-unit-id, and a "
    "reverse sweep proves every on-disk receipt has exactly one manifest row and every manifest "
    "row has a file. What is the current count of orphan rows and unregistered files?",
    [SPEC + ":10643", "command-center/ARTIFACT-MANIFEST.json"],
    ["TST-0001"],
    OPUS_CE, "TEST", "local-parallel", 2700, "C",
    "both directions measured as set differences with the two counts printed, not a single "
    "'looks consistent' assertion",
    ["test_close_writes_manifest_row",
     "test_orphan_manifest_row_detected",
     "test_unregistered_file_detected"],
    XV, "2S", "GOV"))

A(U(12, "Downstream-consumer readability: a real consumer must parse the artifact",
    "10",
    "Predicate condition 12: 'downstream consumers can read it' (:10644). Target: for each "
    "artifact kind, instantiate the ACTUAL downstream consumer (the synthesis reader, the monitor "
    "renderer, the manifest indexer) and require a successful parse plus one field read - not a "
    "schema check alone. Which artifact kinds have no identified downstream consumer at all?",
    [SPEC + ":10644", "command-center/PHASE-GRAPH.json", "tools/command-center/render.py"],
    ["TST-0011"],
    OPUS, "TEST", "local-parallel", 3600, "C",
    "a consumer-x-artifact matrix with a real parse call per cell; cells with no consumer are "
    "reported as UNCONSUMED rather than silently omitted",
    ["test_each_artifact_kind_has_a_named_consumer",
     "test_consumer_parse_and_field_read_succeeds",
     "negative control: corrupt one byte and require the consumer to fail loudly"],
    XV, "2S", "CORE"))

# =========================================================================
# G2 - Detector control and negative-control infrastructure (0013..0022)
#     spec: :10658 "Verify detectors against known-broken and known-good controls",
#           :11026 negative controls, :11324 detector silent in both states
# =========================================================================
A(U(13, "Reusable both-states control harness",
    "0",
    "Target: ship a single importable fixture/decorator that takes (check, good_state, "
    "broken_state) and asserts the check is SILENT on good and FIRES on broken, emitting a typed "
    "control record. A probe silent in both states measures nothing (:11324). Every downstream "
    "test unit in this bucket consumes this harness rather than re-implementing it.",
    [SPEC + ":10658", SPEC + ":11324", "rules/common/single-signal-verification.md#3b"],
    ["BKT-CMD"],
    OPUS_DA, "TEST", "local-parallel", 2700, "D",
    "the harness source plus its own self-test: a deliberately inert check must be REJECTED by "
    "the harness (the harness is itself both-states controlled)",
    ["test_harness_rejects_a_check_silent_in_both_states",
     "test_harness_rejects_a_check_that_fires_in_both_states",
     "test_harness_accepts_a_correct_check"],
    XV, "2S", "CORE"))

A(U(14, "Detector-control registry and CI gate for uncontrolled detectors",
    "0",
    "Target: every detector in the repo (hook check, validator rule, gate script) must declare a "
    "known-present fixture and a known-broken fixture in a registry; CI fails on any detector "
    "with no control. Question: how many detectors exist today and how many have zero controls? "
    "Report the raw count before proposing the gate threshold.",
    [SPEC + ":10658", "hooks/_dispatch/manifest.json", "tools/command-center/validate.py"],
    ["TST-0013"],
    OPUS_DA, "TEST", "local-parallel", 3600, "D",
    "an enumerated detector inventory with a controlled/uncontrolled verdict per row; the "
    "enumerator itself must be proven to find a known-present detector before any zero is trusted",
    ["test_enumerator_finds_a_known_detector (detector control on the detector census)",
     "test_ci_gate_fails_on_an_uncontrolled_detector"],
    XV, "2S", "GOV"))

A(U(15, "Estate-specific mutation-operator library",
    "10",
    "Generic mutation operators (arithmetic, boundary) do not model this estate's real defects. "
    "Target: implement operators that inject the defect classes that actually shipped here - LF->"
    "CRLF flip, JSON key-case flip, path-separator flip, sentinel deletion, mid-write truncation, "
    "default-argument change, and a use-vs-mention swap. Which of these survive the current suite?",
    [SPEC + ":11000", SPEC + ":11298-11347", "rules/common/windows-shell.md"],
    ["TST-0013"],
    OPUS_DA, "TEST", "local-parallel", 5400, "D",
    "each operator demonstrated producing a tree that differs from HEAD in exactly the intended "
    "way (diff attached) and a survival verdict per operator",
    ["test_each_operator_produces_a_valid_but_defective_tree",
     "test_operator_is_reversible (tree restores to the pinned SHA)"],
    XV, "2S", "CORE"))

A(U(16, "Fail-fast gate ordering hides N-1 defects behind the first red step",
    "10",
    "A CI job stops at its FIRST failing step, so one red job reports one defect while hiding "
    "every later one. Measured on this estate: a single red e2e job was actually FOUR stacked "
    "independent failures, discovered only by fixing them one at a time across four round trips. "
    "Target: independent checks must run to completion and aggregate their results, so one run "
    "reveals the full defect set; only genuinely dependent steps may short-circuit. Question: how "
    "many steps in each workflow are independent yet sequenced behind a fail-fast predecessor?",
    [".github/workflows/quality.yml", ".github/workflows/no-runtime-junk.yml",
     "rules/common/ci-hygiene.md"],
    ["TST-0013"],
    CDX_GA, "GH", "local-parallel", 2700, "T",
    "a step-dependency classification per workflow (independent vs genuinely dependent) with the "
    "justification per step, plus a seeded run carrying THREE independent defects that must be "
    "reported in ONE run rather than three",
    ["test_three_seeded_independent_defects_are_all_reported_in_one_run",
     "test_a_genuinely_dependent_step_still_short_circuits",
     "test_aggregate_exit_code_is_red_when_any_check_is_red"],
    XV, "2S", "GREEN"))

A(U(17, "Use-vs-mention discriminator kit",
    "10",
    "Target: a reusable helper that answers 'is this token USED (a semantic role in a typed "
    "field) or MENTIONED (text inside a payload, a fenced block, a doc body)?' and a test kit of "
    "adversarial fixtures. A file documenting a defect necessarily contains that defect's text - "
    "measured ~8 hits in one session, mostly inside the verification probes themselves.",
    [SPEC + ":11323", "rules/common/single-signal-verification.md"],
    ["TST-0013"],
    OPUS_DA, "TEST", "local-parallel", 3600, "D",
    "precision and recall on a labelled fixture set that deliberately includes this unit's own "
    "description as a MENTION case",
    ["test_token_in_fenced_code_block_is_mention",
     "test_token_in_typed_status_field_is_use",
     "test_the_kit_does_not_flag_its_own_documentation"],
    XV, "2S", "CORE"))

A(U(18, "Silent-in-both-states scanner over the existing detector inventory",
    "0",
    "Target: run every registered detector against BOTH its known-good and known-broken fixture "
    "and report the ones that produce identical output in both. Ledger precedent: a codex-exec "
    "probe printed nothing in the broken state too and was one step from being reported as "
    "verification. How many currently-shipped detectors are inert?",
    [SPEC + ":11324", "rules/common/single-signal-verification.md#3b"],
    ["TST-0014"],
    CDX_DA, "TEST", "local-parallel", 3600, "D",
    "a per-detector output pair (good, broken) with a byte-diff verdict; identical output is "
    "reported as INERT with the detector name, never summarised as 'all clean'",
    ["test_scanner_flags_a_planted_inert_detector",
     "test_scanner_does_not_flag_a_known_good_detector"],
    XV, "2S", "GOV"))

A(U(19, "Self-matching probe guard: a probe whose pattern matches its own command line",
    "10",
    "Measured failure: a Win32_Process probe matched ITSELF and reported a dead session as ACTIVE, "
    "twice; the tell was the reported CreationDate equalling the probe's own start time. Target: a "
    "guard that excludes the probing process (by PID and by start-time equality) and a test that "
    "reproduces the self-match.",
    ["rules/common/single-signal-verification.md", SPEC + ":11323"],
    ["TST-0013"],
    OPUS_DA, "TESTWIN", "local-serialized", 1800, "D",
    "a reproduction of the self-match on this Windows box (before) and its absence after the "
    "guard (after), with both PIDs recorded",
    ["test_probe_excludes_own_pid",
     "test_probe_still_finds_a_genuinely_running_process (the both-states pair)"],
    XV_WIN, "2S", "WIN"))

A(U(20, "Self-contradicting-output detector: one run reporting two mutually exclusive facts",
    "10",
    "Measured: one run reported 'all 7 PRs hit' AND 'empty intersection' simultaneously because "
    "`grep -c pat || echo 0` printed '0\\n0'. Target: a post-processor that asserts declared "
    "invariants over a single run's own output (counts must sum, a subset cannot exceed its "
    "superset) and fails the RUN as a detector failure rather than reporting either number.",
    ["rules/common/single-signal-verification.md", SPEC + ":11324"],
    ["TST-0013"],
    OPUS_DA, "TEST", "local-parallel", 2700, "D",
    "the invariant set written down before the run, plus a reproduction where a contradictory "
    "output is classified detector-failure and no number is published",
    ["test_contradictory_counts_fail_the_run",
     "test_consistent_counts_pass",
     "test_failure_message_names_the_violated_invariant"],
    XV, "2S", "CORE"))

A(U(21, "Shell-idiom lint for counting bugs in test and gate scripts",
    "10",
    "Target: a lint that flags the specific shell idioms that silently produce wrong counts - "
    "`grep -c ... || echo 0` (grep -c prints 0 AND exits 1, so both fire), unquoted `$(...)` in a "
    "numeric comparison, `wc -l` on a possibly-empty stream, and `[ -n $x ]` without quotes. "
    "How many live gate scripts contain at least one?",
    ["rules/common/single-signal-verification.md", ".github/workflows/quality.yml"],
    ["TST-0013"],
    CDX_GA, "ANALYZE", "local-parallel", 2700, "T",
    "each flagged site quoted with file:line plus a two-line reproduction proving the miscount "
    "for at least one real occurrence",
    ["test_lint_flags_grep_c_or_echo_zero",
     "test_lint_does_not_flag_the_corrected_form"],
    XV, "2S", "GOV"))

A(U(22, "Source-probe / verifier independence gate",
    "10",
    "A CONFIRMED verdict must declare BOTH the measurement that PRODUCED the claim and the "
    "mechanically different measurement that CHECKED it; an undeclared source is zero signals, "
    "not one. Measured hole: claim_gate.py validates id/text/verdict but not source_probe, so an "
    "absent source normalises to empty strings that any verifier trivially differs from. Target: "
    "require a non-empty source_probe for CONFIRMED/REFUTED before comparing fingerprints.",
    ["rules/common/single-signal-verification.md#6", "command-center/CLAIM-REGISTRY.json"],
    ["TST-0009"],
    OPUS_DA, "TEST", "local-parallel", 2700, "T",
    "a run of the fixed gate over the existing claim registry reporting how many CONFIRMED claims "
    "currently declare no source probe",
    ["test_confirmed_without_source_probe_is_a_violation",
     "test_same_probe_rerun_is_a_violation",
     "test_genuinely_independent_pair_passes"],
    XV, "2S", "GOV"))

# =========================================================================
# G3 - Baseline, freeze, replay, determinism (0023..0032)   spec Phase 0
# =========================================================================
A(U(23, "Pinned-SHA baseline snapshot schema and capture tool",
    "0",
    "Spec Phase 0 requires a snapshot of repo, branches, worktrees, live deployments, caches, "
    "plugin settings, marketplaces, hooks, skills, MCPs (:10654). Target: a typed schema plus a "
    "capture tool whose every count is anchored to the commit SHA, so the artifact is a rollback "
    "anchor rather than a timestamped sample. Which captured facts are SHA-anchored and which are "
    "only wall-clock samples?",
    [SPEC + ":10654", "command-center/BASELINE-SNAPSHOT.json"],
    ["BKT-CMD"],
    OPUS_PT, "TESTWIN", "local-serialized", 5400, "T",
    "each field tagged SHA-ANCHORED or SAMPLED-AT-TIME in the schema itself; a field that cannot "
    "be anchored must carry the sample timestamp",
    ["test_every_field_declares_its_anchoring_kind",
     "test_recapture_at_the_same_sha_reproduces_the_anchored_fields exactly"],
    XV_WIN, "2S", "WIN"))

A(U(24, "Clean-room lane: fresh clone plus fresh user profile",
    "0",
    "Spec: 'Produce a clean-room baseline from a fresh clone and fresh user profile where "
    "possible' (:10655). Target: a lane that clones to a scratch path with an empty HOME/"
    "USERPROFILE and runs the suite, so results cannot inherit the developer's live "
    "~/.claude configuration. Which tests only pass because of ambient local state?",
    [SPEC + ":10655", "rules/common/harness-vcs-hygiene.md"],
    ["TST-0023"],
    OPUS_PT, "TESTWIN", "local-serialized", 7200, "T",
    "the delta between the ambient-profile run and the clean-room run, enumerated test-by-test; "
    "a test that passes only in one is reported as ambient-dependent",
    ["test_clean_room_home_is_actually_empty (control before trusting the lane)",
     "test_ambient_dependent_tests_are_enumerated"],
    XV_WIN, "2S", "GREEN"))

A(U(25, "Benchmark baseline capture BEFORE behaviour changes",
    "0",
    "Spec: 'Capture benchmark baselines before changing behavior' (:10657). Target: freeze the "
    "pre-change numbers for router latency, hook overhead, fan-out throughput and suite wall-clock "
    "at the pinned SHA, with inputs recorded alongside. Guard against the measured failure where "
    "two benchmarks ran on EMPTY inputs and returned a clean, meaningless green.",
    [SPEC + ":10657", ".github/workflows/routing-benchmark.yml"],
    ["TST-0023"],
    OPUS_BE, "TEST", "local-parallel", 5400, "B",
    "per-benchmark input cardinality printed next to every number; a benchmark whose input set is "
    "empty must FAIL rather than report a time",
    ["test_benchmark_asserts_nonempty_input",
     "test_baseline_is_reproducible_within_the_declared_variance_band"],
    XV_STAT, "SEED", "BENCH"))

A(U(26, "Launcher and schema freeze gate with a versioned-migration requirement",
    "0",
    "Spec: 'Freeze the launchers and schemas once the first implementation wave starts; changes "
    "require a versioned migration' (:10660). Target: a gate that hashes the frozen launcher and "
    "schema set and fails any change lacking a migration entry and a schema_version bump. "
    "Precedent: editing a preamble mid-run left contradictory live instructions.",
    [SPEC + ":10660", "rules/common/fan-out-contract.md#A10"],
    ["TST-0023"],
    OPUS_CE, "TEST", "local-parallel", 2700, "C",
    "the frozen-set hash committed, plus a demonstration that an unmigrated schema edit is "
    "rejected and a migrated one is accepted",
    ["test_unmigrated_schema_change_is_rejected",
     "test_migrated_change_with_version_bump_is_accepted"],
    XV, "2S", "GOV"))

A(U(27, "Deterministic seed record-and-replay policy for every randomised suite",
    "10",
    "Target: every property test, fuzz run and chaos run records its seed in the receipt, and a "
    "replay entry point reproduces the identical verdict from that seed alone. Without this, a "
    "randomised failure is unactionable noise. Which randomised suites currently discard their "
    "seed?",
    [SPEC + ":11001-11002", SPEC + ":11006"],
    ["TST-0013"],
    OPUS, "TEST", "local-parallel", 2700, "T",
    "a seed census across randomised suites plus a proof-of-replay: the same seed re-run twice "
    "yields byte-identical verdicts, and a different seed yields a different execution trace",
    ["test_seed_is_recorded_in_the_receipt",
     "test_replay_from_seed_is_deterministic",
     "test_two_different_seeds_produce_different_traces (proves the seed is actually used)"],
    XV, "SEED", "CORE"))

A(U(28, "Differential replay harness: record, replay, diff",
    "10",
    "Spec Phase 10 layer 11 (:10999). Target: record real executions (inputs, tool calls, "
    "artifacts) and replay them against a changed build, diffing the artifact set and the "
    "decision trace. A behaviour change with no corresponding intent is a regression candidate. "
    "What fraction of a recorded run is replayable without live network or credentials?",
    [SPEC + ":10999"],
    ["TST-0027"],
    OPUS, "TEST", "local-parallel", 5400, "T",
    "a replayability percentage with the non-replayable steps enumerated by reason (network, "
    "credential, clock, GUI), not a bare 'mostly replayable'",
    ["test_identical_build_replays_with_an_empty_diff",
     "test_a_planted_behaviour_change_shows_up_in_the_diff"],
    XV, "2S", "CORE"))

A(U(29, "Deterministic workflow replay: same inputs must yield the same DAG execution trace",
    "10",
    "Spec Phase 7 requires 'deterministic replay' (:10889). Target: a workflow run twice with the "
    "same inputs and seed produces the same node order, the same fan-out cardinality and the same "
    "barrier resolution. Ledger precedent: Date.now() in a saved workflow is a banned "
    "non-determinism source. Where does wall-clock or PID leak into the DAG?",
    [SPEC + ":10889"],
    ["TST-0027"],
    CDX_CE, "TEST", "local-parallel", 3600, "T",
    "a trace-hash comparison across two runs plus an enumerated list of every non-determinism "
    "source found by injecting a frozen clock and a fixed PID",
    ["test_two_runs_same_seed_same_trace_hash",
     "test_frozen_clock_does_not_change_the_trace (isolates clock leakage)"],
    XV, "SEED", "CORE"))

A(U(30, "Freeze-versus-sample labelling: detect concurrent mutation during a snapshot",
    "0",
    "Measured on this program: the tree was NOT frozen during baseline capture - concurrent "
    "sibling agents mutated it mid-snapshot, so every working-tree number was a timestamped "
    "sample. Target: the capture tool re-hashes the tree at start and end and labels the artifact "
    "FROZEN or SAMPLED accordingly, refusing to call a mutated capture a baseline.",
    ["command-center/BASELINE-SNAPSHOT.json", SPEC + ":10654"],
    ["TST-0023"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "start and end tree hashes recorded in the artifact; if they differ, the changed paths are "
    "enumerated and the label is SAMPLED",
    ["test_mutation_during_capture_forces_the_sampled_label",
     "test_quiescent_capture_earns_the_frozen_label"],
    XV_WIN, "NONE", "WIN"))

A(U(31, "Blob-versus-worktree EOL parity gate (git cat-file, never git archive)",
    "10",
    "Measured on this box: `git archive | tar -x` returns CRLF worktree bytes (3,837 B / 100 CRLF) "
    "while `git cat-file -p` returns the true blob (3,737 B / 0 CRLF) for the same file. A local "
    "formatter green measured against the wrong bytes verifies nothing. Target: a gate that "
    "verifies formatting and hashing against the BLOB, plus a lint banning git archive for this "
    "purpose. Note RELEASE-CHECKLIST.md currently prescribes the wrong recipe.",
    ["rules/common/windows-shell.md#8b", "command-center/RELEASE-CHECKLIST.md"],
    ["TST-0013"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "the three-route byte/CRLF table (git archive, cat-file, show) reproduced on this box for at "
    "least one file, with an LF-normalisation control proving the content is otherwise identical",
    ["test_gate_reads_blob_bytes_not_worktree_bytes",
     "test_lint_flags_git_archive_used_as_a_blob_source",
     "test_release_checklist_recipe_matches_the_gate"],
    XV_WIN, "2S", "WIN"))

A(U(32, "Flake quarantine ledger and re-run policy",
    "10",
    "Target: a ledger that re-runs each test N times at the same SHA, classifies it "
    "DETERMINISTIC / FLAKY / BROKEN, and blocks any 'suite green' claim that depends on a "
    "quarantined test. Question: what is the measured flake rate of the current suite at a fixed "
    "SHA, and which tests are order- or clock-sensitive?",
    [SPEC + ":11026", "rules/common/testing.md"],
    ["TST-0027"],
    CDX_GA, "TEST", "local-parallel", 7200, "T",
    "N>=20 repetitions per test at one SHA with the per-test pass ratio recorded; a test at "
    "0<ratio<1 is FLAKY and named",
    ["test_ledger_detects_a_planted_coin_flip_test",
     "test_green_claim_is_blocked_when_a_quarantined_test_is_in_the_path"],
    XV, "NONE", "GOV"))

# =========================================================================
# G4 - Phase-4 executable contract conformance (0033..0051)
#     spec :10797-10822 "Write executable conformance tests before broad implementation"
# =========================================================================
_contracts = [
    (33, "plugin manifest",
     "Does the shipped .claude-plugin/plugin.json validate against the client's ACTUAL strict "
     "parser (not a hand-written schema), and does an unknown top-level field cause a load "
     "failure that the tests observe?",
     [".claude-plugin/plugin.json", SPEC + ":10801"], OPUS_CE, "TEST", "local-parallel", 2700,
     "the manifest validated by the real client loader with the load result captured, plus one "
     "deliberately invalid manifest rejected", XV),
    (34, "marketplace manifest",
     "Does .claude-plugin/marketplace.json round-trip through the registry reader and back "
     "byte-identically, and are plugin entries resolvable to real on-disk paths?",
     [".claude-plugin/marketplace.json", SPEC + ":10802"], CDX_CE, "TEST", "local-parallel", 2700,
     "each listed entry resolved to a path that exists, with the unresolved count printed", XV),
    (35, "package metadata",
     "Is every declared package field (name, version, entry points, engines, files) consistent "
     "with what the build actually emits, and does a metadata/build mismatch fail the gate?",
     [SPEC + ":10803"], OPUS_CE, "TEST", "local-parallel", 2700,
     "a field-by-field metadata-vs-built-artifact comparison table", XV),
    (36, "permission model",
     "Can a component request a permission not declared in its manifest, and is that request "
     "denied AND logged rather than silently granted?",
     [SPEC + ":10804", "rules/common/security.md"], OPUS_CE, "TEST", "local-parallel", 3600,
     "an attempted undeclared-permission call with the denial record; a silent grant is a P0", XV_SEC),
    (37, "workflow DSL",
     "Does every construct the workflow DSL documents (fan-out, barrier, loop-with-convergence, "
     "human checkpoint, subworkflow, retry, resume) have a schema rule AND a conformance case, "
     "and which documented construct has no validator at all?",
     [SPEC + ":10805", SPEC + ":10875-10896"], OPUS_CE, "TEST", "local-parallel", 3600,
     "a construct-by-construct table with schema-rule and conformance-case columns", XV),
    (38, "work-unit schema",
     "Does the work-unit schema require all 19 enumerated fields PER UNIT with a real override "
     "key, rather than satisfying them from a single global defaults block? Measured defect: 9 of "
     "19 mandatory fields exist only as a global default, present on 0/103 items, and validate.py "
     "cannot detect the whole defaults block being deleted because require_complete defaults "
     "False and CI invokes the tool bare.",
     ["command-center/WORK-UNIT-CATALOG.json", "tools/command-center/validate.py", SPEC + ":10605-10625"],
     OPUS_CE, "TEST", "local-parallel", 3600,
     "a per-field per-unit presence matrix over the whole catalog plus the mutation showing the "
     "bare CI invocation passes when the defaults block is deleted", XV),
    (39, "artifact schema and the receipt schema family",
     "Define and conformance-test the receipt schema family (base receipt, test receipt, "
     "benchmark receipt, detector-control record, fault-injection receipt, conformance report). "
     "Measured gap: defaults.output_schema points at command-center/schema/receipt.schema.json "
     "which does not exist, and command-center/receipts/ is absent, so 0/103 units can emit a "
     "schema-validated receipt today.",
     [SPEC + ":10807", "command-center/WORK-UNIT-CATALOG.json"], OPUS_CE, "TEST", "local-parallel",
     3600, "each schema file created and exercised by at least one real artifact from another "
     "unit in this slice, not by a synthetic sample only", XV),
    (40, "claim schema",
     "Does every claim record carry id, canonical mechanism, verdict, confidence band, source "
     "lineage, source_probe, verifier probe and settling experiment, and is a claim missing a "
     "settling experiment rejected?",
     [SPEC + ":10808", SPEC + ":10664-10677", "command-center/CLAIM-REGISTRY.json"], CDX_CE,
     "TEST", "local-parallel", 2700,
     "the existing registry re-validated against the schema with a per-field missing count", XV),
    (41, "event schema and append-only guarantee",
     "Is the event log genuinely append-only and monotonic - can a test rewrite or reorder a "
     "prior event without detection, and does every event carry a monotonically non-decreasing "
     "sequence plus a producing-unit id?",
     [SPEC + ":10809", "command-center/events/EVENTS.jsonl"], OPUS_CE, "TEST", "local-parallel",
     2700, "a tamper attempt (edit an earlier line) detected by the verifier, plus a "
     "concurrent-append test proving no interleaved corruption", XV),
    (42, "hook contract",
     "Does every registered hook declare a resolvable event name, matcher and explicit "
     "interpreter that the dispatcher can actually bind, and does the manifest REJECT a hook whose "
     "declared event does not exist in the client's event vocabulary? Runtime fail-open behaviour "
     "is owned by TST-0086 and is deliberately not re-tested here.",
     [SPEC + ":10811", "hooks/_dispatch/manifest.json", "rules/common/hooks.md"], OPUS_CE,
     "TESTWIN", "local-serialized", 3600,
     "the bind result per manifest entry captured from the dispatcher, plus a manifest carrying an "
     "invented event name shown to be rejected at load", XV_WIN),
    (43, "skill contract",
     "Does every skill declare a resolvable name, description and trigger surface, and is a skill "
     "whose SKILL.md front-matter is malformed rejected at deploy rather than silently skipped?",
     [SPEC + ":10812"], CDX_CE, "TEST", "local-parallel", 2700,
     "the deploy log showing an explicit rejection line for a malformed skill; silence is a "
     "failure of this unit, not a pass", XV),
    (44, "MCP adapter contract",
     "For each mounted MCP server, does the adapter surface tool schemas faithfully, and does a "
     "server that returns a malformed tool result degrade loudly instead of producing an empty "
     "success?",
     [SPEC + ":10813"], OPUS_CE, "TEST", "local-parallel", 3600,
     "a malformed-result injection per adapter with the resulting classification; an empty "
     "success is a P1", XV),
    (45, "cross-vendor adapter contract",
     "Does the cross-vendor adapter enforce the dispatch rules that were ledger-proven here - "
     "prompt-by-file (never inline, 32,767-char Windows limit), blocking dispatch (never "
     "background), and an AND-gate of exit-0 PLUS a parsed output file before SUCCESS?",
     [SPEC + ":10814", "rules/common/cross-vendor-dispatch.md"], OPUS_CE, "XVENDOR",
     "local-serialized", 5400,
     "a real dispatch whose prompt exceeds 33,000 chars completing via --prompt-file, plus a "
     "rejected attempt to return a background job receipt as a result", XV),
    (46, "versioning rules",
     "Does the version bump policy match the actual change surface - can a breaking schema change "
     "ship under a patch bump, and does the gate catch it?",
     [SPEC + ":10816"], CDX_CE, "TEST", "local-parallel", 2700,
     "a planted breaking change under a patch bump rejected by the gate, and a genuine patch "
     "accepted", XV),
    (47, "migration rules",
     "For every schema_version transition, does a migration exist, is it idempotent, and does "
     "running it twice leave the artifact unchanged?",
     [SPEC + ":10817"], OPUS_CE, "TEST", "local-parallel", 3600,
     "each migration applied twice with a byte-comparison after the second run", XV),
    (48, "rollback contract",
     "Does the rollback contract specify exactly which state is restored and which is preserved, "
     "and is 'rollback removes existing commands or user data' (:11347) impossible by "
     "construction rather than by convention?",
     [SPEC + ":10818", SPEC + ":11347"], OPUS_CE, "TEST", "local-parallel", 3600,
     "a rollback executed against a tree carrying user data, with a before/after inventory of "
     "user-owned paths proving zero loss", XV_SEC),
    (49, "compatibility matrix",
     "Is every cell of the declared OS x client x version matrix backed by an actual run or "
     "explicitly marked UNTESTED - and how many cells are currently asserted without evidence?",
     [SPEC + ":10819"], OPUS_CE, "TEST", "local-parallel", 2700,
     "the matrix with a run-id or the literal UNTESTED token in every cell; no blank cells", XV),
    (50, "telemetry and privacy contract",
     "Does any telemetry path emit a field not declared in the privacy contract, and is a "
     "credential-shaped or path-shaped value ever included?",
     [SPEC + ":10819", "rules/common/security.md"], OPUS_CE, "TEST", "local-parallel", 3600,
     "a capture of every emitted telemetry payload diffed against the declared field set, with "
     "an entropy check flagging credential-shaped values (never printing them)", XV_SEC),
    (51, "release policy",
     "Are the release gates enumerated in the policy the SAME set the release tooling actually "
     "enforces, and can a release proceed with a gate that was never run?",
     [SPEC + ":10820", "command-center/RELEASE-CHECKLIST.md"], OPUS_RE, "TEST", "local-parallel",
     2700, "a set difference between policy-declared gates and tooling-enforced gates, both "
     "directions printed", XV),
]
for (_n, _name, _q, _inp, _mvr, _tk, _sub, _to, _ev, _rev) in _contracts:
    A(U(_n, "Executable conformance tests for the %s contract" % _name, "4",
        _q, _inp, ["TST-0026", "BKT-ARC"], _mvr, _tk, _sub, _to, "C", _ev,
        ["conformance suite for the %s written BEFORE its broad implementation (:10822)" % _name,
         "at least one negative case per contract rule",
         "a both-states control proving the suite fails on a deliberately non-conforming input"],
        _rev, "2S", "CORE"))

# =========================================================================
# G5 - Strict-parser and serialization hazards (0052..0059)
# =========================================================================
A(U(52, "Strict parser must reject unknown fields, and the rejection must be observable",
    "10",
    "Failure class :11302. Target: feed each manifest/config kind an extra unknown field and "
    "assert a hard rejection with a message naming the field. Question: which parsers currently "
    "ACCEPT unknown fields silently, and what does the client do with the ignored value?",
    [SPEC + ":11302", ".claude-plugin/plugin.json"],
    ["TST-0033", "TST-0034"],
    OPUS_PT, "TEST", "local-parallel", 2700, "T",
    "a per-parser accept/reject table with the exact error text captured for rejections",
    ["test_unknown_field_rejected_per_parser",
     "test_known_field_still_accepted (the both-states pair)"],
    XV, "2S", "CORE"))

A(U(53, "Case-insensitive parser collision on case-distinct JSON keys",
    "10",
    "Failure class :11309. Target: build a document containing both \"Name\" and \"name\" and "
    "determine, per consumer, whether it errors, silently drops one, or last-wins. A "
    "case-insensitive consumer downstream of a case-sensitive producer is a silent data-loss path.",
    [SPEC + ":11309"],
    ["TST-0052"],
    CDX_PT, "TEST", "local-parallel", 2700, "T",
    "the resolved value recorded per consumer for the same input document, showing the divergence "
    "explicitly rather than asserting a single expected value",
    ["test_case_distinct_keys_do_not_silently_merge",
     "test_producer_refuses_to_emit_case_colliding_keys"],
    XV, "2S", "CORE"))

A(U(54, "Duplicate-key last-wins divergence across parsers",
    "10",
    "Target: a document with a repeated key is resolved differently by different JSON parsers "
    "(first-wins, last-wins, error). Determine the behaviour of every parser in the pipeline and "
    "require the producer to make duplicates impossible. Distinct from :11309 - same case, "
    "repeated key.",
    [SPEC + ":11014"],
    ["TST-0052"],
    OPUS_PT, "TEST", "local-parallel", 2700, "T",
    "a parser-by-parser resolution table for one duplicate-key fixture",
    ["test_duplicate_key_is_rejected_by_the_producer",
     "test_each_consumer_parser_behaviour_is_recorded_not_assumed"],
    XV, "2S", "CORE"))

A(U(55, "Encoding and BOM parse matrix",
    "10",
    "Target: every config/artifact reader must be exercised against UTF-8, UTF-8-with-BOM, "
    "UTF-16-LE and Latin-1 inputs. On Windows, PowerShell historically emits UTF-8-with-BOM and a "
    "strict reader chokes on the leading \\ufeff. Which readers fail, and do they fail loudly?",
    [SPEC + ":11014", "rules/common/windows-shell.md"],
    ["TST-0052"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "a reader x encoding outcome matrix produced on this Windows box, with the exact exception "
    "text for each failure",
    ["test_bom_prefixed_json_is_handled_or_rejected_loudly",
     "test_utf16_input_does_not_silently_parse_as_empty"],
    XV_WIN, "2S", "WIN"))

A(U(56, "Numeric precision and big-integer round-trip",
    "10",
    "Target: ids, timestamps and byte counts must survive a JSON round-trip without precision "
    "loss. A 64-bit id beyond 2^53 silently degrades through a JavaScript consumer. Which fields "
    "in the artifact schemas can exceed 2^53, and are any of them read by a JS tool "
    "(tools/lib/*.mjs)?",
    [SPEC + ":10807", "tools/lib/handled-ledger.mjs"],
    ["TST-0039"],
    CDX_PT, "TEST", "local-parallel", 2700, "T",
    "a field census of numeric ranges plus a demonstrated round-trip through the actual JS "
    "consumer for the widest field",
    ["test_large_integer_round_trips_through_the_js_consumer",
     "test_schema_forbids_unbounded_integers_where_a_js_consumer_exists"],
    XV, "2S", "CORE"))

A(U(57, "Unicode normalization collision in identifiers",
    "10",
    "Target: two ids that differ only by NFC/NFD normalization must not resolve to the same "
    "entity in one component and different entities in another. Directly relevant to this "
    "program's measured 31-way M-NN id collision class, at the byte level rather than the "
    "namespace level.",
    [SPEC + ":11309", "command-center/OPTION-ID-RESOLUTION.json"],
    ["TST-0053"],
    OPUS_PT, "TEST", "local-parallel", 2700, "T",
    "an id-normalisation census over every id namespace in the command center with the count of "
    "non-ASCII ids reported (zero is an acceptable result only if the detector is proven to find "
    "a planted one)",
    ["test_detector_finds_a_planted_nfd_id (detector control)",
     "test_ids_are_normalised_at_the_boundary"],
    XV, "2S", "CORE"))

A(U(58, "Lenient-versus-strict parser differential",
    "10",
    "Target: the same document parsed by the lenient path (comments, trailing commas, single "
    "quotes tolerated) and the strict path must either both accept or both reject. A document "
    "that the dev tool accepts and the shipped client rejects is a green-not-live defect.",
    [SPEC + ":11302", SPEC + ":11014"],
    ["TST-0052"],
    CDX_PT, "TEST", "local-parallel", 2700, "T",
    "an accept/reject agreement matrix over a corpus of >=50 real config documents plus 10 "
    "adversarial ones",
    ["test_no_document_is_accepted_by_one_path_and_rejected_by_the_other",
     "test_the_adversarial_documents_are_rejected_by_both"],
    XV, "2S", "GREEN"))

A(U(59, "YAML scalar coercion hazards in configuration",
    "10",
    "Target: YAML config readers must not coerce NO/OFF/ON/YES to booleans, bare version-like "
    "scalars to floats, or empty to null in a way that changes meaning. A country code NO "
    "becoming False is the canonical instance. Which config keys are exposed to this?",
    [SPEC + ":11014", ".github/workflows/quality.yml"],
    ["TST-0052"],
    OPUS_PT, "TEST", "local-parallel", 2700, "T",
    "a key-by-key coercion probe over every YAML config in the repo, listing keys whose loaded "
    "type differs from the declared type",
    ["test_no_key_is_silently_coerced",
     "test_probe_detects_a_planted_coercion (detector control)"],
    XV, "2S", "CORE"))

# =========================================================================
# G6 - Shell, path and OS-surface hazards (0060..0069)
# =========================================================================
A(U(60, "Shell quoting must not corrupt script content in transit",
    "10",
    "Failure class :11308 and Phase 10 layer 27 (:11015). Target: write a script containing "
    "nested quotes, backslashes, dollar signs and backticks through every transport used here "
    "(Write tool, here-string, heredoc, -c inline) and byte-compare the landed file against the "
    "intended bytes. Measured: the here-string route failed 8/59 (13.6%) vs the Write tool 0/40.",
    [SPEC + ":11308", "rules/common/windows-shell.md#9"],
    ["TST-0013"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "a transport x payload byte-equality matrix measured on this box, with the failure rate per "
    "transport, not a single sample",
    ["test_each_transport_round_trips_the_adversarial_payload",
     "test_the_matrix_records_a_known_failing_transport (control: the harness must be able to "
     "show a red cell)"],
    XV_WIN, "2S", "WIN"))

A(U(61, "Windows mandatory file locking during update, rollback and uninstall",
    "10",
    "POSIX allows unlinking and replacing a file another process holds open; Windows takes a "
    "mandatory lock and the same operation fails with a sharing violation. Target: hold an open "
    "handle on each file the lifecycle commands must replace (a loaded hook script, an active log, "
    "a running interpreter's own module) and assert the command either completes via a "
    "replace-on-reboot / rename-then-write strategy or fails with a message naming the locking "
    "process - never a partial replacement. Which lifecycle step leaves the install half-updated "
    "when a handle is held? (Scoped to file LOCKING; MSYS argument rewriting is owned by "
    "TST-0190 in slice TST-2 and is deliberately not duplicated here.)",
    ["rules/common/windows-shell.md", SPEC + ":10994", SPEC + ":11347"],
    ["TST-0060"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "T",
    "for each lifecycle command, the held-handle run recorded with the resulting on-disk state "
    "inventoried file by file; a half-replaced tree is a P0 even when the command exits 0",
    ["test_update_with_a_held_handle_is_atomic_or_loudly_refused",
     "test_rollback_with_a_held_handle_leaves_no_partial_tree",
     "test_error_names_the_locking_process_id",
     "test_unlocked_control_run_succeeds (the both-states pair)"],
    XV_WIN, "2S", "WIN"))

A(U(62, "PowerShell caret escaping mangles git refs",
    "10",
    "Measured: `git rev-parse v1.4.1^{commit}` is corrupted in PowerShell because ^ is the escape "
    "character. Target: a lint that flags unquoted ^ in any ref passed from PowerShell, plus the "
    "sanctioned alternative (`git rev-list -n 1 <tag>` or a single-quoted ref) proven equivalent.",
    ["rules/common/windows-shell.md#2"],
    ["TST-0060"],
    OPUS_PT, "TESTWIN", "local-serialized", 1800, "T",
    "the corrupted invocation reproduced on this box AND the corrected form returning the same "
    "SHA that Git Bash returns (two shells = two independent signals)",
    ["test_caret_ref_is_flagged_by_the_lint",
     "test_corrected_form_resolves_to_the_same_object_in_both_shells"],
    XV_WIN, "2S", "WIN"))

A(U(63, "Command-line length overflow at the Windows 32,767-character limit",
    "10",
    "Failure class :11310. Measured: an inline Codex prompt produced payload_len=34,472 and died "
    "with os error 206, killing both runs that attempted real work. Target: every dispatcher "
    "measures its assembled command line and switches to a file-based payload before the limit, "
    "with the threshold tested at the boundary.",
    [SPEC + ":11310", "rules/common/cross-vendor-dispatch.md#3"],
    ["TST-0045"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "boundary runs at limit-1, limit and limit+1 characters with the outcome of each recorded, "
    "plus the auto-switch to --prompt-file demonstrated",
    ["test_payload_just_under_the_limit_succeeds_inline",
     "test_payload_over_the_limit_switches_to_a_file_and_succeeds",
     "test_the_switch_is_logged (a silent switch hides the near-miss)"],
    XV_WIN, "2S", "WIN"))

A(U(64, "Path-casing collisions between case-insensitive and case-sensitive filesystems",
    "10",
    "Phase 10 layer 28 (:11016). Target: two paths differing only in case must not both be "
    "created; a repo carrying Foo.md and foo.md checks out broken on Windows/macOS. Question: "
    "does the tree contain any case-colliding pair today, and does the gate catch a planted one?",
    [SPEC + ":11016"],
    ["TST-0013"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "a case-folded path census over all tracked files with the collision count; the detector "
    "proven by planting a colliding pair in a scratch clone",
    ["test_detector_finds_a_planted_case_collision",
     "test_current_tree_collision_count_is_reported_not_assumed_zero"],
    XV_WIN, "2S", "WIN"))

A(U(65, "Long-path handling beyond MAX_PATH",
    "10",
    "Phase 10 layer 29 (:11017). Target: artifacts written into a deep worktree path exceeding "
    "260 characters must either succeed via the extended-length prefix or fail loudly. Question: "
    "which writers fail silently (partial write, swallowed exception) rather than erroring?",
    [SPEC + ":11017"],
    ["TST-0064"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "a per-writer outcome at 250, 270 and 400 characters, with the exception text where it fails",
    ["test_long_path_write_is_either_correct_or_loud",
     "test_no_writer_silently_truncates_the_path"],
    XV_WIN, "2S", "WIN"))

A(U(66, "Path aliasing bypasses a guard: trailing dot-or-space stripping and 8.3 short names",
    "10",
    "Windows silently normalises a trailing dot or space away, so a blob recorded as `hook.py.` "
    "checks out as `hook.py`, and it exposes legacy 8.3 aliases so `PROGRA~1\\x` and "
    "`Program Files\\x` are ONE file reachable by two different strings. Target: prove that every "
    "path allowlist, deny-guard and repo-root containment check resolves to a canonical real path "
    "before comparing, so neither alias slips past. Question: which guard on this estate compares "
    "path STRINGS rather than resolved identities? (Reserved device names are a different "
    "normalisation defect and are owned by TST-0197 in slice TST-2.)",
    ["rules/common/windows-shell.md", "rules/common/security.md", SPEC + ":11016"],
    ["TST-0065"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "for each guard, an attempted bypass via BOTH aliases with the accept/reject outcome; the "
    "bypass must be shown to succeed against a deliberately string-comparing control guard, "
    "proving the probe can detect the hole it is looking for",
    ["test_trailing_dot_alias_does_not_bypass_the_guard",
     "test_short_name_alias_does_not_bypass_the_guard",
     "test_string_comparing_control_guard_IS_bypassed (detector control)",
     "test_canonicalisation_is_applied_before_every_comparison"],
    XV_SEC, "2S", "WIN"))

A(U(67, "Environment-variable scope: the value a child process SEES, not the value that was written",
    "10",
    "Measured on this estate: `setx` writes the persistent store but misses the already-running "
    "session, so a tool reads the OLD value while the writer believes it succeeded - and the same "
    "class re-appeared as a config key written at the wrong SCOPE (root instead of per-project) "
    "that was inert while looking correct. Target: every test that depends on an environment "
    "variable or a scoped config key asserts the value OBSERVED BY THE CHILD PROCESS that "
    "consumes it, never the value the setter wrote. Which scope does each consumer actually read? "
    "(Shell-script line endings are owned by TST-0192 in slice TST-2.)",
    ["rules/common/windows-shell.md", "rules/common/single-signal-verification.md"],
    ["TST-0031"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "for each variable and scoped key, the value read back FROM THE CONSUMER PROCESS alongside "
    "the value written, in the same run; agreement of the writer with itself is not evidence",
    ["test_child_process_observes_the_new_value_in_the_same_session",
     "test_a_write_at_the_wrong_scope_is_detected_as_inert",
     "test_probe_reads_from_the_consumer_not_from_the_setter (detector control)"],
    XV_WIN, "2S", "WIN"))

A(U(68, "Explicit interpreters: a bare .sh invocation on Windows",
    "10",
    "Failure class :11304, and Phase 5 requires 'explicit interpreters for scripts' (:10832). "
    "Target: no hook, launcher or command may invoke a script by path alone; each declares its "
    "interpreter. Question: how many entries in hooks/_dispatch/manifest.json and the plugin "
    "command set rely on shebang resolution that Windows does not perform?",
    [SPEC + ":11304", SPEC + ":10832", "hooks/_dispatch/manifest.json"],
    ["TST-0042"],
    OPUS_PT, "TESTWIN", "local-serialized", 2700, "T",
    "an entry-by-entry interpreter audit plus a live invocation of each on Windows recording "
    "success or the exact 'not recognized' error",
    ["test_every_script_entry_declares_an_interpreter",
     "test_bare_sh_invocation_is_reproduced_as_a_failure_on_windows"],
    XV_WIN, "2S", "WIN"))

A(U(69, "Apostrophe-bearing content breaks the agent shell transport",
    "10",
    "Measured: a literal apostrophe inside a Bash-tool heredoc, grep pattern or python -c closes "
    "the tool's own outer quoting and kills the call before a byte runs - 6+ consecutive failures "
    "in one session. Target: a transport-selection rule (file + -F, or the Write tool) enforced by "
    "a lint over agent-authored commands, with the failure reproduced as the control.",
    ["rules/common/windows-shell.md#10"],
    ["TST-0060"],
    CDX_PT, "TESTWIN", "local-serialized", 2700, "T",
    "the failing invocation reproduced verbatim plus the file-based route succeeding on the "
    "identical payload",
    ["test_apostrophe_payload_fails_the_inline_route (control)",
     "test_apostrophe_payload_succeeds_via_the_file_route"],
    XV_WIN, "2S", "WIN"))

# =========================================================================
# G7 - Plugin lifecycle (0070..0081)   spec Phase 5 :10824-10842, Phase 10 layers 5-8
# =========================================================================
A(U(70, "Clean-install test from the published artifact into an empty profile",
    "10",
    "Phase 10 layer 5 (:10993). Target: install the built package - not the source tree - into a "
    "fresh profile and prove the golden journeys run. A CI-green source tree does not prove the "
    "packaged deliverable works (the measured Reframe precedent). Which runtime dependency is "
    "present in the repo but missing from the package?",
    [SPEC + ":10993", SPEC + ":10826-10840"],
    ["TST-0024", "TST-0035"],
    OPUS_RE, "TESTWIN", "local-serialized", 5400, "T",
    "the install performed against the built artifact with a deterministic postcondition probe on "
    "what it produced (file exists AND parses AND has minimum size), not an exit code",
    ["test_clean_install_into_empty_profile",
     "test_at_least_three_golden_journeys_pass_against_the_installed_artifact"],
    XV_WIN, "2S", "PKG"))

A(U(71, "Upgrade-in-place from every supported prior version",
    "10",
    "Phase 10 layer 6 (:10994). Target: upgrade from each supported prior version and assert user "
    "configuration, enabled/disabled state and custom entries survive. Precedent on this estate: "
    "MCP enabled/disabled curation is load-bearing and must never be wiped by a schema change.",
    [SPEC + ":10994"],
    ["TST-0070", "TST-0047"],
    OPUS_RE, "TESTWIN", "local-serialized", 5400, "T",
    "a per-version before/after diff of the user-owned settings surface with a zero-loss assertion "
    "on every user-authored key",
    ["test_upgrade_preserves_enabled_disabled_curation",
     "test_upgrade_from_each_supported_version",
     "test_upgrade_is_idempotent_when_already_current"],
    XV_WIN, "2S", "PKG"))

A(U(72, "Rollback must restore the prior version without removing user data or commands",
    "10",
    "Phase 10 layer 7 (:10995) and failure class :11347. Target: after a rollback, every "
    "user-created artifact and every previously available command still exists. Question: is any "
    "user-owned path inside the managed directory tree, making it collateral by construction?",
    [SPEC + ":10995", SPEC + ":11347"],
    ["TST-0048", "TST-0071"],
    OPUS_RE, "TESTWIN", "local-serialized", 5400, "T",
    "a full inventory of user-owned paths before and after, compared as sets; any deletion is a "
    "P0 regardless of whether the rollback otherwise succeeded",
    ["test_rollback_restores_prior_version",
     "test_rollback_deletes_zero_user_owned_paths",
     "test_command_inventory_is_unchanged_after_rollback"],
    XV_OWN, "1S", "OWNER", True))

A(U(73, "Uninstall leaves no orphan state",
    "10",
    "Phase 10 layer 8 (:10996). Target: after uninstall, no hook remains registered, no scheduled "
    "task remains, no MCP entry remains, and the profile diff versus pre-install is empty except "
    "for explicitly documented user data. What does the current uninstall leave behind?",
    [SPEC + ":10996"],
    ["TST-0070"],
    OPUS_RE, "TESTWIN", "local-serialized", 5400, "T",
    "a pre-install versus post-uninstall profile diff enumerated path by path, with every residual "
    "either documented-intentional or a defect",
    ["test_no_orphan_hook_registration",
     "test_no_orphan_scheduled_task_or_mcp_entry",
     "test_documented_user_data_survives"],
    XV_WIN, "2S", "PKG"))

A(U(74, "Repair command recovers a deliberately corrupted install",
    "10",
    "Phase 5 lists a repair command (:10836). Target: corrupt the INSTALL TREE in each distinct "
    "way (missing file, truncated manifest, wrong file permissions, missing interpreter shim) and "
    "require repair to restore a working state or fail naming the unrepairable component. Cache "
    "corruption is a different substrate and is owned by TST-0097.",
    [SPEC + ":10836"],
    ["TST-0070"],
    CDX_PT, "TESTWIN", "local-serialized", 5400, "F",
    "one corruption mode per test with the repair outcome and the post-repair golden-journey "
    "result; 'repair returned 0' alone is not evidence",
    ["test_repair_from_each_corruption_mode",
     "test_unrepairable_corruption_fails_loudly_naming_the_component"],
    XV_WIN, "2S", "PKG"))

A(U(75, "Health check must be truthful in both the healthy and the broken state",
    "10",
    "Phase 5 lists a health check (:10835). Target: the health check reports GREEN on a good "
    "install and RED on each seeded breakage. A health check that is green in both states is the "
    "single most dangerous component in the platform.",
    [SPEC + ":10835", SPEC + ":11324"],
    ["TST-0013", "TST-0074"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "D",
    "the both-states pair run for every individual health sub-check, not for the aggregate verdict "
    "only",
    ["test_each_subcheck_fires_on_its_own_breakage",
     "test_aggregate_green_requires_all_subchecks_green",
     "test_a_subcheck_that_cannot_fail_is_rejected"],
    XV_WIN, "2S", "GREEN"))

A(U(76, "Conformance validator self-test: prove the validator is armed in CI",
    "10",
    "Measured defect: tools/command-center/validate.py's field-completeness check is disarmed "
    "because require_complete defaults False and CI invokes the tool bare, so deleting the entire "
    "defaults block exits 0. Target: mutation-test the validator itself - every rule it claims to "
    "enforce must be shown to fire under the ACTUAL CI invocation, not under a hand-picked flag.",
    ["tools/command-center/validate.py", ".github/workflows/quality.yml",
     "tools/command-center/tests/test_validate.py"],
    ["TST-0038", "TST-0015"],
    OPUS_DA, "TEST", "local-parallel", 3600, "D",
    "a rule-by-rule mutation table run through the exact CI command line; any rule that does not "
    "fire under the CI invocation is reported as DISARMED with the flag that would arm it",
    ["test_every_validator_rule_fires_under_the_ci_invocation",
     "test_deleting_the_defaults_block_turns_ci_red"],
    XV, "2S", "GREEN"))

A(U(77, "Migration from every historical on-disk layout",
    "10",
    "Phase 5 requires migration from old layouts (:10837). Target: reconstruct each historical "
    "layout from git history, run the migration, and assert the result is byte-equivalent to a "
    "clean install plus the migrated user data. Which historical layouts exist and which have no "
    "migration path?",
    [SPEC + ":10837"],
    ["TST-0047", "TST-0070"],
    CDX_PT, "TESTWIN", "local-serialized", 5400, "T",
    "each historical layout reconstructed from a real commit (SHA recorded) rather than "
    "hand-built, with the post-migration comparison attached",
    ["test_migration_from_each_reconstructed_layout",
     "test_migration_is_idempotent",
     "test_a_layout_with_no_migration_is_reported_not_skipped"],
    XV_WIN, "2S", "PKG"))

A(U(78, "Compatibility detection: refuse every unsupported combination and no supported one",
    "10",
    "Phase 5 requires compatibility diagnostics (:10838). Target: attempt installation against "
    "every declared UNSUPPORTED client/OS/version combination and assert it is refused, and "
    "against every SUPPORTED combination and assert it proceeds - a both-states matrix over the "
    "whole support contract. A refusal on a supported combination is as much a defect as a "
    "silent install on an unsupported one. The WORDING of the resulting message is scored by "
    "TST-0113 and is deliberately not duplicated here.",
    [SPEC + ":10838", "command-center/RELEASE-CHECKLIST.md"],
    ["TST-0049"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "T",
    "an outcome recorded for every cell of the support matrix, both halves populated; a cell "
    "never attempted is reported UNTESTED rather than assumed to behave",
    ["test_every_unsupported_combination_is_refused",
     "test_every_supported_combination_proceeds (the both-states pair)",
     "test_untested_cells_are_reported_not_omitted"],
    XV_WIN, "2S", "PKG"))

A(U(79, "Live-deployment synchronisation must be non-destructive under two-directional drift",
    "10",
    "Failure class :11305 plus a measured instance: of 88 rules files only 5 are byte-identical "
    "between the repo tree and the live tree, 28 differ in real content, 25 are repo-larger and 3 "
    "are live-larger - so neither side is a superset and a one-directional Copy-Item -Force in "
    "EITHER direction destroys content. Target: the sync tool must detect two-directional drift "
    "and refuse rather than overwrite.",
    [SPEC + ":11305", "scripts/sync-rules.ps1", "rules/common/harness-vcs-hygiene.md"],
    ["TST-0031"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "T",
    "a per-file three-way classification (repo-ahead, live-ahead, diverged, EOL-only) computed by "
    "a deterministic differ, not by agent judgement; the measured estate precedent is that LLM "
    "classification of this exact comparison was 86% accurate with 100% of errors pointing at "
    "data loss",
    ["test_sync_refuses_on_a_diverged_pair",
     "test_sync_proceeds_on_a_strictly_one_directional_pair",
     "test_eol_only_differences_are_not_reported_as_content_drift"],
    XV_OWN, "1S", "OWNER", True))

A(U(80, "Stale cache must not mask a fixed package",
    "10",
    "Failure class :11306. Target: install a broken version, fix it, reinstall, and assert the "
    "fixed behaviour is observed - i.e. the cache key includes something that actually changes. "
    "Question: what is the cache key composed of, and can two materially different packages share "
    "one?",
    [SPEC + ":11306"],
    ["TST-0070"],
    CDX_PT, "TESTWIN", "local-serialized", 3600, "F",
    "the cache key derivation quoted at file:line plus a demonstrated collision attempt; a "
    "content hash that omits a shipped file is a defect",
    ["test_fixed_package_is_observed_after_reinstall",
     "test_cache_key_changes_when_any_shipped_byte_changes",
     "test_explicit_cache_invalidation_works"],
    XV_WIN, "2S", "PKG"))

A(U(81, "Package hygiene: no .git, no unrelated caches, no gigabyte payloads",
    "10",
    "Failure class :11307 and the explicit prohibition at :10842. Target: a packaging gate that "
    "fails on any .git directory, transcript, credential-shaped file, log, or total size above a "
    "declared budget. Question: what does the current package actually contain, file by file?",
    [SPEC + ":11307", SPEC + ":10842", ".github/workflows/no-runtime-junk.yml"],
    ["TST-0035"],
    OPUS_RE, "TEST", "local-parallel", 2700, "T",
    "a complete file listing of the built package with sizes, plus the gate demonstrated failing "
    "on a deliberately polluted build",
    ["test_gate_fails_on_a_planted_dot_git",
     "test_gate_fails_above_the_size_budget",
     "test_clean_package_passes (the both-states pair)"],
    XV_SEC, "2S", "PKG"))

# =========================================================================
# G8 - Hook, skill and router live wiring (0082..0087)
# =========================================================================
A(U(82, "Installed but unloaded: the plugin appears present while its hooks never fire",
    "10",
    "Failure class :11303. Measured precedent: a $schema key in hooks.json made Codex load ZERO "
    "hooks while everything looked installed. Target: an end-to-end probe that triggers each hook "
    "event and asserts an observable side effect - registration is not execution.",
    [SPEC + ":11303", "hooks/_dispatch/manifest.json", "hooks/_dispatch/test_wiring.py"],
    ["TST-0042", "TST-0070"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "D",
    "a per-hook trigger with the observed side effect (a written receipt line), plus the "
    "known-broken control (a deliberately malformed config) proving the probe can see the "
    "unloaded state",
    ["test_each_hook_produces_an_observable_effect_when_triggered",
     "test_malformed_config_is_detected_as_zero_hooks_loaded (control)"],
    XV_WIN, "2S", "GREEN"))

A(U(83, "A skill exists in the repository but not in the live skill directory",
    "10",
    "Failure class :11329. Target: a bidirectional reconciliation between the repo skill set and "
    "the deployed skill set, reporting repo-only, live-only and content-divergent entries. "
    "Distinct from unit TST-0079 (which tests the sync TOOL's safety); this measures the "
    "AVAILABILITY consequence for capability routing.",
    [SPEC + ":11329", "rules/common/harness-vcs-hygiene.md"],
    ["TST-0079"],
    CDX_PT, "TESTWIN", "local-serialized", 2700, "T",
    "three counts (repo-only, live-only, divergent) computed by a deterministic differ, each with "
    "its file list; a zero must be backed by the differ finding a planted case",
    ["test_differ_finds_a_planted_repo_only_skill",
     "test_all_three_directions_are_reported"],
    XV_WIN, "2S", "GOV"))

A(U(84, "Capability router must select an installed skill when it is the right one",
    "8",
    "Failure class :11330 and Phase 8 (:10952-10963). Target: a labelled benchmark of "
    "(task prompt -> expected capability) pairs measuring recall of the router over the FULL "
    "installed repertoire, including rarely-used skills. The spec forbids pruning capabilities "
    "merely because they were rarely used (:10950).",
    [SPEC + ":11330", SPEC + ":10950-10963", ".github/workflows/routing-benchmark.yml"],
    ["TST-0083"],
    OPUS_BE, "TEST", "local-parallel", 5400, "B",
    "recall and precision reported per capability with the labelled set committed; a headline "
    "average that hides a zero-recall capability is an overclaim",
    ["test_recall_reported_per_capability_not_only_in_aggregate",
     "test_a_rarely_used_but_correct_skill_is_selected",
     "negative control: a task with no matching capability must produce the fallback, not a "
     "confident wrong pick"],
    XV, "2S", "BENCH"))

A(U(85, "Router top-k injection must not flood the context window",
    "8",
    "Phase 8 requires 'top-k injection with confidence' and a regression suite proving the router "
    "selects relevant capabilities 'without flooding context' (:10957, :10963). Target: measure "
    "injected tokens per turn as a function of the installed capability count and assert a budget. "
    "Precedent: skills-context-budget overflow was the root cause of naive sessions on this estate.",
    [SPEC + ":10957", SPEC + ":10963"],
    ["TST-0084"],
    OPUS_BE, "TEST", "local-parallel", 3600, "B",
    "injected-token counts measured at 10, 100 and 500 installed capabilities, with the growth "
    "curve reported; a single-point measurement cannot show flooding",
    ["test_injected_tokens_stay_under_budget_at_500_capabilities",
     "test_growth_is_sublinear_in_the_installed_count"],
    XV_STAT, "2S", "BENCH"))

A(U(86, "Every hook must fail open: any hook error exits 0",
    "10",
    "AGENTS.md 6 and the hook contract require all hook code wrapped so that an error exits 0 "
    "(fail-open), blocking only on genuinely dangerous operations. Target: inject an exception at "
    "each hook's entry point and assert the session continues; separately assert that the "
    "block-worthy cases still exit 2.",
    ["rules/common/hooks.md", "hooks/_dispatch/dispatch.py", SPEC + ":10811"],
    ["TST-0042"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "D",
    "per-hook injected-exception outcome plus the exit code, and the paired evidence that a "
    "genuinely dangerous operation still blocks",
    ["test_injected_exception_exits_zero_for_every_hook",
     "test_dangerous_operation_still_exits_two (the both-states pair)"],
    XV_WIN, "2S", "GREEN"))

A(U(87, "Editing a deployed copy must be detected: the repo is the source of truth",
    "10",
    "harness-vcs-hygiene requires that the repo is the source of truth and the live tree is a "
    "deploy target; editing a deployed copy is invisible to git and is overwritten on the next "
    "deploy. Target: an edit-time guard that fires when a write targets a deployed path that has "
    "a repo counterpart, and stays silent for genuinely live-only scratch paths.",
    ["rules/common/harness-vcs-hygiene.md"],
    ["TST-0083"],
    CDX_PT, "TESTWIN", "local-serialized", 2700, "D",
    "the guard fired on a real deployed-path write and silent on a scratch write, both recorded "
    "with the paths",
    ["test_guard_fires_on_a_deployed_path_with_a_repo_counterpart",
     "test_guard_is_silent_on_a_live_only_scratch_path"],
    XV_WIN, "2S", "GOV"))

# =========================================================================
# G9 - Distributed execution reliability (0088..0104)
# =========================================================================
A(U(88, "Partial artifact without a sentinel: kill a unit mid-write",
    "10",
    "Failure classes :11009 and :11313. Target: SIGKILL a unit while it is streaming its artifact "
    "and assert the fan-in classifies the truncated file FAILED at condition 5, never SUCCESS. "
    "Distinct from TST-0004 (artifact wholly absent): here the file exists, parses partially, and "
    "looks plausible.",
    [SPEC + ":11009", SPEC + ":11313"],
    ["TST-0008"],
    OPUS_FI, "FAULT", "local-serialized", 3600, "F",
    "the truncated artifact preserved as a fixture with its byte length, plus the classification "
    "and the condition id that rejected it",
    ["test_truncated_artifact_is_failed_not_success",
     "test_atomic_write_prevents_the_partial_from_being_visible_at_all (the stronger fix)"],
    XV, "NONE", "DIST"))

A(U(89, "The monitor dies while remote work continues",
    "10",
    "Failure class :11315 and Phase 10 layer 22 (:11010). Target: kill the monitor mid-run and "
    "assert (a) the remote work completes, (b) its results are harvestable afterwards, and (c) the "
    "monitor's death is distinguishable from the work's death in the ledger.",
    [SPEC + ":11315", SPEC + ":11010"],
    ["TST-0088"],
    OPUS_FI, "FAULT", "local-serialized", 3600, "F",
    "the post-mortem harvest recovering the completed results, with the ledger showing two "
    "distinct events (monitor-died, work-completed) rather than one ambiguous silence",
    ["test_work_survives_monitor_death",
     "test_results_are_harvestable_after_monitor_death",
     "test_ledger_distinguishes_monitor_death_from_work_death"],
    XV, "NONE", "DIST"))

A(U(90, "Orphaned work must be reclaimable exactly once: lease expiry with a fencing token",
    "10",
    "Phase 9 requires work claims, file leases, conflict detection and duplicate-work suppression "
    "(:10972-10975). Target: when the dispatcher holding a unit's lease dies, a new dispatcher may "
    "reclaim the unit after lease expiry, and the ORIGINAL must be unable to commit a late result "
    "afterwards - a monotonically increasing fencing token, not a timeout alone, is what makes "
    "reclaim safe. Question: can a zombie dispatcher that wakes after expiry still write a "
    "receipt? (Monitor-death observation is TST-0089; mtime-based stall detection is owned by "
    "TST-0152 in slice TST-2.)",
    [SPEC + ":10972-10975", SPEC + ":11315"],
    ["TST-0089"],
    OPUS_FI, "FAULT", "local-serialized", 3600, "F",
    "a run in which the original dispatcher is frozen past lease expiry, the unit is reclaimed and "
    "completed, and the thawed original's write is then REJECTED with its stale token recorded",
    ["test_expired_lease_permits_exactly_one_reclaim",
     "test_thawed_original_write_is_rejected_by_the_fencing_token",
     "test_two_concurrent_reclaimers_do_not_both_win",
     "test_unexpired_lease_blocks_reclaim (the both-states pair)"],
    XV, "NONE", "DIST"))

A(U(91, "One hung unit must not block a large batch",
    "10",
    "Failure class :11317. Measured: parallel() has no per-agent timeout, so one hung agent "
    "deadlocks the whole phase - detected only by a write-freeze longer than 25 minutes. Target: "
    "per-unit timeouts and a per-work-unit pipeline so the barrier resolves on the survivors with "
    "the hung unit classified, not silently awaited.",
    [SPEC + ":11317", "rules/common/fan-out-contract.md"],
    ["TST-0089"],
    OPUS_FI, "FAULT", "local-serialized", 5400, "F",
    "a batch of N units with one deliberately hung: the barrier must resolve within the declared "
    "timeout with N-1 results plus one typed timeout classification",
    ["test_barrier_resolves_despite_one_hung_unit",
     "test_hung_unit_is_classified_timeout_not_silently_dropped",
     "test_survivor_results_are_complete_and_attributed"],
    XV, "NONE", "DIST"))

A(U(92, "Arrival-rate scheduler: stagger and jitter as a measured property",
    "10",
    "Spec: 'Stagger arrivals to avoid 429 thundering-herd failures. Treat quota and arrival rate "
    "as scheduler inputs' (:10577-10578). Target: a property test over the scheduler asserting "
    "that for any batch size and any declared rate cap, the realised inter-arrival distribution "
    "never exceeds the cap in any sliding window. Distinct from TST-0093, which tests the "
    "RESPONSE to a 429 rather than its prevention.",
    [SPEC + ":10577-10578"],
    ["TST-0027"],
    OPUS_BE, "TEST", "local-parallel", 3600, "B",
    "sliding-window arrival counts computed from a simulated dispatch of >=1000 units at several "
    "caps, with the max observed window rate printed per cap",
    ["test_no_sliding_window_exceeds_the_cap (property, >=1000 generated schedules)",
     "test_jitter_is_actually_applied (identical timestamps across units is a defect)"],
    XV_STAT, "SEED", "BENCH"))

A(U(93, "429 backoff and resume correctness under a mocked rate limiter",
    "10",
    "Failure class :11318 and Phase 10 layer 20 (:11008). Target: with a deterministic mock "
    "returning 429 with Retry-After, assert the dispatcher backs off, does not duplicate work, and "
    "resumes to completion. Estate rule: a 529/overload is provider-side and must NOT trigger a "
    "self-imposed concurrency reduction - assert the concurrency setting is unchanged after the "
    "storm.",
    [SPEC + ":11318", SPEC + ":11008"],
    ["TST-0092"],
    OPUS_FI, "FAULT", "local-parallel", 3600, "F",
    "the request timeline captured from the mock, showing honoured Retry-After, zero duplicate "
    "unit executions, and an unchanged concurrency setting",
    ["test_retry_after_is_honoured",
     "test_no_duplicate_execution_after_a_429_storm",
     "test_concurrency_setting_is_not_self_throttled"],
    XV, "NET3", "DIST"))

A(U(94, "Remote harvest that silently does nothing",
    "10",
    "Failure class :11319. Target: a harvest run against a remote substrate that has produced zero "
    "new artifacts must be distinguishable from a harvest whose connection or filter silently "
    "matched nothing. Measured analogue: a job filter keyed on session id where the written record "
    "carried null, hiding every result.",
    [SPEC + ":11319", "rules/common/cross-vendor-dispatch.md#1"],
    ["TST-0089"],
    OPUS_FI, "FAULT", "local-serialized", 3600, "F",
    "three runs recorded - genuinely-nothing-to-harvest, filter-mismatch, and connection-failure - "
    "each producing a DIFFERENT typed outcome rather than a shared empty result",
    ["test_empty_harvest_and_broken_harvest_are_distinguishable",
     "test_a_null_key_in_the_filter_is_rejected_at_write_time"],
    XV, "2S", "DIST"))

A(U(95, "Duplicate units from colliding catalogs",
    "10",
    "Failure class :11320. Directly live on this program: 31 option IDs resolve to two unrelated "
    "meanings across two artifacts sharing the M-NN namespace, and a third and fourth M-NN "
    "namespace exist on disk. Target: a namespace-collision gate over every id-bearing artifact "
    "(work units, options, blueprints, presets) that fails on any id resolving to more than one "
    "definition.",
    [SPEC + ":11320", "command-center/OPTION-ID-RESOLUTION.json"],
    ["TST-0057"],
    OPUS_GA, "TEST", "local-parallel", 3600, "T",
    "a full id -> definitions map across all namespaces with the multi-definition ids enumerated; "
    "the extractor proven on the known 31-way case before any zero elsewhere is trusted",
    ["test_extractor_reproduces_the_known_collision_set (detector control)",
     "test_gate_fails_on_any_id_with_two_definitions",
     "test_dispatch_refuses_to_run_two_units_with_the_same_id"],
    XV, "2S", "GOV"))

A(U(96, "Resume after a crash mid-unit",
    "9",
    "Phase 10 layer 24 (:11012) and Phase 9 crash recovery (:10976). Target: kill the runner at "
    "each of several checkpoints and assert resume re-executes exactly the incomplete units, "
    "re-executes nothing already complete, and produces the identical final artifact set as an "
    "uninterrupted run.",
    [SPEC + ":11012", SPEC + ":10976"],
    ["TST-0088"],
    OPUS_FI, "FAULT", "local-serialized", 5400, "F",
    "an artifact-set hash comparison between the interrupted-then-resumed run and a clean run, "
    "plus the list of units re-executed",
    ["test_resume_reexecutes_only_incomplete_units",
     "test_resumed_artifact_set_hash_equals_the_clean_run",
     "test_resume_from_each_of_at_least_four_checkpoints"],
    XV, "NONE", "DIST"))

A(U(97, "Corrupted cache recovery",
    "10",
    "Phase 10 layer 25 (:11013). Target: corrupt the cache in each distinct way (truncated entry, "
    "wrong hash, unreadable permissions, half-written temp file left behind) and assert the system "
    "detects and rebuilds rather than serving corrupt data. Precedent: a render cancelled mid-write "
    "can leave a half-file unless writes are atomic (tmp + mv -f).",
    [SPEC + ":11013", "rules/common/bash-hud-and-terminal-emit.md#7"],
    ["TST-0080"],
    CDX_FI, "FAULT", "local-serialized", 3600, "F",
    "one corruption mode per case with the detection mechanism named; serving a corrupt entry "
    "silently is a P0",
    ["test_each_corruption_mode_is_detected",
     "test_cache_writes_are_atomic",
     "test_rebuild_produces_a_correct_entry"],
    XV, "2S", "DIST"))

A(U(98, "Network fault-injection matrix",
    "10",
    "Phase 10 layer 19 (:11007). Target: inject DNS failure, connection reset, TLS error, slow "
    "loris, truncated response and mid-stream disconnect at every external boundary, asserting a "
    "typed failure and preserved partial work. Which boundary swallows a fault into an empty "
    "success?",
    [SPEC + ":11007"],
    ["TST-0093"],
    OPUS_FI, "FAULT", "local-parallel", 5400, "F",
    "a boundary x fault outcome matrix; every cell must be a typed classification, and any cell "
    "reading 'empty success' is a P1 with the code path quoted",
    ["test_every_boundary_produces_a_typed_failure_per_fault",
     "test_partial_work_is_preserved_across_every_fault"],
    XV, "NET3", "DIST"))

A(U(99, "Parallel agents sharing one git index contaminate each other",
    "10",
    "Phase 10 layer 15 (:11003) plus a measured estate defect: file-disjoint agents share one git "
    "index, so a broad `git add -A` sweeps siblings' work. Target: prove isolation (worktree per "
    "shard, per :10581) or prove the scoped-add discipline holds under real concurrency.",
    [SPEC + ":11003", SPEC + ":10581"],
    ["TST-0096"],
    OPUS_FI, "FAULT", "local-serialized", 5400, "F",
    "a concurrent run of >=4 file-disjoint agents with the staged-file set captured per commit; "
    "any commit containing a sibling's path is the defect, quoted",
    ["test_no_commit_contains_a_sibling_agents_path",
     "test_worktree_isolation_actually_isolates_the_index",
     "test_the_probe_can_detect_a_planted_contamination (control)"],
    XV, "NONE", "DIST"))

A(U(100, "A worktree pointing at the wrong repository",
    "9",
    "Failure class :11321. Target: before any write, a guard resolves the worktree's origin URL "
    "and refuses when it is not the pinned repository. This program operates under a hard "
    "constraint naming a concurrently-owned tree that must never be touched; the guard is what "
    "makes that mechanical rather than a matter of care.",
    [SPEC + ":11321", "rules/common/harness-vcs-hygiene.md"],
    ["TST-0099"],
    OPUS_FI, "TESTWIN", "local-serialized", 2700, "D",
    "the guard demonstrated refusing a write in a scratch clone of a DIFFERENT repository, and "
    "permitting it in the pinned one",
    ["test_write_to_a_foreign_worktree_is_refused",
     "test_write_to_the_pinned_worktree_is_permitted",
     "test_guard_resolves_origin_by_command_not_by_path_string"],
    XV_WIN, "1S", "DIST"))

A(U(101, "A stale branch would revert newer work",
    "10",
    "Failure class :11322. Measured: a leftover feature branch showed 1,188 files / 316,222 "
    "deletions against main; and separately, squash-merge makes a fully merged branch report as "
    "AHEAD, so commit ancestry is not a delete authorisation. Target: a pre-PR gate computing the "
    "three-dot commit-to-commit surface and failing on mass deletion.",
    [SPEC + ":11322", "rules/common/windows-shell.md#8d", "rules/common/ci-hygiene.md"],
    ["TST-0100"],
    OPUS_GA, "GH", "local-serialized", 2700, "T",
    "the three-dot diffstat for the branch under test alongside the two-dot one, showing the "
    "difference explicitly; plus a squash-merged branch demonstrated reporting AHEAD",
    ["test_gate_fails_on_a_stale_branch_proposing_mass_deletion",
     "test_gate_uses_three_dot_not_two_dot",
     "test_squash_merged_branch_is_not_treated_as_unmerged"],
    XV, "2S", "GOV"))

A(U(102, "Eager per-session MCP process multiplication",
    "10",
    "Failure class :11326. Measured: 23 sessions x 65 servers produced 2,037 processes; the same "
    "class later showed 320 live MCP processes with disabled servers still spawning 10 minutes "
    "after a restart, because the disable was written at the wrong config scope. Target: a test "
    "that counts real processes (not config intent) after opening N sessions.",
    [SPEC + ":11326"],
    ["TST-0086"],
    OPUS_PT, "TESTWIN", "local-serialized", 3600, "F",
    "a process-table count taken from the OS after N sessions, corroborated against the config "
    "state; the config alone is not evidence that the disable took effect",
    ["test_process_count_scales_as_designed_not_multiplicatively",
     "test_a_disabled_server_spawns_zero_processes (measured from the process table)"],
    XV_WIN, "1S", "DIST", True))

A(U(103, "Commit-exhaustion guard: process creation freezes before RAM is exhausted",
    "10",
    "Failure class :11327. Measured root cause on this box: the freeze is COMMIT charge "
    "(RAM+pagefile) exhaustion, not RAM OOM - Task Manager hides it and Event 2004 is the smoking "
    "gun. Target: a load test that drives commit charge toward the limit and asserts the guard "
    "sheds load BEFORE process creation fails, plus a probe that reads commit charge rather than "
    "working set.",
    [SPEC + ":11327"],
    ["TST-0102"],
    OPUS_FI, "FAULT", "local-serialized", 5400, "F",
    "commit-charge and available-commit sampled during the ramp (two different counters), with "
    "the shed-load event timestamped before the first process-creation failure",
    ["test_guard_sheds_load_before_process_creation_fails",
     "test_probe_reads_commit_charge_not_working_set (a working-set probe is silent in the "
     "failing state)"],
    XV_OWN, "1S", "OWNER", True))

A(U(104, "A kill-based memory guard must not terminate a live shared service",
    "10",
    "Failure class :11328. Target: with a shared always-on service running (the local agent-mail "
    "server is the concrete case), drive memory pressure and assert the guard's kill selection "
    "excludes protected services and orphan-reaps only genuine orphans. A guard that kills the "
    "coordination channel converts a slowdown into an outage.",
    [SPEC + ":11328"],
    ["TST-0103"],
    OPUS_FI, "FAULT", "local-serialized", 3600, "F",
    "the guard's selected kill set recorded under pressure, compared against the protected list; "
    "the shared service must still answer its health endpoint afterwards",
    ["test_protected_service_survives_the_guard",
     "test_genuine_orphan_is_reaped (the both-states pair)",
     "test_kill_selection_is_logged_with_a_reason_per_pid"],
    XV_OWN, "1S", "OWNER", True))

# =========================================================================
# G10 - Benchmark and overhead (0105..0110)
# =========================================================================
A(U(105, "Benchmark harness with a mandatory non-empty-input control",
    "10",
    "Measured on this estate: two benchmarks measured EMPTY inputs and returned a clean, "
    "meaningless green. Target: the harness refuses to emit a number unless it asserts input "
    "cardinality and echoes it beside the result; a zero-cardinality run is FAILED, not fast.",
    [SPEC + ":11021", ".github/workflows/routing-benchmark.yml"],
    ["TST-0025"],
    OPUS_BE, "TEST", "local-parallel", 3600, "B",
    "every emitted benchmark row carries n_inputs; the harness demonstrated failing on an "
    "empty-input run",
    ["test_empty_input_run_is_failed_not_reported",
     "test_input_cardinality_is_printed_with_every_number"],
    XV_STAT, "SEED", "BENCH"))

A(U(106, "Benchmark regression gate against the pinned baseline",
    "10",
    "Phase 10 layer 33 (:11021) and stopping condition 8 (:11385). Target: compare against the "
    "TST-0025 baseline with a declared tolerance derived from measured variance, so a regression "
    "verdict is statistically meaningful rather than a single-run comparison.",
    [SPEC + ":11021", SPEC + ":11385"],
    ["TST-0105", "TST-0109"],
    OPUS_BE, "TEST", "local-parallel", 3600, "B",
    "the tolerance derived from the measured variance band (TST-0109), quoted, with the "
    "regression decision shown for at least one planted slowdown",
    ["test_planted_slowdown_beyond_tolerance_is_caught",
     "test_within_noise_change_is_not_reported_as_a_regression"],
    XV_STAT, "SEED", "BENCH"))

A(U(107, "Per-invocation overhead budget for hooks and the status surface",
    "10",
    "Phase 10 layer 34 (:11022). Measured: the status line is debounced at 300 ms and a slow "
    "render is CANCELLED, with a jq spawn at ~200 ms and a bare bash at ~350 ms - so process "
    "spawn count, not code, is the budget. Target: measure spawns per invocation by shimming PATH "
    "(never by grepping the script text) and enforce a budget.",
    [SPEC + ":11022", "rules/common/bash-hud-and-terminal-emit.md#7"],
    ["TST-0105"],
    OPUS_BE, "TESTWIN", "local-serialized", 3600, "B",
    "spawn counts from the PATH shim, with the shim first proven to catch a known spawn before "
    "any zero is trusted",
    ["test_shim_catches_a_known_spawn (detector control)",
     "test_spawn_count_per_invocation_is_within_budget",
     "test_idle_session_pays_zero_for_gated_probes"],
    XV_WIN, "SEED", "BENCH"))

A(U(108, "Fan-out cost model: tokens and wall-clock per work unit",
    "10",
    "The spec makes resource cost a scheduler input rather than an objective (:10578, :10584). "
    "Target: a measured cost model (tokens and wall-clock per unit, by substrate) that the "
    "scheduler can consume, plus a dry-run estimate (:10892) validated against actuals. What is "
    "the estimate's error distribution?",
    [SPEC + ":10578", SPEC + ":10892"],
    ["TST-0092"],
    OPUS_BE, "TEST", "local-parallel", 5400, "B",
    "estimate-versus-actual for >=50 real units with the error distribution reported, not a mean "
    "alone",
    ["test_estimate_is_within_the_declared_error_band_for_the_median_unit",
     "test_the_tail_error_is_reported_explicitly"],
    XV_STAT, "SEED", "BENCH"))

A(U(109, "Variance banding: how many runs before a benchmark number means anything",
    "10",
    "Target: for each benchmark, run n repetitions at one SHA and compute the variance band, then "
    "derive the minimum n at which a claimed improvement is distinguishable from noise. Without "
    "this, every regression and improvement claim in the program is uncalibrated.",
    [SPEC + ":11021"],
    ["TST-0105"],
    OPUS_BE, "TEST", "local-parallel", 5400, "B",
    "per-benchmark n, mean, standard deviation and the derived minimum detectable effect, with "
    "the raw per-run numbers attached",
    ["test_minimum_detectable_effect_is_computed_per_benchmark",
     "test_raw_per_run_numbers_are_preserved_not_only_the_summary"],
    XV_STAT, "SEED", "BENCH"))

A(U(110, "Benchmark-gaming detector: does the metric move without the mechanism?",
    "10",
    "Spec Phase 12 assigns a refuter for benchmark gaming (:11059) and requires that a merged "
    "workflow is 'not accepted because it contains more stages' (:11170). Target: for each "
    "benchmark, construct a null change that should NOT move the metric and a mechanism change "
    "that SHOULD; a metric that moves on the null is gameable and must be replaced.",
    [SPEC + ":11059", SPEC + ":11170"],
    ["TST-0109"],
    CDX_GA, "TEST", "local-parallel", 3600, "B",
    "a null-change and mechanism-change pair per benchmark with the measured delta for each; a "
    "significant delta on the null is reported as GAMEABLE with the benchmark named",
    ["test_null_change_does_not_move_the_metric",
     "test_mechanism_change_does_move_the_metric (the both-states pair)"],
    XV_STAT, "SEED", "BENCH"))

# =========================================================================
# G11 - Documentation, error text and accessibility (0111..0115)
# =========================================================================
A(U(111, "Every command printed in the documentation must execute",
    "10",
    "Phase 10 layer 36 (:11024). Target: extract every fenced command from the docs, execute it in "
    "a sandbox with a declared allowlist, and assert success or an explicit NOT-EXECUTABLE marker "
    "in the doc. How many documented commands are currently broken?",
    [SPEC + ":11024", SPEC + ":11115-11117"],
    ["TST-0070"],
    OPUS_DX, "TESTWIN", "local-serialized", 5400, "T",
    "a command-by-command execution table with exit codes; a command excluded from execution must "
    "carry an explicit marker in the source doc, not merely be skipped by the runner",
    ["test_every_fenced_command_is_executed_or_explicitly_marked",
     "test_extractor_finds_a_planted_command (detector control)"],
    XV_WIN, "2S", "GREEN"))

A(U(112, "Docs-and-code parity gate",
    "10",
    "Stopping condition 12 requires 'docs and code agree' (:11389) and Phase 14 meta-review checks "
    "for 'mismatches between code and docs' (:11095). Target: a mechanical parity check over the "
    "surfaces where drift is detectable - documented CLI flags versus the parser's actual flags, "
    "documented config keys versus the schema, documented file paths versus the tree.",
    [SPEC + ":11389", SPEC + ":11095"],
    ["TST-0111"],
    CDX_GA, "TEST", "local-parallel", 3600, "T",
    "three set differences (flags, keys, paths) computed in both directions with counts; a "
    "documented-but-absent flag and an undocumented-but-real flag are different defects",
    ["test_documented_flags_match_the_parser_both_directions",
     "test_documented_config_keys_exist_in_the_schema",
     "test_documented_paths_resolve"],
    XV, "2S", "GOV"))

A(U(113, "User-facing error messages must name the component, the cause and the remedy",
    "10",
    "Phase 5 requires 'clear user-facing error messages' (:10840). Target: trigger every "
    "error path and score its message against a three-part rubric (what failed, why, what to do). "
    "A message that only says an operation failed is a defect, not a style preference.",
    [SPEC + ":10840"],
    ["TST-0078"],
    OPUS_DX, "TESTWIN", "local-serialized", 3600, "T",
    "the verbatim message for every triggered error path with a rubric score per part; scores "
    "assigned against the captured text, not from reading the source",
    ["test_every_error_path_is_triggered_at_least_once",
     "test_each_message_scores_on_all_three_rubric_parts"],
    XV_WIN, "2S", "GOV"))

A(U(114, "Accessibility tests for the operator-facing surfaces",
    "10",
    "Phase 10 layer 35 (:11023). Target: for the cockpit and any UI surface, assert contrast "
    "ratios, focus visibility, keyboard reachability and screen-reader labels; for terminal "
    "surfaces, assert the line is readable under NO_COLOR and monochrome, and that no glyph is "
    "double-width (a width-2 mark corrupts alignment on Windows Terminal).",
    [SPEC + ":11023", "rules/common/bash-hud-and-terminal-emit.md#5"],
    ["TST-0113"],
    OPUS_DX, "TESTWIN", "local-serialized", 3600, "T",
    "measured contrast ratios and a rendered capture per theme; for the terminal surface, a "
    "cell-width assertion per glyph rather than a visual judgement",
    ["test_no_double_width_glyph_in_the_status_surface",
     "test_surface_is_readable_under_no_color",
     "test_contrast_meets_the_declared_threshold_in_both_themes"],
    XV_WIN, "2S", "GOV"))

A(U(115, "Quick-start examples must run end-to-end against the packaged artifact",
    "10",
    "Phase 15 requires quick-start and advanced workflow examples (:11116-11117). Target: run each "
    "example against the INSTALLED package in a clean profile and assert a deterministic "
    "postcondition on what it produced - not that the command exited 0.",
    [SPEC + ":11116", SPEC + ":11117"],
    ["TST-0070", "TST-0111"],
    OPUS_RE, "TESTWIN", "local-serialized", 5400, "T",
    "for each example, the produced artifact probed for existence, parseability and a "
    "content-specific property; an exit code alone does not close this unit",
    ["test_each_quick_start_example_produces_its_documented_artifact",
     "test_each_advanced_example_produces_its_documented_artifact",
     "test_examples_run_against_the_package_not_the_source_tree"],
    XV_WIN, "2S", "PKG"))

# =========================================================================
# G12 - Property, fuzz, mutation and chaos INFRASTRUCTURE (0116..0122)
#       (per-target campaigns are left to slices TST-2 and TST-3)
# =========================================================================
A(U(116, "Property-based testing infrastructure with a shrinking and reporting policy",
    "10",
    "Phase 10 layer 13 (:11001). Target: stand up the property-test substrate - generators for the "
    "domain types (work unit, receipt, council spec, workflow DAG), a shrinking policy, and a "
    "reporting format that records the minimal counterexample plus its seed. What domain types "
    "have no generator, and are therefore unreachable by every property test?",
    [SPEC + ":11001"],
    ["TST-0027", "TST-0039"],
    OPUS, "TEST", "local-parallel", 5400, "T",
    "a type-by-type generator inventory with coverage of the schema's field space, plus a shrunk "
    "counterexample demonstrated for a planted invariant violation",
    ["test_a_planted_invariant_violation_is_found_and_shrunk",
     "test_every_domain_type_has_a_generator_or_is_listed_as_ungenerated"],
    XV, "SEED", "CORE"))

A(U(117, "Fuzz corpus management and crash-triage infrastructure",
    "10",
    "Phase 10 layer 14 (:11002). Target: a seed corpus, a coverage-guided loop where available, "
    "crash deduplication by stack fingerprint, and automatic minimisation of each crashing input. "
    "Without triage, a fuzz campaign produces a pile of duplicates rather than defects.",
    [SPEC + ":11002"],
    ["TST-0116"],
    CDX_FI, "TEST", "local-parallel", 7200, "F",
    "the corpus committed with provenance per seed, plus a demonstrated dedup of two crashes "
    "sharing one root cause into a single triage entry",
    ["test_two_inputs_with_one_root_cause_dedup_to_one_entry",
     "test_crashing_input_is_minimised",
     "test_corpus_seeds_are_reproducible_from_the_receipt"],
    XV, "SEED", "CORE"))

A(U(118, "Grammar-aware fuzzing of the workflow DSL and the manifest formats",
    "10",
    "Byte-level fuzzing of a structured format spends its budget on lexer rejects. Target: a "
    "grammar-derived generator that emits syntactically valid but semantically hostile documents "
    "(deep nesting, cyclic subworkflow references, a barrier with zero producers, a loop with no "
    "convergence rule) and asserts a typed rejection rather than a hang or a crash.",
    [SPEC + ":11002", SPEC + ":10805", SPEC + ":10875-10896"],
    ["TST-0117", "TST-0037"],
    OPUS_FI, "TEST", "local-parallel", 7200, "F",
    "the grammar committed alongside the count of generated documents that reached the semantic "
    "layer (a low reach-rate means the fuzzer is testing the lexer, not the system)",
    ["test_semantic_reach_rate_is_reported",
     "test_cyclic_subworkflow_is_rejected_not_hung",
     "test_zero_producer_barrier_is_rejected"],
    XV, "SEED", "CORE"))

A(U(119, "Mutation runner wiring with a measured baseline survival score",
    "10",
    "Phase 10 layer 12 (:11000) and failure class :11325. Target: wire the mutation runner over "
    "the estate-specific operator library (TST-0015), measure the baseline survival score per "
    "module, and enforce a gate that fails on a surviving mutant in the completion-predicate and "
    "detector modules specifically. Measured precedent: one of six mutations survived and exposed "
    "a genuine hole in an otherwise 15/15-green suite.",
    [SPEC + ":11000", SPEC + ":11325"],
    ["TST-0015", "TST-0120"],
    OPUS_DA, "TEST", "local-parallel", 7200, "D",
    "per-module survival scores with every surviving mutant listed by operator and location; an "
    "aggregate score alone hides exactly the survivor that matters",
    ["test_gate_fails_on_a_surviving_mutant_in_the_predicate_module",
     "test_baseline_score_is_recorded_per_module_not_only_in_aggregate"],
    XV, "2S", "GREEN"))

A(U(120, "Equivalent-mutant triage policy so the score cannot be gamed",
    "10",
    "A mutation score is only meaningful once equivalent mutants (semantically identical to the "
    "original) are excluded, and exclusion is exactly where the score becomes gameable. Target: a "
    "written policy plus a review trail - every claimed equivalent mutant needs a justification "
    "recorded and a reviewer, and the count of exclusions is published alongside the score.",
    [SPEC + ":11000", SPEC + ":11059"],
    ["TST-0015"],
    CDX_GA, "TEST", "local-parallel", 3600, "D",
    "the exclusion list with a per-mutant justification and reviewer id; a score published without "
    "its exclusion count is an overclaim",
    ["test_score_is_published_with_the_exclusion_count",
     "test_an_unjustified_exclusion_is_rejected"],
    XV, "2S", "GOV"))

A(U(121, "Differential fuzzing across the strict and lenient parser implementations",
    "10",
    "Target: generate documents and feed them to BOTH parser implementations, treating any "
    "accept/reject disagreement or any value disagreement as a finding. Distinct from TST-0058, "
    "which checks a fixed corpus; this one searches for the disagreement.",
    [SPEC + ":11002", SPEC + ":11014"],
    ["TST-0058", "TST-0117"],
    CDX_FI, "TEST", "local-parallel", 7200, "F",
    "the disagreement corpus preserved as fixtures with the two divergent interpretations recorded "
    "side by side",
    ["test_a_planted_divergence_is_found_by_the_differential",
     "test_every_discovered_disagreement_becomes_a_permanent_fixture"],
    XV, "SEED", "CORE"))

A(U(122, "Chaos fault-point primitive library",
    "10",
    "Phase 10 layer 18 (:11006). Target: a library of injectable fault points - filesystem "
    "(ENOSPC, EACCES, slow write), clock (jump forward, jump back, freeze), process (kill, stop, "
    "resume), and network (delegated to TST-0098) - each individually addressable, deterministic "
    "under a seed, and safe to run against the local box. Per-target chaos campaigns are out of "
    "this slice.",
    [SPEC + ":11006"],
    ["TST-0027", "TST-0098"],
    OPUS_FI, "FAULT", "local-serialized", 5400, "F",
    "each primitive demonstrated causing an observable, reversible effect on a scratch target, "
    "with the reversal verified; a primitive that cannot be reverted is not shipped",
    ["test_each_primitive_produces_its_declared_fault",
     "test_each_primitive_is_reversible",
     "test_a_clock_jump_backwards_does_not_corrupt_the_append_only_log"],
    XV_OWN, "1S", "OWNER", True))

# =========================================================================
# G13 - Test governance and anti-false-coverage (0123..0128)
# =========================================================================
A(U(123, "TEST-REGISTRY and the collected test set must reconcile in both directions",
    "10",
    "Target: every entry in command-center/TEST-REGISTRY.json must map to a test the runner "
    "actually collects, and every collected test must map to a registry entry. Report both counts. "
    "A registry that is a superset manufactures coverage; a runner that is a superset means "
    "unregistered tests gate nothing.",
    ["command-center/TEST-REGISTRY.json", SPEC + ":10596"],
    ["TST-0011"],
    OPUS_GA, "TEST", "local-parallel", 3600, "T",
    "two set differences with explicit counts, computed from the runner's own collection output "
    "rather than from a source grep",
    ["test_registry_only_entries_are_enumerated",
     "test_collected_only_tests_are_enumerated",
     "test_reconciler_finds_a_planted_orphan (detector control)"],
    XV, "2S", "GOV"))

A(U(124, "CI-gate census: every test suite must map to a gate that can turn red",
    "10",
    "Measured on this estate: 162 of 244 suites ran in NO CI gate, and every triage lane that "
    "looked inside that set found a live bug. Target: enumerate suites and gates, join them, and "
    "report the ungated set. A suite nobody runs is not coverage.",
    [".github/workflows/quality.yml", ".github/workflows/no-runtime-junk.yml", SPEC + ":11026"],
    ["TST-0123"],
    CDX_GA, "GH", "local-parallel", 3600, "T",
    "the suite x gate join table with the ungated count; the join must be proven by showing a "
    "known-gated suite appearing on the gated side",
    ["test_every_suite_is_classified_gated_or_ungated",
     "test_a_known_gated_suite_is_correctly_joined (control)",
     "test_ungated_suites_are_listed_by_path"],
    XV, "2S", "GOV"))

A(U(125, "Coverage-threshold source of truth with an explicit NOT-CHECKED emitter",
    "10",
    "Target: read the project's .coverage-thresholds.json enforcement command and run it; when a "
    "project has no such file, emit NOT-CHECKED and surface it rather than folding the absence "
    "into a silent pass. Question: which sub-trees of this repo are coverage-gated and which are "
    "not?",
    ["rules/common/testing.md", SPEC + ":11026"],
    ["TST-0124"],
    OPUS_GA, "TEST", "local-parallel", 2700, "T",
    "the per-subtree verdict (threshold value, or NOT-CHECKED with the reason); a subtree reported "
    "as passing must name the file whose enforcement command was executed",
    ["test_absent_thresholds_file_yields_not_checked_not_pass",
     "test_present_thresholds_file_runs_its_own_enforcement_command"],
    XV, "2S", "GOV"))

A(U(126, "No-op test census: enumerate every test that cannot produce a red",
    "10",
    "Target: one census over three no-op shapes - a test with no assertion, a test skipped "
    "unconditionally, and a test marked xfail that always xfails. Each is a test that cannot fail, "
    "and each inflates the green count. Report the three counts separately and the union.",
    [SPEC + ":11026", "rules/common/testing.md"],
    ["TST-0123"],
    CDX_GA, "TEST", "local-parallel", 3600, "T",
    "the three counts plus the union with every member listed by node id; the census must be "
    "proven by planting one of each shape and finding all three",
    ["test_census_finds_a_planted_assertionless_test",
     "test_census_finds_a_planted_unconditional_skip",
     "test_census_finds_a_planted_always_xfail"],
    XV, "2S", "GOV"))

A(U(127, "Test-order dependence: run the suite in a randomised order",
    "10",
    "Target: run the full suite in several randomised orders at one SHA and identify tests whose "
    "outcome depends on execution order (shared temp dirs, module-level state, a fixture that "
    "leaks). Distinct from the flake ledger (TST-0032), which repeats the SAME order.",
    [SPEC + ":11003", "rules/common/testing.md"],
    ["TST-0032"],
    OPUS_GA, "TEST", "local-parallel", 5400, "T",
    ">=5 distinct seeded orders with the per-test outcome matrix; any test that is not invariant "
    "across orders is named with the suspected shared state",
    ["test_at_least_five_randomised_orders_are_executed",
     "test_order_dependent_tests_are_named_with_their_shared_state",
     "test_a_planted_order_dependence_is_detected (control)"],
    XV, "SEED", "GOV"))

A(U(128, "Invocation parity: console script versus python -m versus the CI entry point",
    "10",
    "Measured residual on this program's own baseline: the runner used `python -m pytest` while CI "
    "uses the console script, which makes that baseline a broken detector for packaging and "
    "import-path regressions by construction. Target: run the same suite through every supported "
    "entry point and assert identical collection sets and identical outcomes.",
    ["command-center/BASELINE-SNAPSHOT.md", SPEC + ":10993"],
    ["TST-0124", "TST-0070"],
    OPUS_GA, "TESTWIN", "local-serialized", 5400, "T",
    "the collected-node-id sets from each entry point compared as sets; a difference in COLLECTION "
    "is a packaging defect even when the outcomes match",
    ["test_collection_sets_are_identical_across_entry_points",
     "test_outcomes_are_identical_across_entry_points",
     "test_a_planted_import_path_break_is_visible_via_the_console_script"],
    XV_WIN, "2S", "PKG"))

# ------------------------------------------------- substrate reassignment ----
# The spec's scaling doctrine (:10574-10584) names four substrates. A first pass
# used only two, which under-uses the doctrine. These overrides carry the reason
# per unit. Rule applied: Windows-specific / GUI / credentialed / live-harness
# probes STAY local-serialized (owner brief + :10575); tree-MUTATING portable
# work goes worktree-isolated (:10581); stateless high-volume portable compute
# goes cloud-batch (:10574, :10576). Benchmarks are deliberately NOT sent to
# cloud-batch: variable hardware would destroy the variance band TST-0109 exists
# to measure.
SUBSTRATE_OVERRIDE = {
    "TST-0015": ("worktree-isolated", "mutation operators rewrite a working tree; must not "
                                      "touch the shared checkout"),
    "TST-0028": ("worktree-isolated", "record/replay needs two materialised builds side by side"),
    "TST-0047": ("worktree-isolated", "migrations mutate artifacts in place; idempotence must be "
                                      "measured on a disposable tree"),
    "TST-0101": ("worktree-isolated", "operates on branch clones and must never stage into the "
                                      "shared index"),
    "TST-0119": ("worktree-isolated", "the mutation runner materialises one defective tree per "
                                      "mutant"),
    "TST-0032": ("cloud-batch", "N>=20 full-suite repetitions is stateless, portable and the "
                                "single largest wall-clock item in the slice"),
    "TST-0092": ("cloud-batch", "pure scheduler simulation over >=1000 generated schedules; no "
                                "local state touched"),
    "TST-0116": ("cloud-batch", "property generation is stateless and embarrassingly parallel"),
    "TST-0117": ("cloud-batch", "fuzz campaigns are long-running, stateless and must not compete "
                                "for local commit charge (see TST-0103)"),
    "TST-0118": ("cloud-batch", "grammar fuzzing is stateless and portable"),
    "TST-0121": ("cloud-batch", "differential fuzzing runs two portable parsers over generated "
                                "input; no local dependency"),
}
_by_id = {u["id"]: u for u in units}
for _uid, (_sub, _why) in SUBSTRATE_OVERRIDE.items():
    _u = _by_id[_uid]
    assert _u["execution_substrate"] != _sub, "%s override is a no-op" % _uid
    _u["execution_substrate"] = _sub
    _u["evidence_requirement"] += (
        " | substrate note: runs %s because %s" % (_sub, _why))

# ------------------------------------------------------------------ emit ----
out = pathlib.Path(__file__).with_name("TST-1.json")
ids = [u["id"] for u in units]
assert len(ids) == len(set(ids)), "duplicate ids"
expected = ["TST-%04d" % i for i in range(1, len(units) + 1)]
assert ids == expected, "ids not sequential from 1: first mismatch at %s" % (
    next(a for a, b in zip(ids, expected) if a != b))
REQUIRED = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
            "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
            "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
            "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
            "failure_classification", "owner_approval_required"]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9", "10",
          "11", "12", "13", "14", "15", "16"}
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
for u in units:
    assert list(u.keys()) == REQUIRED, "%s field mismatch: %s" % (u["id"], list(u.keys()))
    assert u["phase"] in PHASES, "%s bad phase %r" % (u["id"], u["phase"])
    assert u["execution_substrate"] in SUBS, "%s bad substrate" % u["id"]
    assert isinstance(u["owner_approval_required"], bool)
    assert u["completion_sentinel"] == "SUCCESS:" + u["id"]
    assert u["output_path"] == "command-center/receipts/%s.json" % u["id"]
    for k in ("inputs", "dependencies", "tool_permissions", "tests_required",
              "failure_classification"):
        assert isinstance(u[k], list) and u[k], "%s empty list %s" % (u["id"], k)
    assert len(u["question_or_target"]) > 120, "%s question too thin" % u["id"]

out.write_text(json.dumps(units, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
print("WROTE", out, len(units), "units")
