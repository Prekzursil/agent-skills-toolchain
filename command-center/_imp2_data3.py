# -*- coding: utf-8 -*-
"""IMP-2 slice, data part 3: units IMP-0230..IMP-0256 - the built-in blueprint library.

Blueprint accounting, counted from _USER-PROMPTS.md:10902-10907 (NOT hardcoded - the counts were
re-derived by reading the five category bullets plus the collective-intelligence bullet):
    research & evidence            15
    engineering & reliability      21
    security, governance, risk     12
    product, design, strategy      15
    data, science, knowledge       16
    collective intelligence + meta 17
                                  ---
                                   96   == the spec's own >=96 floor, exactly.

Of the 17 collective-intelligence entries, 9 are COUNCIL PROTOCOLS (configurable council,
100-idea brainstorm, Delphi, Oxford debate, Socratic cross-examination, jury, negotiation,
mediation, council-of-councils). Those are Phase 7A deliverables (_USER-PROMPTS.md:10915-10946)
and are NOT implemented here; IMP-0256 registers them as delegating library entries so the
library still exposes 96 while the runtime lives in 7A. Phase-7 blueprints implemented in this
slice therefore total 87.

SPLIT HONESTY: each family unit below owns 3-5 blueprints. A strict one-unit-per-blueprint
decomposition would need 87 units and would consume two thirds of this 128-unit slice, starving
the runtime and foundry machinery that every blueprint depends on. Each family unit names its
exact blueprint list so the orchestrator can split it later without re-deriving scope.
"""

FOUNDRY = "tools/foundry"
SPEC_LIB = "_USER-PROMPTS.md:10900-10907"


def fam(names):
    return ", ".join(names)


UNITS_3 = [
    # --------------------------------------------------------- H infra (4) 230-233
    dict(
        t="Define the blueprint authoring contract and ship a scaffold generator",
        q="Target: one contract every built-in blueprint satisfies - typed Workflow, at least one runnable example, "
        "at least one preset, documented stopping rules, a smoke test, and a declared capability vector - plus a "
        "scaffold generator that emits a compliant skeleton. Acceptance: a blueprint that omits any required "
        "element cannot be registered, and the scaffold's own output passes the contract (the generator must not "
        "emit something its own gate rejects - a tool that commits the defect class it exists to prevent has "
        "happened three times on this estate).",
        i=[
            SPEC_LIB,
            "_USER-PROMPTS.md:10911 (examples, tests, presets, stopping rules)",
        ],
        d=["IMP-0129", "IMP-0133", "IMP-0168"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) scaffold output passes the contract gate unmodified; (2) each of the six required "
        "elements, removed one at a time, produces a distinct registration failure (6/6).",
        ts=[
            "scaffold output passes its own gate (self-application control)",
            "6 one-at-a-time omissions produce 6 distinct rejections",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim"],
        oa=False,
    ),
    dict(
        t="Build the blueprint conformance harness that every library entry must pass",
        q="Target: one suite run over EVERY registered blueprint - schema validation, static validation, hermetic "
        "simulation, example execution, preset load, stopping-rule evaluation, docs presence. Acceptance: the "
        "harness discovers blueprints from the registry (not a hand-maintained list), so a blueprint added without "
        "a test cannot hide; a planted untested blueprint must turn the harness red.",
        i=["IMP-0230 contract", "IMP-0199 simulator", "tools/detector-self-test"],
        d=["IMP-0230", "IMP-0199"],
        role="test-author",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) discovered blueprint count equals registry count (computed equality, no hand list); "
        "(2) a planted untested blueprint turns the harness red.",
        ts=[
            "discovered count == registry count",
            "planted untested blueprint detected (detector fires on the broken state)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Build the material-distinctness catalog and make it a blocking gate",
        q="Question: are the 96 library entries materially distinct, or are some the same mechanism reworded? "
        "Target: the explicit catalog the spec demands (10909), computed from structural fingerprints plus "
        "capability vectors, with every near-duplicate pair listed and adjudicated. Acceptance: the gate BLOCKS "
        "registration of an entry whose fingerprint matches an incumbent, and the catalog reports the 96 total by "
        "re-deriving the category counts from the spec text rather than asserting them.",
        i=[
            "_USER-PROMPTS.md:10909",
            "IMP-0170 fingerprint",
            "IMP-0177 capability vectors",
        ],
        d=["IMP-0170", "IMP-0177", "IMP-0230"],
        role="librarian",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) fingerprint collisions == 0 across the registered library (computed); (2) a planted "
        "reworded duplicate is blocked at registration.",
        ts=[
            "zero fingerprint collisions across the library",
            "planted reworded duplicate blocked (both-states: a genuinely distinct entry registers)",
        ],
        rev="cross-vendor reviewer (Codex) - the anti-padding gate must not be graded by its author",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Define the flagship tier and the 40-flagship end-to-end test contract",
        q="Target: declare which 40 of the 96 are flagship and what 'full end-to-end test' means for them (real rail, "
        "real artifacts, deterministic postcondition probe on the artifact produced - not a mocked run). "
        "Acceptance: flagship membership is recorded in the registry, the count is computed (==40) rather than "
        "claimed, and a flagship whose e2e test never touches a real artifact fails the contract check.",
        i=[
            "_USER-PROMPTS.md:10898 (at least 40 flagship with full end-to-end tests)",
            "IMP-0231 harness",
        ],
        d=["IMP-0231"],
        role="test-author",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) flagship count computed from the registry == 40; (2) each flagship e2e asserts a "
        "postcondition on a real produced artifact (existence + minimum size + parse), verified by a meta-test.",
        ts=[
            "computed flagship count == 40",
            "a mocked-only flagship e2e is rejected by the meta-test (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    # ------------------------------------------------- research & evidence (4) 234-237
    dict(
        t="Implement research blueprints 1-4: deep research, gem hunt, systematic and rapid literature review",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "deep-research",
                "gem-hunt",
                "systematic-literature-review",
                "rapid-literature-review",
            ]
        )
        + ". Acceptance: deep-research and gem-hunt are FLAGSHIP (full e2e). All four "
        "must preserve negative and contradictory evidence rather than optimizing for favorable results "
        "(11278), and systematic vs rapid must differ in a DECLARED parameter (breadth/depth/quota), not merely "
        "in prose - otherwise they are one blueprint wearing two names.",
        i=[
            SPEC_LIB,
            "_USER-PROMPTS.md:11246-11278 (deep-research required behavior)",
            "IMP-0230 contract",
        ],
        d=["IMP-0230", "IMP-0168"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) systematic and rapid differ by a computed parameter diff, and their fingerprints differ; "
        "(2) a run whose sources are all favorable is flagged for missing contradiction search.",
        ts=[
            "systematic vs rapid: computed parameter diff non-empty and fingerprints differ",
            "all-favorable evidence set triggers the contradiction-search gate (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "rate-limited"],
        oa=False,
    ),
    dict(
        t="Implement research blueprints 5-8: evidence map, fact/citation audit, official-doc audit, source-code archaeology",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "evidence-map",
                "fact-citation-audit",
                "official-doc-audit",
                "source-code-archaeology",
            ]
        )
        + ". Acceptance: fact-citation-audit must resolve every citation it checks "
        "(a citation that cannot be fetched is UNRESOLVED, never assumed valid), and source-code-archaeology must "
        "read the blob via `git cat-file -p <rev>:<path>` rather than `git archive`, which returns CRLF on this box.",
        i=[SPEC_LIB, "rules/common/windows-shell.md (8b)", "IMP-0230 contract"],
        d=["IMP-0230"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) an unresolvable citation is marked UNRESOLVED, proven with a planted dead reference; "
        "(2) archaeology's blob read is byte-identical to CI's checkout for a control file.",
        ts=[
            "planted dead citation is UNRESOLVED, not silently accepted (both-states)",
            "blob read matches the LF blob, not the CRLF worktree (byte comparison)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement research blueprints 9-12: prior-art/patent, standards/regulatory, niche/forum, multilingual",
        q="Target: implement 4 blueprints - "
        + fam(
            ["prior-art-patent", "standards-regulatory", "niche-forum", "multilingual"]
        )
        + ". Acceptance: multilingual must record the source language and whether a claim came "
        "from a translation (a translated claim carries a distinct confidence path), and niche-forum must tag "
        "practitioner anecdote as a separate evidence class from documentation.",
        i=[
            SPEC_LIB,
            "_USER-PROMPTS.md:10696-10699 (niche, multilingual, archival source classes)",
        ],
        d=["IMP-0230", "IMP-0137"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) evidence-class tags are present on 100% of harvested claims (computed coverage); "
        "(2) a translated claim is distinguishable from a native-language claim in the output schema.",
        ts=[
            "evidence-class coverage == 100% (no untagged claims)",
            "translation provenance present and distinct (schema assertion)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "rate-limited"],
        oa=False,
    ),
    dict(
        t="Implement research blueprints 13-15: archival, contradiction/negative-result, watchlist",
        q="Target: implement 3 blueprints - "
        + fam(["archival", "contradiction-negative-result", "watchlist"])
        + ". Acceptance: watchlist is the only one of the three that is SCHEDULED rather than one-shot, so it must "
        "be resumable and idempotent across runs; and contradiction/negative-result must be able to return a "
        "proof-of-impossibility record when the requested counterevidence provably cannot be obtained.",
        i=[
            SPEC_LIB,
            "_USER-PROMPTS.md:11276 (proof-of-impossibility)",
            "IMP-0139 RepairLoop",
        ],
        d=["IMP-0230", "IMP-0139"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a repeated watchlist run produces no duplicate findings (idempotence, computed); "
        "(2) an impossible counterevidence request yields a schema-valid proof-of-impossibility record.",
        ts=[
            "watchlist idempotent across two runs (zero duplicate findings)",
            "impossible request yields a proof-of-impossibility record, not an empty pass (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "uncontrolled-silence"],
        oa=False,
    ),
    # --------------------------------------------- engineering & reliability (5) 238-242
    dict(
        t="Implement engineering blueprints 1-4: root-cause investigation, regression triage, incident response, postmortem",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "root-cause-investigation",
                "regression-triage",
                "incident-response",
                "postmortem",
            ]
        )
        + ". Acceptance: root-cause-investigation is FLAGSHIP and must "
        "REPRODUCE the failure before proposing a cause; a proposed cause with no reproduction is rejected by the "
        "blueprint's own gate, because a cause that was never reproduced is a hypothesis.",
        i=[SPEC_LIB, "_USER-PROMPTS.md:11036 (reproduce the baseline failure)"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a cause without a reproduction receipt is rejected; (2) the reproduction is re-run by a "
        "different process than the one that proposed it (independence, not self-report).",
        ts=[
            "unreproduced cause rejected (both-states: reproduced cause accepted)",
            "reproduction is executed by an independent process, asserted from the ledger",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement engineering blueprints 5-8: architecture tournament, planning, TDD implementation, code review",
        q="Target: implement 4 blueprints - "
        + fam(
            ["architecture-tournament", "planning", "tdd-implementation", "code-review"]
        )
        + ". Acceptance: tdd-implementation is FLAGSHIP and must PROVE the red phase - the test "
        "is executed and observed failing BEFORE the implementation exists, recorded as a receipt; a suite that "
        "was never red is not evidence that it tests anything.",
        i=[SPEC_LIB, "guides/testing-patterns.md", "IMP-0230 contract"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=5400,
        ev="Two signals: (1) a red-phase receipt exists and its failure output names the missing symbol; (2) the "
        "same test passes after implementation, in a separate recorded run.",
        ts=[
            "red-phase receipt required before implementation is accepted (both-states)",
            "architecture-tournament preserves dissent - a unanimous verdict with no minority record is rejected",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement engineering blueprints 9-12: refactoring, migration rehearsal, dependency/supply-chain audit, cross-vendor compatibility",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "refactoring",
                "migration-rehearsal",
                "dependency-supply-chain-audit",
                "cross-vendor-compatibility",
            ]
        )
        + ". Acceptance: dependency audit must "
        "treat a stored green as DECAYED (its advisory database is live, so last week's clean scan is not a "
        "control for today), and refactoring must produce an equivalence argument for pure functions rather than "
        "asserting 'no functional change'.",
        i=[SPEC_LIB, "osv-scanner.toml", "rules/common/single-signal-verification.md"],
        d=["IMP-0230", "IMP-0159"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a scan result older than its TTL is reported STALE and re-run; (2) a refactor whose "
        "output differs on a generated input is caught by the equivalence check.",
        ts=[
            "stale advisory scan is re-run, never reused (both-states)",
            "planted behavior change in a 'pure refactor' is caught by differential testing",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement engineering blueprints 13-16: plugin conformance, marketplace conformance, release go/no-go, rollback rehearsal",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "plugin-conformance",
                "marketplace-conformance",
                "release-go-no-go",
                "rollback-rehearsal",
            ]
        )
        + ". Acceptance: rollback-rehearsal actually EXECUTES a "
        "rollback against a packaged artifact and verifies no user data is lost; release-go-no-go must consume the "
        "shared completion predicate rather than its own checklist logic.",
        i=[
            SPEC_LIB,
            "_USER-PROMPTS.md:11347 (rollback removes existing commands or user data)",
            "B07 phase-5/6",
        ],
        d=["IMP-0230", "IMP-0226", "B07"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) a rehearsed rollback preserves a planted user-data file (existence + hash); (2) "
        "go/no-go calls the shared oracle (AST assertion, no local checklist).",
        ts=[
            "planted user-data file survives a rehearsed rollback (both-states with a naive rollback that loses it)",
            "go/no-go uses the shared predicate (AST assertion)",
        ],
        rev="cross-vendor reviewer (Codex) - data-loss adjacent",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement engineering blueprints 17-21: benchmark generation, reproducibility, performance, concurrency/load/soak, abandoned-work salvage",
        q="Target: implement 5 blueprints - "
        + fam(
            [
                "benchmark-generation",
                "reproducibility",
                "performance",
                "concurrency-load-soak",
                "abandoned-work-salvage",
            ]
        )
        + ". Acceptance: abandoned-work-salvage must never "
        "authorize a delete on ancestry alone (squash-merge makes a fully merged branch report as AHEAD on this "
        "estate) - it requires PR-merged state or byte-level content comparison; concurrency/load/soak must run "
        "long enough to observe a leak, with the duration declared.",
        i=[
            SPEC_LIB,
            "rules/common/single-signal-verification.md",
            "_USER-PROMPTS.md:11003-11006",
        ],
        d=["IMP-0230", "IMP-0198"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) salvage refuses a delete backed only by ancestry, and accepts one backed by content "
        "equality; (2) soak duration and observed resource curve are recorded as data, not adjectives.",
        ts=[
            "ancestry-only delete authorization refused (both-states with content-proof)",
            "soak run records a resource curve; a planted leak is detected",
        ],
        rev="cross-vendor reviewer (Codex) - data-loss adjacent",
        retry="two-strikes",
        fc=["overclaim", "uncontrolled-silence"],
        oa=False,
    ),
    # ------------------------------------------ security, governance, risk (3) 243-245
    dict(
        t="Implement security blueprints 1-4: threat modeling, red/blue review, permission least-privilege, secret exposure",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "threat-modeling",
                "red-blue-review",
                "permission-least-privilege",
                "secret-exposure",
            ]
        )
        + ". Acceptance: secret-exposure NEVER prints a secret "
        "value (a zero-entropy prefix only), NEVER rotates or revokes anything, and reports the blast radius plus "
        "an explicit rotation RECOMMENDATION handed back to the owner - rotation is the owner's action, not the "
        "workflow's.",
        i=[SPEC_LIB, "AGENTS.md 9 and 9b", "SECURITY.md"],
        d=["IMP-0230", "IMP-0136"],
        role="security-implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a planted fake credential is detected and its VALUE never appears in any artifact "
        "(grep over all outputs returns zero hits for the value, non-zero for the prefix); (2) no code path in "
        "the blueprint can call a rotation API (AST assertion over the allowed call set).",
        ts=[
            "planted credential detected; value absent from every artifact (computed grep)",
            "no rotation/revocation call site exists (AST assertion)",
        ],
        rev="cross-vendor reviewer (Codex) - credential surface",
        retry="two-strikes",
        fc=["overclaim", "owner-blocked"],
        oa=False,
    ),
    dict(
        t="Implement security blueprints 5-8: privacy, legal/compliance, policy-as-code, governance proposal",
        q="Target: implement 4 blueprints - "
        + fam(["privacy", "legal-compliance", "policy-as-code", "governance-proposal"])
        + ". Acceptance: policy-as-code emits EXECUTABLE policy that is evaluated in CI "
        "(a policy that exists only as prose is not policy-as-code), and legal-compliance flags jurisdictional "
        "uncertainty as UNKNOWN rather than producing a confident answer the program cannot support.",
        i=[SPEC_LIB, "_USER-PROMPTS.md:10904", "QUALITY-CHARTER.md"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) an emitted policy is executed against a violating fixture and fails it; (2) the same "
        "policy passes a compliant fixture (both-states, so the policy is not vacuous).",
        ts=[
            "emitted policy fails a violating fixture and passes a compliant one",
            "jurisdictional uncertainty surfaces as UNKNOWN, never as a confident verdict",
        ],
        rev="cross-vendor reviewer (Codex) - legal surface",
        retry="two-strikes",
        fc=["overclaim", "owner-blocked"],
        oa=True,
    ),
    dict(
        t="Implement security blueprints 9-12: vulnerability triage, malicious-plugin review, risk/premortem, standards committee",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "vulnerability-triage",
                "malicious-plugin-review",
                "risk-premortem",
                "standards-committee",
            ]
        )
        + ". Acceptance: malicious-plugin-review is FLAGSHIP and must "
        "detect an excessive-permission package AND a package carrying auto-loading agent config (a cloned repo's "
        ".claude/.codex/hooks can execute the moment an agent runs inside it) - both planted, both caught.",
        i=[
            SPEC_LIB,
            "AGENTS.md 9 (cloned repo auto-loaded config)",
            "_USER-PROMPTS.md:11346",
        ],
        d=["IMP-0230", "IMP-0169"],
        role="security-implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) planted over-permissioned package flagged; (2) planted auto-loading agent config in a "
        "fixture repo flagged - and a clean package is not flagged (false-positive control).",
        ts=[
            "two planted malicious patterns detected; clean package not flagged (both-states)",
            "triage severity is derived from a declared rubric, not from the reporter's adjective",
        ],
        rev="cross-vendor reviewer (Codex) - adversarial surface",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    # -------------------------------------------- product, design, strategy (4) 246-249
    dict(
        t="Implement product blueprints 1-4: product discovery, user-research synthesis, requirements mining/reconciliation, roadmap prioritization",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "product-discovery",
                "user-research-synthesis",
                "requirements-mining-reconciliation",
                "roadmap-prioritization",
            ]
        )
        + ". Acceptance: "
        "requirements-mining-reconciliation must detect a requirement that SILENTLY DISAPPEARED between two "
        "documents (a named Phase-13 blind-spot question, 11073), proven with a planted dropped requirement.",
        i=[SPEC_LIB, "_USER-PROMPTS.md:11073 (what owner requirements disappeared)"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) planted dropped requirement is detected across a document pair; (2) an unchanged pair "
        "produces zero false alarms.",
        ts=[
            "planted dropped requirement detected; unchanged pair silent (both-states)",
            "prioritization output is reproducible from recorded inputs (no hidden ranking state)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement product blueprints 5-8: competitive teardown, market landscape, scenario planning, strategy war game",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "competitive-teardown",
                "market-landscape",
                "scenario-planning",
                "strategy-war-game",
            ]
        )
        + ". Acceptance: every forward-looking claim these produce carries a calibrated "
        "confidence band and an evidence tag; a bare 'likely fine' with no band is rejected by the output lint, "
        "because an unbanded forecast cannot be scored later.",
        i=[SPEC_LIB, "AGENTS.md 7 (confidence lexicon)"],
        d=["IMP-0230"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) planted unbanded claim rejected by the lint; (2) a fully banded output passes, so the "
        "lint is not always-failing.",
        ts=[
            "unbanded forward-looking claim rejected (both-states)",
            "bands map to declared numeric ranges, checked mechanically",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement product blueprints 9-12: design critique, UX, accessibility, launch readiness",
        q="Target: implement 4 blueprints - "
        + fam(["design-critique", "ux", "accessibility", "launch-readiness"])
        + ". Acceptance: accessibility must produce MEASURED numbers (contrast ratios, tap "
        "target sizes) from a real render rather than a model's opinion, and a screenshot-based check must assert "
        "it captured the intended surface (a colour-count or window-title assertion), because a fullscreen capture "
        "has silently photographed the wrong application on this estate.",
        i=[SPEC_LIB, "MEMORY (Reframe 2026-08-08 screenshot capture defect)"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) contrast ratios computed from pixels, not asserted; (2) the capture-target assertion "
        "fires when pointed at a decoy window (detector control).",
        ts=[
            "contrast measured from pixels (numbers recorded)",
            "capture-target assertion fires on a decoy window (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement product blueprints 13-15: pricing/packaging, customer council, outcome retrospective",
        q="Target: implement 3 blueprints - "
        + fam(["pricing-packaging", "customer-council", "outcome-retrospective"])
        + ". Acceptance: customer-council is a COUNCIL CONSUMER - it composes a "
        "CouncilSpec and delegates to the Phase-7A runtime rather than embedding its own deliberation loop; a "
        "second deliberation implementation here would be exactly the duplicate control plane the charter forbids.",
        i=[SPEC_LIB, "_USER-PROMPTS.md:10483", "B07 phase-7A council runtime"],
        d=["IMP-0230", "B07"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) AST assertion shows customer-council contains no deliberation loop of its own; (2) it "
        "produces a valid CouncilSpec that the 7A runtime accepts.",
        ts=[
            "no embedded deliberation loop (AST assertion)",
            "emitted CouncilSpec validates against the 7A schema (contract test, dependency-gated)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["dependency-blocked", "overclaim"],
        oa=False,
    ),
    # ------------------------------- data, science, knowledge, creative (4) 250-253
    dict(
        t="Implement data blueprints 1-4: extraction/normalization, data-quality audit, dataset documentation, knowledge-base construction",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "extraction-normalization",
                "data-quality-audit",
                "dataset-documentation",
                "knowledge-base-construction",
            ]
        )
        + ". Acceptance: extraction/normalization must "
        "sanitize control bytes INSIDE the parse, before any delimiter split - sanitizing per field afterwards is "
        "too late because a delimiter byte inside a value shifts every later column, a measured defect on this "
        "estate.",
        i=[SPEC_LIB, "rules/common/bash-hud-and-terminal-emit.md (2)"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a planted in-field delimiter does not shift columns (round-trip equality); (2) the "
        "same fixture WITHOUT the fix reproduces the shift (both-states control).",
        ts=[
            "in-field delimiter does not shift columns",
            "pre-fix control reproduces the shift, proving the test can see it",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement science blueprints 5-8: experiment design, statistical review, scientific replication, model evaluation",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "experiment-design",
                "statistical-review",
                "scientific-replication",
                "model-evaluation",
            ]
        )
        + ". Acceptance: statistical-review must flag an "
        "underpowered comparison and a result reported without an effect size; model-evaluation must run against a "
        "held-out slice and refuse a verdict computed on the visible slice alone.",
        i=[SPEC_LIB, "IMP-0198 held-out partition"],
        d=["IMP-0230", "IMP-0198"],
        role="implementer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) an underpowered fixture is flagged; (2) a visible-slice-only evaluation is refused, "
        "while a held-out evaluation proceeds (both-states).",
        ts=[
            "underpowered comparison flagged; adequately powered one not flagged",
            "visible-slice-only verdict refused",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement knowledge blueprints 9-12: documentation verification, teaching/curriculum, writing room, invention/wildcard",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "documentation-verification",
                "teaching-curriculum",
                "writing-room",
                "invention-wildcard",
            ]
        )
        + ". Acceptance: documentation-verification EXECUTES the commands a "
        "document claims work and records their exit codes (a documented command that has never been run is an "
        "untested claim - 'documentation command tests' is a required test layer at 11024), and invention/wildcard "
        "must be graded on novelty against the existing library rather than on volume.",
        i=[SPEC_LIB, "_USER-PROMPTS.md:11024", "IMP-0232 distinctness catalog"],
        d=["IMP-0230", "IMP-0232"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=5400,
        ev="Two signals: (1) every documented command in the control document is executed and its exit code "
        "recorded (coverage computed); (2) a planted broken command is caught.",
        ts=[
            "documented-command coverage computed; planted broken command caught (both-states)",
            "invention output scored for novelty against the library fingerprint set, not counted",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement analysis blueprints 13-16: morphological analysis, simulation/counterfactual, forecasting, expert elicitation",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "morphological-analysis",
                "simulation-counterfactual",
                "forecasting",
                "expert-elicitation",
            ]
        )
        + ". Acceptance: forecasting must emit resolvable predictions "
        "(each with a resolution date and a checkable criterion) so calibration can be scored later; a forecast "
        "that cannot be resolved is rejected at emission rather than discovered to be unscoreable months later.",
        i=[SPEC_LIB, "AGENTS.md 7 (Sherman-Kent bands)"],
        d=["IMP-0230"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) an unresolvable forecast is rejected at emission; (2) a resolvable one is accepted and "
        "its resolution criterion is machine-checkable (executed against a synthetic future state).",
        ts=[
            "unresolvable forecast rejected (both-states)",
            "resolution criterion is executable against a synthetic state, not prose",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    # --------------------------------- collective intelligence / meta (3) 254-256
    dict(
        t="Register the meta-workflow blueprints 1-4: scout, forge, merger/composer, tournament",
        q="Target: register 4 library blueprints - "
        + fam(
            [
                "workflow-scout",
                "workflow-forge",
                "workflow-merger-composer",
                "workflow-tournament",
            ]
        )
        + " - as library entries with presets, examples, "
        "documented stopping rules and e2e coverage, DELEGATING to the implementations in IMP-0209, IMP-0212, "
        "IMP-0182..IMP-0192 and IMP-0200. Acceptance: no logic is reimplemented here - an AST assertion proves "
        "each entry only composes existing units, so the library entry and the engine cannot drift apart.",
        i=["IMP-0209", "IMP-0212", "IMP-0200 outputs", "IMP-0230 contract"],
        d=["IMP-0209", "IMP-0212", "IMP-0200", "IMP-0230"],
        role="librarian",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) AST assertion shows zero reimplemented logic in the four entries; (2) each entry's e2e "
        "exercises the real engine (the engine's own counters increment).",
        ts=[
            "zero reimplemented logic (AST assertion)",
            "e2e drives the real engine, proven by engine-side counters (not a mock)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Implement the meta-workflow blueprints 5-8: repair/optimization, benchmark/selection, supersession, self-improvement validation",
        q="Target: implement 4 blueprints - "
        + fam(
            [
                "workflow-repair-optimization",
                "workflow-benchmark-selection",
                "workflow-supersession",
                "self-improvement-validation",
            ]
        )
        + ". Acceptance: self-improvement-validation "
        "KEEPS a change only when improvement is measured and REVERTS when neutral or harmful (11145-11146), and "
        "the revert path is exercised in a test - a self-improvement loop whose revert branch has never run is "
        "an unproven safety mechanism. Note: Phase 16 is the only spec phase with NO allocation bucket, so this "
        "blueprint is currently the program's only funded home for the closed loop.",
        i=[
            "_USER-PROMPTS.md:11135-11150",
            "command-center/PHASE-GRAPH.json (FINDING_unfunded_phase)",
        ],
        d=["IMP-0230", "IMP-0201", "IMP-0204"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) a neutral change is reverted and the revert is observed in the tree state; (2) a "
        "measured improvement is kept, with the measurement archived (both branches exercised).",
        ts=[
            "neutral change reverted; measured improvement kept (both-states, both branches run)",
            "the benchmark is updated so the same regression cannot silently return (11148), verified by re-running it",
        ],
        rev="cross-vendor reviewer (Codex) - the loop must not grade its own improvements",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Register the 9 council-protocol blueprints as delegating entries owned by Phase 7A",
        q="Target: register "
        + fam(
            [
                "configurable-council",
                "100-idea-brainstorm",
                "delphi",
                "oxford-debate",
                "socratic-cross-examination",
                "jury",
                "negotiation",
                "mediation",
                "council-of-councils",
            ]
        )
        + " as library "
        "entries that compile a CouncilSpec and delegate to the Phase-7A runtime. Acceptance: this slice "
        "implements ZERO deliberation logic - the boundary is mechanical (AST assertion) - and the library still "
        "exposes 96 entries: 87 implemented in phase 7 plus these 9. Question this settles: does the 96 floor "
        "hold without double-implementing the council?",
        i=[
            "_USER-PROMPTS.md:10915-10946 (Phase 7A)",
            SPEC_LIB,
            "IMP-0232 distinctness catalog",
        ],
        d=["IMP-0230", "IMP-0232", "B07"],
        role="librarian",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) registered library count == 96, computed from the registry (87 + 9), not asserted; "
        "(2) AST assertion shows zero deliberation loops in this slice's code.",
        ts=[
            "computed registry count == 96 (87 phase-7 + 9 delegated)",
            "zero deliberation logic in phase-7 code (AST assertion); a planted loop must fail it",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["dependency-blocked", "overclaim"],
        oa=False,
    ),
]
