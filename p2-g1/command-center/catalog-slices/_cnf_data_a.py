# -*- coding: utf-8 -*-
"""CNF slice data, part A: units 1-44.

Families: A = confirmation apparatus (1-14); B = baseline-failure reproduction
(15-27); C = corrected-behaviour reproduction (28-40); D = rollback verification
begins at 41.
"""

UNITS_A = [
# ---------------------------------------------------------------- FAMILY A --
dict(
 t="Confirmation receipt and discrepancy-record schemas with a rejecting validator",
 ph="4",
 q=("Implementation target: write command-center/schema/confirmation-receipt.schema.json and "
    "command-center/schema/discrepancy-record.schema.json plus a validator CLI that REJECTS any "
    "receipt missing claim_id, confirmer identity, source_probe fingerprint, a mechanically "
    "different verifier_probe fingerprint, verbatim probe output, a verdict from the closed set "
    "{CONFIRMED,REFUTED,PARTIAL,NOT-CHECKED,BLOCKED}, and a residual statement. Exact question the "
    "validator must answer NO to: does a receipt with verdict=CONFIRMED and an EMPTY source_probe "
    "pass? That is the measured hole in claim_gate.py, where an absent source normalises to empty "
    "strings that any verifier trivially differs from."),
 inp=["_USER-PROMPTS.md:11028-11041 (Phase 11 contract)",
      "_USER-PROMPTS.md:10605-10625 (the mandatory per-unit field list)",
      "rules/common/single-signal-verification.md (claim_gate.py:132-185 empty-source hole)",
      "command-center/CLAIM-REGISTRY.json"],
 dep=["B01"], role="contract-engineer", tools="rw", sub="worktree-isolated", to=5400,
 out="command-center/schema/confirmation-receipt.schema.json",
 sch="command-center/schema/_meta/json-schema-2020-12.json",
 ev=("both schema files on disk cited by absolute path, plus the validator exit code for each of six "
     "hand-built negative fixtures pasted verbatim; a claim that the validator rejects a shape must "
     "cite the exit code, never the presence of a rule in the schema text"),
 ts=["negative fixture: verdict=CONFIRMED with source_probe empty must exit non-zero",
     "negative fixture: verifier_probe fingerprint identical to source_probe must be rejected as same-probe-rerun",
     "positive fixture: one complete receipt must exit zero in the same run as the six rejections"],
 rv="xv", fc=["schema-invalid", "detector-failure", "overclaim"], ap=False, rt="two_strikes",
 post="all six negative fixtures exited non-zero and the positive fixture exited zero in the same invocation"),

dict(
 t="Machine-checkable confirmer-independence predicate with transitive author exclusion",
 ph="4",
 q=("Implementation target: make spec line 11030 (fresh agents that did not write the implementation) "
    "executable. A confirmer is independent of a claim only when (a) its agent id appears nowhere in "
    "the authoring provenance of the implementation receipt, (b) it did not review that "
    "implementation, and (c) it did not author an ancestor artifact the claim depends on. Question: "
    "how many catalog items can name an author at all today, and what fraction of confirmations does "
    "the transitive rule (c) reject that the direct rule (a) lets through?"),
 inp=["command-center/events/EVENTS.jsonl",
      "command-center/WORK-UNIT-CATALOG.json (103 items)",
      "git log --format=%an over each artifact path",
      "_USER-PROMPTS.md:11030"],
 dep=["B01", "CNF-0001"], role="contract-engineer", tools="rw", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0002-independence-predicate.json",
 sch="command-center/schema/confirmation-policy.schema.json",
 ev=("the predicate source at file:line plus the measured rejection counts of rule (a) and rule (c) "
     "over the real receipt corpus; if the corpus is empty today, report 0 of 0 explicitly rather "
     "than letting an empty set read as a pass"),
 ts=["planted case: a confirmer that reviewed the implementation must be rejected by (b) and accepted by an authorship-only rule; if both agree, (b) is inert",
     "planted case: a confirmer that authored a dependency artifact must be rejected by (c)"],
 rv="raw", fc=["author-not-independent", "detector-failure", "empty-set-read-as-pass"], ap=False, rt="zero",
 post="the predicate ran against the real receipt corpus and the measured counts, including any 0-of-0, are stated in the artifact"),

dict(
 t="Seeded stratified sampling frame with census coverage of every P0 and P1 claim",
 ph="4",
 q=("Implementation target: build the confirmation sampling frame. Every P0 and P1 claim is a census "
    "at 100 percent; P2 and P3 claims are drawn by a SEEDED stratified sampler whose seed, per-stratum "
    "population and draw are recorded so any reviewer re-draws the identical list. Question to answer "
    "numerically: what per-stratum sample size detects a 10 percent class error rate at 90 percent "
    "confidence, and does that many confirmers fit under the arrival-rate cap set by CNF-0011?"),
 inp=["command-center/CLAIM-REGISTRY.json", "_USER-PROMPTS.md:11030 and 11041",
      "command-center/PHASE-GRAPH.json#allocation_buckets"],
 dep=["B01", "CNF-0001"], role="sampling-statistician", tools="rw", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0003-sampling-frame.json",
 sch="command-center/schema/sampling-frame.schema.json",
 ev="the seed, the per-stratum population and draw sizes, and the full drawn id list, all in the artifact",
 ts=["re-draw with the same seed must reproduce the identical id list byte for byte",
     "re-draw with seed+1 must produce a DIFFERENT list, proving the seed is actually consumed",
     "set difference: every P0/P1 id in the registry appears in the frame"],
 rv="stat", fc=["sampling-gap", "schema-invalid", "overclaim"], ap=False, rt="zero",
 post="both the same-seed reproduction and the different-seed control ran inside this unit and their outputs are attached"),

dict(
 t="Error-rate threshold fixed in advance plus the executable whole-class escalation",
 ph="4",
 q=("Implementation target: turn spec line 11041 into code. Fix the discrepancy-rate threshold BEFORE "
    "any confirmation runs, because a threshold chosen after seeing results is not a threshold, then "
    "implement the trigger that re-queues an entire affected class for census confirmation when a "
    "stratum exceeds it. Question: how many additional units does one failing stratum add, and is that "
    "expansion bounded or can it cascade without limit?"),
 inp=["_USER-PROMPTS.md:11041", "command-center/confirmation/CNF-0003-sampling-frame.json",
      "command-center/WORK-UNIT-CATALOG.json"],
 dep=["CNF-0003"], role="policy-engineer", tools="rw", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0004-escalation-policy.json",
 sch="command-center/schema/confirmation-policy.schema.json",
 ev=("the threshold value plus the commit timestamp proving it predates the earliest confirmation "
     "receipt in the corpus, and a simulated stratum failure printing the exact expansion count"),
 ts=["simulate a stratum at threshold minus epsilon: no expansion",
     "simulate at threshold plus epsilon: expansion fires and enumerates the re-queued ids",
     "the two simulations must differ; identical output means the comparison is not being evaluated"],
 rv="two", fc=["policy-set-after-the-fact", "detector-failure", "unbounded-expansion"], ap=False, rt="zero",
 post="the committed threshold timestamp is earlier than every confirmation receipt and both simulations are attached"),

dict(
 t="Blind confirmation brief that strips the implementer conclusion, with a leak detector",
 ph="11",
 q=("Implementation target: a brief builder that hands a confirmer the claim statement, the raw source "
    "and the tests, and NOTHING of the implementer conclusion, receipt prose, confidence band or "
    "summary table (spec 11034). Then answer: over 100 generated briefs does the leak detector find "
    "zero conclusion fragments, AND does the same detector fire when a conclusion is deliberately left "
    "in one brief?"),
 inp=["the implementation receipt corpus", "_USER-PROMPTS.md:11034",
      "command-center/schema/confirmation-receipt.schema.json"],
 dep=["CNF-0001", "CNF-0002"], role="harness-engineer", tools="rw", sub="worktree-isolated", to=5400,
 out="command-center/confirmation/CNF-0005-blind-brief-builder.json",
 sch="command-center/schema/harness-report.schema.json",
 ev="the builder source at file:line, the leak-detector output over 100 briefs, and the deliberate-leak control run",
 ts=["100 generated briefs yield 0 conclusion fragments",
     "control: inject an implementer conclusion into exactly one brief; the detector must flag that brief and no other",
     "a detector silent in both states measures nothing and fails this unit outright"],
 rv="det", fc=["anchoring-leak", "detector-failure", "harness-defect"], ap=False, rt="two_strikes",
 post="the deliberate-leak control fired on exactly the injected brief and on no other"),

dict(
 t="Probe fingerprinting that rejects a confirmation which only re-ran the original probe",
 ph="11",
 q=("Implementation target: fingerprint every probe by the tuple (tool, shell, data field, measurement "
    "kind) and reject any confirmation whose verifier fingerprint equals its source fingerprint. "
    "Question: across the confirmation corpus what percentage of CONFIRMED verdicts are same-probe "
    "re-runs? The precedent is two agents CONFIRMING a false fact by re-running the orchestrator's own "
    "broken Git-Bash which."),
 inp=["rules/common/fan-out-contract.md section A4",
      "rules/common/single-signal-verification.md",
      "the confirmation receipt corpus"],
 dep=["CNF-0001"], role="verification-engineer", tools="rw", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0006-probe-independence.json",
 sch="command-center/schema/confirmation-audit.schema.json",
 ev=("the fingerprint function at file:line and the measured same-probe rate with every offending "
     "receipt id listed; an empty offender list is only meaningful when the detector control result "
     "is attached beside it"),
 ts=["control: file a confirmation re-running the identical command; it must be rejected",
     "control: file one differing only in shell (Git Bash to PowerShell); it must be ACCEPTED, since shell is a declared independence axis",
     "an empty source_probe must count as a violation, never as differs-from-verifier"],
 rv="det", fc=["evidence-theatre", "detector-failure", "schema-invalid"], ap=False, rt="zero",
 post="both fingerprint controls ran in the same invocation and returned opposite verdicts as designed"),

dict(
 t="Cross-vendor confirmer assignment matrix and the measured vendor-independence rate",
 ph="11",
 q=("For every P0/P1 claim, is the assigned confirmer from a different vendor than the implementer, and "
    "what is the measured cross-vendor rate? Build the assignment matrix, execute at least one real "
    "dispatch end to end, and report the rate. A same-vendor confirmation must be labelled "
    "correlated-confirmation, not independent."),
 inp=["command-center/CLAIM-REGISTRY.json",
      "command-center/confirmation/CNF-0002-independence-predicate.json",
      "rules/common/cross-vendor-dispatch.md"],
 dep=["CNF-0002", "CNF-0003"], role="dispatch-coordinator", tools="xv", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0007-crossvendor-matrix.json",
 sch="command-center/schema/assignment-matrix.schema.json",
 ev=("the matrix with a vendor per claim, the measured rate, and for every dispatch BOTH the exit code "
     "AND the non-empty parsed output file; exit code alone is a severed stream, not a result"),
 ts=["run one live cross-vendor dispatch to completion and attach its output file",
     "a dispatch returning only a progress stream or a job receipt is classified severed-stream and must not count",
     "prompt must be passed by file, never inline, or the Windows 32767-char command line truncates it"],
 rv="xv", fc=["severed-stream", "correlated-confirmation", "win-arg-limit", "timeout"], ap=False, rt="escalate",
 post="at least one real cross-vendor dispatch produced a non-empty parsed output file, not merely exit code 0"),

dict(
 t="Execution attestation: prove a confirmer ran the probe instead of asserting it",
 ph="11",
 q=("Did the confirmer actually RUN the probe it reports? Cross-check every confirmation receipt "
    "against the session tool-call ledger and against on-disk side effects (exit codes, produced files "
    "and their mtimes), then report the fraction of receipts whose claimed probe has no execution "
    "record. Any assertion with no execution record is downgraded from CONFIRMED to NOT-CHECKED."),
 inp=["~/.claude/event-ledger/", "command-center/events/EVENTS.jsonl",
      "the confirmation receipt corpus"],
 dep=["CNF-0001", "CNF-0006"], role="audit-engineer", tools="ro", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0008-execution-attestation.json",
 sch="command-center/schema/confirmation-audit.schema.json",
 ev="per receipt either a ledger row id or a produced file path with its mtime; receipts with neither are listed by id as unattested",
 ts=["plant a receipt claiming a probe that was never run: it must be flagged unattested",
     "control: a receipt whose probe WAS run must not be flagged, proving the auditor is not flagging everything"],
 rv="raw", fc=["evidence-theatre", "unattested-claim", "detector-failure"], ap=False, rt="zero",
 post="both the planted unattested receipt and the genuine control receipt were classified oppositely"),

dict(
 t="Set-difference proof that the sampling frame omits no P0 or P1 claim",
 ph="11",
 q=("Is any P0/P1 claim missing from the confirmation frame? Compute the two-directional set difference "
    "between CLAIM-REGISTRY severity>=P1 and the frame, and prove the comparator works by planting a "
    "known P0 id that the frame does not contain. A zero difference is only credible once the planted "
    "id has been shown to produce a non-zero difference."),
 inp=["command-center/CLAIM-REGISTRY.json",
      "command-center/confirmation/CNF-0003-sampling-frame.json"],
 dep=["CNF-0003"], role="completeness-auditor", tools="ro", sub="local-parallel", to=1800,
 out="command-center/confirmation/CNF-0009-frame-completeness.json",
 sch="command-center/schema/confirmation-audit.schema.json",
 ev="both difference directions printed verbatim, plus the planted-id control run showing a non-zero difference",
 ts=["registry-minus-frame must be empty", "frame-minus-registry must be empty (no phantom ids)",
     "planted absent P0 id must make registry-minus-frame non-empty"],
 rv="det", fc=["sampling-gap", "detector-failure", "phantom-id"], ap=False, rt="zero",
 post="the planted-id control produced a non-zero difference in the same run as the clean comparison"),

dict(
 t="Environment pinning manifest so a confirmation discrepancy is attributable",
 ph="11",
 q=("When a confirmer and an implementer disagree, was it the code or the environment? Capture a pinned "
    "manifest per confirmation run - OS build, shell and version, python and node versions, every "
    "pinned tool version, git core.autocrlf, the active locale and code page, and the PATH resolution "
    "of each named tool - and answer: how many disagreements in the corpus are explained by a manifest "
    "delta alone?"),
 inp=["the confirmation receipt corpus", "rules/common/windows-shell.md section 8b (CRLF pin parity)",
      "the CI workflow files that declare pinned tool versions"],
 dep=["CNF-0001"], role="environment-auditor", tools="ro", sub="local-serialized", to=2400,
 out="command-center/confirmation/CNF-0010-environment-manifest.json",
 sch="command-center/schema/environment-manifest.schema.json",
 ev=("the captured manifest verbatim for at least one Windows run and one Linux run, plus the "
     "per-disagreement attribution table"),
 ts=["resolve each tool with the PowerShell resolver, not a POSIX which, because a .cmd shim is invisible to which",
     "assert the local pinned version equals the CI pinned version for every formatter or linter in the manifest",
     "control: force a version mismatch and confirm the attributor reports environment rather than code"],
 rv="raw", fc=["environment-drift", "version-mismatch", "detector-failure"], ap=False, rt="env_once",
 post="manifests from two different operating systems are attached and the forced-mismatch control was attributed to environment"),

dict(
 t="Arrival-staggered confirmation scheduler with quota awareness and starvation proof",
 ph="11",
 q=("Implementation target: a scheduler for the confirmation fan-out that staggers arrivals, respects a "
    "declared per-vendor rate cap, and cannot starve any unit. Question: at the configured concurrency "
    "does the run produce zero 429-class rejections, and does every queued unit reach a terminal state "
    "rather than waiting behind one hung unit?"),
 inp=["_USER-PROMPTS.md:10570-10584 (concurrency doctrine: substrate, staggering, quota as scheduler input)",
      "command-center/confirmation/CNF-0003-sampling-frame.json",
      "rules/common/fan-out-contract.md"],
 dep=["CNF-0003"], role="scheduler-engineer", tools="rw", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0011-scheduler-report.json",
 sch="command-center/schema/scheduler-report.schema.json",
 ev="the measured arrival histogram, the rejection count by class, and the per-unit terminal state table",
 ts=["inject one deliberately hung unit and prove the cohort still completes (per-unit pipeline, not a global barrier)",
     "429 rejections observed must be zero at the configured rate, and the rate must be recorded",
     "reducing concurrency in response to a provider-side 529 is forbidden and must not appear in the log"],
 rv="two", fc=["starvation", "rate-limit-storm", "deadlock", "timeout"], ap=False, rt="resume",
 post="the hung-unit injection completed the surviving cohort and the per-unit terminal state table has no blank rows"),

dict(
 t="Confirmation freshness decay: a stored PASS whose inputs changed becomes STALE",
 ph="11",
 q=("A green confirmation decays. Implement TTL plus input-hash invalidation so that when any hashed "
    "input of a confirmed claim changes, the stored verdict flips from CONFIRMED to STALE rather than "
    "continuing to read as a pass. Question: applying this rule today, how many existing confirmations "
    "in the corpus are already STALE, and which of them are load-bearing for a Phase 15 gate?"),
 inp=["the confirmation receipt corpus", "command-center/ARTIFACT-MANIFEST.json",
      "the advisory-database class of gates whose result changes without any code change"],
 dep=["CNF-0001", "CNF-0008"], role="freshness-auditor", tools="ro", sub="local-parallel", to=2400,
 out="command-center/confirmation/CNF-0012-freshness-decay.json",
 sch="command-center/schema/confirmation-audit.schema.json",
 ev="the per-receipt input hash set at confirmation time versus today, and the resulting STALE list with load-bearing flags",
 ts=["mutate one input byte and confirm the receipt flips to STALE",
     "leave inputs untouched and confirm the receipt stays CONFIRMED, so the rule is not flipping everything",
     "a receipt with no recorded input hashes must be STALE by default, never CONFIRMED by omission"],
 rv="raw", fc=["stale-green", "missing-provenance", "detector-failure"], ap=False, rt="zero",
 post="the mutate-one-byte control flipped exactly one receipt and the untouched control flipped none"),

dict(
 t="Discrepancy triage router that cannot close a discrepancy without a disposition",
 ph="11",
 q=("Implementation target: route every recorded discrepancy (spec 11039) into exactly one disposition - "
    "implementation-defect, confirmation-defect, specification-ambiguity, environment-difference, or "
    "accepted-residual - and open a severity-tagged defect for the first two. Question: can any "
    "discrepancy currently reach a closed state without a disposition, and does the router block that?"),
 inp=["_USER-PROMPTS.md:11039", "command-center/RISK-REGISTER.md",
      "command-center/schema/discrepancy-record.schema.json"],
 dep=["CNF-0001"], role="triage-engineer", tools="rw", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0013-discrepancy-router.json",
 sch="command-center/schema/discrepancy-record.schema.json",
 ev="the router source at file:line plus the closed-without-disposition count before and after the gate is armed",
 ts=["attempt to close a discrepancy with a null disposition: must be refused",
     "an accepted-residual disposition must require a named settling experiment or be refused",
     "control: a fully dispositioned discrepancy must close cleanly"],
 rv="impl", fc=["silent-closure", "missing-settling-experiment", "schema-invalid"], ap=False, rt="two_strikes",
 post="the null-disposition close was refused and the fully dispositioned close succeeded in the same run"),

dict(
 t="Confirmation coverage board computed from receipts on disk, with hand-edit detection",
 ph="11",
 q=("Implementation target: generate the Phase 11 coverage board purely from receipts on disk - claims "
    "by severity, confirmed, refuted, partial, not-checked, blocked, stale - stamp it with the commit "
    "that produced it, and fail the build if a human edits a number in the board directly. Question: "
    "does the hand-edit detector fire when one digit is changed by hand?"),
 inp=["the confirmation receipt corpus", "command-center/STATUS.md",
      "command-center/ARTIFACT-MANIFEST.json"],
 dep=["CNF-0001", "CNF-0012"], role="reporting-engineer", tools="rw", sub="local-parallel", to=2400,
 out="command-center/confirmation/CNF-0014-coverage-board.json",
 sch="command-center/schema/coverage-board.schema.json",
 ev="the generator source at file:line, the generated board, and the exit code of the hand-edit control",
 ts=["change one digit by hand and require the gate to go red",
     "regenerate without changes and require a byte-identical board (determinism)",
     "an empty receipt corpus must render as 0 of N measured, never as a green board"],
 rv="det", fc=["hand-typed-metric", "nondeterministic-output", "empty-set-read-as-pass"], ap=False, rt="zero",
 post="the hand-edit control went red and the unchanged regeneration was byte-identical"),

# ---------------------------------------------------------------- FAMILY B --
dict(
 t="Reproduce the pinned option-id blocker as a failing test from a clean clone",
 ph="0",
 q=("The program brief pins a 31-way M-NN option-id collision as a live blocker while a ground lane "
    "reports the re-prefix was already applied. From a CLEAN CLONE at the pinned SHA, write a test that "
    "fails if and only if the collision is live, then run it: is the literal shared-id count between "
    "07-OPTION-UNIVERSE family M and 13-ARCHITECTURE-CANDIDATES mechanisms 31, or 0? Also assert the "
    "second half: does 17-DECISION-LOG.md contain zero MECH tokens while stating the collision in the "
    "present tense?"),
 inp=["a fresh clone at the pinned SHA (not the working tree)",
      "07-OPTION-UNIVERSE.md and 13-ARCHITECTURE-CANDIDATES.md",
      "17-DECISION-LOG.md:175", "the pre-fix backup of doc 13 if present"],
 dep=["B01"], role="reproduction-engineer", tools="ro", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0015-blocker-repro.json",
 sch="command-center/schema/repro-report.schema.json",
 ev=("the extractor source at file:line, the two id sets, the intersection size, and the MECH token "
     "count in doc 17; read the files with git cat-file at the pinned rev, never from the mutating "
     "working tree"),
 ts=["the test must FAIL against the pre-fix backup of doc 13 (proving it can see a live collision)",
     "the test must PASS against today's doc 13",
     "a test that passes in both states measures nothing and fails this unit"],
 rv="det", fc=["stale-premise", "detector-failure", "repro-not-reproducible"], ap=False, rt="zero",
 post="the test was executed against BOTH the pre-fix and post-fix document states and returned opposite results"),

dict(
 t="Repro-recipe sufficiency rate across every P0 defect record",
 ph="11",
 q=("For each P0 defect, can a fresh agent reproduce the baseline failure using ONLY the recorded repro "
    "steps, with no access to the reporter? Measure the sufficiency rate. Every insufficient recipe "
    "becomes a defect filed against the RECORD, not against the code, and names the exact missing step."),
 inp=["command-center/RISK-REGISTER.md", "the defect corpus with recorded repro steps",
      "command-center/confirmation/CNF-0005-blind-brief-builder.json"],
 dep=["CNF-0005"], role="reproduction-engineer", tools="ro", sub="local-parallel", to=7200,
 out="command-center/confirmation/CNF-0016-repro-sufficiency.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="per defect: the verbatim commands run, the observed output, and PASS or the exact step that was missing",
 ts=["at least one recipe must be attempted verbatim with zero improvisation, to establish the floor",
     "where improvisation was required, the improvised step is recorded as the missing step"],
 rv="impl", fc=["repro-recipe-insufficient", "repro-not-reproducible", "timeout"], ap=False, rt="flake",
 post="every P0 defect has either a PASS with verbatim commands or a named missing step; no blank rows"),

dict(
 t="Baseline reproduction on a fresh Windows user profile with no inherited harness state",
 ph="11",
 q=("Does the baseline failure survive a fresh Windows profile - empty user config, no plugins, no "
    "skills, no MCP servers, default PATH? Reproduce it there and answer: which of the recorded "
    "baseline failures are actually artefacts of the developer's accumulated local state rather than "
    "properties of the code?"),
 inp=["the recorded baseline failure list", "a fresh Windows profile or an equivalent isolated home",
      "command-center/BASELINE-SNAPSHOT.json"],
 dep=["CNF-0016"], role="platform-reproduction-engineer", tools="ro", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0017-fresh-profile-repro.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="the profile path used, proof it was empty at start (a listing), and the per-failure outcome in both profiles",
 ts=["run the identical command set in the loaded profile and the fresh profile and diff the outcomes",
     "any failure that disappears in the fresh profile is reclassified as local-state-dependent, not a code defect"],
 rv="raw", fc=["local-state-dependence", "environment-drift", "repro-not-reproducible"], ap=False, rt="env_once",
 post="both profiles were exercised with the identical command set and the outcome diff is attached"),

dict(
 t="Baseline reproduction inside a disposable Linux container at the same commit",
 ph="11",
 q=("Is the baseline failure a property of the code or of Windows? Reproduce it inside a disposable "
    "Linux container checked out at the identical commit and report, per failure, whether it is "
    "cross-platform, Windows-only, or Linux-only. The three CRLF-artefact failures measured in the "
    "Phase 0 baseline are the specific hypothesis under test."),
 inp=["the baseline failure list from command-center/BASELINE-SNAPSHOT.json",
      "the pinned commit SHA", "a disposable container image with the pinned toolchain"],
 dep=["CNF-0017"], role="platform-reproduction-engineer", tools="sandbox", sub="cloud-batch", to=5400,
 out="command-center/confirmation/CNF-0018-linux-container-repro.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="the image digest, the checkout SHA, and the per-failure outcome table for Windows versus Linux",
 ts=["the three suspected CRLF failures must PASS in the container if the CRLF hypothesis is right",
     "at least one known cross-platform failure must FAIL in the container, proving the container can see failures at all"],
 rv="xv", fc=["platform-specific", "container-drift", "detector-failure"], ap=False, rt="env_once",
 post="the container reproduced at least one known failure, establishing it is not silently green for setup reasons"),

dict(
 t="Byte-acquisition route audit: which bytes does each gate actually judge",
 ph="11",
 q=("CI judges blobs, not your working tree, and the three ways of obtaining those bytes do not agree on "
    "this platform. Measure all three routes - git archive, git cat-file, and the worktree - for a "
    "control file, then re-run every formatting, linting and hash-sensitive gate on each route and "
    "answer: for how many gates does the verdict depend on which route supplied the bytes, and is the "
    "recipe currently prescribed in the release checklist the one that returns CRLF?"),
 inp=["rules/common/windows-shell.md section 8b",
      "the gates named in the CI workflow files",
      "command-center/RELEASE-CHECKLIST.md (which currently prescribes the git archive route)",
      "a deliberately misformatted copy of one gated file"],
 dep=["CNF-0015"], role="byte-parity-engineer", tools="ro", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0019-byte-route-audit.json",
 sch="command-center/schema/byte-parity-report.schema.json",
 ev=("for the control file: byte count and CRLF count from all three routes in one table; plus the "
     "per-gate verdict on each route and the verdict on the misformatted copy"),
 ts=["prove the three routes are byte-identical after LF normalisation, isolating line endings as the only variable",
     "both-states control: each gate must go RED on the misformatted copy, or its green measures nothing",
     "any gate whose verdict depends on the route is filed as a portability defect and the checklist recipe is corrected"],
 rv="det", fc=["crlf-artefact", "wrong-bytes-verified", "detector-failure", "documentation-defect"], ap=False, rt="zero",
 post="the three-route byte table is attached, the git archive route is shown to return CRLF, and every gate went red on the misformatted control"),

dict(
 t="Frequency-measured reproduction of an intermittent baseline failure",
 ph="11",
 q=("For each baseline failure suspected of being intermittent, what is its reproduction FREQUENCY? Run "
    "it 50 times under the recorded conditions and report k of 50 with a binomial interval. A single "
    "green does not refute an intermittent failure and a single red does not establish a deterministic "
    "one; the deliverable is the rate, not a boolean."),
 inp=["the baseline failure list", "the concurrency and load conditions recorded with each failure",
      "command-center/confirmation/CNF-0010-environment-manifest.json"],
 dep=["CNF-0010", "CNF-0016"], role="flake-analyst", tools="ro", sub="local-parallel", to=10800,
 out="command-center/confirmation/CNF-0020-flake-frequency.json",
 sch="command-center/schema/flake-report.schema.json",
 ev="the k of n table with the interval per failure and the full per-run outcome vector, not just the summary",
 ts=["a failure reported as deterministic must be 50 of 50 or be reclassified as intermittent",
     "the harness must record every run outcome; discarding reds and reporting the last run is a unit failure"],
 rv="stat", fc=["flake", "under-sampling", "outcome-discarded"], ap=False, rt="flake",
 post="every failure has a full n=50 outcome vector attached, not a summarised verdict"),

dict(
 t="Version-parity reproduction against the exact tool versions CI pins",
 ph="11",
 q=("Is the local reproduction using the same tool versions as CI? Re-run every version-sensitive "
    "baseline check with the CI-pinned version invoked explicitly, and answer: for which tools does the "
    "ambient local version disagree with the pin, and does any verdict change as a result? The measured "
    "precedent is a formatter differing between 0.15.17 and 0.15.22 on identical bytes."),
 inp=["the CI workflow files with their pinned tool versions",
      "the locally resolved tool versions",
      "rules/common/windows-shell.md section 8b (pin parity)"],
 dep=["CNF-0010"], role="toolchain-auditor", tools="ro", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0021-version-parity.json",
 sch="command-center/schema/environment-manifest.schema.json",
 ev="a table of tool, CI pin, ambient local version, and verdict under each; version strings captured verbatim from the tools",
 ts=["for at least one tool, run BOTH versions on the same bytes and report whether the verdicts differ",
     "resolve versions in PowerShell, not with a POSIX which, so .cmd shims are visible"],
 rv="raw", fc=["version-mismatch", "environment-drift", "detector-failure"], ap=False, rt="env_once",
 post="at least one tool was run at both the pinned and the ambient version on identical bytes and both verdicts are recorded"),

dict(
 t="Time-travel reproduction at the pre-fix commit to prove the defect existed there",
 ph="11",
 q=("Did the defect actually exist before the fix, at the parent commit of the fix? Check out that "
    "parent in a scratch worktree and run the failing test there. A defect that does not reproduce at "
    "its own pre-fix commit means either the fix commit is misattributed or the test is measuring "
    "something else; both are discrepancies to file."),
 inp=["the fix commit list from git log", "the failing tests associated with each fix",
      "a scratch worktree (never the shared checkout)"],
 dep=["CNF-0016"], role="history-reproduction-engineer", tools="gh", sub="worktree-isolated", to=5400,
 out="command-center/confirmation/CNF-0022-pre-fix-timetravel.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="per fix: the parent SHA, the test invocation, and its verbatim red output at the parent",
 ts=["the test must be RED at the parent and GREEN at the fix commit; any other pattern is a discrepancy",
     "the worktree must be disposable and its removal must be proven, so no shared index is touched"],
 rv="raw", fc=["misattributed-fix", "test-measures-something-else", "repro-not-reproducible"], ap=False, rt="zero",
 post="every examined fix has a recorded red-at-parent and green-at-fix pair, or a filed discrepancy"),

dict(
 t="Mechanise prose repro steps into an executable script and fail the ones that cannot be",
 ph="11",
 q=("Implementation target: convert each prose reproduction recipe into a runnable script with a "
    "deterministic exit code. Question: what fraction of recipes cannot be mechanised, and for each one "
    "which step requires human judgement? A recipe that cannot be mechanised is a documentation defect "
    "that will silently rot, and it is filed as such."),
 inp=["the prose repro steps in the defect corpus",
      "rules/common/windows-shell.md section 10 (apostrophes break inline shell commands)"],
 dep=["CNF-0016"], role="automation-engineer", tools="rw", sub="local-parallel", to=5400,
 out="command-center/confirmation/CNF-0023-mechanised-repros.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="each generated script path plus its exit code on a live run; the non-mechanisable list with the blocking step named",
 ts=["every generated script must be written to a file and invoked by path, never inlined into a shell command body",
     "each script must exit non-zero on the unfixed state and zero on the fixed state"],
 rv="xv", fc=["not-mechanisable", "shell-quoting-defect", "documentation-defect"], ap=False, rt="two_strikes",
 post="every generated script was executed once and its exit code recorded; unexecuted scripts do not count"),

dict(
 t="Reproduce a CI-log-only defect on a matching runner image",
 ph="11",
 q=("Some defects exist only in CI logs and have never been reproduced locally. For each, reproduce it "
    "on an image matching the workflow runner rather than on the developer box, and answer: is it a "
    "genuine code defect, a runner-image property, or an artefact of the CI cache?"),
 inp=["the CI run logs for the failing workflows", "the workflow runs-on image identifiers",
      "the workflow cache configuration"],
 dep=["CNF-0018"], role="ci-reproduction-engineer", tools="sandbox", sub="cloud-batch", to=7200,
 out="command-center/confirmation/CNF-0024-ci-image-repro.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="the image identifier, the reproduced log excerpt aligned to the CI log excerpt, and the classification per defect",
 ts=["run once with the CI cache warm and once cold, and report whether the outcome differs",
     "a defect that only reproduces with a warm cache is classified as a cache defect, not a code defect"],
 rv="xv", fc=["cache-artefact", "runner-image-specific", "repro-not-reproducible"], ap=False, rt="env_once",
 post="both warm-cache and cold-cache runs completed and their outcomes are separately recorded"),

dict(
 t="Specificity control: prove the reproduction fires only on the defective component",
 ph="11",
 q=("Does the reproduction discriminate? Run each repro against an unrelated, known-healthy component "
    "and require it NOT to fire. A repro that fires everywhere is measuring the environment, not the "
    "defect, and every conclusion drawn from it is void."),
 inp=["the mechanised repro scripts from CNF-0023",
      "a list of known-healthy components with no attached defect"],
 dep=["CNF-0023"], role="detector-control-engineer", tools="ro", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0025-repro-specificity.json",
 sch="command-center/schema/detector-control.schema.json",
 ev="a matrix of repro by component with the exit code in each cell, defective and healthy columns side by side",
 ts=["every repro must be red on its own target and green on at least three healthy components",
     "any repro red on a healthy component is quarantined and its dependent conclusions are re-opened"],
 rv="det", fc=["non-specific-detector", "false-positive", "detector-failure"], ap=False, rt="zero",
 post="the full repro-by-component matrix is attached with no empty cells"),

dict(
 t="Proof-of-impossibility record for baselines that cannot be reproduced",
 ph="11",
 q=("For each baseline failure that resists reproduction, produce a proof-of-impossibility record rather "
    "than a silent omission: what was attempted, on which substrates, what evidence would settle it, and "
    "what prerequisite is missing. Question: how many baseline failures end in this state, and does any "
    "of them block a Phase 15 gate?"),
 inp=["the unreproduced remainder from CNF-0016, CNF-0017, CNF-0018 and CNF-0024",
      "_USER-PROMPTS.md:11400 (two-signal proof of a blocker)"],
 dep=["CNF-0016", "CNF-0018", "CNF-0024"], role="blocker-analyst", tools="ro", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0026-impossibility-records.json",
 sch="command-center/schema/impossibility-record.schema.json",
 ev="per record: two mechanically different signals supporting the blocker, the exact missing prerequisite, and the settling experiment",
 ts=["a record with only one signal is rejected by the schema",
     "a record with no named settling experiment is rejected",
     "control: a reproducible failure must not be accepted into this file"],
 rv="two", fc=["blocked-external", "single-signal-blocker", "schema-invalid"], ap=False, rt="zero",
 post="every record carries two independent signals and a named settling experiment, and the reproducible control was refused entry"),

dict(
 t="Re-measure the Phase 0 benchmark baselines with variance rather than a single sample",
 ph="11",
 q=("Are the recorded Phase 0 benchmark baselines reproducible, and what is their noise floor? Re-measure "
    "each with at least 11 repetitions on a quiesced machine, report median and interquartile range, and "
    "answer: is any later improvement claim smaller than the measured noise floor of its own baseline?"),
 inp=["command-center/BASELINE-SNAPSHOT.json (the recorded baseline numbers)",
      "the benchmark harness used to produce them",
      "the machine quiescence procedure"],
 dep=["CNF-0010"], role="benchmark-reproduction-engineer", tools="ro", sub="local-serialized", to=10800,
 out="command-center/confirmation/CNF-0027-baseline-variance.json",
 sch="command-center/schema/benchmark-report.schema.json",
 ev="all raw repetition values, not just the summary statistics, plus the quiescence evidence (load and memory at start)",
 ts=["report the noise floor explicitly and mark any claimed improvement below it as unmeasurable",
     "a baseline captured while a sibling agent was mutating the tree must be flagged as a sample, not a freeze"],
 rv="stat", fc=["under-sampling", "noise-dominated-claim", "environment-drift"], ap=False, rt="flake",
 post="all raw repetition values are present in the artifact and the noise floor is stated numerically"),

# ---------------------------------------------------------------- FAMILY C --
dict(
 t="Confirm the fix through a clean-venv wheel install and its console script",
 ph="11",
 q=("Does the corrected behaviour survive packaging? Build the wheel, install it into a brand-new "
    "virtual environment with no source tree on the path, and invoke the INSTALLED console script - not "
    "python -m from the repo. Question: does any fix that passes in-tree fail once the import path comes "
    "from site-packages? The Phase 0 baseline explicitly ran python -m and is a broken detector for this "
    "class by construction."),
 inp=["the built wheel or sdist", "the console entry points declared in packaging metadata",
      "command-center/BASELINE-SNAPSHOT.json (records that the baseline used python -m)"],
 dep=["CNF-0019"], role="packaging-reproduction-engineer", tools="ro", sub="worktree-isolated", to=5400,
 out="command-center/confirmation/CNF-0028-clean-venv-install.json",
 sch="command-center/schema/packaging-report.schema.json",
 ev="the venv path, pip install output, the resolved script path proving it is outside the repo, and the invocation output",
 ts=["the repo directory must not be on sys.path during the run; prove it by printing sys.path",
     "invoke via the console script AND via python -m and report both outcomes separately",
     "a missing runtime dependency must surface here, not be masked by the developer environment"],
 rv="xv", fc=["packaging-gap", "import-path-defect", "missing-runtime-dependency"], ap=False, rt="two_strikes",
 post="sys.path was printed and contains no repo path, and both invocation routes were exercised"),

dict(
 t="Change-surface confirmation on the three-dot commit range, not the working-tree diff",
 ph="11",
 q=("Does the change a branch would actually propose match the change its author describes? Compute the "
    "commit-to-commit surface with the three-dot range against the integration branch and answer: how "
    "many files and deletions does the branch propose, does it propose reverting work the base already "
    "has, and does the two-dot diff give a different answer because it folds in working-tree noise? A "
    "stale branch can silently propose mass deletion, measured once at 1188 files and 316222 deletions."),
 inp=["each candidate branch and the integration branch",
      "rules/common/windows-shell.md section 8d",
      "the author description of the intended change"],
 dep=["CNF-0022"], role="change-surface-auditor", tools="gh", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0029-change-surface.json",
 sch="command-center/schema/regression-delta.schema.json",
 ev="the three-dot stat, the two-dot stat, and the deletion count per branch, with the merge-base SHA recorded",
 ts=["the three-dot and two-dot surfaces must both be computed and reported; only reporting one hides working-tree noise",
     "any deletion of a path the base gained after the merge base is flagged as a would-revert and listed by path",
     "control: a freshly branched HEAD must show an empty surface, proving the comparison is not inventing changes"],
 rv="raw", fc=["stale-branch-would-revert", "surface-misreported", "detector-failure"], ap=False, rt="zero",
 post="both the three-dot and two-dot surfaces are recorded per branch and the freshly-branched control returned empty"),

dict(
 t="Confirm the fix in a fresh clone rather than the developer tree",
 ph="11",
 q=("Does the fix depend on untracked local files? Clone the repository fresh at the fix commit into a "
    "new directory, run the associated tests, and answer: which fixes pass in the developer tree but "
    "fail in a clean clone because a required file was never committed?"),
 inp=["the fix commit list", "a clean clone target directory outside the working checkout",
      "git status output for untracked files in the developer tree"],
 dep=["CNF-0022"], role="reproduction-engineer", tools="ro", sub="worktree-isolated", to=5400,
 out="command-center/confirmation/CNF-0030-fresh-clone-confirm.json",
 sch="command-center/schema/repro-report.schema.json",
 ev="the clone path, the clone SHA, the test invocation and result, plus the untracked-file inventory of the source tree",
 ts=["run the identical test command in both trees and diff the outcomes",
     "any file that must be copied in by hand for the clone to pass is a missing-commit defect"],
 rv="raw", fc=["uncommitted-dependency", "environment-drift", "repro-not-reproducible"], ap=False, rt="zero",
 post="the clone SHA equals the fix SHA and both trees ran the identical command"),

dict(
 t="Duplicate-dispatch suppression across two concurrent sessions",
 ph="11",
 q=("If two sessions claim the same work unit at the same time, how many times does it execute? Dispatch "
    "one unit simultaneously from two sessions and answer: does the work-claim layer admit exactly one "
    "execution, does the loser receive a distinguishable already-claimed response rather than a silent "
    "no-op, and do two catalogs holding a colliding id produce two units or one?"),
 inp=["the work-claim and file-lease layer",
      "two independently registered sessions",
      "a pair of catalogs deliberately holding one colliding unit id"],
 dep=["CNF-0011"], role="coordination-verification-engineer", tools="ro", sub="local-serialized", to=5400,
 out="command-center/confirmation/CNF-0031-duplicate-dispatch.json",
 sch="command-center/schema/coordination-report.schema.json",
 ev="the claim log from both sessions with timestamps, the execution count, and the loser response text",
 ts=["exactly one execution must occur; two executions is a P1 and zero is a starvation defect",
     "the colliding-id catalogs must be detected at load, not silently merged into one unit",
     "control: two DIFFERENT units dispatched simultaneously must both execute, proving the layer is not simply serialising everything"],
 rv="two", fc=["duplicate-execution", "silent-no-op", "catalog-collision"], ap=False, rt="zero",
 post="the execution count is exactly one for the contested unit and exactly two for the non-contested control"),

dict(
 t="Causality proof by reverting only the fix hunk and requiring the failure to return",
 ph="11",
 q=("Is the fix the CAUSE of the corrected behaviour, or did something else change alongside it? In a "
    "scratch worktree revert ONLY the fix hunk, leaving tests and everything else intact, and require "
    "the failure to return. Question: for how many fixes does the failure NOT return, meaning the fix is "
    "not load-bearing for the behaviour it claims?"),
 inp=["the fix diffs at hunk granularity", "the associated tests",
      "a scratch worktree that is not the shared checkout"],
 dep=["CNF-0022", "CNF-0030"], role="causality-engineer", tools="gh", sub="worktree-isolated", to=7200,
 out="command-center/confirmation/CNF-0032-hunk-revert-causality.json",
 sch="command-center/schema/causality-report.schema.json",
 ev="per fix: the reverted hunk, the test output after revert, and the test output after restore",
 ts=["failure must return on revert and disappear on restore, in the same session",
     "if the failure does not return, the fix is filed as non-load-bearing and the real cause is sought",
     "never stage or commit from the scratch worktree; the orchestrator owns the index"],
 rv="raw", fc=["non-load-bearing-fix", "confounded-change", "repro-not-reproducible"], ap=False, rt="zero",
 post="each examined fix has a matched revert-red and restore-green pair recorded"),

dict(
 t="Recompute every claimed improvement metric from raw measurement data",
 ph="11",
 q=("Recompute each claimed improvement directly from the raw measurement files, never from the "
    "implementer summary table, and answer: does the recomputed value match the claim within the stated "
    "precision, and is the claimed delta larger than the measured noise floor from CNF-0027?"),
 inp=["the raw measurement outputs behind each improvement claim",
      "the implementer summary tables (used only for comparison, never as input)",
      "command-center/confirmation/CNF-0027-baseline-variance.json"],
 dep=["CNF-0027"], role="metric-auditor", tools="ro", sub="local-parallel", to=5400,
 out="command-center/confirmation/CNF-0033-metric-recompute.json",
 sch="command-center/schema/benchmark-report.schema.json",
 ev="the recomputation script at file:line, the recomputed value, the claimed value and the delta for every claim",
 ts=["a claim whose raw data is missing is NOT-CHECKED, never confirmed by plausibility",
     "a delta inside the noise floor is downgraded to unmeasurable regardless of sign",
     "control: recompute one metric two different ways and require agreement"],
 rv="stat", fc=["overclaim", "missing-raw-data", "noise-dominated-claim"], ap=False, rt="zero",
 post="every claim has a recomputed value or an explicit NOT-CHECKED with the missing raw file named"),

dict(
 t="Confirm the fixed behaviour through a different entry point than the author used",
 ph="11",
 q=("Was the fix verified only through the one interface the author happened to use? Exercise the same "
    "behaviour through a different entry point - library call versus CLI versus hook versus MCP tool - "
    "and answer: does the corrected behaviour hold on every surface, or only on the tested one?"),
 inp=["the entry-point inventory for each fixed component",
      "the author test invocations (used only to identify the surface already covered)"],
 dep=["CNF-0028"], role="interface-coverage-engineer", tools="ro", sub="local-parallel", to=5400,
 out="command-center/confirmation/CNF-0034-alternate-interface.json",
 sch="command-center/schema/interface-coverage.schema.json",
 ev="per component: the surfaces enumerated, which the author tested, which this unit tested, and the outcome on each",
 ts=["at least one untested surface per component must be exercised, or the unit reports NOT-CHECKED for that component",
     "a surface that cannot be exercised must name the blocking prerequisite"],
 rv="xv", fc=["surface-gap", "not-checked-folded-into-pass", "blocked-external"], ap=False, rt="two_strikes",
 post="each component lists at least one surface exercised by this unit that the author did not exercise"),

dict(
 t="Strict-parser confirmation: unknown fields and case-distinct key collisions",
 ph="11",
 q=("Does the fixed manifest survive a strict parser? Feed each manifest and config through a strict "
    "reader and answer three questions: is an unknown field rejected rather than silently ignored, do "
    "two case-distinct JSON keys collide under a case-insensitive client, and does a duplicate key "
    "produce an error rather than a last-wins overwrite?"),
 inp=["the plugin and marketplace manifests", "the settings and hook configuration files",
      "_USER-PROMPTS.md:11302 and 11310 (strict-parser and case-collision failure classes)"],
 dep=["CNF-0028"], role="parser-conformance-engineer", tools="ro", sub="local-parallel", to=3600,
 out="command-center/confirmation/CNF-0035-strict-parser.json",
 sch="command-center/schema/conformance-report.schema.json",
 ev="the exact parser and version used, plus the verbatim error text for each of the three negative fixtures",
 ts=["unknown-field fixture must be rejected", "case-distinct key fixture must be reported as a collision",
     "duplicate-key fixture must error rather than silently take the last value",
     "control: a valid manifest must parse cleanly in the same run"],
 rv="det", fc=["parser-permissive", "case-collision", "schema-invalid"], ap=False, rt="zero",
 post="all three negative fixtures errored and the valid control parsed cleanly in the same invocation"),

dict(
 t="Repeat-application safety for every mutating operation, forward and reverse",
 ph="11",
 q=("Which mutating operations are safe to run twice? Apply each forward operation twice and each reverse "
    "operation twice from an already-applied state, and answer per operation: is the on-disk state after "
    "the second application byte-identical to after the first, is the second exit code clean or at least "
    "carrying a distinguishable already-applied message, and does any create-if-missing path truncate an "
    "existing file?"),
 inp=["every mutating operation: install, deploy, migrate, sync, repair, and their reverse counterparts",
      "a disposable target directory snapshot",
      "rules/common/windows-shell.md section 4 (force-create truncates an existing file)"],
 dep=["CNF-0030"], role="idempotency-engineer", tools="ro", sub="local-serialized", to=5400,
 out="command-center/confirmation/CNF-0036-repeat-application.json",
 sch="command-center/schema/idempotency-report.schema.json",
 ev="per operation and direction: the hash manifest after each of the two applications and both exit codes",
 ts=["hash sets after application one and two must be equal for every operation in both directions",
     "a create-if-missing call must be probed against an existing non-empty file and must not truncate it",
     "a non-zero second exit is acceptable only when the message explicitly says already-applied",
     "control: a deliberately non-idempotent operation must be caught by the same comparison"],
 rv="raw", fc=["non-idempotent", "data-loss", "unclear-error", "detector-failure"], ap=False, rt="zero",
 post="both directions were exercised for every operation and the non-idempotent control was detected"),

dict(
 t="Execute the documented commands verbatim and diff against the documented output",
 ph="11",
 q=("Do the docs match the code? Extract every command from the user-facing documentation, run each "
    "verbatim in a clean environment, and diff the real output against the documented output. Question: "
    "how many documented commands do not exist, fail, or produce different output than the docs claim?"),
 inp=["the user-facing docs, quick-start and advanced examples",
      "command-center/RUNBOOK.md", "a clean environment per CNF-0017"],
 dep=["CNF-0017", "CNF-0028"], role="documentation-conformance-engineer", tools="ro", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0037-doc-command-conformance.json",
 sch="command-center/schema/conformance-report.schema.json",
 ev="per command: the source doc path:line, the verbatim invocation, the actual output, and the documented output",
 ts=["a command that does not exist is a documentation defect, filed with its doc path:line",
     "output differences are diffed, not eyeballed",
     "commands requiring credentials are run in a read-only mode or reported BLOCKED, never skipped silently"],
 rv="two", fc=["documentation-defect", "command-missing", "blocked-external"], ap=False, rt="two_strikes",
 post="every extracted command has a recorded outcome including explicit BLOCKED entries; no command is silently omitted"),

dict(
 t="Independent fail-first re-derivation of the test from the requirement alone",
 ph="11",
 q=("Would a fresh agent, reading only the requirement and the public API and never the author test, "
    "write a test that fails before the fix and passes after? Do exactly that and answer: does the "
    "independently derived test agree with the author test, and where it disagrees, which one matches "
    "the requirement text?"),
 inp=["the requirement statement for each fix (spec line or issue text)",
      "the public API surface only", "the pre-fix and post-fix commits"],
 dep=["CNF-0005", "CNF-0022"], role="blind-test-synthesiser", tools="rwxv", sub="worktree-isolated", to=7200,
 out="command-center/confirmation/CNF-0038-blind-test-synthesis.json",
 sch="command-center/schema/blind-test-report.schema.json",
 ev="the synthesised test source, its red result at the pre-fix commit and green result at the post-fix commit",
 ts=["the synthesiser must never read the diff or the author test; the brief is generated by CNF-0005",
     "red-then-green is the expected pattern; any other pattern is a spec-miss or an overfitted patch and is filed",
     "an independently derived test that is green at the pre-fix commit means the requirement was already satisfied"],
 rv="impl", fc=["spec-miss", "overfitted-patch", "requirement-ambiguous"], ap=False, rt="escalate",
 post="the synthesised test was executed at both commits and both outcomes are recorded verbatim"),

dict(
 t="Golden-journey confirmation against the packaged artifact with a deterministic postcondition",
 ph="11",
 q=("Does the built deliverable actually work, as opposed to its source tree being green? Drive three to "
    "five golden journeys against the PACKAGED artifact and end each in a deterministic postcondition "
    "probe on the file it produced - existence, minimum size, and a format or content assertion. "
    "Question: does any journey pass on the source tree but fail on the package?"),
 inp=["the packaged artifact from CNF-0028", "the golden-journey definitions",
      "the postcondition probe definitions per journey"],
 dep=["CNF-0028"], role="smoke-test-engineer", tools="ro", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0039-packaged-golden-journeys.json",
 sch="command-center/schema/smoke-report.schema.json",
 ev="per journey: the artifact path launched, the produced output path, and the verbatim postcondition probe output",
 ts=["a journey whose postcondition is only exit code zero is rejected; a produced-file assertion is mandatory",
     "control: corrupt the produced file and confirm the postcondition probe fails",
     "the source tree must not be on the path during the run"],
 rv="det", fc=["packaging-gap", "weak-postcondition", "detector-failure"], ap=False, rt="two_strikes",
 post="every journey ended in a file-level postcondition probe and the corruption control failed as designed"),

dict(
 t="Confirm the fix under least-privilege tool permissions rather than a full grant",
 ph="11",
 q=("Was the fix only verified with a permissive tool grant? Re-run its verification with the minimum "
    "declared permission set and answer: does it still pass, does it fail loudly with a clear message, "
    "or does it silently degrade to a weaker behaviour that still reports success?"),
 inp=["the declared tool_permissions of the implementing unit",
      "the permission enforcement layer", "the verification commands"],
 dep=["CNF-0034"], role="permission-boundary-engineer", tools="ro", sub="local-serialized", to=3600,
 out="command-center/confirmation/CNF-0040-least-privilege-confirm.json",
 sch="command-center/schema/permission-report.schema.json",
 ev="the exact permission set applied, the run outcome, and the error text when denied",
 ts=["silent degradation to a weaker success is the worst outcome and must be specifically probed for",
     "control: grant the full set and confirm the same run passes, isolating permissions as the variable"],
 rv="sec", fc=["silent-degradation", "permission-overreach", "unclear-error"], ap=False, rt="zero",
 post="the reduced-permission run and the full-permission control both ran and their outcomes differ or are explained"),

# ---------------------------------------------------------------- FAMILY D --
dict(
 t="Byte-level proof that rollback restores the exact pre-state",
 ph="11",
 q=("Does rollback restore the pre-state exactly? Hash every file in the affected trees before the "
    "change, after the change, and after rollback, then answer: is the post-rollback hash set identical "
    "to the pre-change set, and if not, exactly which paths differ and in which direction?"),
 inp=["command-center/ROLLBACK-MANIFEST.md", "the affected tree list",
      "a hashing walker that follows the manifest scope exactly"],
 dep=["CNF-0036"], role="rollback-verification-engineer", tools="ro", sub="local-serialized", to=5400,
 out="command-center/confirmation/CNF-0041-rollback-byte-parity.json",
 sch="command-center/schema/rollback-report.schema.json",
 ev="the three hash manifests (pre, post, post-rollback) and the symmetric difference between the first and third",
 ts=["the pre and post-rollback sets must be equal; any residue is listed by path",
     "the walker must handle reserved device names with the extended-length prefix or it crashes and reports zero files",
     "control: plant one extra file before rollback and confirm the comparison detects it"],
 rv="det", fc=["incomplete-rollback", "walker-crash", "detector-failure"], ap=False, rt="zero",
 post="all three hash manifests are attached and the planted-file control was detected"),

dict(
 t="Rollback must not remove user data or previously existing commands",
 ph="11",
 q=("Does rollback destroy anything the user owned before the change? Seed the environment with "
    "user-authored files, custom commands and personal settings, run the rollback, and answer: is every "
    "seeded item still present and byte-identical afterwards? Spec line 11347 names this exact failure "
    "class."),
 inp=["a seeded user-data fixture (files, custom commands, settings)",
      "command-center/ROLLBACK-MANIFEST.md", "_USER-PROMPTS.md:11347"],
 dep=["CNF-0041"], role="rollback-verification-engineer", tools="ro", sub="local-serialized", to=5400,
 out="command-center/confirmation/CNF-0042-rollback-user-data.json",
 sch="command-center/schema/rollback-report.schema.json",
 ev="the seeded inventory with hashes before and after, plus the rollback command transcript",
 ts=["every seeded item must survive byte-identical",
     "a user-authored file whose name collides with a shipped file must survive, which is the sharpest case",
     "control: an item the rollback IS supposed to remove must actually be removed, or the test is vacuous"],
 rv="owner", fc=["data-loss", "over-broad-rollback", "detector-failure"], ap=True, rt="zero",
 post="the seeded inventory is fully accounted for and the intentional-removal control also passed"),

dict(
 t="Rollback from a partially applied upgrade killed mid-install",
 ph="11",
 q=("Can the system roll back from a half-applied upgrade? Kill the installer at three different points - "
    "after file copy, after manifest write, after cache invalidation - then run rollback from each state "
    "and answer: does each recover to a consistent pre-state, or does any leave an unusable hybrid?"),
 inp=["the installer implementation and its ordered phases",
      "command-center/ROLLBACK-MANIFEST.md", "a disposable install target"],
 dep=["CNF-0041"], role="crash-recovery-engineer", tools="ro", sub="local-serialized", to=7200,
 out="command-center/confirmation/CNF-0043-partial-upgrade-rollback.json",
 sch="command-center/schema/rollback-report.schema.json",
 ev="per kill point: the state inventory at kill time, the rollback transcript, and the final hash comparison",
 ts=["all three kill points must be exercised; a single kill point does not cover the class",
     "after each rollback the health check must pass, not merely the file count",
     "a hybrid state that reports healthy is the worst outcome and is probed for explicitly"],
 rv="two", fc=["inconsistent-state", "false-healthy", "incomplete-rollback"], ap=False, rt="bounded3",
 post="all three kill points were exercised and each has a recorded post-rollback health-check result"),

dict(
 t="Rollback of registry state plus proof that the stale cache no longer masks it",
 ph="11",
 q=("After rollback, does a stale cache still serve the rolled-back version? Roll back a package, then "
    "answer: does the client resolve the restored version, is the cache entry invalidated, and does a "
    "cold client and a warm client agree? Spec line 11306 names stale cache masking a fixed package as a "
    "required regression case; this is its mirror on the rollback path."),
 inp=["the marketplace or plugin registry state", "the client cache directories",
      "_USER-PROMPTS.md:11306"],
 dep=["CNF-0043"], role="cache-coherence-engineer", tools="ro", sub="local-serialized", to=5400,
 out="command-center/confirmation/CNF-0044-rollback-cache-coherence.json",
 sch="command-center/schema/rollback-report.schema.json",
 ev="the resolved version reported by a warm client and by a cold client after rollback, plus the cache entry state",
 ts=["warm and cold clients must resolve the identical version",
     "control: skip the invalidation step and confirm the warm client then resolves the WRONG version, proving the probe discriminates",
     "cache paths must be enumerated from the implementation, not assumed"],
 rv="det", fc=["stale-cache", "detector-failure", "resolution-mismatch"], ap=False, rt="zero",
 post="the skip-invalidation control produced a resolution mismatch, establishing the probe can see the defect"),
]
