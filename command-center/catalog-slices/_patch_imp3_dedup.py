"""De-duplicate IMP-3 against siblings IMP-4.json and CC-1.json, then refill to 128.

WHY: a token-Jaccard scan reported max cross-slice similarity 0.279 (below any sane
threshold) yet a direct title read showed ~26 of my phase-8/phase-9 units are the SAME
MECHANISM as IMP-4's phase-8 (22 units) and phase-9 (28 units) blocks, plus CC-0003
(the shared completion reducer). Lexical similarity is a BROKEN detector for
mechanism-level duplication across independently-authored slices. Duplicates manufacture
false coverage, which the spec explicitly forbids (line 10568: merge when two units are
the same mechanism in different wording).

ACTION:
  - keep units[0:96] verbatim (phase 7 = 27, phase 7A = 69) - IMP-4 has ZERO phase 7/7A
    units, CNL-1 is phase 2C DESIGN only, WFA-2 is 2A/2B, so this space is provably mine
  - drop 26 of the 28 phase-8/9 units as mechanism duplicates of IMP-4/CC-1
  - keep the 2 that are genuinely ABSENT from IMP-4 (lazy activation; two-directional
    divergence detection), repointed to depend on IMP-4's units
  - add 26 new phase-7 / phase-7A units covering surface nobody holds
  - keep the 4 phase-16 units (IMP-4 has no phase 16; TST-2's single phase-16 unit TESTS
    the loop, it does not build it), repointing the CC-0003 dependency
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IMP-3.json")
data = json.loads(io.open(SRC, encoding="utf-8").read())
assert len(data) == 128, len(data)

CORP = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SPEC = CORP + "/_USER-PROMPTS.md"
A_PRED = SPEC + ":10627-10648"
A_SCALE = SPEC + ":10570-10584"
A_P7 = SPEC + ":10873-10913"
A_P7PROD = SPEC + ":11152-11170"
A_P7A = SPEC + ":10915-10946"
A_P2C = SPEC + ":10746-10767"
A_CPROD = SPEC + ":11172-11244"
A_FAIL = SPEC + ":11298-11347"
C_SPEC = CORP + "/11-COUNCIL-SPECIFICATION.md"
C_SCHEMA = CORP + "/11-COUNCIL-SPECIFICATION.schema.json"
C_PROTO = CORP + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
W_BP = CORP + "/09-WORKFLOW-BLUEPRINT-LIBRARY.json"
D_ARCH = CORP + "/13-ARCHITECTURE-CANDIDATES.md"
D_NOREG = CORP + "/14-NO-REGRESSION-CONTRACT.md"

R_PIVOT = ("two strikes then pivot (AGENTS.md 4b): after two failures sharing an error "
           "fingerprint, enumerate >=2 alternative designs before a third attempt")
R_NORETRY = ("no automatic retry on schema-invalid or contract-violation - the contract is "
             "frozen by B06; fix the spec via versioned migration or escalate to the owner")
R_ONCE = ("single attempt; on failure preserve partial artifacts and emit FAILED:<id> with a "
          "two-signal blocker proof (spec 11400)")
REV_SOLO = ("one independent adversarial reviewer in a fresh context who did not author the "
            "module and starts from the tests, not the author's summary")
REV_SEC = ("two reviewers: correctness plus a security refuter who defaults to REFUTED when "
           "evidence is insufficient (spec 11062)")
REV_OWNER = ("one independent adversarial reviewer plus an explicit owner sign-off block in the "
             "receipt; the reviewer may not grant the owner half")
T_W = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
T_WP = ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "PowerShell"]
M_OPUS = {"vendor": "anthropic", "model": "opus", "role": "implementer"}
M_ARCH = {"vendor": "anthropic", "model": "opus", "role": "runtime-architect"}

FAM = {
    "7": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
              retry=R_PIVOT, prof="workflow-foundry-module",
              fc=["schema-invalid", "overclaim", "green-not-live", "dependency-blocked"]),
    "7A": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="council-runtime-module",
               fc=["schema-invalid", "overclaim", "detector-failure", "dependency-blocked"]),
    "8": dict(sub="local-serialized", to=2700, tools=T_WP, rev=REV_SOLO, model=M_OPUS,
              retry=R_PIVOT, prof="router-module",
              fc=["overclaim", "detector-failure", "green-not-live", "dependency-blocked"]),
    "9": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
              retry=R_PIVOT, prof="crossvendor-module",
              fc=["detector-failure", "overclaim", "green-not-live", "dependency-blocked"]),
}
NEW = []


def add(phase, title, q, inputs, deps, ev, tests, **kw):
    NEW.append(dict(phase=phase, title=title, q=q, inputs=inputs, deps=deps, ev=ev,
                    tests=tests, kw=kw))


P7 = [A_P7, A_P7PROD, A_PRED]
P7A = [A_P7A, A_P2C, A_CPROD, C_SPEC, C_SCHEMA]

# ---- 12 new PHASE 7 units (IMP-0353..IMP-0364) --------------------------------
add("7", "Built-in blueprint registry with a release-blocking distinctness gate",
    "Implement tools/foundry/registry.py holding the built-in blueprint set and a gate that "
    "BLOCKS release when the materially-distinct count falls below the 96 floor. Falsifiable "
    "question: is the gate wired to the release checklist such that adding two renamed copies "
    "RAISES the raw count but not the distinct count, and does the gate fail closed when the "
    "distinctness scan itself errors?",
    P7 + [W_BP, SPEC + ":10909", SPEC + ":11394"],
    ["IMP-0277", "IMP-0281"],
    "1) the gate run with two planted renamed copies, raw count up and distinct count flat; 2) an "
    "induced scanner exception producing a BLOCK, not a pass.",
    ["control: renamed copies must not raise the distinct count",
     "negative control: a scanner crash must fail closed, not fail open"],
    to=2700, prof="workflow-registry-gate")

add("7", "Per-workflow preset, example and documented-stopping-rule fixture gate",
    "Implement tools/foundry/completeness.py asserting that every shipped workflow carries at "
    "least one runnable example, one preset and an explicitly documented stopping rule (spec "
    "10911). Falsifiable question: how many of the current blueprints would fail this gate today, "
    "and is a stopping rule that merely says 'when done' detected as undocumented?",
    P7 + [W_BP, SPEC + ":10911"],
    ["IMP-0257", "IMP-0353"],
    "1) a per-blueprint pass/fail table with the current failing count published, not summarised; "
    "2) a vacuous-stopping-rule fixture that must be rejected.",
    ["census: pass/fail per blueprint, failing ids listed",
     "negative control: a vacuous stopping rule must FAIL the gate"],
    to=2700, prof="workflow-registry-gate")

add("7", "Workflow documentation generator with docs-versus-code parity check",
    "Implement tools/foundry/docgen.py deriving each workflow's documentation from its typed "
    "definition and failing when hand-written docs disagree with the definition. Falsifiable "
    "question: when a stage is renamed in code but not in prose, does the parity check catch it, "
    "and can documentation ever describe a stage that no longer exists?",
    P7 + [SPEC + ":11389"],
    ["IMP-0257"],
    "1) a symbol-set diff between documented stages and defined stages, both directions; 2) a "
    "rename mutation that must turn the check red.",
    ["unit: generated docs match the definition for 20 workflows",
     "negative control (stopping condition 12, docs and code agree): rename a stage in code only "
     "and assert the parity check FIRES"],
    to=2700, prof="workflow-docs-artifact")

add("7", "Per-stage progress events into the cockpit observability surface",
    "Implement tools/foundry/observe.py emitting typed start/heartbeat/finish events per stage to "
    "the existing cockpit rather than building a second monitor. Falsifiable question: does a "
    "workflow that is genuinely working but silent (a long single stage) appear as healthy, and "
    "does a dead workflow appear as stale within the declared window?",
    P7 + [A_FAIL, "command-center/events/EVENTS.jsonl"],
    ["IMP-0257", "IMP-0275"],
    "1) a heartbeat trace during a deliberately long silent stage; 2) a kill test where the "
    "cockpit must show stale within the window, timed independently of the emitter.",
    ["control (spec 11316 no-change-monitor class): silent-but-working must not read as dead",
     "control (spec 11315 monitor-dies class): killed run must read as stale",
     "negative control: freeze the clock and assert the staleness check FAILS, proving it is "
     "time-sensitive"],
    to=2700, sub="local-serialized", tools=T_WP, prof="workflow-observability-module",
    fc=["uncontrolled-silence", "detector-failure", "green-not-live", "overclaim"])

add("7", "Artifact-manifest registration at every stage boundary",
    "Implement tools/foundry/manifest.py registering each produced artifact into "
    "ARTIFACT-MANIFEST.json as a precondition of stage completion (predicate condition 11). "
    "Falsifiable question: can a stage complete with an artifact on disk that never reaches the "
    "manifest, and can the manifest list an artifact that is absent from disk?",
    P7 + [A_PRED, "command-center/ARTIFACT-MANIFEST.json"],
    ["IMP-0263"],
    "1) a two-directional reconcile disk-vs-manifest with both orphan classes counted; 2) a "
    "completion attempt with an unregistered artifact, expected refused.",
    ["unit: registration on success, rollback on failure",
     "invariant: disk and manifest agree in both directions",
     "negative control: delete a manifest entry and assert the reconcile FIRES"],
    to=1800, prof="workflow-manifest-module")

add("7", "Workflow idempotency keys preventing duplicate external side effects",
    "Implement tools/foundry/idempotency.py so a re-run with the same idempotency key does not "
    "repeat an external side effect (a PR, a publish, a paid call). Falsifiable question: after "
    "an interrupted run is retried, how many external calls were made in total, counted at the "
    "transport rather than inferred from the run log?",
    P7 + [A_SCALE],
    ["IMP-0266", "IMP-0268"],
    "1) a transport-level call counter across an interrupt-and-retry cycle; 2) the idempotency "
    "store inspected for the key and its recorded result.",
    ["integration: interrupt-and-retry yields exactly one external effect",
     "negative control: remove the key and assert the counter shows two"],
    prof="workflow-idempotency-module")

add("7", "Partial-result harvesting from an aborted run",
    "Implement tools/foundry/harvest.py recovering every usable artifact from a run that aborted, "
    "labelling each as COMPLETE or PARTIAL against the shared predicate. Falsifiable question: is "
    "a PARTIAL artifact ever consumed downstream as if complete, and does harvesting itself ever "
    "overwrite a good artifact with a partial one?",
    P7 + [A_PRED, SPEC + ":11313"],
    ["IMP-0263", "IMP-0268"],
    "1) a downstream-consumer audit showing every read checks the label; 2) a pre/post hash census "
    "proving harvest wrote no existing artifact.",
    ["control (spec 11313 partial-without-sentinel class): a partial must not satisfy a consumer",
     "negative control: strip the label and assert the consumer audit FAILS"],
    to=2700, prof="workflow-recovery-module")

add("7", "In-flight run migration across a workflow version bump",
    "Implement tools/foundry/inflight.py so a paused run started on definition v1 either completes "
    "on v1 or is explicitly migrated, honouring the frozen-launcher rule (spec 10660). Falsifiable "
    "question: what happens today to a paused run when its definition changes underneath it - does "
    "it silently resume against the new graph?",
    P7 + [SPEC + ":10660"],
    ["IMP-0268", "IMP-0269"],
    "1) a definition-hash comparison at resume time with both hashes recorded; 2) a migrated run "
    "compared against a straight-through v2 run on the same inputs.",
    ["unit: v1-pinned resume, explicit migration, and refusal paths",
     "negative control: remove the hash pin and assert a silent cross-version resume occurs"],
    to=2700, retry=R_NORETRY, prof="workflow-migration-module")

add("7", "Shared blackboard with explicit read and write scopes",
    "Implement tools/foundry/blackboard.py giving stages a typed shared context whose read and "
    "write permissions are declared per stage. Falsifiable question: can a stage read a key it "
    "never declared, and does a write conflict between two concurrent fan-out children get "
    "detected rather than last-writer-wins?",
    P7,
    ["IMP-0261", "IMP-0262"],
    "1) an undeclared-read attempt producing a refusal event; 2) a concurrent-write fixture whose "
    "conflict is reported with both values retained.",
    ["unit: scope enforcement on read and write",
     "concurrency: simultaneous writes produce a reported conflict",
     "negative control: enable last-writer-wins and assert the conflict test FAILS"],
    prof="workflow-state-module")

add("7", "Stage heartbeat and hang detection",
    "Implement tools/foundry/heartbeat.py detecting a stage that has stopped making progress, "
    "distinct from one that is merely slow. Falsifiable question: on what independent signal is "
    "hang declared, given that neither file mtime nor elapsed time alone can separate a hung stage "
    "from a long-running one?",
    P7 + [A_FAIL],
    ["IMP-0275", "IMP-0356"],
    "1) an AND-gate of process CPU delta and output-byte growth over a window; 2) a long-but-live "
    "control stage that must NOT be declared hung.",
    ["control: hung stage detected by the AND-gate",
     "control: slow-but-live stage not flagged (false-positive rate reported)",
     "negative control (spec 11317 one-hung-unit class): mtime-only detection must be shown to "
     "misclassify the control"],
    to=2700, sub="local-serialized", tools=T_WP, prof="workflow-liveness-module",
    fc=["uncontrolled-silence", "detector-failure", "timeout", "overclaim"])

add("7", "Runtime credential injection with no bundled auth files",
    "Implement tools/foundry/secrets.py injecting credentials at runtime from the owner's existing "
    "store, with a hard prohibition on writing any credential into a workflow package, artifact or "
    "log (spec 10580). Falsifiable question: does any produced artifact, cache entry or log line "
    "contain a credential, scanned across env-style, JSON-embedded, camelCase and base64 forms?",
    P7 + [SPEC + ":10580", SPEC + ":11345"],
    ["IMP-0273", "IMP-0276"],
    "1) a planted-credential corpus scanned across every produced artifact and log, required zero "
    "survivors; 2) an independent gitleaks-style scan of the same output tree. This unit reads "
    "credential PRESENCE only and never rotates, prints or modifies any credential.",
    ["security: 4-encoding planted-credential corpus",
     "negative control: disable the redactor and assert all 4 encodings are found, proving the "
     "scanner is not silently passing"],
    to=2700, sub="local-serialized", tools=T_WP, rev=REV_OWNER, oa=True,
    prof="workflow-secrets-module",
    fc=["secret-exposure", "detector-failure", "owner-blocked", "overclaim"])

add("7", "Per-run disposable worktree and container provisioning",
    "Implement tools/foundry/isolation.py provisioning a disposable worktree or container per "
    "implementation shard and tearing it down deterministically (spec 10581). Falsifiable "
    "question: can two concurrent runs contaminate one another through a shared git index, and "
    "does teardown ever remove a worktree whose content is not preserved elsewhere?",
    P7 + [A_SCALE, SPEC + ":10581"],
    ["IMP-0262"],
    "1) a contamination probe running two file-disjoint shards concurrently and diffing each "
    "shard's staged set; 2) a pre-teardown content-preservation proof (content present in the "
    "target branch or archived) recorded before any removal.",
    ["concurrency: two concurrent shards must not appear in each other's staged set",
     "safety: teardown refuses without a preservation proof",
     "negative control: share one index deliberately and assert the contamination probe FIRES"],
    to=3600, sub="local-serialized", tools=T_WP, prof="workflow-isolation-module",
    fc=["green-not-live", "detector-failure", "overclaim", "owner-blocked"])

# ---- 14 new PHASE 7A units (IMP-0365..IMP-0378) -------------------------------
add("7A", "Committee and caucus topology",
    "Implement tools/council/topology/committee.py partitioning a council into standing committees "
    "and ad-hoc caucuses that deliberate separately and report up. Falsifiable question: does a "
    "caucus formed from like-minded participants produce an echo chamber, measured as reduced "
    "position spread relative to a randomly formed caucus of the same size?",
    P7A,
    ["IMP-0287", "IMP-0313"],
    "1) position-spread comparison between affinity-formed and random caucuses on the same "
    "question; 2) a report-up fidelity check that each caucus conclusion is traceable to member "
    "turns.",
    ["experiment: affinity vs random caucus spread",
     "negative control: a random caucus must not be flagged as an echo chamber"],
    prof="council-topology-module")

add("7A", "Nominal-group technique with private ranking aggregation",
    "Implement tools/council/protocol/ngt.py collecting silent idea generation then PRIVATE "
    "rankings aggregated without cross-influence. Falsifiable question: are rankings genuinely "
    "private until aggregation - can any participant's ranking be inferred from what another "
    "participant was shown?",
    P7A,
    ["IMP-0297", "IMP-0325"],
    "1) a delivered-prompt scan proving no ranking content reached a peer before aggregation; 2) "
    "an aggregation result reproduced independently from the raw ballots.",
    ["unit: silent generation, private ranking, aggregation",
     "negative control: leak one ranking and assert the prompt scan FIRES"],
    to=1800, prof="council-protocol-module")

add("7A", "Oxford debate engine with sides, timing and rebuttal depth",
    "Implement tools/council/protocol/oxford.py running a motion with proposition and opposition "
    "sides, timed turns and a bounded rebuttal depth. Falsifiable question: does the side a "
    "participant is assigned change its stated conclusion more than the evidence does - i.e. what "
    "is the measured side-assignment effect?",
    P7A,
    ["IMP-0287", "IMP-0305"],
    "1) a swapped-sides replication on the same motion measuring conclusion flip rate; 2) a "
    "turn-timing audit against the configured limits.",
    ["experiment: side-swap flip rate published",
     "negative control: an evidence-decisive motion should show a LOW flip rate, so a high rate "
     "everywhere indicates the protocol is measuring rhetoric not truth"],
    prof="council-protocol-module")

add("7A", "Six-Hats lens-rotation engine",
    "Implement tools/council/protocol/hats.py rotating every participant through a fixed set of "
    "thinking lenses so each perspective is applied by more than one participant. Falsifiable "
    "question: does rotation actually change a participant's output, or does the same participant "
    "produce lens-invariant text (a role-collapse signal under a different name)?",
    P7A,
    ["IMP-0287", "IMP-0347"],
    "1) per-participant across-lens output divergence, compared against the across-participant "
    "divergence baseline; 2) a lens-vocabulary presence check per turn.",
    ["unit: rotation schedule completeness (every lens covered)",
     "negative control: lens-invariant output must be flagged, not accepted as compliance"],
    to=1800, prof="council-protocol-module")

add("7A", "Fishbowl topology with observer promotion",
    "Implement tools/council/topology/fishbowl.py with an inner speaking ring and an outer "
    "observing ring, plus rules for promoting an observer into the ring. Falsifiable question: do "
    "observers contribute anything measurable, or is the outer ring pure cost - measured as the "
    "fraction of final decisions that cite an observer-originated point?",
    P7A,
    ["IMP-0287", "IMP-0300"],
    "1) the observer-origination rate in final decisions across 15 runs; 2) a promotion-event "
    "audit checking each promotion against its declared trigger.",
    ["unit: ring membership, promotion and demotion",
     "measurement: observer contribution rate published even if it is near zero"],
    to=1800, prof="council-topology-module")

add("7A", "Premortem protocol with a structured failure-mode ledger",
    "Implement tools/council/protocol/premortem.py asserting the plan has already failed and "
    "harvesting causes into a typed ledger with likelihood and detectability. Falsifiable "
    "question: do premortem-identified failure modes ever get carried into the action plan as "
    "mitigations, or are they collected and dropped?",
    P7A,
    ["IMP-0287", "IMP-0374"],
    "1) a traceability count from ledger entries to action-plan mitigations; 2) the unmitigated "
    "entries listed explicitly rather than omitted.",
    ["unit: ledger schema and harvest",
     "invariant: every failure mode is either mitigated or explicitly accepted",
     "negative control: drop a mode silently and assert the traceability count FALLS"],
    to=1800, prof="council-protocol-module")

add("7A", "Speaking-order strategy engine",
    "Implement tools/council/order.py providing round-robin, random, priority, seniority-inverted "
    "and chair-recognition orders as pluggable strategies. Falsifiable question: does speaking "
    "order bias the outcome - measured as the correlation between first-speaker position and final "
    "decision alignment across matched runs?",
    P7A,
    ["IMP-0287"],
    "1) a first-speaker-effect measurement across 20 matched runs with order shuffled; 2) an "
    "order-trace audit confirming each strategy produced the sequence it claims.",
    ["unit: each strategy's sequence against a hand-computed expectation",
     "experiment: first-speaker effect measured and published",
     "negative control: a deliberately biased order must show a detectable effect"],
    to=1800, prof="council-kernel-module")

add("7A", "Per-seat context assembly under a declared context budget",
    "Implement tools/council/context.py building each participant's prompt from its partition, "
    "role, history and evidence within a declared token budget, with a documented eviction order. "
    "Falsifiable question: when the budget forces eviction, what is dropped first, and can a "
    "participant lose the very evidence it is required to weigh?",
    P7A + [A_P2C],
    ["IMP-0297", "IMP-0321"],
    "1) measured per-seat token counts against the declared budget; 2) an evidence-retention check "
    "asserting required anchors survive eviction.",
    ["unit: eviction order against the documented policy",
     "negative control: evict a required anchor and assert the retention check FIRES"],
    prof="council-kernel-module")

add("7A", "Idea-to-option-card promotion pipeline",
    "Implement tools/council/artifacts/option_cards.py promoting ledger ideas that clear a "
    "maturity bar into typed option cards with mechanism, cost, risk and evidence fields. "
    "Falsifiable question: what fraction of raw ideas survive promotion, and is the bar doing work "
    "- would a random subset of the same size be indistinguishable from the promoted set on an "
    "independent quality rating?",
    P7A + [SPEC + ":10933"],
    ["IMP-0313", "IMP-0323"],
    "1) promotion rate plus a blind quality comparison of promoted versus random-subset cards; 2) "
    "field-completeness validation on every promoted card.",
    ["unit: promotion criteria and card schema",
     "control: promoted set must beat a random subset on blind rating, else the bar is decorative"],
    to=2700, prof="council-artifacts-module")

add("7A", "Action-plan generator from a council decision",
    "Implement tools/council/outcomes/action_plan.py turning a decision into typed, owned, "
    "sequenced actions with preconditions. Falsifiable question: is every action traceable to a "
    "decision element, and does the plan ever contain an action the council never agreed to?",
    P7A + [SPEC + ":10933"],
    ["IMP-0331", "IMP-0333"],
    "1) an action-to-decision traceability check listing untraceable actions; 2) a schema "
    "validation on every action (owner, precondition, verification).",
    ["unit: plan schema and sequencing",
     "negative control: inject an unagreed action and assert traceability FIRES"],
    to=1800, prof="council-outcomes-module")

add("7A", "Unresolved-question and experiment ledger",
    "Implement tools/council/outcomes/unresolved.py capturing every unresolved question with the "
    "EXACT experiment that would settle it, per the program stopping condition on residual "
    "unknowns. Falsifiable question: does every unresolved entry name a settling experiment that "
    "is actually executable, or do some name an aspiration?",
    P7A + [SPEC + ":11392"],
    ["IMP-0332", "IMP-0333"],
    "1) an executability audit of each named experiment (command exists, inputs exist, oracle "
    "defined); 2) a count of entries failing that audit, published rather than summarised.",
    ["unit: entry schema requires a settling experiment",
     "control: a vague experiment string must FAIL the executability audit",
     "negative control: a concrete command-plus-oracle entry must PASS"],
    to=1800, prof="council-outcomes-module")

add("7A", "Owner-intervention channel with recorded interventions",
    "Implement tools/council/owner.py letting the owner pause a live council, inject guidance or "
    "a constraint, and resume, with the intervention recorded as a first-class event. Falsifiable "
    "question: is an owner intervention distinguishable from a participant contribution in the "
    "final artifact, and can an intervention silently rewrite an earlier recorded position?",
    P7A + [SPEC + ":11349-11370"],
    ["IMP-0287", "IMP-0335"],
    "1) an artifact scan confirming every intervention carries an owner-origin marker; 2) an "
    "append-only proof that no prior event was mutated, by comparing the event-log prefix hash "
    "before and after.",
    ["unit: pause, inject, resume lifecycle",
     "invariant: event-log prefix hash unchanged by an intervention",
     "negative control: mutate a prior event and assert the prefix hash check FIRES"],
    sub="local-serialized", tools=T_WP, rev=REV_OWNER, oa=True,
    prof="council-owner-module",
    fc=["owner-blocked", "detector-failure", "overclaim", "dissent-loss"])

add("7A", "Behavioural independence audit of first-round briefs",
    "Implement tools/council/antifail/independence.py measuring whether first-round briefs are "
    "actually independent, as opposed to merely configured to be. Falsifiable question: on a "
    "council configured for blind independence, what is the measured pairwise brief similarity, "
    "and how does it compare with a deliberately non-blind control run?",
    P7A + [A_CPROD],
    ["IMP-0312", "IMP-0299"],
    "1) pairwise brief-similarity distributions for blind and non-blind configurations of the same "
    "council; 2) a shared-phrase census identifying any text common to all briefs.",
    ["control: blind and non-blind distributions must separate; if they do not, report that the "
     "blind configuration is not achieving independence rather than declaring it works",
     "negative control: identical briefs must score at the top of the range"],
    prof="council-antifail-module")

add("7A", "Council-as-a-workflow-stage bridge",
    "Implement tools/council/bridge.py letting a workflow stage invoke a council with typed inputs "
    "and receive a typed decision, so deliberation composes with execution without a second control "
    "plane. Falsifiable question: does the bridge introduce a second scheduler or event log, and "
    "does a council failure inside a workflow classify under the workflow's failure policy or "
    "silently pass?",
    P7A + [A_P7, D_ARCH],
    ["IMP-0287", "IMP-0263", "IMP-0275"],
    "1) a control-plane census proving one scheduler and one event log across the composed run; 2) "
    "a council-failure fixture whose classification is read from the workflow's failure policy.",
    ["integration: council invoked as a stage, decision consumed downstream",
     "invariant: no second control plane (spec 10727)",
     "negative control: make the council swallow its own failure and assert the fixture detects it"],
    model=M_ARCH, prof="council-bridge-module",
    fc=["duplicate-control-plane", "overclaim", "detector-failure", "dependency-blocked"])

# ---- 2 kept stragglers, repointed at IMP-4's units (IMP-0379..IMP-0380) -------
add("8", "Lazy capability activation and gateway loader",
    "Implement tools/router/lazy.py so a capability's full body loads only when selected, keeping "
    "turn-zero cost to the index summary. This is the one phase-8 mechanism absent from IMP-4's "
    "22-unit routing block (which covers index, matchers, fusion, budget, conflict, override, "
    "explanation, fallback, telemetry, regression, mutation, repo-vs-live, staleness, dry-run, "
    "hook contract, tombstones and shadow mode, but not lazy body loading). Falsifiable question: "
    "how many tokens does turn zero cost with lazy loading versus eager, measured rather than "
    "estimated, and does any capability still load eagerly by accident?",
    [SPEC + ":10948-10963", D_ARCH, A_FAIL],
    ["IMP-0385", "IMP-0392", "IMP-0402"],
    "1) measured turn-zero token counts for eager and lazy configurations on the same index; 2) a "
    "load-event trace listing every capability body loaded during a turn.",
    ["measurement: eager vs lazy turn-zero token counts published",
     "negative control: mark one capability always-on and assert the load trace shows it, proving "
     "the trace can detect an eager load"],
    to=2700, prof="router-loader-module")

add("9", "Two-directional content-divergence detector for concurrent edits",
    "Implement tools/crossvendor/divergence.py classifying a contested path as identical, ahead, "
    "behind or DIVERGED using a byte-level differ, not a heuristic. This complements IMP-4's "
    "phase-9 block (claims, leases, lease-overlap, reaper, git-index guard) which detects "
    "CONTENTION but not two-directional content divergence. Falsifiable question: does the "
    "classifier catch the DIVERGED case where BOTH sides hold unique content, which every "
    "one-directional check on this estate reported as safe-to-overwrite?",
    [SPEC + ":10965-10983", SPEC + ":11320", D_NOREG],
    ["IMP-0410", "IMP-0428"],
    "1) per-class accuracy on a labelled 4-class fixture set, reported per class; 2) a "
    "one-directional check run over the same fixtures, whose misses on the DIVERGED class are "
    "counted and published.",
    ["control: 4-class labelled fixture, per-class accuracy (never a pooled figure)",
     "control: error DIRECTION reported - how many errors point at data loss",
     "negative control: a one-directional check must MISS the diverged class, proving the "
     "two-directional test adds real coverage"],
    to=2700, model=M_ARCH, prof="crossvendor-divergence-module",
    fc=["detector-failure", "overclaim", "green-not-live", "dependency-blocked"])

# ============================================================================
# assemble: 96 kept + 26 new + 2 stragglers + 4 phase-16 = 128
# ============================================================================
kept = data[:96]
assert all(u["phase"] in ("7", "7A") for u in kept), "kept block is not pure phase 7/7A"
p16 = [u for u in data if u["phase"] == "16"]
assert len(p16) == 4

built = []
for u in NEW:
    ph = u["phase"]
    base = FAM[ph]
    kw = u["kw"]
    built.append({
        "id": None, "title": u["title"], "phase": ph, "question_or_target": u["q"],
        "inputs": u["inputs"], "dependencies": u["deps"],
        "assigned_model_vendor_role": kw.get("model", base["model"]),
        "tool_permissions": kw.get("tools", base["tools"]),
        "execution_substrate": kw.get("sub", base["sub"]),
        "timeout_seconds": kw.get("to", base["to"]),
        "output_path": None,
        "output_schema": ("command-center/schema/receipt.schema.json profile=%s "
                          "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
                          "test_ids[], negative_control_ids[], reviewer_verdict, "
                          "residual_unknowns[])" % kw.get("prof", base["prof"])),
        "evidence_requirement": u["ev"], "tests_required": u["tests"],
        "reviewer_requirement": kw.get("rev", base["rev"]),
        "completion_sentinel": None,
        "retry_policy": kw.get("retry", base["retry"]),
        "failure_classification": kw.get("fc", base["fc"]),
        "owner_approval_required": kw.get("oa", False),
    })

final = kept + built + p16
assert len(final) == 128, len(final)

# renumber (positions 0..95 keep their existing ids by construction) and repoint deps
REPOINT = {"IMP-0376": "CC-0003"}
for i, u in enumerate(final):
    uid = "IMP-%04d" % (257 + i)
    u["id"] = uid
    u["output_path"] = "command-center/receipts/%s.json" % uid
    u["completion_sentinel"] = "SUCCESS:%s" % uid
    u["dependencies"] = [REPOINT.get(d, d) for d in u["dependencies"]]

with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(final, fh, indent=2, ensure_ascii=True)
    fh.write("\n")

ph = {}
for u in final:
    ph[u["phase"]] = ph.get(u["phase"], 0) + 1
print("wrote %s n=%d phases=%s first=%s last=%s"
      % (SRC, len(final), sorted(ph.items()), final[0]["id"], final[-1]["id"]))
