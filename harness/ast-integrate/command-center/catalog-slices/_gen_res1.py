"""Generator for catalog slice RES-1 (deep-research / ecosystem / gem-hunt, units 1-128).

Hand-authored unit table; this script only materializes the 19 mandated fields on
every unit so that NO field exists solely as a global default.
"""
import json
import os
import re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RES-1.json")

CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SHARDS = "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19"

# ---------------------------------------------------------------- tool profiles
T_WEB = ["WebSearch", "WebFetch", "mcp__search-hub__web_search_exa",
         "mcp__search-hub__firecrawl_scrape", "Read", "Write(command-center/research/**)"]
T_WEB_BROAD = T_WEB + ["mcp__search-hub__tavily_search", "mcp__brightdata__search_engine",
                       "mcp__searxng__searxng_web_search"]
T_CODE = ["mcp__github__search_code", "mcp__github__get_file_contents", "mcp__github__list_commits",
          "mcp__github__search_repositories", "mcp__deepwiki__ask_question",
          "mcp__repomix__pack_remote_repository", "Read", "Write(command-center/research/**)"]
T_ISSUES = ["mcp__github__search_issues", "mcp__github__issue_read",
            "mcp__github__search_pull_requests", "mcp__github__list_releases",
            "WebFetch", "Read", "Write(command-center/research/**)"]
T_PAPERS = ["mcp__paper-search__search_arxiv", "mcp__paper-search__read_arxiv_paper",
            "mcp__paper-search__search_semantic", "mcp__scholarly-access__paper_resolve",
            "mcp__scholarly-access__paper_find_oa_pdf", "Read",
            "Write(command-center/research/**)"]
T_LOCAL = ["Read", "Grep", "Glob", "Bash", "PowerShell", "Write(command-center/research/**)"]
T_LOCAL_RO = ["Read", "Grep", "Glob", "Write(command-center/research/**)"]
T_ARCHIVE = ["WebFetch", "mcp__brightdata__scrape_as_markdown", "Bash(curl web.archive.org)",
             "Bash(curl archive.softwareheritage.org)", "Read",
             "Write(command-center/research/**)"]
T_SEC = ["WebSearch", "WebFetch", "Bash(osv-scanner)", "mcp__github__search_code",
         "mcp__github__list_releases", "Read", "Write(command-center/research/**)"]
T_TOR = ["Bash(torsocks curl, sandboxed + egress-logged)", "Read",
         "Write(command-center/research/**)"]
T_PROTO = ["Read", "Write", "Edit", "Grep", "Glob", "Bash(python)", "Bash(pytest)"]
T_MIX = T_WEB + ["mcp__github__search_code", "mcp__github__get_file_contents"]
T_PAPERS_WEB = T_PAPERS + ["WebSearch", "WebFetch"]

# ---------------------------------------------------------------- schema targets
S_CLAIM = "command-center/schema/research-claim-record.schema.json"
S_REG = "command-center/schema/research-registry.schema.json"
S_MATRIX = "command-center/schema/compatibility-matrix.schema.json"
S_LIC = "command-center/schema/license-graph.schema.json"
S_MEAS = "command-center/schema/measurement-run.schema.json"
S_NEG = "command-center/schema/negative-result-record.schema.json"
S_THREAT = "command-center/schema/threat-model.schema.json"
S_META = "https://json-schema.org/draft/2020-12/schema"

# ---------------------------------------------------------------- reviewer texts
RV_XV = ("one cross-vendor independent reproducer (OpenAI Codex rail) must re-derive the top-3 "
         "claims from raw sources without reading this unit's prose; disagreement blocks acceptance")
RV_ADV = ("one adversarial refuter in a fresh context, defaulting to REFUTED where evidence is "
          "insufficient (_USER-PROMPTS.md:11062); every surviving claim states its strongest caveat")
RV_TWO = ("two independent reviewers with PARTITIONED evidence (each gets a disjoint half of the "
          "source set) - 05-ECO anti-adoption #2 forbids a second same-vendor reviewer on the same input")
RV_MEAS = ("one measurement reviewer who re-runs the recorded command on a different shell "
           "(PowerShell 7 vs Git Bash) and must reproduce the number to within the stated tolerance")
RV_LEGAL = ("one licence/legal reviewer plus explicit owner sign-off before any downstream unit "
            "may act on the classification; no unit may treat this output as legal advice")
RV_SEC = ("one security reviewer who must attempt to construct a bypass of every mitigation listed "
          "before the mitigation may be recorded as effective")
RV_SELF = ("one independent reviewer who re-runs the emitted checker against BOTH a known-good and a "
           "known-broken fixture and confirms it fires only on the broken one")

# ---------------------------------------------------------------- retry policies
RT_STD = ("two strikes then pivot (AGENTS.md 4b): after 2 failed attempts on the same source route, "
          "switch source class (official doc -> source code -> issue tracker -> archive) before a "
          "third attempt; hard stop at 4 total, then emit a proof-of-impossibility record")
RT_XV = ("on a Codex-rail failure retry ONCE with --ignore-user-config and a prompt FILE "
         "(rules/common/cross-vendor-dispatch.md 3/4); a second failure reassigns the unit to "
         "anthropic/opus and records failure_classification=vendor-rail-unavailable")
RT_QUOTA = ("on HTTP 429 or a quota rejection, back off exponentially and rotate to a different "
            "search rail (Exa -> Tavily -> Firecrawl -> SearXNG); never lower the evidence bar to "
            "finish inside a quota window; 3 rail rotations then park as dependency-blocked")
RT_LOCAL = ("two strikes then pivot; a repeated identical local reading is ONE signal, not two "
            "(rules/common/single-signal-verification.md) - a third attempt must change shell, "
            "data field, or measurement or it does not count")
RT_PROTO = ("red-green-refactor; if the checker cannot be made to fail on the known-broken fixture "
            "in 2 attempts, STOP and report the detector as unbuildable rather than shipping a "
            "probe that is silent in both states")
RT_GATED = ("no retry without re-reading the owner gate; if the gate is unanswered the unit parks "
            "as owner-blocked with its partial artifact preserved and its exact question restated")

# ---------------------------------------------------------------- failure classes
F_WEB = ["source-unavailable", "paywalled-or-login-walled", "version-skew",
         "single-signal-only", "overclaim", "quota-exhausted"]
F_CODE = ["source-unavailable", "repo-renamed-or-redirected", "version-skew",
          "detector-failure", "overclaim"]
F_LOCAL = ["detector-failure", "environment-drift", "single-signal-only",
           "measurement-artifact", "overclaim"]
F_PAPER = ["paywalled-or-login-walled", "irreproducible-claim", "benchmark-contamination",
           "overclaim", "single-signal-only"]
F_SEC = ["source-unavailable", "advisory-embargoed", "unverifiable-exploit-claim",
         "overclaim", "legal-blocked"]
F_LEGAL = ["legal-blocked", "owner-blocked", "noassertion-unresolved", "version-skew",
           "overclaim"]
F_PROTO = ["detector-failure", "silent-in-both-states", "fixture-unrepresentative",
           "overclaim", "dependency-blocked"]
F_XV = ["vendor-rail-unavailable", "source-unavailable", "version-skew", "overclaim",
        "single-signal-only"]
F_GATED = ["owner-blocked", "legal-blocked", "source-unavailable", "overclaim",
           "policy-violation-averted"]

DEP_BASE = ["RES-0001", "RES-0002", "RES-0003"]
DEP_LOCAL = ["RES-0001", "B02"]
DEP_PAPER = ["RES-0001", "RES-0002"]

# ================================================================= THE UNIT TABLE
# (n, title, question, inputs_extra, deps, role, vendor, model, tools, substrate,
#  timeout, out_schema, evidence, tests[], reviewer, retry, failcls, owner, postcond)
U = []


def u(n, title, q, inputs, deps, role, vendor, model, tools, subst, timeout, schema,
      evidence, tests, reviewer, retry, fail, owner, postcond):
    U.append(dict(n=n, title=title, q=q, inputs=inputs, deps=deps, role=role, vendor=vendor,
                  model=model, tools=tools, subst=subst, timeout=timeout, schema=schema,
                  evidence=evidence, tests=tests, reviewer=reviewer, retry=retry, fail=fail,
                  owner=owner, postcond=postcond))


EV_TWO_RAIL = ("every claim carries TWO mechanically independent rails (the 05-ECO R1/R2 pattern: a "
               "structured API probe AND a prose source), each with a permalink, a fetch timestamp, "
               "an HTTP status and a sha256 of the captured bytes; a claim with one rail is graded "
               "E3 and may not be cited as measured fact")
EV_VERSIONED = ("every claim is pinned to an exact version/commit SHA and a fetch timestamp; an "
                "unversioned claim about a moving surface is a defect, not a finding "
                "(05-ECO section 6: the 2026-07-20 star/push snapshot decayed on write)")
EV_LOCAL2 = ("two mechanically independent local signals per claim - different shell, different data "
             "field, or different measurement - never the same probe re-run "
             "(rules/common/single-signal-verification.md)")
EV_BOTH = ("each emitted detector ships its known-good AND known-broken fixture inline, with the "
           "recorded output of both runs; a probe silent in both states measures nothing")
EV_PAPER = ("each mechanism cites the paper DOI/arXiv id, the exact section or figure the number "
            "comes from, the reported effect size AND the reported baseline; a headline number "
            "without its baseline is recorded as E3 and cannot promote a mechanism")
EV_INDEP = ("independence of sources is asserted explicitly, not assumed: sources sharing one "
            "upstream primitive count as ONE signal (05-ECO section 6 - npm/PyPI/Homebrew signing "
            "share one OIDC primitive and are one data point)")

# ---------------------------------------------------------- A. substrate & method
u(1, "Author the shared research claim-record and source-lineage schema family",
  "What is the minimal typed record that makes a Phase-2 research claim independently re-checkable "
  "(claim id, canonical mechanism, source lineage, evidence tier E1-E4, confidence band, named "
  "settling probe, contradiction/support edges, freshness stamp, snapshot sha256) - and does a "
  "round-trip test prove that deleting ANY single field breaks at least one named downstream "
  "consumer (Phase-1 dedup, Phase-4 contract authoring, Phase-12 refutation)?",
  [CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md (E1-E4 ledger, section 6)",
   "command-center/WORK-UNIT-CATALOG.json#contract",
   "_USER-PROMPTS.md:10662-10679 (Phase 1 canonical record fields)"],
  ["B01"], "schema-author", "anthropic", "opus", T_PROTO, "worktree-isolated", 2700, S_META,
  "the field list is justified field-by-field against a named consumer; a field nobody consumes is "
  "deleted, and the deletion test is recorded as the evidence",
  ["round-trip: serialize 10 real claims lifted from 05-ECO, validate, re-load, assert byte-stable",
   "field-necessity mutation: delete each field in turn and assert at least one consumer test goes red",
   "negative control: a record missing source_lineage must FAIL validation (not warn)"],
  RV_SELF, RT_PROTO, F_PROTO, False,
  "the 8 schema files exist under command-center/schema/ AND a fixture claim validates green while "
  "a source_lineage-stripped copy of the same claim validates RED")

u(2, "Operationalize the E1-E4 evidence-tier ledger as a mechanical classifier",
  "Can the shard's four-tier evidence ledger (E1 verbatim / E2 multi-source / E3 single source / "
  "E4 degraded-fetch where the fetcher INFERRED rather than extracted, hedge words being the tell) "
  "be turned into a mechanical grader whose output agrees with the shard author's own grading on a "
  "40-row held-out sample at Cohen kappa >= 0.6?",
  [SHARDS + "/05-ECO-frontier-orchestration.md:11 (the E1-E4 ledger)",
   "RES-0001 claim-record schema"],
  ["RES-0001", "RES-0006"], "measurement-engineer", "anthropic", "opus", T_PROTO,
  "worktree-isolated", 2700, S_MEAS,
  EV_BOTH + "; the kappa is computed, printed and stored, not asserted",
  ["kappa computed against a 40-row hand-labelled held-out set drawn from 05-ECO shards",
   "adversarial fixture: an E1-quality claim padded with hedge words must NOT be demoted to E4",
   "adversarial fixture: an E4 inference written confidently must still be caught (hedge words are "
   "a tell, not the definition)"],
  RV_TWO, RT_PROTO, F_PROTO, False,
  "a printed confusion matrix and a kappa >= 0.6 recorded with the 40 labelled rows attached")

u(3, "Build the content-addressed evidence snapshot and 30-day re-check substrate",
  "Can every cited external source be captured as (URL, final URL after redirects, HTTP status, "
  "fetch timestamp, sha256 of body, archived copy) such that a re-check 30 days later "
  "mechanically distinguishes SOURCE-CHANGED from CLAIM-WAS-WRONG - and does it correctly record "
  "the known 301 chain docs.claude.com/en/docs/claude-code/* -> code.claude.com/docs/en/*?",
  [CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:146 (observed HTTP 301)",
   "RES-0001 claim-record schema"],
  ["RES-0001", "RES-0006"], "measurement-engineer", "anthropic", "opus",
  T_PROTO + ["WebFetch", "Bash(curl)"], "local-serialized", 2700, S_MEAS,
  "the substrate is proven on 3 real URLs of different shapes (a 301 chain, a JS-rendered page, a "
  "raw file), with the stored sha256 re-hashed in the same run",
  ["re-check control: mutate a stored snapshot byte and assert the re-checker reports CHANGED",
   "re-check control: unchanged source must report UNCHANGED, not CHANGED (no false positive)",
   "redirect capture: the recorded final URL for a docs.claude.com path is a code.claude.com URL"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a snapshot store exists whose every entry re-hashes to its recorded sha256 in a fresh process")

u(4, "Define and validate the contradiction / support edge model for research claims",
  "What edge types are required to represent two sources disagreeing - direct contradiction, scope "
  "mismatch, version skew, measurement artifact, independence collapse - and does the model "
  "classify 30 real disagreement pairs harvested from the 05-ECO shards with an 'other' residual "
  "below 10%?",
  [SHARDS + "/05-ECO-workflow-sources.md (R1 caught R2 in five errors)",
   "RES-0001 claim-record schema"],
  ["RES-0001"], "contradiction-hunter", "anthropic", "opus", T_PROTO, "worktree-isolated", 1800,
  S_CLAIM,
  "each of the 30 pairs is cited to both of its sources; the five R1-vs-R2 errors are included as "
  "gold pairs because their ground truth is already settled",
  ["all five known R1/R2 ownership-redirect disagreements classify as version-skew/stale-pointer",
   "residual 'other' bucket measured and reported, must be < 10% of 30 pairs",
   "negative control: two claims about DIFFERENT subjects must not be linked by any edge"],
  RV_ADV, RT_PROTO, F_PROTO, False,
  "an edge-typed graph over 30 pairs with a printed residual rate and the five gold pairs correct")

u(5, "Measure per-source-class freshness half-life and set revalidation triggers",
  "What is the observed change frequency of 50 tracked sources across the 16 spec source classes, "
  "and what per-class half-life makes a stored claim require revalidation before it may gate a "
  "decision - given that the 05-ECO star/push figures were a 2026-07-20 snapshot that decayed on "
  "write?",
  [SHARDS + "/05-ECO-workflow-sources.md (2026-07-20 snapshot)",
   "RES-0003 snapshot store"],
  ["RES-0003"], "measurement-engineer", "anthropic", "opus", T_WEB + ["Bash(python)"],
  "local-parallel", 3600, S_MEAS,
  EV_VERSIONED + "; the half-life is measured from repeated snapshots, never assumed from a "
  "source's reputation",
  ["the tracker re-fetches all 50 sources twice at a >=24h interval and reports per-class churn",
   "control: a deliberately static source (an archived tag) must show zero churn"],
  RV_MEAS, RT_QUOTA, F_WEB, False,
  "a per-class half-life table backed by >=2 timestamped snapshots per tracked source")

u(6, "Settle the tool-sentinel detector inversion that corrupts every fetch-based unit",
  "05-ECO section 6 records that a downstream reader who trusted the tool-sentinel would have "
  "discarded good evidence, and names the probe: does the tool-sentinel PostToolUse hook report "
  "FAILED (exit code 200) only for WebFetch, or does it also fire for WebSearch and Read in the "
  "same session - i.e. is the inversion WebFetch-specific or general?",
  ["~/.claude/hooks (live tool-sentinel implementation)",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:183-188 (the named probe)"],
  ["B02"], "detector-auditor", "anthropic", "opus", T_LOCAL, "local-serialized", 900, S_MEAS,
  EV_LOCAL2 + "; the hook SOURCE is read as one signal and a live triggered run is the second - "
  "reading the code alone does not settle it",
  ["run WebSearch, Read and WebFetch in one session and record the sentinel verdict for each",
   "both-states control: force a genuinely failing fetch (HTTP 404) and confirm the sentinel also "
   "reports FAILED there - if it reports FAILED in both states it measures nothing",
   "read the hook source and locate the exit-code comparison that produces the inversion"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a recorded verdict per tool type PLUS the file:line of the comparison that maps HTTP 200 to "
  "FAILED, or an explicit REFUTED if no such line exists")

# ------------------------------------------- B. Claude Code / Anthropic ground truth
u(7, "Extract the CURRENT plugin.json schema and its unknown-field strictness, versioned",
  "What are the exact required and optional fields of plugin.json at the currently shipped client "
  "version, and is the measured behaviour on an unrecognised TOP-LEVEL field a warning (Claude) "
  "while Codex's HooksFile is serde(deny_unknown_fields) - i.e. does the asymmetry recorded in "
  "05-ECO-plugin-specs still hold on today's builds?",
  [SHARDS + "/05-ECO-plugin-specs.md:10 (eight packaging findings)",
   "code.claude.com/docs/en/* plugin reference", "the installed client"],
  DEP_BASE, "platform-cartographer", "anthropic", "opus", T_MIX, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the doc rail and a shipped-client behavioural rail must agree or the "
  "disagreement itself is the finding",
  ["feed a manifest with one unknown top-level key to the real validator and record the verdict",
   "both-states control: a manifest with a MISSING required key must be rejected"],
  RV_XV, RT_STD, F_CODE, False,
  "a field table pinned to a client version string plus the verbatim validator output for the "
  "unknown-field and missing-field cases")

u(8, "Extract the marketplace.json schema and the plugin-vs-marketplace precedence rule",
  "What is the exact marketplace.json schema today, and does plugin.json still silently WIN over "
  "the marketplace entry for the version field - the trap that makes commits without a version "
  "bump ship nothing while both files pin 0.2.0?",
  [SHARDS + "/05-ECO-plugin-specs.md:139-141 (version pins the plugin)",
   ".claude-plugin/marketplace.json in this repo"],
  DEP_BASE, "platform-cartographer", "anthropic", "opus", T_MIX, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["construct a fixture where plugin.json and marketplace.json disagree on version and observe "
   "which one the client honours",
   "negative control: identical versions must produce no precedence signal at all"],
  RV_ADV, RT_STD, F_CODE, False,
  "a precedence verdict backed by a reproducible two-file fixture and the observed installed version")

u(9, "Map the hook contract: event names, payload shape, exit-code semantics, timeouts",
  "For every hook event the current client supports, what is the exact stdin payload shape, what "
  "do exit codes 0/1/2 mean, how is additionalContext delivered, and what happens on timeout - "
  "measured against the shipped client rather than read from docs alone?",
  ["~/.claude/hooks/_dispatch/manifest.json", "code.claude.com/docs/en/* hooks reference"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL + ["WebFetch"],
  "local-serialized", 3600, S_CLAIM,
  EV_LOCAL2 + "; each event's payload is captured verbatim from a real firing, not paraphrased",
  ["fire each supported event once with a logging hook and store the raw payload",
   "exit-2 control: confirm a blocking exit actually blocks, and that exit 0 with additionalContext "
   "actually injects",
   "timeout control: a deliberately slow hook must show the documented timeout behaviour"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "one captured raw payload per supported event plus an observed block/inject/timeout transcript")

u(10, "Measure skill loading: frontmatter fields, paths: lazy-load semantics, injection budget",
  "Which skill frontmatter fields does the current client actually read, and is it CONFIRMED that "
  "a rule/skill with NO paths: frontmatter is injected at turn 0 while one WITH paths: loads "
  "lazily on a matching touch - the inverse of the assumption that cost this estate a wrong "
  "'arming' change?",
  ["~/.claude/skills", "~/.agents/skills",
   "rules/common/single-signal-verification.md (the 2026-08-07 frontmatter row)"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL, "local-serialized", 2700,
  S_MEAS,
  EV_LOCAL2 + "; a direct instrument reading (what the client reports as loaded) outranks any "
  "inference about what it 'should' load",
  ["install two fixture skills - one with paths:, one without - and record which is present at turn 0",
   "both-states control: touching a matching path must load the paths:-scoped one and only then"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a loaded/not-loaded observation per fixture at turn 0 and after a matching touch")

u(11, "Map the agent and slash-command definition contracts and their tool-restriction surface",
  "What frontmatter keys do agent (.md) and command definitions support today, how is a subagent's "
  "model chosen, and can a definition genuinely RESTRICT the tool set a subagent receives - or is "
  "the restriction advisory?",
  ["~/.claude/agents", "~/.claude/commands", "code.claude.com/docs/en/* subagents reference"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL + ["WebFetch"],
  "local-serialized", 2700, S_CLAIM,
  EV_LOCAL2,
  ["spawn a fixture subagent with a restricted tool list and have it attempt a forbidden tool",
   "negative control: an unrestricted subagent must succeed at the same call"],
  RV_ADV, RT_LOCAL, F_LOCAL, False,
  "a transcript showing the forbidden call refused for the restricted agent and allowed for the "
  "unrestricted one")

u(12, "Resolve settings precedence across enterprise/user/project/local scopes",
  "For each settings key this program depends on (enabledPlugins, disabledMcpServers, hooks, "
  "permissions, model), which FILE at which scope actually wins - given the measured trap that "
  "disabledMcpServers at the root of ~/.claude.json was inert while the real map lived per-project, "
  "and enabledPlugins lives in ~/.claude/settings.json not ~/.claude.json?",
  ["~/.claude/settings.json", "~/.claude.json",
   "rules/common/single-signal-verification.md (the right-key-wrong-file rows)"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL, "local-serialized", 3600,
  S_MATRIX,
  EV_LOCAL2 + "; a key's presence in a file is NOT evidence it is honoured - the second signal "
  "must be an observed behaviour change",
  ["set the same key at two scopes with conflicting values and observe which takes effect",
   "inertness control: a key placed at a scope believed inert must produce NO behaviour change"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a per-key winning-scope table where every row cites an observed behaviour delta, not a file read")

u(13, "Archaeology of every breaking change to the plugin/skill/hook/MCP surfaces",
  "Across the client's published release notes, which exact version introduced each breaking or "
  "silently-behaviour-changing modification to the plugin, skill, hook or MCP surface, and which "
  "of those changes is this repo still coded against?",
  ["client CHANGELOG / release notes", "this repo's plugin and hook sources"],
  DEP_BASE, "changelog-archaeologist", "anthropic", "opus", T_ISSUES, "local-parallel", 3600,
  S_REG,
  EV_VERSIONED + "; every entry names the version that introduced it AND the version that shipped "
  "the fix, if any",
  ["spot-check 5 recorded changes against the actual diff or the shipped artifact",
   "coverage control: the extractor must find a deliberately seeded known breaking change"],
  RV_XV, RT_STD, F_CODE, False,
  "a version-indexed breaking-change register where >=5 rows are corroborated by a second artifact")

u(14, "Mine the client issue tracker for plugin-loading, hook-inert and marketplace-install defects",
  "What open and recently-closed issues describe a plugin appearing installed while its hooks are "
  "unloaded, a marketplace install failing silently, or a skill present on disk but absent from the "
  "loaded set - and which of them match a failure this program has already measured locally?",
  ["public issue tracker for the client",
   CORPUS + "/14-NO-REGRESSION-CONTRACT.md (locally measured failure classes)"],
  DEP_BASE, "defect-archaeologist", "anthropic", "opus", T_ISSUES, "local-parallel", 3600, S_REG,
  EV_TWO_RAIL + "; a matched issue must quote the upstream reproduction AND the local one, and say "
  "explicitly whether they are the same mechanism or merely the same symptom",
  ["for each match, state the discriminating observation that would separate same-mechanism from "
   "same-symptom",
   "detector control: the search must retrieve a known-present issue seeded by the operator"],
  RV_ADV, RT_STD, F_CODE, False,
  "a matched-issue table where each row carries a discriminating observation, not just a keyword hit")

u(15, "Map the headless/SDK surface: programmatic invocation, stream-json control channel, modes",
  "What is the exact non-interactive surface today - flags, stream-json control_request channel, "
  "permission modes, output schemas - and which of it is stable enough for this program's "
  "distributed runner to depend on?",
  ["client CLI --help output", "code.claude.com/docs/en/* SDK/headless reference",
   "reference_mcp_live_control_proven_2026-07-18 (control_request channel, prior estate finding)"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL + ["WebFetch"],
  "local-serialized", 3600, S_CLAIM,
  EV_LOCAL2 + "; a documented flag that the installed binary does not accept is recorded as a "
  "doc-vs-binary contradiction, not as a capability",
  ["every documented flag is executed once against the installed binary and its acceptance recorded",
   "negative control: an invented flag must be rejected, proving the acceptance test discriminates"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a flag-by-flag accepted/rejected table produced by running the installed binary")

u(16, "Measure subagent/Task semantics: nesting depth, tool and permission inheritance, concurrency",
  "How deep can subagents nest before the runtime refuses, do subagents inherit the parent's "
  "permission mode (the estate finding says they do NOT and it must be passed explicitly), and "
  "what is the observed concurrency ceiling for parallel spawns?",
  ["reference_bypass_permissions_and_subagent_mode (prior estate finding)",
   "the installed client"],
  DEP_LOCAL, "measurement-engineer", "anthropic", "opus", T_LOCAL, "local-serialized", 3600, S_MEAS,
  EV_LOCAL2 + "; the concurrency ceiling is measured by escalating spawn counts until refusal, and "
  "the refusal message is captured verbatim",
  ["nest subagents until refusal and record the depth and the exact error",
   "inheritance control: spawn one subagent WITHOUT an explicit mode and one WITH, and compare",
   "concurrency: record the spawn count at first refusal, repeated twice to exclude a transient"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a measured depth limit, an inheritance verdict backed by two contrasting spawns, and a "
  "twice-reproduced concurrency ceiling")

u(17, "Measure what actually consumes the context window (skills, MCP schemas, rules, tools)",
  "In bytes and tokens, what does each capability class contribute to the turn-0 context of a real "
  "session on this box, and which class dominates - measured with the client's own accounting "
  "rather than inferred from file sizes?",
  ["~/.claude/skills", "~/.mcp.json", "~/.claude/rules", "a live session's own usage report"],
  DEP_LOCAL, "measurement-engineer", "anthropic", "opus", T_LOCAL, "local-serialized", 3600, S_MEAS,
  EV_LOCAL2 + "; cumulative token totals must not be used as an occupancy numerator - the estate "
  "has already burned one wrong restart on exactly that confusion",
  ["ablate one capability class, re-measure, and attribute the delta",
   "control: re-measure with no change and confirm the measurement is stable within tolerance"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a per-class byte and token attribution where at least one class is confirmed by an "
  "ablate-and-remeasure delta")

u(18, "Map the plugin install/update/repair/rollback/uninstall lifecycle to on-disk state",
  "For each lifecycle command, exactly which files and settings keys are created, mutated or "
  "removed - and does uninstall leave orphaned state that a subsequent install would silently "
  "inherit?",
  [CORPUS + "/03-PLUGIN-LIFECYCLE-MAP.md", "a throwaway --settings home"],
  ["RES-0001", "RES-0007", "RES-0008"], "lifecycle-cartographer", "anthropic", "opus", T_LOCAL,
  "local-serialized", 5400, S_MATRIX,
  EV_LOCAL2 + "; every mutation is proven by a before/after filesystem diff of a THROWAWAY profile, "
  "never the live profile",
  ["full-cycle diff: install -> update -> rollback -> uninstall, diffing the profile at each step",
   "orphan control: after uninstall, a fresh install must not inherit any prior-state marker",
   "the throwaway profile must be proven isolated from the live one before the first command"],
  RV_MEAS, RT_LOCAL, F_LOCAL + ["live-profile-contamination-averted"], False,
  "a per-command filesystem diff from a provably isolated throwaway profile plus an orphan verdict")

u(19, "Settle the 136-inert-skills inference by installing into a throwaway profile and counting",
  "The 05-ECO author banded the 136-inert inference at very likely 80-90% and explicitly labelled "
  "it spec-derived, NOT install-observed - so: does installing this plugin into a throwaway "
  "--settings home load 110 skills (confirming replace-semantics and the inference) or 222 "
  "(refuting it)?",
  [SHARDS + "/05-ECO-marketplace-teardown.md:17 (222/110/136/24)",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:67-70 (the named settling probe)"],
  ["RES-0018"], "independent-reproducer", "openai", "codex-cli", T_LOCAL, "local-serialized", 3600,
  S_MEAS,
  "the count comes from the client's own loaded-skill report inside the throwaway profile, plus a "
  "filesystem count as the mechanically different second signal; the two numbers are reported "
  "separately even when they agree",
  ["count loaded skills in the throwaway profile and compare against 110 and 222",
   "detector control: add one uniquely-named fixture skill and confirm the counter sees it",
   "isolation control: the live profile's loaded-skill count must be unchanged after the test"],
  RV_MEAS, RT_XV, F_XV + ["live-profile-contamination-averted"], False,
  "an observed integer skill count from a throwaway profile with the fixture skill visible in the "
  "listing, and an explicit CONFIRMED or REFUTED against the 110/222 fork")

u(20, "Determine what a plugin/MCP install actually sends off the box (telemetry and privacy)",
  "What network egress does installing and running a plugin or MCP server produce on this client, "
  "to which endpoints, carrying what fields - measured at the socket, not read from a privacy page?",
  ["the installed client", "vendor privacy documentation"],
  DEP_LOCAL, "privacy-analyst", "anthropic", "opus",
  T_LOCAL + ["Bash(netstat)", "Bash(pktmon or equivalent)"], "local-serialized", 3600, S_CLAIM,
  EV_LOCAL2 + "; a documented privacy claim and an observed connection are two rails and both are "
  "reported, including where they disagree; no captured payload is stored verbatim if it could "
  "carry a credential",
  ["capture endpoints during install with and without telemetry-disabling settings and diff",
   "control: a known-offline operation must produce zero new endpoints"],
  RV_SEC, RT_LOCAL, F_LOCAL + ["credential-redaction-required"], False,
  "an endpoint list with a with/without-telemetry diff and an explicit statement of which fields "
  "were observed versus merely documented")

u(21, "Inventory undocumented and beta surfaces observable in the shipped client",
  "Which environment variables, feature flags and hidden subcommands does the installed client "
  "actually honour that appear in no published documentation, and which of them would change this "
  "program's design if relied upon?",
  ["the installed client binary and its bundled resources"],
  DEP_LOCAL, "platform-cartographer", "anthropic", "opus", T_LOCAL, "local-serialized", 3600, S_REG,
  EV_LOCAL2 + "; a string found in a binary is ONE signal - a flag is only 'honoured' once an "
  "observed behaviour change corroborates it",
  ["for each candidate flag, run with and without it and record the behaviour delta",
   "negative control: an invented flag name must produce no delta, proving the test discriminates"],
  RV_ADV, RT_LOCAL, F_LOCAL, False,
  "a candidate list where every 'honoured' entry cites an observed behaviour delta and every "
  "unconfirmed entry is explicitly marked string-only")

u(22, "Hunt counterevidence: where the official documentation contradicts shipped behaviour",
  "For the 20 documentation statements this program most depends on, which are contradicted by the "
  "installed client's observed behaviour - and for each contradiction, is the doc stale, the "
  "behaviour a regression, or the reader wrong?",
  ["code.claude.com/docs/en/* pages cited by RES-0007..RES-0018",
   "the observations produced by RES-0007..RES-0018"],
  ["RES-0007", "RES-0009", "RES-0010", "RES-0012", "RES-0015"], "contradiction-hunter", "openai",
  "codex-cli", T_MIX + ["Bash", "PowerShell"], "local-serialized", 3600, S_CLAIM,
  "each contradiction cites the doc URL with its fetch sha256 AND the exact reproducing command "
  "with its output; the reproducer must not have read the sibling unit's conclusion first",
  ["each contradiction is reproduced from the raw doc and raw command, blind to the sibling's prose",
   "false-alarm control: at least 3 statements confirmed CONSISTENT, proving the hunt can say no"],
  RV_TWO, RT_XV, F_XV, False,
  "a contradiction table where every row carries a doc sha256 and a reproducing command, plus at "
  "least 3 explicitly consistent rows")

# ---------------------------------------------------- C. cross-vendor agent runtimes
u(23, "Map the OpenAI Codex CLI configuration, AGENTS.md and plugin surface, versioned",
  "What is the exact Codex CLI configuration surface today - config.toml keys, AGENTS.md "
  "resolution order, hooks file schema, .codex-plugin/plugin.json - and is HooksFile still "
  "serde(deny_unknown_fields) such that a stray $schema key silently unloads every hook?",
  [SHARDS + "/05-ECO-plugin-specs.md:298 (Codex CLI strict surface)",
   "the installed Codex CLI", "openai/codex source"],
  DEP_BASE, "platform-cartographer", "anthropic", "opus", T_CODE + ["Bash"], "local-serialized",
  3600, S_CLAIM,
  EV_TWO_RAIL + "; the deny_unknown_fields claim must be corroborated by the upstream source line "
  "AND by a live load of a manifest carrying an extra key",
  ["load a hooks file with one extra top-level key and record whether hooks load",
   "both-states control: the same file without the extra key must load hooks successfully"],
  RV_XV, RT_STD, F_CODE, False,
  "the upstream source line for the strictness attribute plus an observed loaded/unloaded pair")

u(24, "Map the Gemini CLI extension and GEMINI.md surface and test rail availability",
  "What is the Gemini CLI extension manifest and context-file surface, and is the Gemini rail "
  "actually available on this box (installed, authenticated) such that this program may assign work "
  "units to it - or must every Gemini-assigned unit fall back?",
  ["google-gemini/gemini-cli source and docs", "this box's PATH and config"],
  DEP_BASE, "platform-cartographer", "anthropic", "opus", T_CODE + ["Bash", "PowerShell"],
  "local-serialized", 2700, S_CLAIM,
  EV_LOCAL2 + "; availability is settled by Get-Command in PowerShell AND an invocation, never by "
  "`which` in Git Bash, which misses .cmd shims",
  ["probe availability in BOTH PowerShell and Git Bash and report both results",
   "negative control: probe a deliberately absent binary name to prove the detector can say no"],
  RV_MEAS, RT_LOCAL, F_LOCAL + ["vendor-rail-unavailable"], False,
  "a two-shell availability verdict plus, if present, a version string from an actual invocation")

u(25, "Teardown of the Cursor rules and agent-configuration surface",
  "What does Cursor's .cursor/rules (.mdc) and agent surface express that this program's rule "
  "system does not, and which of those expressive features is portable to a file-based rule loaded "
  "by a different client?",
  ["cursor documentation", "public .cursor/rules corpora on GitHub"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_MIX, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["sample 20 public rule files and classify which features are used in practice versus documented",
   "control: the sampler must report the count of files it could NOT parse rather than dropping them"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a feature table separating documented-from-used, with the unparsed-file count reported")

u(26, "Teardown of the GitHub Copilot coding-agent and CLI customization surface",
  "What customization contract does the Copilot coding agent expose (instructions files, allowed "
  "tools, MCP configuration, firewall policy), and which parts are enforced server-side and "
  "therefore not portable to a local runtime?",
  ["GitHub Copilot documentation", "public repositories using copilot-instructions"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_MIX, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL + "; a server-enforced control must be labelled as such - assuming it is portable is "
  "the specific error this unit exists to prevent",
  ["classify each control as client-side or server-enforced and justify each classification",
   "control: at least one control must be classified server-enforced or the classifier is suspect"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a control table with a client-vs-server enforcement column justified per row")

u(27, "Teardown of Continue.dev assistant blocks and its config composition model",
  "How does Continue compose an assistant from blocks (models, rules, prompts, MCP), and is its "
  "hub-and-block composition model a better fit for this program's marketplace than a monolithic "
  "plugin package?",
  ["continuedev/continue source and hub documentation"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["read the block schema from source, not only from docs, and cite the file:line",
   "control: identify at least one composition feature this program CANNOT adopt and say why"],
  RV_ADV, RT_STD, F_CODE, False,
  "a block-composition summary citing source file:line plus one named non-adoptable feature")

u(28, "Extract the Aider repo-map mechanism and its measured token/accuracy tradeoff",
  "How exactly does Aider build its repo map (graph ranking over symbol references, token budget), "
  "and what evidence exists that it improves edit accuracy versus simply sending more files?",
  ["Aider-AI/aider source", "Aider benchmark writeups"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_PAPER + "; a blog-reported improvement without a stated baseline is E3 and cannot promote the "
  "mechanism to Tier 1",
  ["cite the ranking implementation at file:line, not the blog description",
   "control: state explicitly whether any independent party has reproduced the improvement"],
  RV_ADV, RT_STD, F_CODE, False,
  "the ranking algorithm cited at source file:line plus an explicit reproduced/not-reproduced verdict")

u(29, "Teardown of OpenHands runtime isolation and its microagent trigger model",
  "How does OpenHands isolate execution (container runtime, action/observation loop) and how do its "
  "microagents get triggered - and is the trigger mechanism a better router than keyword matching?",
  ["All-Hands-AI/OpenHands source"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["cite the trigger evaluation code at file:line",
   "control: name one failure mode of the trigger model observed in its own issue tracker"],
  RV_ADV, RT_STD, F_CODE, False,
  "the trigger implementation cited at file:line plus one issue-tracker-sourced failure mode")

u(30, "Extract Goose recipes and its lead/worker failure-threshold escalation mechanism",
  "What exactly triggers Goose's lead-to-worker escalation, at what failure threshold, and is there "
  "evidence the escalation beats retrying the same worker - noting the repository moved from "
  "block/goose to a new owner and the old pointer is a silent-redirect dependency?",
  [SHARDS + "/05-ECO-workflow-sources.md (block/goose -> aaif-goose/goose redirect)",
   "the current Goose repository"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the repository's CURRENT canonical location is resolved and recorded before any "
  "line is cited, because the old pointer is a redirect that can drop",
  ["resolve the canonical repo URL and record the redirect chain before citing",
   "cite the escalation threshold at source file:line",
   "control: state whether the threshold is configurable or hard-coded"],
  RV_ADV, RT_STD, F_CODE + ["repo-renamed-or-redirected"], False,
  "the resolved canonical URL with its redirect chain plus the escalation threshold at file:line")

u(31, "Survey the Cline/Roo/Windsurf rule and MCP surfaces for portable primitives",
  "Across Cline, Roo Code and Windsurf, which rule/memory/MCP primitives appear in ALL THREE - and "
  "is that intersection the real portable core for a cross-vendor adapter, as opposed to the union "
  "each vendor advertises?",
  ["Cline, Roo Code and Windsurf documentation and sources"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_MIX, "local-parallel", 3600, S_MATRIX,
  EV_TWO_RAIL + "; the intersection is computed mechanically from three feature lists, not eyeballed",
  ["compute the three-way intersection with a script and print it",
   "control: the script must also print the per-vendor unique sets so the intersection can be audited"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a printed three-way intersection plus the three unique-feature sets it was derived from")

u(32, "Determine which hosted-agent platforms expose a contract stable enough to adapt to",
  "For hosted agents (Devin-class, Factory-class, Copilot Workspace-class), which expose a public, "
  "versioned API or artifact contract that a cross-vendor adapter could target - and which are "
  "UI-only and therefore out of scope regardless of capability?",
  ["public API documentation for hosted agent platforms"],
  DEP_BASE, "ecosystem-cartographer", "anthropic", "opus", T_WEB, "cloud-batch", 2700, S_MATRIX,
  EV_VERSIONED,
  ["classify each platform as public-versioned-API / private-API / UI-only with a citation each",
   "control: at least one platform must land in UI-only or the classifier is not discriminating"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a platform classification table with one citation per row and at least one UI-only verdict")

u(33, "Compute the cross-vendor primitive intersection that a portable work unit may rely on",
  "Given the per-vendor surfaces mapped by RES-0023..RES-0032, what is the exact set of primitives "
  "present in EVERY supported vendor (the portable core), and what is the size of that set relative "
  "to the union - the number that decides whether a cross-vendor adapter is worth building?",
  ["outputs of RES-0023 through RES-0032"],
  ["RES-0023", "RES-0024", "RES-0026", "RES-0031", "RES-0032"], "adapter-architect", "anthropic",
  "opus", T_PROTO, "worktree-isolated", 2700, S_MATRIX,
  "the intersection is COMPUTED by set operations over the sibling outputs and the script is "
  "included; an eyeballed intersection is rejected because mechanical questions get mechanical "
  "answers (rules/common/fan-out-contract.md C4)",
  ["set-intersection computed by script over the sibling JSON outputs",
   "control: a deliberately vendor-unique primitive must NOT appear in the intersection"],
  RV_TWO, RT_PROTO, F_PROTO, False,
  "a computed intersection set with its cardinality and the ratio to the union, plus the script")

u(34, "Inventory the abstraction leaks where a portable work unit demonstrably cannot be portable",
  "Which specific capabilities differ so much between vendors that pretending interchangeability "
  "would silently corrupt a result - and for each, what is the loud-degradation behaviour the "
  "adapter must implement instead (_USER-PROMPTS.md:10983)?",
  ["outputs of RES-0033", "_USER-PROMPTS.md:10965-10983 (Phase 9 requirements)"],
  ["RES-0033"], "adversarial-refuter", "openai", "codex-cli", T_MIX, "local-parallel", 3600, S_CLAIM,
  "each leak names a concrete task that produces a DIFFERENT correct-looking answer on two vendors, "
  "with both outputs captured; a leak asserted without a divergent pair is not a leak",
  ["for at least 3 leaks, run the same task on two rails and capture both outputs",
   "control: run one task expected to be genuinely portable and show the outputs agree"],
  RV_TWO, RT_XV, F_XV, False,
  "at least 3 captured divergent output pairs plus one captured agreeing pair as the control")

u(35, "Measure config-surface breakage velocity per vendor to price adapter maintenance",
  "How many breaking configuration-surface changes has each vendor shipped over the last 12 months, "
  "measured from their release notes - and what does that rate imply for the maintenance cost of "
  "each adapter this program might build?",
  ["release notes and changelogs for each supported vendor"],
  DEP_BASE, "measurement-engineer", "anthropic", "opus", T_ISSUES, "local-parallel", 3600, S_MEAS,
  EV_VERSIONED + "; 'breaking' is defined by a written rule applied uniformly before counting, not "
  "decided per entry after seeing it",
  ["publish the breaking-change definition BEFORE counting and apply it to all vendors identically",
   "control: two independent passes over one vendor's notes must produce counts within 10%"],
  RV_MEAS, RT_STD, F_CODE, False,
  "a per-vendor breaking-change count with the pre-registered definition and a two-pass agreement "
  "figure for at least one vendor")

# ------------------------------------------------------- D. MCP ecosystem + security
u(36, "Diff the MCP specification revisions and identify what is optional versus mandatory",
  "Between the MCP protocol revisions currently in the wild, which capabilities became mandatory, "
  "which remain optional, and which clients implement which revision - the matrix that decides what "
  "an MCP adapter may assume?",
  ["modelcontextprotocol specification repository and its revision history"],
  DEP_BASE, "protocol-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_MATRIX,
  EV_VERSIONED + "; every cell cites the spec revision identifier, and a client's claimed support is "
  "separated from its observed support",
  ["build the revision-by-capability matrix from the spec source, citing revision ids",
   "control: at least one capability must be marked optional-and-unimplemented somewhere"],
  RV_ADV, RT_STD, F_CODE, False,
  "a revision-by-capability matrix where every cell cites a spec revision id")

u(37, "Measure the per-session process cost of stdio versus HTTP MCP transports on this box",
  "How many OS processes does one session spawn per stdio MCP server versus one shared HTTP server, "
  "and does the measured multiplication reproduce the estate's recorded commit-exhaustion driver "
  "(sessions x servers) on today's fleet?",
  ["~/.mcp.json and the live process table",
   "reference_commit_exhaustion_root_cause_2026-07-19 (prior estate measurement)"],
  DEP_LOCAL, "measurement-engineer", "anthropic", "opus", T_LOCAL, "local-serialized", 3600, S_MEAS,
  EV_LOCAL2 + "; the process count is read from the OS process table AND from a per-server handle "
  "count, and a probe must not match its own command line (a self-matching probe reported a dead "
  "session as ACTIVE on this estate)",
  ["count processes with a pattern proven NOT to match the probe's own command line",
   "control: start and stop one known server and confirm the count moves by the expected delta"],
  RV_MEAS, RT_LOCAL, F_LOCAL + ["self-matching-probe"], False,
  "a per-transport process count with a start/stop delta control and a stated proof the probe does "
  "not match itself")

u(38, "Teardown the official MCP registry: schema, publish flow and the trust signals it exposes",
  "What metadata does the official MCP registry require and expose, what does its publish flow "
  "verify, and which of its trust signals are actually verifiable by a client at install time "
  "rather than merely displayed?",
  ["the official MCP registry specification and API"],
  DEP_BASE, "registry-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_REG,
  EV_TWO_RAIL + "; a displayed badge is not a verifiable signal unless a client can recompute it",
  ["separate signals into client-verifiable and display-only, with a justification per signal",
   "control: attempt to recompute at least one claimed-verifiable signal end to end"],
  RV_SEC, RT_STD, F_CODE, False,
  "a signal table split into client-verifiable and display-only with one signal actually recomputed")

u(39, "Catalogue MCP-specific attack classes and the mitigations that survive an attempted bypass",
  "What are the demonstrated MCP attack classes (tool poisoning, description injection, confused "
  "deputy, rug-pull update, cross-server shadowing), and for each proposed mitigation, can a "
  "reviewer construct a bypass - the test that separates a real control from a comfort blanket?",
  ["published MCP security research and advisories", "this program's threat surface"],
  DEP_BASE, "security-researcher", "anthropic", "opus", T_SEC, "local-parallel", 3600, S_THREAT,
  EV_TWO_RAIL + "; every attack class cites a public write-up AND a concrete instantiation against "
  "THIS program's surface; no exploit is executed against any third-party system",
  ["for each mitigation, record an attempted bypass and its outcome",
   "control: at least one mitigation must survive the bypass attempt, or the attempts are not honest"],
  RV_SEC, RT_STD, F_SEC, False,
  "an attack-class table where every mitigation row carries an attempted-bypass outcome")

u(40, "Compare MCP permission and consent models across the clients this program supports",
  "How does each supported client gate an MCP tool call (per-call prompt, allowlist, trust-on-first-"
  "use, none), and which model can express the least-privilege tool_permissions this catalog "
  "assigns to its own work units?",
  ["client documentation and settings schemas for each supported client"],
  ["RES-0012", "RES-0036"], "permission-analyst", "anthropic", "opus", T_MIX, "local-parallel",
  2700, S_MATRIX,
  EV_TWO_RAIL + "; a permission model is only 'expressive enough' if a concrete tool_permissions "
  "list from this very catalog can be encoded in it, and the encoding is shown",
  ["encode one real tool_permissions list from this slice in each client's model, or show it cannot be",
   "control: an intentionally over-broad list must be encodable everywhere, proving the test is not "
   "trivially failing"],
  RV_ADV, RT_STD, F_CODE, False,
  "a per-client encoding attempt for one real tool_permissions list with an explicit can/cannot verdict")

u(41, "Measure the token cost of MCP tool schemas across the installed fleet",
  "How many tokens does each installed MCP server's tool schema set add to a turn, which servers "
  "dominate, and what is the measured cost of the deferred-tool mechanism versus eager exposure?",
  ["~/.mcp.json", "the live client's tool inventory"],
  ["RES-0017"], "measurement-engineer", "anthropic", "opus", T_LOCAL, "local-serialized", 2700,
  S_MEAS,
  EV_LOCAL2 + "; tokens are counted with a tokenizer, not estimated from characters",
  ["count tokens per server schema set and rank; publish the tokenizer and its version",
   "control: disable one server and confirm the measured total drops by that server's share"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a ranked per-server token table plus a disable-and-remeasure delta matching the predicted drop")

u(42, "Census the maintenance state of every MCP server installed on this box",
  "For each installed MCP server, when was its upstream last released, is its repository archived or "
  "renamed, does it still resolve, and which installed servers are effectively abandoned dependencies?",
  ["~/.mcp.json", "upstream repositories for each installed server"],
  ["RES-0003"], "ecosystem-cartographer", "anthropic", "opus", T_CODE + ["Read"], "local-parallel",
  3600, S_REG,
  EV_VERSIONED + "; last-release dates are snapshot-dated on write because they decay, and a "
  "redirect is recorded as a redirect rather than followed silently",
  ["resolve every upstream URL and record the redirect chain and final status code",
   "control: a deliberately invalid URL must be reported unresolvable rather than skipped"],
  RV_ADV, RT_QUOTA, F_CODE + ["repo-renamed-or-redirected"], False,
  "a per-server row carrying final URL, HTTP status, last release date and a snapshot timestamp")

u(43, "Determine real-world adoption of MCP sampling, elicitation and roots versus their spec status",
  "The spec defines sampling, elicitation and roots - how many real servers and clients implement "
  "each, and is any of them adoptable by this program today or must it be treated as aspirational?",
  ["MCP specification", "a sampled set of public MCP servers and clients"],
  ["RES-0036"], "protocol-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; an implementation is counted only when the capability is found in code, not when "
  "a README mentions it",
  ["grep a sampled server corpus for the capability handlers and count code-level hits",
   "control: report the sample size and the README-mentions-but-no-code count separately"],
  RV_ADV, RT_STD, F_CODE, False,
  "a per-capability code-level adoption count with the sample size and the README-only count stated")

u(44, "Map the remote-MCP authorization profile and which clients actually implement it",
  "What does the MCP authorization profile require of a remote server, which supported clients "
  "implement the full flow, and can this program consume a remote MCP without ever writing a "
  "credential into an artifact?",
  ["MCP authorization specification", "client implementations"],
  ["RES-0036"], "security-researcher", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the no-credential-in-artifact property is demonstrated by naming where the token "
  "lives at each step, not asserted; no live token value appears anywhere in the output",
  ["trace one full authorization flow and name the storage location at each hop",
   "control: confirm that a captured artifact from the flow contains no credential material"],
  RV_SEC, RT_STD, F_SEC + ["credential-redaction-required"], False,
  "a hop-by-hop token-location trace plus a scan result showing the artifact is credential-free")

u(45, "Decide whether a second agent protocol deserves adapter support alongside MCP",
  "Do the competing agent-interoperability protocols (A2A-class, agent-connect-class) expose any "
  "capability MCP cannot express, and is the marginal capability worth a second adapter - or is the "
  "honest answer that supporting one protocol well beats supporting two badly?",
  ["specifications for the competing protocols", "RES-0036 MCP capability matrix"],
  ["RES-0036"], "adapter-architect", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700,
  S_CLAIM,
  EV_TWO_RAIL + "; the recommendation must state the specific capability that would be lost by "
  "declining, or explicitly record that none was found",
  ["name at least one capability unique to each protocol, or record NONE-FOUND explicitly",
   "control: the analysis must produce a defensible NO answer if the evidence supports it"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a per-protocol unique-capability list (possibly empty and explicitly marked so) plus a "
  "reasoned adopt/decline recommendation")

u(46, "Survey MCP gateway, proxy and lazy-activation prior art for the fleet-bloat pathology",
  "Which existing MCP gateways or proxies solve per-session server multiplication and lazy tool "
  "activation, what does each cost operationally (a daemon is a liability with a self-healing tax), "
  "and does any of them beat the client's native deferred-tool mechanism?",
  ["public MCP gateway/proxy projects",
   SHARDS + "/05-ECO-frontier-orchestration.md (gateway federation, Tier 2 with modification)"],
  ["RES-0037"], "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; the 05-ECO call sheet already grades gateway federation Tier 2 'supervisor + "
  "degraded-mode fallback first' - this unit must either corroborate or refute that grade, not "
  "restate it",
  ["for each candidate, record whether it requires a persistent daemon and what happens when it dies",
   "control: compare against the native mechanism as the baseline, not against doing nothing"],
  RV_ADV, RT_STD, F_CODE, False,
  "a candidate table with a daemon-liability column and an explicit corroborate-or-refute verdict "
  "on the existing Tier-2 grade")

# -------------------------------------------------- E. marketplace / supply-chain trust
u(47, "Comparative teardown: which trust signals each mature package registry actually exposes",
  "Across npm, PyPI, crates.io, the VS Code Marketplace, JetBrains and the Chrome Web Store, which "
  "trust signals are (a) published, (b) machine-readable at install time, and (c) enforced at "
  "publish time - and which of the three columns is the one this program is missing?",
  [SHARDS + "/05-ECO-marketplace-teardown.md (six-axis teardown)"],
  DEP_BASE, "registry-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 5400, S_MATRIX,
  EV_INDEP + "; the teardown must not triple-count signals that share one upstream primitive",
  ["build the three-column matrix and mark shared-primitive signals as one",
   "control: state the number of signals collapsed by the shared-primitive rule"],
  RV_TWO, RT_QUOTA, F_WEB, False,
  "a six-registry three-column matrix with a stated count of collapsed shared-primitive signals")

u(48, "Assess keyless signing (Sigstore/cosign) applicability to a file-based plugin marketplace",
  "Can a marketplace whose packages are directories of markdown and scripts obtain a meaningful "
  "keyless signature, what exactly does the signature attest to, and what does it NOT prevent?",
  ["Sigstore documentation and reference implementations"],
  ["RES-0047"], "supply-chain-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the answer must state the attack the signature does NOT stop, because a control "
  "sold beyond its scope is worse than none",
  ["name at least two attacks the signature does not prevent",
   "control: verify one real signature end to end rather than describing the process"],
  RV_SEC, RT_STD, F_SEC, False,
  "one end-to-end verified signature transcript plus a named list of what it does not prevent")

u(49, "Determine the minimum viable SLSA/provenance level for this program's artifacts",
  "Which SLSA level can a single-owner, PR-only release process actually reach without a hosted "
  "builder, what evidence would prove the level, and is in-toto-shaped attestation on every agent "
  "artifact (Tier 1 in the call sheet) achievable with the existing CI?",
  ["SLSA specification", "in-toto specification", "this repo's CI workflows",
   SHARDS + "/05-ECO-frontier-orchestration.md:81-86 (Tier 1 attestation row)"],
  ["RES-0048"], "supply-chain-analyst", "anthropic", "opus", T_CODE + ["Read", "Grep"],
  "local-parallel", 3600, S_CLAIM,
  EV_TWO_RAIL + "; the achievable level is justified against THIS repo's actual CI configuration, "
  "cited at file:line, not against a generic pipeline",
  ["cite the specific CI capability that caps the achievable level",
   "control: state what would have to change to reach the next level"],
  RV_ADV, RT_STD, F_CODE, False,
  "a level verdict citing this repo's CI at file:line plus the named delta to the next level")

u(50, "Choose an SBOM format for a package whose payload is prompts and scripts, not compiled code",
  "Do SPDX and CycloneDX express anything meaningful about a package of markdown skills, shell "
  "hooks and Python tools - and if the components are not libraries, what is the SBOM actually "
  "protecting against here?",
  ["SPDX and CycloneDX specifications", "this repo's package contents"],
  ["RES-0049"], "supply-chain-analyst", "anthropic", "opus", T_CODE + ["Read"], "local-parallel",
  2700, S_CLAIM,
  EV_TWO_RAIL + "; the unit must answer the 'protecting against what' question explicitly, and a "
  "'because everyone does it' answer is recorded as no answer",
  ["generate a draft SBOM for this repo in the chosen format and inspect what it captured",
   "control: identify at least one real risk the SBOM does NOT capture for this payload type"],
  RV_ADV, RT_STD, F_CODE, False,
  "a generated draft SBOM plus a named risk it fails to capture")

u(51, "Compare vulnerability data sources for coverage and latency on this program's ecosystems",
  "For the ecosystems this program ships into (Python, Node, plus prompt/script payloads with no "
  "ecosystem at all), how do OSV, GHSA and NVD differ in coverage and disclosure latency - and what "
  "does 'zero open alerts' actually mean given a green scan decays as the advisory DB moves?",
  ["OSV, GHSA and NVD data and documentation", "this repo's dependency set"],
  ["RES-0047"], "security-researcher", "anthropic", "opus", T_SEC, "local-parallel", 3600, S_CLAIM,
  EV_VERSIONED + "; every scan result is stamped with the advisory-database snapshot date, because a "
  "stored green from last week is not a control for today",
  ["run the same scan against two dated advisory snapshots and report any verdict change",
   "control: seed one known-vulnerable dependency in a scratch manifest and confirm detection"],
  RV_SEC, RT_STD, F_SEC, False,
  "a two-snapshot scan comparison plus a positive detection on the seeded vulnerable fixture")

u(52, "Design a lockfile that is reproducible for a non-code package of prompts and scripts",
  "What must a lockfile record for a package whose contents are files rather than resolved library "
  "versions (content hashes, source commit, resolution order), and does a re-install from the "
  "lockfile reproduce a byte-identical tree on Windows given CRLF normalization?",
  ["lockfile designs from mature registries", "this repo's package layout",
   "rules/common/windows-shell.md section 8b (CRLF vs blob bytes)"],
  ["RES-0047"], "supply-chain-analyst", "anthropic", "opus", T_PROTO, "worktree-isolated", 3600,
  S_CLAIM,
  EV_BOTH + "; byte-identity is checked against the git BLOB via git cat-file, never via git "
  "archive, which returns CRLF on this box and would falsely fail the check",
  ["install twice from the same lockfile and compare trees hash by hash",
   "CRLF control: prove the comparison uses blob bytes by showing git archive and git cat-file differ",
   "negative control: mutate one file and confirm the comparison reports a mismatch"],
  RV_MEAS, RT_PROTO, F_PROTO + ["crlf-artifact"], False,
  "two installs whose per-file blob hashes match exactly, plus a demonstrated mismatch on mutation")

u(53, "Determine how registries actually revoke a bad package and what the client-side story is",
  "When a published package must be pulled, what does each mature registry actually do (yank, "
  "unpublish, deprecate, advisory) and what does an ALREADY-INSTALLED client see - the half of "
  "revocation that most designs forget?",
  ["registry revocation policies and incident write-ups"],
  ["RES-0047"], "registry-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700,
  S_CLAIM,
  EV_TWO_RAIL + "; the installed-client half must be answered separately from the registry half, "
  "and 'nothing happens' is a valid and important finding",
  ["for each registry, state explicitly what an installed client observes after a revocation",
   "control: cite at least one real revocation incident and what users experienced"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a per-registry revocation table with a separate installed-client column and one cited incident")

u(54, "Catalogue publisher-identity and namespace-squatting defenses that a one-owner registry can run",
  "Which identity and namespace defenses (scoped names, verified publishers, reserved prefixes, "
  "typo-distance blocking) are implementable by a single-owner marketplace with no review staff, "
  "and which fundamentally require human moderation?",
  ["registry identity policies", "typosquatting incident write-ups"],
  ["RES-0047"], "security-researcher", "anthropic", "opus", T_SEC, "local-parallel", 2700, S_THREAT,
  EV_TWO_RAIL + "; each defense is classified as automatable or moderation-dependent with a reason",
  ["classify every defense automatable vs moderation-dependent",
   "control: at least one must land in moderation-dependent or the classification is not honest"],
  RV_SEC, RT_STD, F_SEC, False,
  "a defense table with an automatable/moderation-dependent column and at least one of each")

u(55, "Reconstruct the exact bypass used in real malicious-extension incidents",
  "For a set of documented malicious extension and package incidents, what was the EXACT mechanism "
  "that got past review (obfuscated payload, post-install script, update-after-approval, dependency "
  "confusion) - and which of those mechanisms is possible against a prompt-payload marketplace?",
  ["public incident write-ups and vendor postmortems"],
  ["RES-0047"], "security-researcher", "openai", "codex-cli", T_SEC, "local-parallel", 3600,
  S_THREAT,
  EV_TWO_RAIL + "; each incident cites a primary source (vendor postmortem or researcher write-up), "
  "and applicability to a prompt payload is argued per incident rather than assumed",
  ["map each mechanism onto this program's payload type with an applicable/not-applicable verdict",
   "control: at least one mechanism must be genuinely not applicable, with the reason"],
  RV_SEC, RT_XV, F_SEC, False,
  "an incident table with primary-source citations and a per-incident applicability verdict")

u(56, "Determine whether a declarative permission manifest is enforceable when the payload is prompts",
  "Extension ecosystems enforce declared permissions at runtime because the payload is code - when "
  "the payload is a prompt or a rule that merely PERSUADES an agent, what does a declared permission "
  "actually constrain, and is the honest answer that only the tool layer can enforce anything?",
  ["extension permission models", "this program's skill/rule/hook payload types"],
  ["RES-0040", "RES-0054"], "permission-analyst", "anthropic", "opus", T_MIX, "local-parallel",
  3600, S_THREAT,
  EV_TWO_RAIL + "; the finding must distinguish what is ENFORCED from what is merely DECLARED, and "
  "an unenforceable declaration must be named as security theatre rather than a control",
  ["construct a prompt payload that violates its own declared permission and observe whether "
   "anything stops it",
   "control: the same violation attempted through the tool layer must be blocked"],
  RV_SEC, RT_STD, F_SEC, False,
  "a demonstrated prompt-layer violation that was not stopped, paired with the same violation "
  "blocked at the tool layer")

u(57, "Identify which quality-score signals are gameable and which resist gaming",
  "For OpenSSF Scorecard and registry quality scores, which individual checks can a publisher "
  "trivially satisfy without improving anything, and which resist gaming - the difference that "
  "decides whether a conformance score belongs in this marketplace?",
  ["OpenSSF Scorecard checks and registry scoring documentation"],
  ["RES-0047"], "adversarial-refuter", "openai", "codex-cli", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; for each gameable check the exact cheap action that satisfies it is named, "
  "because 'gameable' without the recipe is an unfalsifiable assertion",
  ["name the cheap satisfying action for every check graded gameable",
   "control: at least one check must be graded gaming-resistant with a reason"],
  RV_TWO, RT_XV, F_XV, False,
  "a per-check gameability grade where each gameable row carries its cheap-satisfaction recipe")

u(58, "Survey private mirror, federation and offline export/import designs for registries",
  "How do mature ecosystems support private mirrors, federated indexes and fully offline "
  "install/export - and which of those designs works when the index is a single JSON file in a git "
  "repository?",
  ["mirroring and federation designs from mature registries"],
  ["RES-0047"], "registry-analyst", "anthropic", "opus", T_WEB_BROAD, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["for each design, state whether it survives a git-file index and why",
   "control: identify one design that does NOT survive, with the failing property"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a design table with a survives-git-file-index verdict per row and at least one negative")

u(59, "Extract governance, moderation and dispute models that a single-owner marketplace must state",
  "What must a marketplace's published governance say (who may publish, how a dispute is raised, "
  "how a takedown is decided, what the appeal is) when there is exactly one owner and no committee "
  "- and which mature model degrades most gracefully to N=1?",
  ["governance documents of open registries and foundations"],
  ["RES-0053"], "governance-analyst", "anthropic", "opus", T_WEB_BROAD, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; each borrowed clause is cited to the source governance document it came from",
  ["produce the minimal clause set with a citation per clause",
   "control: name one clause that CANNOT be honoured at N=1 and must be omitted rather than faked"],
  RV_LEGAL, RT_QUOTA, F_LEGAL, False,
  "a minimal clause set with per-clause citations and at least one explicitly omitted clause")

u(60, "Determine what makes a package findable and how ranking is computed in extension marketplaces",
  "What signals drive discovery ranking in mature extension marketplaces, how much of ranking is "
  "install-count feedback (a rich-get-richer loop), and what would make a genuinely useful but new "
  "package discoverable in this program's index?",
  ["marketplace ranking documentation and reverse-engineering write-ups"],
  ["RES-0047"], "registry-analyst", "anthropic", "opus", T_WEB_BROAD, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; a ranking factor asserted by a blog is E3 unless the marketplace documents it or "
  "an experiment demonstrates it",
  ["separate documented ranking factors from inferred ones and label each",
   "control: state the proportion of the ranking that is admitted to be undocumented"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a ranking-factor list split documented-versus-inferred with the undocumented proportion stated")

u(61, "Characterize the prompt-payload supply-chain risk where a config file IS an instruction",
  "A cloned repository carrying .claude/, .codex/, AGENTS.md or hooks can auto-load instructions the "
  "moment an agent runs inside it - what is the published prior art on this class, what does each "
  "client actually auto-load without consent, and which mitigation survives an attempted bypass?",
  ["published research on agent-config auto-loading",
   "AGENTS.md section 9 (the cloned-repo auto-load rule)"],
  ["RES-0039", "RES-0056"], "security-researcher", "anthropic", "opus", T_SEC + ["Bash"],
  "local-serialized", 3600, S_THREAT,
  EV_LOCAL2 + "; the auto-load behaviour is measured by placing a benign marker config in a scratch "
  "directory and observing whether it is read - never by executing a hostile payload",
  ["place a benign marker config in a scratch tree and record which clients read it unprompted",
   "both-states control: the same tree without the config must produce no marker read",
   "no payload used may perform any action beyond writing a marker to a scratch path"],
  RV_SEC, RT_LOCAL, F_SEC + ["policy-violation-averted"], False,
  "a per-client auto-load observation using a benign marker plus a clean-tree control read")

# ------------------------------------------------ F. workflow / orchestration engines
u(62, "Extract the determinism mechanics of durable-execution engines and what they cost",
  "How do durable-execution engines achieve deterministic replay (event-sourced history, "
  "side-effect wrapping, versioned code paths), and which of those constraints can a workflow whose "
  "steps are non-deterministic LLM calls actually satisfy?",
  ["Temporal, Restate and DBOS documentation and sources"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; the answer must state the specific determinism property that an LLM step breaks, "
  "rather than concluding that replay is 'partially' possible",
  ["name the exact determinism constraint an LLM step violates and cite the engine's own rule",
   "control: name the subset of a workflow that CAN be replayed deterministically"],
  RV_ADV, RT_STD, F_CODE, False,
  "a named violated constraint cited to an engine rule plus the identified deterministic subset")

u(63, "Extract resume, backfill and idempotency semantics from mature DAG schedulers",
  "How do Airflow, Prefect, Dagster and Flyte define a task's identity, decide what to re-run after "
  "a partial failure, and enforce idempotency - and which definition of task identity fits work "
  "units whose output is a research artifact rather than a data partition?",
  ["Airflow, Prefect, Dagster and Flyte documentation and sources"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL,
  ["extract each engine's task-identity definition and cite it at source or spec level",
   "control: apply each definition to one real unit from this catalog and record whether it fits"],
  RV_ADV, RT_STD, F_CODE, False,
  "four cited task-identity definitions each tested against one real work unit from this slice")

u(64, "Extract typed-IO and provenance mechanisms from scientific workflow languages",
  "What do CWL, WDL, Nextflow and Snakemake do for typed inputs/outputs and machine-readable "
  "provenance (RO-Crate-class) that this program's workflow schema currently cannot express - and "
  "is the provenance model adoptable without adopting a second runtime?",
  ["CWL, WDL, Nextflow, Snakemake and RO-Crate specifications"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; the extraction must respect the spec's own rule that a transferable MECHANISM is "
  "adopted, never a second orchestration runtime (_USER-PROMPTS.md:10727)",
  ["state for each mechanism whether adopting it would import a runtime, and how to avoid that",
   "control: identify at least one mechanism that is NOT separable from its runtime"],
  RV_ADV, RT_STD, F_CODE, False,
  "a mechanism table with a runtime-entanglement verdict per row and one inseparable example")

u(65, "Extract the reuse and versioning model of CI workflow languages",
  "How do reusable workflows, composite actions and pinned action versions solve the "
  "reuse-with-versioning problem, what does the pinning-to-SHA practice actually buy, and which of "
  "those mechanics maps onto a workflow blueprint library?",
  ["GitHub Actions reusable workflow documentation", "this repo's own workflows"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE + ["Read"], "local-parallel", 2700,
  S_CLAIM,
  EV_TWO_RAIL + "; the analysis cites this repo's own workflow files at file:line as the concrete "
  "application target",
  ["map each mechanism onto a named blueprint-library requirement",
   "control: identify one CI mechanism with no blueprint-library analogue"],
  RV_ADV, RT_STD, F_CODE, False,
  "a mechanism-to-requirement mapping citing this repo's workflows at file:line")

u(66, "Extract checkpoint, interrupt and human-in-the-loop mechanics from agent graph frameworks",
  "How do LangGraph, AutoGen/AG2 and CrewAI implement checkpointing, interrupt-and-resume and human "
  "approval gates, and which of those mechanics is expressible without importing their runtime?",
  ["LangGraph, AG2 and CrewAI sources and documentation"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; note the licence trap already recorded on this corpus - microsoft/autogen "
  "returns CC-BY-4.0, a content licence on a code repo, so the licence must be read before any "
  "code-derived mechanism is adopted",
  ["record each project's LICENSE file content, not the classifier's label",
   "control: state whether any mechanism requires copying code rather than reimplementing"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "per-project LICENSE file contents (read, not classified) plus a copy-versus-reimplement verdict")

u(67, "Find the evidence on declarative versus imperative workflow definition from engines that switched",
  "Which orchestration engines migrated between declarative and imperative definitions, what "
  "reasons did their maintainers publish, and what does that history say about the 05-ECO "
  "anti-adoption 'do not build a workflow language'?",
  ["migration announcements and design documents from orchestration engines",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:118-119 (anti-adoption 1)"],
  DEP_BASE, "prior-art-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 3600, S_CLAIM,
  EV_TWO_RAIL + "; the unit must be able to REFUTE the anti-adoption if the evidence supports it - "
  "confirming an inherited position without testing it is the failure mode here",
  ["state explicitly whether the evidence corroborates or refutes the anti-adoption",
   "control: find and report at least one case that cuts AGAINST the anti-adoption"],
  RV_TWO, RT_QUOTA, F_WEB, False,
  "a corroborate-or-refute verdict on anti-adoption 1 plus at least one counter-case reported")

u(68, "Extract dynamic fan-out and barrier semantics under partial failure",
  "How do existing engines express map-over-unknown-N with a barrier, and specifically what happens "
  "at the barrier when K of N children fail - the exact case where this estate measured a fan-in "
  "deadlock from one hung agent?",
  ["orchestration engine documentation on mapped tasks and barriers",
   "feedback_workflow_orchestration (prior estate finding: no per-agent timeout deadlocks a phase)"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; each engine's partial-failure barrier policy is quoted from its documentation or "
  "source, not summarized from memory",
  ["quote each engine's stated barrier policy for K-of-N failure",
   "control: identify at least one engine with no per-child timeout, matching the local pathology"],
  RV_ADV, RT_STD, F_CODE, False,
  "quoted barrier policies per engine plus a named engine exhibiting the local no-timeout pathology")

u(69, "Extract loop-convergence and stopping-rule constructs from existing workflow engines",
  "Which engines express a loop that terminates on a CONDITION rather than a fixed count, how is the "
  "condition evaluated, and how does each prevent an infinite loop when the condition never becomes "
  "true?",
  ["orchestration engine documentation on loops and conditions"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL,
  ["for each engine, record the infinite-loop guard and whether it is mandatory or optional",
   "control: identify one engine whose guard is optional, i.e. an infinite loop is expressible"],
  RV_ADV, RT_STD, F_CODE, False,
  "a per-engine loop-guard table distinguishing mandatory from optional guards")

u(70, "Assess content-addressed memoization for agent steps: what is safely cacheable",
  "Bazel and Nix cache on a hash of inputs - for an agent step whose output depends on a model "
  "version, a temperature and a live web source, what exactly must enter the cache key, and which "
  "steps are honestly not cacheable at all?",
  ["Bazel, Nix and dvc caching documentation"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the deliverable is a cache-key specification with a named uncacheable class, not "
  "an aspiration that everything can be cached",
  ["specify the cache key field by field and justify each field's inclusion",
   "control: name at least one step class that must be marked uncacheable"],
  RV_ADV, RT_STD, F_CODE, False,
  "a field-by-field cache-key specification plus a named uncacheable step class")

u(71, "Survey prior art on dry-run, cost estimation and impact preview for agent pipelines",
  "Which systems can tell a user what a run will cost and touch BEFORE it runs, how accurate are "
  "their estimates when measured against actuals, and what is the minimum viable dry-run for a "
  "workflow whose cost is dominated by model tokens?",
  ["cost-estimation features in orchestration and infrastructure tools"],
  DEP_BASE, "mechanism-extractor", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL + "; any accuracy figure must cite a published estimate-versus-actual comparison, and "
  "its absence must be reported as absent rather than glossed",
  ["report the estimate-versus-actual accuracy for each system or mark it NOT-PUBLISHED",
   "control: at least one system must be marked NOT-PUBLISHED if no comparison exists"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a per-system accuracy column where unpublished figures are explicitly marked NOT-PUBLISHED")

u(72, "Evaluate model-routing prior art and whether measured savings survive independent replication",
  "What do published routers (cost-quality cascades, learned routers) claim, and has any of the "
  "claimed cost saving been reproduced by an independent party on a different task distribution?",
  ["published model-routing research and implementations"],
  DEP_PAPER, "prior-art-analyst", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; a saving claimed only by the router's own authors on their own benchmark is E3 and "
  "may not promote the mechanism",
  ["record independent-replication status per router: replicated / self-reported-only / unknown",
   "control: at least one router must be marked self-reported-only if that is the truth"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a per-router replication-status column with the benchmark each figure came from")

u(73, "Determine whether visual workflow builders are used or abandoned, and by whom",
  "For tools that ship both a visual builder and a text definition, what evidence exists about which "
  "one real users end up using - and does the answer differ for authoring versus reviewing?",
  ["usage write-ups, issue trackers and post-mortems for visual workflow tools"],
  DEP_BASE, "product-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700, S_CLAIM,
  EV_TWO_RAIL + "; vendor marketing is not evidence of use; practitioner reports and issue-tracker "
  "signals are, and each must be labelled with its source class",
  ["separate authoring evidence from reviewing evidence and report each",
   "control: state the sample size and its obvious selection bias"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "an authoring-versus-reviewing evidence split with a stated sample size and named selection bias")

u(74, "Determine whether any workflow interchange format is real enough to import from",
  "Is there any interchange format that more than one orchestration ecosystem actually reads and "
  "writes, or is every 'export' effectively a one-way dump - the answer that decides whether this "
  "program's importer targets a format or writes per-source adapters?",
  ["interchange format specifications and their implementations"],
  DEP_BASE, "adapter-architect", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; a format counts as real only when TWO independent implementations both read and "
  "write it, and the two implementations are named",
  ["for each format, name the reading and writing implementations or mark it one-way",
   "control: at least one format must be marked one-way"],
  RV_ADV, RT_STD, F_CODE, False,
  "a per-format table naming read and write implementations, with one-way formats marked")

# --------------------------------------------------- G. council / deliberation science
u(75, "Extract the operational rules that make the Delphi method work, and its documented failures",
  "What are the concrete procedural rules of a Delphi study (anonymity, controlled feedback, "
  "iteration, statistical group response), what evidence exists that each rule matters, and what are "
  "the documented ways Delphi fails?",
  ["Delphi methodology literature"],
  DEP_PAPER, "deliberation-scientist", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the failure modes are extracted with the same rigour as the rules, because a method "
  "summary that omits its failures is not usable as a design input",
  ["extract at least 4 documented failure modes with citations",
   "control: state which rules have empirical support and which are convention"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a rule list split into empirically-supported and conventional, plus >=4 cited failure modes")

u(76, "Hunt the negative results on multi-agent debate: where it does NOT beat a single model",
  "Which published studies find multi-agent debate performing at or below a single well-prompted "
  "model, on what task types, and does the negative evidence explain the 05-ECO reject of "
  "'multi-round free-form debate to consensus'?",
  ["multi-agent debate literature including null and negative results",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:97-103 (Tier 3 rejects)"],
  DEP_PAPER, "negative-result-hunter", "openai", "codex-cli", T_PAPERS_WEB, "cloud-batch", 3600,
  S_NEG,
  EV_PAPER + "; the search must be constructed to FIND nulls (searching for the negative phrasing "
  "explicitly), because a search built from the positive claim will return only confirmations",
  ["publish the query set and show it includes explicitly negative phrasings",
   "control: report how many of the retrieved studies were positive, to expose search bias"],
  RV_TWO, RT_XV, F_PAPER, False,
  "a negative-result register with the query set printed and the positive/negative retrieval ratio")

u(77, "Catalogue LLM-as-judge biases and which corrections survive measurement",
  "What biases are measured in LLM judges (position, verbosity, self-preference, style), what "
  "magnitude does each have, and which proposed correction has been shown to reduce it rather than "
  "merely being proposed?",
  ["LLM-as-judge evaluation literature"],
  DEP_PAPER, "calibration-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; each correction is graded measured-effective / proposed-only / refuted, and the "
  "grading rule is stated before the grading",
  ["grade every correction measured-effective / proposed-only / refuted with a citation",
   "control: at least one widely-cited correction must land outside measured-effective if the "
   "evidence says so"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a bias-by-correction table with per-row effect sizes and an explicit grade")

u(78, "Determine which voting rules survive when every participant is the same model",
  "Social-choice theory assumes independent voters - when N participants share one model and "
  "therefore correlate their errors (the 05-ECO reject cites 60%+ correlated errors), which voting "
  "rule degrades least, and is any majority-style rule defensible at all?",
  ["social choice theory literature", "correlated-error measurements for LLM ensembles",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:99 (same-vendor majority-vote reject)"],
  DEP_PAPER, "deliberation-scientist", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the correlated-error figure must be traced to its primary measurement rather than "
  "inherited from the call sheet, since the call sheet is itself a secondary source here",
  ["trace the 60% correlated-error figure to a primary source or mark it UNTRACED",
   "control: compute how the majority rule's error changes as correlation rises, and show the curve"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a traced-or-untraced verdict on the correlation figure plus an error-versus-correlation curve")

u(79, "Determine the right belief-aggregation rule for a panel with unequal calibration",
  "Between linear pooling, logarithmic pooling and Bayesian aggregation, which produces better "
  "calibrated group forecasts when members differ in calibration - and what does each require that "
  "this program does not yet have (a labelled verdict history)?",
  ["opinion pooling and forecast aggregation literature"],
  DEP_PAPER, "calibration-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the prerequisite data each method needs is stated explicitly, because the call "
  "sheet already grades calibration-weighted aggregation as blocked on a labelled history",
  ["state the exact prerequisite dataset each method needs before it can be used here",
   "control: identify which method is usable TODAY with zero history"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a method table with a prerequisite-data column and one method identified as usable at zero history")

u(80, "Port the operational groupthink detectors from social psychology to agent panels",
  "Which conformity and groupthink measurements from human group research (Asch-style conformity "
  "rate, premature-closure timing, dissent-suppression markers) are mechanically computable from an "
  "agent transcript, and what threshold marks a pathological panel?",
  ["groupthink and conformity literature", "council transcript structure from Prompt One"],
  ["RES-0001", "RES-0075"], "deliberation-scientist", "anthropic", "opus", T_PAPERS, "cloud-batch",
  3600, S_CLAIM,
  EV_PAPER + "; a detector is only proposed when the transcript field it reads is named, since a "
  "detector over data the transcript does not carry is not implementable",
  ["name the transcript field each detector reads and confirm the field exists in the council schema",
   "control: at least one classical measure must be marked not-portable with the reason"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a detector list where each entry names an existing transcript field, plus one not-portable measure")

u(81, "Measure the published magnitude of LLM sycophancy and which mitigations survive testing",
  "How large is the measured sycophancy effect (agreement flip rate under user pushback) across "
  "published studies, and which mitigations have been shown to reduce it under adversarial testing "
  "rather than in a single demonstration?",
  ["sycophancy measurement literature"],
  DEP_PAPER, "calibration-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER,
  ["record the flip-rate metric definition used by each study, since they differ",
   "control: report at least one study whose mitigation failed or did not replicate"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a per-study flip-rate table with each study's metric definition and one failed mitigation")

u(82, "Determine the effect of anonymity and information partitioning on deliberation quality",
  "What is the measured effect of anonymizing participants and partitioning their evidence, and does "
  "partitioning genuinely restore independence for same-model participants - the mechanism the "
  "05-ECO anti-adoption prescribes instead of adding reviewers?",
  ["anonymity and information-partition literature",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:120-121 (anti-adoption 2)"],
  DEP_PAPER, "deliberation-scientist", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the specific question 'does partitioning restore independence for identical models' "
  "must be answered with evidence or explicitly marked NOT-ESTABLISHED",
  ["answer the identical-model partition question with a citation or mark it NOT-ESTABLISHED",
   "control: distinguish evidence from human studies from evidence from LLM studies"],
  RV_TWO, RT_STD, F_PAPER, False,
  "an explicit answer or NOT-ESTABLISHED verdict on partitioned independence, with human and LLM "
  "evidence reported separately")

u(83, "Extract scoring rules and extremizing methods from forecasting tournaments",
  "Which proper scoring rules and aggregation adjustments (extremizing, recency weighting, "
  "team-versus-individual effects) are validated by forecasting-tournament research, and which can "
  "score a council's confidence trajectory with the data a council actually produces?",
  ["forecasting tournament literature"],
  DEP_PAPER, "calibration-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; a scoring rule is only recommended when the resolution source for the question is "
  "named - an unresolvable question cannot be scored",
  ["for each rule, name what would resolve the question and over what horizon",
   "control: identify one council output type that is fundamentally unscoreable"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a rule table with a named resolution source per row and one unscoreable output type identified")

u(84, "Solve the 100-unique-idea counting problem without trivial-variant gaming",
  "What method counts unique ideas such that 100 trivially reworded variants do NOT satisfy the "
  "target - and does the method survive an adversarial generator that deliberately produces "
  "near-duplicates at the similarity threshold?",
  ["novelty and diversity metric literature",
   "_USER-PROMPTS.md:11339 (the count-gaming failure class)"],
  ["RES-0004"], "measurement-engineer", "anthropic", "opus", T_PROTO + ["mcp__paper-search__search_arxiv"],
  "worktree-isolated", 3600, S_MEAS,
  EV_BOTH + "; the counter is tested against a deliberately gamed corpus, not only a clean one - a "
  "lexical similarity metric fires on renames and paraphrases but a full rewrite lands in the same "
  "band as a genuinely distinct idea, and that limit must be stated inline",
  ["adversarial fixture: 100 trivially reworded variants must NOT satisfy a 100-unique target",
   "positive control: 100 genuinely distinct ideas must satisfy it",
   "state the metric's blind spot (deep paraphrase) inline with the named settling experiment"],
  RV_SELF, RT_PROTO, F_PROTO, False,
  "a counter that rejects the 100-variant gamed corpus and accepts the 100-distinct corpus, with the "
  "measured threshold and the stated blind spot")

u(85, "Choose a machine-checkable argumentation format for council argument graphs",
  "Between IBIS, Toulmin-structured claims and formal argumentation frameworks, which can be "
  "mechanically checked for an unsupported claim or an unanswered rebuttal - and which is cheap "
  "enough for an agent to emit reliably?",
  ["argumentation theory literature and tool implementations"],
  ["RES-0004"], "deliberation-scientist", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600,
  S_CLAIM,
  EV_TWO_RAIL + "; 'machine-checkable' means a named check over a named field, and each candidate "
  "format is scored by whether that check can be written",
  ["for each format, write the unanswered-rebuttal check in pseudocode or mark it uncheckable",
   "control: at least one format must be marked uncheckable or too costly to emit"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a format comparison with a written unanswered-rebuttal check per checkable format")

u(86, "Extract dissent-preservation mechanisms from institutions that mandate minority reports",
  "How do juries, standards bodies and regulatory advisory panels structurally guarantee that a "
  "minority position survives into the record, and which of those mechanisms is implementable as a "
  "hard gate rather than an instruction the synthesizer may ignore?",
  ["institutional procedure documents and dissent literature"],
  DEP_PAPER, "deliberation-scientist", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600,
  S_CLAIM,
  EV_TWO_RAIL + "; each mechanism is classified as structurally-enforced or norm-dependent, and only "
  "structurally-enforced mechanisms may be recommended as gates",
  ["classify every mechanism structurally-enforced versus norm-dependent",
   "control: name the specific artifact field a hard gate would check"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a mechanism table with an enforcement classification and a named checkable artifact field")

u(87, "Determine where hierarchical council-of-councils aggregation loses information",
  "When subcouncil conclusions are aggregated by a meta-council, what information is provably lost "
  "(dissent, confidence spread, evidence provenance), and what must be forwarded to prevent the "
  "nested-councils-disagree-on-completion failure class?",
  ["hierarchical aggregation literature", "_USER-PROMPTS.md:11343 (nested councils disagree)"],
  ["RES-0079", "RES-0086"], "deliberation-scientist", "anthropic", "opus", T_PAPERS, "cloud-batch",
  3600, S_CLAIM,
  EV_PAPER + "; 'lost' must be demonstrated with a worked two-level example where the meta-level "
  "conclusion differs from what the full evidence supports",
  ["construct a worked two-level example exhibiting the loss",
   "control: specify the minimal forwarding set that prevents the loss in that same example"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a worked two-level example showing the loss plus the minimal forwarding set that fixes it")

# --------------------------------------- H. verification / eval / benchmark integrity
u(88, "Survey completion-predicate prior art and the ways each definition of done fails",
  "What do mature systems use as their definition of done (exit code, artifact existence, schema "
  "validity, reviewer sign-off), which failures does each miss, and does any published system "
  "already implement something equivalent to this program's twelve-condition predicate?",
  ["_USER-PROMPTS.md:10627-10648 (the twelve-condition predicate)",
   "completion and verification designs in published systems"],
  DEP_BASE, "prior-art-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; for every published predicate, the specific failure it cannot catch is named "
  "with a concrete scenario",
  ["name one concrete missed failure per published predicate",
   "control: apply each published predicate to the estate's own exit-zero-missing-artifact case"],
  RV_ADV, RT_STD, F_CODE, False,
  "a predicate table where every row names a concrete missed failure, tested against the "
  "exit-zero-missing-artifact case")

u(89, "Determine how benchmark contamination and gaming are detected, and which detectors work",
  "What methods detect training-data contamination and benchmark gaming (canary strings, held-out "
  "perturbation, timeline analysis), which have been shown to work, and which of this program's own "
  "planned benchmarks would be vulnerable?",
  ["benchmark contamination literature", "this program's planned benchmark set"],
  DEP_PAPER, "adversarial-refuter", "openai", "codex-cli", T_PAPERS_WEB, "cloud-batch", 3600,
  S_CLAIM,
  EV_PAPER + "; each detector's own false-positive rate is reported, since a contamination detector "
  "with an unmeasured false-positive rate cannot be used to disqualify a result",
  ["report each detector's false-positive rate or mark it UNMEASURED",
   "control: apply the strongest detector to one benchmark this program intends to use"],
  RV_TWO, RT_XV, F_PAPER, False,
  "a detector table with false-positive rates or UNMEASURED marks, plus one applied result")

u(90, "Determine whether mutation testing has a defensible analogue for prompt and agent systems",
  "Mutation testing works because a code mutant is a well-defined perturbation - what is the "
  "equivalent well-defined mutation for a skill, a rule or a hook, and does a mutant survive rate "
  "over such mutations mean anything?",
  ["mutation testing literature", "this repo's hooks and skills as mutation targets"],
  ["RES-0001"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 3600,
  S_MEAS,
  EV_BOTH + "; the mutation operator set is defined and published BEFORE any survival rate is "
  "computed, so the rate cannot be tuned by choosing convenient mutants",
  ["publish the mutation operator set before computing any rate",
   "apply the operators to one real hook and report the survival rate",
   "control: a mutation known to break behaviour must be killed by the existing tests, or the "
   "test suite is confirmed not to protect that behaviour"],
  RV_SELF, RT_PROTO, F_PROTO, False,
  "a pre-published operator set plus a measured survival rate on one real hook with a killed control")

u(91, "Identify which properties of an agent's output are genuinely property-testable",
  "For an agent-produced artifact, which invariants can a property-based test assert without "
  "asserting the model's opinion (schema validity, idempotence of re-runs, monotonicity of a "
  "counter, absence of a credential) - and which desirable properties are fundamentally untestable?",
  ["property-based testing literature", "this program's artifact schemas"],
  ["RES-0001"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 3600,
  S_CLAIM,
  EV_BOTH + "; the deliverable includes at least one property implemented and run, not only a list",
  ["implement and run at least 3 properties against a real artifact",
   "control: name at least 2 desirable properties that are fundamentally untestable and say why"],
  RV_SELF, RT_PROTO, F_PROTO, False,
  "3 implemented properties with run output plus 2 named untestable properties")

u(92, "Extract metamorphic testing relations applicable to LLM-driven pipelines",
  "Which metamorphic relations (reordering inputs, renaming identifiers, paraphrasing a prompt) "
  "should leave an agent pipeline's output invariant, and does the pipeline actually satisfy them - "
  "the test that needs no ground-truth oracle?",
  ["metamorphic testing literature"],
  ["RES-0091"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 3600,
  S_CLAIM,
  EV_BOTH + "; a relation is only useful if a violation is a genuine defect - relations whose "
  "violation is acceptable variance must be excluded and the exclusion justified",
  ["implement one relation and run it against a real pipeline step",
   "control: state the acceptable-variance threshold and how it was chosen, before running"],
  RV_SELF, RT_PROTO, F_PROTO, False,
  "one implemented relation with its run output and a pre-stated variance threshold")

u(93, "Census agent benchmarks and state precisely what each one measures and does not",
  "For each major agent benchmark, what capability does it actually measure, what is its known "
  "contamination or saturation status, and which of them could measure THIS program's improvement "
  "rather than a model's raw ability?",
  ["agent benchmark papers and leaderboards"],
  ["RES-0089"], "benchmark-analyst", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600, S_REG,
  EV_PAPER + "; a benchmark is only marked applicable when the specific harness-level improvement it "
  "would detect is named",
  ["name the harness-level improvement each applicable benchmark would detect",
   "control: mark at least one popular benchmark inapplicable with a reason"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a benchmark register with an applicability verdict and a named detectable improvement per "
  "applicable row")

u(94, "Enumerate the sources of nondeterminism in an agent run and which are controllable",
  "What makes two identical agent runs differ (sampling, tool ordering, clock, network, model "
  "version drift, concurrent siblings), which of those can be pinned, and what is the residual "
  "variance after pinning everything pinnable?",
  ["reproducibility literature", "this estate's own concurrent-sibling contamination measurements"],
  ["RES-0003"], "measurement-engineer", "anthropic", "opus", T_LOCAL + ["Bash(python)"],
  "local-serialized", 3600, S_MEAS,
  EV_LOCAL2 + "; the residual variance is measured by repeated runs, not estimated - and the "
  "measurement must acknowledge that a tree mutating under the runner is itself a variance source",
  ["run the same pinned task N>=5 times and report the observed output variance",
   "control: deliberately unpin one factor and confirm variance increases"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "an N>=5 repeated-run variance figure plus an unpin-and-increase control")

u(95, "Compute the sample size needed to detect this program's intended benchmark improvement",
  "Given the expected effect size and the observed per-case variance, how many benchmark cases are "
  "needed to detect the intended improvement at conventional power - and is the planned suite large "
  "enough or is it underpowered by construction?",
  ["RES-0094 variance measurements", "the planned benchmark suite size"],
  ["RES-0094"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 2700,
  S_MEAS,
  "the power calculation is executed with the variance measured by RES-0094, and the assumed effect "
  "size is stated as an assumption with its own confidence band rather than smuggled in",
  ["run the power calculation and print the required N alongside the planned N",
   "control: show how required N changes if the assumed effect size halves"],
  RV_MEAS, RT_PROTO, F_PROTO, False,
  "a printed required-N versus planned-N comparison plus a sensitivity row for a halved effect size")

u(96, "Determine how green regression suites stop protecting behaviour over time",
  "What mechanisms cause a passing test suite to lose its protective power (defaults never "
  "exercised, fixtures drifting from production, assertions weakened to fix flakes), and which of "
  "them is present in this repo's own suite?",
  ["test-decay literature", "this repo's test suite",
   "rules/common/single-signal-verification.md (the DEFAULT_MIN_BYTES mutation that survived)"],
  ["RES-0090"], "adversarial-refuter", "openai", "codex-cli", T_PROTO + ["Grep", "Glob"],
  "worktree-isolated", 3600, S_CLAIM,
  "each decay mechanism found in this repo is proven by a mutation that the suite fails to kill, "
  "with the surviving mutant recorded verbatim",
  ["find at least one surviving mutant in this repo's suite or state that none was found after N "
   "operators were applied",
   "control: a mutation the suite DOES kill must also be recorded, proving the harness works"],
  RV_TWO, RT_XV, F_PROTO, False,
  "at least one recorded surviving-or-killed mutant pair from this repo's actual suite")

u(97, "Extract negative-control practice from disciplines where it is mandatory",
  "How do clinical trials and experimental physics define and validate a negative control, and what "
  "does their practice add to this estate's both-states rule that the rule does not already say?",
  ["experimental methodology literature from clinical and physical sciences",
   "rules/common/single-signal-verification.md section 3b (the both-states test)"],
  DEP_PAPER, "prior-art-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 2700, S_CLAIM,
  EV_PAPER + "; the deliverable must state what is NEW relative to the existing rule; 'it agrees "
  "with our rule' is a null result and must be reported as such rather than dressed up",
  ["state explicitly what is new versus what merely restates the existing rule",
   "control: it is acceptable and expected for this unit to return a null result"],
  RV_ADV, RT_STD, F_PAPER, False,
  "an explicit new-versus-restated split, with a null result reported as a null result if that is "
  "the honest outcome")

u(98, "Define what makes a reproduction genuinely independent rather than a re-run",
  "In replication research, what structural conditions make a reproduction independent (different "
  "team, different tooling, blind to the original conclusion), and which of those conditions can a "
  "same-vendor fresh-context agent actually satisfy?",
  ["replication and reproducibility literature",
   "_USER-PROMPTS.md:11028-11041 (Phase 11 confirmation requirements)"],
  DEP_PAPER, "prior-art-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the answer must confront the uncomfortable case honestly: a fresh-context agent of "
  "the same model reading the same sources may be one signal, not two",
  ["state for each condition whether a same-vendor fresh context satisfies it",
   "control: identify at least one condition that only a cross-vendor reproducer can satisfy"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a condition-by-condition satisfiability verdict for same-vendor fresh context, with at least one "
  "cross-vendor-only condition named")

u(99, "Design the telemetry that would measure this program's own gate false-positive rate",
  "What must be recorded on every gate decision to compute its false-positive and false-negative "
  "rates later, where would that record live, and what is the minimum sample before a rate may be "
  "quoted?",
  ["_USER-PROMPTS.md:11130 (false-positive/negative telemetry must be acceptable)",
   "command-center/events/EVENTS.jsonl"],
  ["RES-0001"], "measurement-engineer", "anthropic", "opus", T_PROTO + ["Read"],
  "worktree-isolated", 2700, S_MEAS,
  "the record design is validated by replaying existing EVENTS.jsonl entries through it and showing "
  "which fields are already present and which would have to be added",
  ["replay existing events through the proposed record and report field coverage",
   "control: state the minimum sample size below which no rate may be quoted, and why"],
  RV_MEAS, RT_PROTO, F_PROTO, False,
  "a field-coverage report against real existing events plus a stated minimum-sample threshold")

# ------------------------------------------------- I. capability routing and context
u(100, "Compare retrieval, rule-based and learned capability routing on measured selection accuracy",
  "For selecting the right skill or tool from a large catalog, what selection accuracy do "
  "retrieval-based, rule-based and learned routers achieve in published measurements, and is the "
  "05-ECO instruction to adopt the NATIVE progressive-disclosure mechanism rather than build a "
  "bespoke retriever supported by that evidence?",
  ["capability routing literature",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:83-84,100 (adopt native, reject bespoke retriever)"],
  DEP_PAPER, "prior-art-analyst", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600, S_CLAIM,
  EV_PAPER + "; the unit must be able to refute the inherited adopt-native grade, and must state "
  "which comparison would settle it if the published evidence is insufficient",
  ["state corroborate or refute on the adopt-native grade with the evidence that decides it",
   "control: report the catalog size each published accuracy figure was measured at, since accuracy "
   "at 20 tools says nothing about 500"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a corroborate-or-refute verdict with every accuracy figure annotated by its catalog size")

u(101, "Measure how tool-selection accuracy degrades as the exposed tool count grows",
  "On this box's real tool inventory, how does selection accuracy change between a small curated "
  "set and the full exposed fleet - measured with a fixed task set rather than inferred from "
  "published curves on other catalogs?",
  ["the live tool inventory", "a fixed set of routing tasks with known-correct answers"],
  ["RES-0041", "RES-0100"], "measurement-engineer", "anthropic", "opus", T_LOCAL,
  "local-serialized", 5400, S_MEAS,
  EV_LOCAL2 + "; the task set with its known-correct answers is fixed and published BEFORE the "
  "measurement, so the accuracy cannot be defined after seeing the results",
  ["publish the task set and its gold answers before running",
   "run at >=3 catalog sizes and report accuracy at each",
   "control: a task with an obviously correct tool must be answered correctly at every size, or the "
   "harness itself is broken"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "an accuracy-versus-catalog-size table at >=3 sizes with the pre-published gold task set attached")

u(102, "Determine what makes a capability description route correctly, by ablation",
  "Which components of a skill description drive correct routing (trigger phrases, negative scope, "
  "examples, length), measured by ablating each component and re-running a fixed routing task set?",
  ["a sample of real skill descriptions from this estate", "RES-0101 task set"],
  ["RES-0101"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 3600,
  S_MEAS,
  EV_BOTH + "; each ablation's effect is a measured delta on the same fixed task set, and a "
  "component with no measured effect is reported as having none rather than quietly retained",
  ["ablate each description component in turn and report the routing-accuracy delta",
   "control: an ablation of an irrelevant component must produce approximately zero delta"],
  RV_MEAS, RT_PROTO, F_PROTO, False,
  "a per-component ablation delta table including at least one approximately-zero control")

u(103, "Determine when a router should inject nothing, and what confidence threshold expresses that",
  "What prior art exists on abstention in retrieval and routing, what threshold minimizes the cost "
  "of a wrong injection versus a missed one, and does judge-abstention-as-a-first-class-verdict "
  "(Tier 1 in the call sheet) transfer to capability routing?",
  ["abstention and selective prediction literature",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:84-85 (judge abstention, Tier 1)"],
  ["RES-0100"], "prior-art-analyst", "anthropic", "opus", T_PAPERS, "cloud-batch", 2700, S_CLAIM,
  EV_PAPER + "; the threshold recommendation must state the assumed relative cost of the two error "
  "types, because the optimum is undefined without it",
  ["state the assumed cost ratio explicitly and show how the threshold moves if it is inverted",
   "control: identify the regime where abstention is strictly worse than always answering"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a threshold recommendation with an explicit cost-ratio assumption and an inverted-ratio sensitivity")

u(104, "Extract progressive-disclosure patterns for very large capability catalogs",
  "How do large-catalog systems (IDE command palettes, large API surfaces, plugin ecosystems) reveal "
  "capability progressively, and which pattern keeps a 500-item catalog usable without loading it "
  "all?",
  ["progressive disclosure and large-catalog UX literature and implementations"],
  ["RES-0100"], "ecosystem-cartographer", "anthropic", "opus", T_WEB_BROAD, "cloud-batch", 2700,
  S_CLAIM,
  EV_TWO_RAIL + "; each pattern is paired with the catalog size at which it is known to work, since "
  "a pattern proven at 50 items is not evidence at 500",
  ["annotate every pattern with the catalog size it was observed at",
   "control: identify one pattern that is known to break above a stated size"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a pattern list annotated with observed catalog sizes and one documented breaking point")

u(105, "Define conflict resolution when two capabilities both match a request",
  "When two skills claim the same trigger, what resolution strategies exist (specificity, scope "
  "depth, explicit priority, ask the user), and which produces the fewest wrong selections on the "
  "fixed routing task set?",
  ["RES-0101 task set", "this estate's directory-scoped skill precedence behaviour"],
  ["RES-0101"], "measurement-engineer", "anthropic", "opus", T_PROTO, "worktree-isolated", 2700,
  S_MEAS,
  EV_BOTH + "; the comparison runs all strategies against the same task set so the numbers are "
  "commensurable",
  ["run every strategy against the identical task set and report wrong-selection counts",
   "control: include a deliberately bad strategy (random) to prove the measurement discriminates"],
  RV_MEAS, RT_PROTO, F_PROTO, False,
  "a per-strategy wrong-selection count on one shared task set, including a random baseline")

u(106, "Extract how other systems build a regression suite that proves a router still routes",
  "What does a router regression suite look like elsewhere (golden query sets, drift alarms, "
  "coverage of never-selected capabilities), and how do they detect the specific failure where a "
  "capability exists but is never selected?",
  ["router and search relevance testing practice"],
  ["RES-0101"], "prior-art-analyst", "anthropic", "opus", T_CODE, "cloud-batch", 2700, S_CLAIM,
  EV_TWO_RAIL + "; the never-selected-capability detector is the specific deliverable, since a "
  "router suite that only tests popular queries cannot see that failure",
  ["specify the never-selected detector including what it reads and when it runs",
   "control: state the false-alarm case (a capability that SHOULD never be selected)"],
  RV_ADV, RT_STD, F_CODE, False,
  "a specified never-selected detector with its data source and its stated false-alarm case")

u(107, "Evaluate embedding-free repo-map construction as a code-context mechanism",
  "Can a symbol-graph ranking over language-server references (no vector store) produce a code "
  "context map competitive with embedding retrieval, what does each cost, and is the "
  "no-vector-store constraint the 05-ECO reject implies actually satisfiable?",
  ["Aider repo-map and LSP-based ranking implementations",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:100 (bespoke vector tool-retriever reject)"],
  ["RES-0028"], "mechanism-extractor", "anthropic", "opus", T_CODE, "cloud-batch", 3600, S_CLAIM,
  EV_TWO_RAIL + "; 'competitive' requires a named comparison metric and a cited measurement, or the "
  "claim is downgraded to a design preference and labelled as such",
  ["name the comparison metric and cite a measurement, or explicitly downgrade the claim",
   "control: state the repository size at which the graph approach becomes too slow"],
  RV_ADV, RT_STD, F_CODE, False,
  "a cited comparison or an explicit downgrade to design-preference, plus a stated scale limit")

# --------------------------- J. gem hunt / salvage / niche / archival / multilingual / tor
u(108, "Pre-register the gem-hunt rubric before any hunting begins",
  "What operational criteria make a mechanism a GEM (leverage per unit of integration cost, "
  "irreplaceability, measured evidence, bus-fit) - and does the rubric, applied blind to the ten "
  "Tier-1 call-sheet rows, reproduce their Tier-1 grading?",
  [CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:74-108 (the tiered call sheet)",
   "the bus-fit vocabulary RIDES-BUS / RIDES-BUS+STATE / RIDES-BUS+DAEMON / SECOND RUNTIME"],
  ["RES-0002"], "gem-hunt-lead", "anthropic", "opus", T_PROTO + ["Read"], "worktree-isolated",
  2700, S_MEAS,
  "the rubric is published BEFORE it is applied, and its calibration against the existing Tier-1 "
  "rows is reported including disagreements - a rubric that reproduces the existing grading "
  "perfectly is suspicious, not reassuring",
  ["apply the rubric blind to the 10 Tier-1 rows and report agreement and disagreement counts",
   "control: apply it to 5 Tier-3 rejects and confirm they do not score as gems"],
  RV_TWO, RT_PROTO, F_PROTO, False,
  "a pre-published rubric with a blind agreement count on Tier-1 rows and a Tier-3 negative control")

u(109, "Salvage transferable mechanisms from archived and unmaintained orchestration projects",
  "Among archived or unmaintained agent-orchestration repositories, which contain a mechanism worth "
  "extracting that has no maintained equivalent - and for each, is the licence compatible with "
  "reimplementation?",
  ["archived repositories in the agent-orchestration space", "RES-0121 licence graph"],
  ["RES-0108"], "salvage-archaeologist", "anthropic", "opus", T_CODE + T_ARCHIVE, "cloud-batch",
  5400, S_REG,
  EV_TWO_RAIL + "; archived status is verified from the repository metadata, and the LICENSE file "
  "is READ rather than trusting the platform's classifier (the NOASSERTION trap)",
  ["read the actual LICENSE file for every salvage candidate and quote its identifying line",
   "control: report how many candidates had a licence label that disagreed with the file"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "a salvage register where every row quotes the LICENSE file's identifying line, plus a count of "
  "label-versus-file disagreements")

u(110, "Find implementable mechanisms in papers that have no popular implementation",
  "Which published mechanisms relevant to this program have a clear enough specification to "
  "implement but no widely used implementation - the highest-leverage gem class because the work is "
  "done and the adoption is not?",
  ["recent literature across orchestration, verification and deliberation"],
  ["RES-0108"], "gem-hunt-lead", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 5400, S_REG,
  EV_PAPER + "; 'no popular implementation' is established by an actual search for one, and the "
  "search is recorded, because absence claimed without a search is not a finding",
  ["record the implementation search performed for each candidate",
   "detector control: the search must find a known-existing implementation for a control mechanism"],
  RV_TWO, RT_STD, F_PAPER, False,
  "a candidate register with a recorded implementation-search per row and a passing detector control")

u(111, "Transfer distributed-systems primitives to agent orchestration",
  "Which distributed-systems primitives (idempotency keys, fencing tokens, lease expiry, exactly-once "
  "illusions, backpressure) map directly onto this program's known failure classes - duplicate "
  "dispatch, stale monitor, one hung unit blocking a batch, 429 storms?",
  ["distributed systems literature", "_USER-PROMPTS.md:11298-11347 (the seeded failure classes)"],
  ["RES-0108"], "mechanism-extractor", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 3600,
  S_CLAIM,
  EV_PAPER + "; each mapping names the exact failure class from the spec's list that it addresses, "
  "and a primitive that maps to nothing on the list is excluded rather than included for elegance",
  ["map each primitive to a named failure class from the spec list or drop it",
   "control: report how many primitives were dropped for having no mapped failure"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a primitive-to-failure-class mapping with a stated count of primitives dropped as unmapped")

u(112, "Transfer checklist and crew-resource-management discipline to agent gates",
  "What does the safety-critical checklist literature say about WHY checklists work (killer items, "
  "read-do versus do-confirm, pause points), and which of those properties do this program's gates "
  "currently lack?",
  ["checklist and CRM literature", "this program's existing gate definitions"],
  ["RES-0108"], "prior-art-analyst", "anthropic", "opus", T_PAPERS_WEB + ["Read"], "local-parallel",
  2700, S_CLAIM,
  EV_PAPER + "; the gap analysis cites this program's actual gate definitions at file:line, so the "
  "'currently lack' half is measured rather than assumed",
  ["cite this program's gates at file:line when claiming a property is absent",
   "control: identify at least one property the existing gates already have"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a property gap table citing existing gates at file:line with at least one already-satisfied row")

u(113, "Transfer intelligence-analysis tradecraft to claim and confidence discipline",
  "What do the analytic tradecraft standards (structured analytic techniques, analysis of competing "
  "hypotheses, the nine analytic standards) add to this program's claim discipline beyond the "
  "Sherman-Kent bands already in use?",
  ["analytic tradecraft standards literature", "this program's existing confidence-band practice"],
  ["RES-0108"], "prior-art-analyst", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 2700, S_CLAIM,
  EV_PAPER + "; the deliverable must separate what is genuinely additive from what merely renames "
  "existing practice, and a mostly-renaming result is an honest and expected outcome",
  ["split findings into additive and renaming",
   "control: at least one technique must be evaluated and rejected as not worth the ceremony"],
  RV_ADV, RT_STD, F_PAPER, False,
  "an additive-versus-renaming split with at least one explicitly rejected technique")

u(114, "Transfer build-system hermeticity to reproducible agent runs",
  "What does a hermetic build guarantee, what does it cost, and which hermeticity properties can an "
  "agent run adopt given that its inputs include a live model and a live web - a question the "
  "estate's own hermetic-probe experience makes concrete?",
  ["hermetic build literature", "the estate's hermetic_probe experience with hidden network fetches"],
  ["RES-0094"], "mechanism-extractor", "anthropic", "opus", T_PAPERS_WEB, "cloud-batch", 2700,
  S_CLAIM,
  EV_PAPER + "; the specific lesson that 14 tests silently downloaded from the network despite "
  "comments claiming otherwise must be treated as the motivating case, and the proposed property "
  "must be one that would have CAUGHT it",
  ["state which proposed property would have caught the silent-download case",
   "control: name one hermeticity property an agent run can never satisfy"],
  RV_ADV, RT_STD, F_PAPER, False,
  "a property list with the silent-download case explicitly mapped and one impossible property named")

u(115, "Mine practitioner forums for failure reports that no vendor documentation contains",
  "What recurring operational failures do practitioners report in public forums that appear in no "
  "vendor documentation or issue tracker, and how many independent reporters does each failure have "
  "before it may be treated as real?",
  ["public practitioner forums and discussion archives"],
  ["RES-0002"], "ecosystem-cartographer", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 3600,
  S_REG,
  EV_INDEP + "; a failure needs independent reporters, and reporters quoting one another are ONE "
  "reporter - the independence check must be performed and recorded",
  ["record the independence check for every failure with more than one reporter",
   "control: report at least one apparent multi-report failure that collapsed to a single source"],
  RV_ADV, RT_QUOTA, F_WEB, False,
  "a failure register with an independent-reporter count and at least one documented collapse to one")

u(116, "Sweep non-English sources for mechanisms absent from the English-language corpus",
  "Do Chinese, Japanese, Russian, German or Korean technical sources describe orchestration or "
  "deliberation mechanisms that have no English-language equivalent in this program's corpus - and "
  "is any of them implementable from the source as written?",
  ["non-English technical publications, blogs and repositories"],
  ["RES-0002"], "ecosystem-cartographer", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 5400,
  S_REG,
  EV_TWO_RAIL + "; every non-English claim carries the original-language quotation alongside the "
  "translation, so a translation error cannot silently become a finding",
  ["include the original-language quotation for every extracted claim",
   "control: report the number of candidates discarded as translations of English sources"],
  RV_TWO, RT_QUOTA, F_WEB, False,
  "a register where each row carries the original-language quote plus a count of discarded "
  "re-translations")

u(117, "Recover deleted or moved prior art from archival sources",
  "For the sources this program's corpus cites that no longer resolve, what does the archival record "
  "contain, and does any recovered artifact change a conclusion currently resting on a dead link?",
  ["web archive and software heritage", "the dead links found by RES-0003 and RES-0042"],
  ["RES-0003", "RES-0042"], "salvage-archaeologist", "anthropic", "opus", T_ARCHIVE, "cloud-batch",
  3600, S_REG,
  EV_VERSIONED + "; a recovered snapshot is dated and its date is compared to the date the original "
  "claim was made, because a snapshot from after the claim proves nothing about what was read",
  ["compare each recovered snapshot's date against the claim's date and flag mismatches",
   "control: report the number of dead links with NO usable archival record"],
  RV_ADV, RT_STD, F_WEB, False,
  "a recovery table with snapshot-versus-claim date comparison and a count of unrecoverable links")

u(118, "Search patent and prior-art databases for orchestration and deliberation mechanisms",
  "Do patents or published applications claim mechanisms this program intends to implement, and what "
  "is the factual landscape - recorded as a research finding with an explicit statement that it is "
  "not legal advice and triggers an owner decision if a hit is material?",
  ["patent and published-application databases"],
  ["RES-0108"], "prior-art-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 3600,
  S_CLAIM,
  EV_VERSIONED + "; every hit records the publication number, jurisdiction, status and claim number "
  "read; no interpretation of scope is offered, because that is legal analysis and out of scope",
  ["record publication number, jurisdiction, legal status and the specific claim read for each hit",
   "control: explicitly state that no scope interpretation is provided and none may be inferred"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "a hit register with publication numbers and statuses plus an explicit not-legal-advice statement")

u(119, "Conduct the lawful public-Tor sweep under the safety policy, or prove it adds nothing",
  "Does any lawful public onion-hosted source contain research material on this program's topics "
  "that is unavailable on the clear web - and if the honest answer is no, is that null result "
  "recorded so the capability is not built on an unexamined assumption?",
  ["_USER-PROMPTS.md:11280-11296 (the Tor safety policy)",
   "lawful public onion-hosted research indexes"],
  ["RES-0002"], "security-researcher", "anthropic", "opus", T_TOR, "local-serialized", 3600, S_CLAIM,
  EV_TWO_RAIL + "; every Tor-derived claim is LABELLED as such and corroborated on the clear web "
  "where possible; nothing is transacted, no access control is bypassed, no illegal content is "
  "collected, and the full egress log is attached",
  ["attach the complete egress log for the session",
   "control: a null result is an acceptable and expected outcome and must be reported as such",
   "policy check: confirm no accessed resource required authentication or payment"],
  RV_LEGAL, RT_GATED, F_GATED, True,
  "an attached egress log plus either labelled corroborated findings or an explicit null result")

u(120, "Teardown the closest whole-product competitor to this toolchain",
  "Which shipping product is the closest whole-product competitor to what this program is building, "
  "what does it do better, and what would a user of that product miss if they switched - the "
  "question a feature-by-feature comparison cannot answer?",
  ["the competitor product, its documentation and its user community"],
  ["RES-0108"], "competitive-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 5400,
  S_CLAIM,
  EV_TWO_RAIL + "; the teardown must name at least three things the competitor does BETTER, because "
  "a competitive analysis that finds only weaknesses is a marketing document",
  ["name at least 3 things the competitor does better, with evidence",
   "control: state which of this program's planned features the competitor already has"],
  RV_TWO, RT_GATED, F_GATED, True,
  "a teardown naming >=3 competitor advantages with evidence plus an overlap list against this "
  "program's planned features")

# ------------------------------------------- K. legal / licence / privacy / governance
u(121, "Read every upstream LICENSE file for the external candidate register and resolve NOASSERTION",
  "For the 189-candidate external register (E001-E189), what does each upstream LICENSE FILE "
  "actually say - closing the recorded gap that 19 rows are NOASSERTION, zero LICENSE files have "
  "been fetched, and blogs call BMAD-METHOD MIT while the classifier returns NOASSERTION?",
  [SHARDS + "/05-ECO-workflow-sources.md (E001-E189 register and licence risk table)",
   CORPUS + "/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json (45-entry internal risk register)"],
  ["RES-0003"], "license-analyst", "anthropic", "opus", T_CODE + ["WebFetch"], "local-parallel",
  5400, S_LIC,
  "every row records the LICENSE file's own identifying text and its sha256, never the platform "
  "classifier's label; the two are reported side by side and every disagreement is called out",
  ["fetch and hash the LICENSE file for every reachable candidate",
   "control: report the count of rows where the file disagrees with the classifier label",
   "the BMAD-METHOD and microsoft/autogen rows must be resolved explicitly as named test cases"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "a licence graph where every reachable row carries a LICENSE sha256, plus the resolved verdicts "
  "for the two named trap rows")

u(122, "Determine the attribution obligations when a workflow is DISTILLED rather than copied",
  "When a mechanism is reimplemented from a description rather than copied, what attribution and "
  "lineage obligations remain under each licence class present in the corpus (permissive, CC-BY, "
  "CC-BY-SA, CC-BY-NC, CC-BY-ND, GPL, trademarked method) - and which classes forbid the "
  "reimplementation itself?",
  ["RES-0121 licence graph",
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:166-170 (the licence classes present)"],
  ["RES-0121"], "license-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 3600, S_LIC,
  EV_TWO_RAIL + "; each obligation cites the licence text clause it derives from; the trademarked-"
  "method cases (implement the generic mechanism, do not name the feature) are handled explicitly",
  ["cite the clause for every stated obligation",
   "control: identify at least one class where reimplementation is the ONLY permitted route"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "a per-class obligation table with clause citations and the trademarked-method handling stated")

u(123, "Establish what vendor terms permit for cross-vendor orchestration and multi-account rails",
  "What do the applicable vendor terms say about programmatic invocation, cross-vendor orchestration "
  "and the multi-account rotation rails this estate already runs - and which planned behaviour is a "
  "genuine owner decision rather than an engineering one?",
  ["vendor terms of service for each rail this program uses"],
  ["RES-0002"], "governance-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 3600,
  S_CLAIM,
  EV_VERSIONED + "; each term is quoted verbatim with its effective date and retrieval sha256; the "
  "unit reports what the terms SAY and does not render a compliance verdict",
  ["quote the relevant clause verbatim with its effective date for every rail",
   "control: flag every clause whose plain reading conflicts with a currently running practice"],
  RV_LEGAL, RT_GATED, F_GATED, True,
  "verbatim dated clause quotes per rail plus an explicit list of conflicts with current practice")

u(124, "Determine the privacy and data-protection surface if this toolchain is ever published",
  "If this program's artifacts were published, what personal or estate-identifying data would leave "
  "with them (paths, usernames, transcripts, event ledgers), and what is the minimum scrubbing "
  "contract that makes publication safe?",
  ["this program's artifact set", "data-protection guidance"],
  ["RES-0001"], "privacy-analyst", "anthropic", "opus", T_LOCAL_RO + ["WebFetch"], "local-parallel",
  3600, S_CLAIM,
  EV_LOCAL2 + "; the scan is run over the ACTUAL artifact tree and reports counts by category; no "
  "discovered secret or personal value is reproduced in the output, only its location and category",
  ["run a categorized scan over the real artifact tree and report counts by category",
   "detector control: seed a synthetic identifier in a scratch file and confirm the scan finds it"],
  RV_SEC, RT_LOCAL, F_LOCAL + ["credential-redaction-required"], False,
  "a category-count scan over the real tree with a passing seeded-identifier detector control")

u(125, "Determine the provenance and licensing obligations for AI-generated blueprint content",
  "For blueprints and presets generated by models rather than written by a person, what provenance "
  "disclosure do the applicable vendor terms and emerging norms require, and what must the "
  "marketplace metadata carry?",
  ["vendor terms on generated output", "emerging provenance norms and standards"],
  ["RES-0123"], "license-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700, S_CLAIM,
  EV_VERSIONED + "; a norm that is proposed but not required is labelled as proposed, so the "
  "marketplace does not over-commit to an unadopted standard",
  ["label each obligation as required-by-terms, required-by-law-somewhere, or proposed-norm",
   "control: at least one item must land in proposed-norm"],
  RV_LEGAL, RT_STD, F_LEGAL, False,
  "an obligation table with a required-versus-proposed label per row")

u(126, "Determine what an export-control and dual-use review would flag in a security-adjacent toolchain",
  "Does a toolchain that includes reverse-engineering, security-scanning and automation capability "
  "raise any export or dual-use consideration worth an owner decision before publication - and what "
  "is the factual basis either way?",
  ["export control and dual-use guidance", "this program's capability inventory"],
  ["RES-0123"], "governance-analyst", "anthropic", "opus", T_WEB_BROAD, "local-parallel", 2700,
  S_CLAIM,
  EV_VERSIONED + "; the unit reports the factual landscape and the owner decision it triggers; it "
  "renders no legal conclusion and says so explicitly",
  ["state the factual basis for each flagged or not-flagged capability",
   "control: a NOT-FLAGGED outcome is acceptable and must be stated with its basis"],
  RV_LEGAL, RT_GATED, F_GATED, True,
  "a capability-by-capability factual basis with an explicit no-legal-conclusion statement")

u(127, "Resolve the two-tree corpus split so no research unit reads only half the evidence",
  "Which research-relevant artifacts exist ONLY in platform-redesign-2026-07-19 and which ONLY in "
  "harness-restore-20260806, and what is the union manifest every downstream unit must read to avoid "
  "the documented under-count?",
  [CORPUS, SHARDS,
   CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md:204-207 (the two-tree split)"],
  ["RES-0001"], "corpus-cartographer", "anthropic", "opus", T_LOCAL_RO + ["Bash(python)"],
  "local-serialized", 2700, S_REG,
  "the union and the two differences are COMPUTED by set operations over directory listings with "
  "content hashes, not eyeballed - and same-named files are compared by hash so a renamed-but-"
  "different pair is not counted as one",
  ["compute only-in-A, only-in-B and in-both-but-different by hash",
   "control: a file present in both with identical bytes must appear in exactly one bucket"],
  RV_MEAS, RT_LOCAL, F_LOCAL, False,
  "a computed three-way partition with hashes, where the in-both-identical bucket is disjoint from "
  "the differing bucket")

# ------------------------------------------------------------ L. bucket instrumentation
u(128, "Audit this research bucket for the source classes and questions it never touched",
  "Which of the spec's 16 source classes and 12 research modes did units RES-0001..RES-0127 actually "
  "exercise, which subjects were never read, and what is the ranked list of blind spots that must "
  "become work units in the second half of this bucket rather than being silently accepted?",
  ["the emitted records of RES-0001 through RES-0127",
   "_USER-PROMPTS.md:10683-10715 (the 16 source classes and 12 research modes)",
   "_USER-PROMPTS.md:11066-11082 (Phase 13 blind-spot questions)"],
  ["RES-0006", "RES-0108", "RES-0127"], "blind-spot-auditor", "openai", "codex-cli",
  T_PROTO + ["Read", "Grep"], "worktree-isolated", 3600, S_REG,
  "coverage is COMPUTED from the emitted records (which class and mode each unit actually used, read "
  "from its output, not from its plan) - a unit that PLANNED a source class but never cited one "
  "counts as not-covered, and that distinction is the point of this unit",
  ["compute per-class and per-mode coverage from emitted outputs, not from unit definitions",
   "control: a class deliberately covered by exactly one unit must show a count of exactly one",
   "every blind spot is emitted as a candidate unit definition, not as prose"],
  RV_TWO, RT_XV, F_XV + ["dependency-blocked"], False,
  "a computed coverage table over 16 classes and 12 modes plus a ranked blind-spot list where each "
  "entry is a draft unit definition")

# ================================================================== materialize
# Reorder the substrate block so the dependency graph is backward-only (and therefore
# trivially acyclic): the tool-sentinel detector probe must precede the evidence-tiering
# and snapshot units that depend on it.  Old -> new unit number, applied to numbers,
# dependency tokens and every id reference in prose.
_RENUM = {6: 2, 2: 3, 3: 4, 4: 5, 5: 6}
_REMAP = {"RES-0006": "RES-0002", "RES-0002": "RES-0003", "RES-0003": "RES-0004",
          "RES-0004": "RES-0005", "RES-0005": "RES-0006"}
_IDPAT = re.compile(r"RES-000[1-6]\b")


def _fix(text):
    return _IDPAT.sub(lambda m: _REMAP.get(m.group(0), m.group(0)), text)


for _s in U:
    _s["n"] = _RENUM.get(_s["n"], _s["n"])
    _s["deps"] = [_REMAP.get(d, d) for d in _s["deps"]]
    _s["inputs"] = [_fix(t) for t in _s["inputs"]]
    _s["q"] = _fix(_s["q"])
U.sort(key=lambda d: d["n"])

assert len(U) == 128, f"expected 128 authored units, got {len(U)}"
assert [x["n"] for x in U] == list(range(1, 129)), "unit numbers are not 1..128"

units = []
for spec in U:
    n = spec["n"]
    uid = "RES-%04d" % n
    inputs = [
        "command-center/sources/REGISTER.md",
        CORPUS + "/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    ] + spec["inputs"]
    units.append({
        "id": uid,
        "title": spec["title"],
        "phase": "2",
        "question_or_target": spec["q"],
        "inputs": inputs,
        "dependencies": spec["deps"],
        "assigned_model_vendor_role": {
            "model": spec["model"],
            "vendor": spec["vendor"],
            "role": spec["role"],
        },
        "tool_permissions": spec["tools"],
        "execution_substrate": spec["subst"],
        "timeout_seconds": spec["timeout"],
        "output_path": "command-center/research/%s.json" % uid,
        "output_schema": spec["schema"],
        "evidence_requirement": spec["evidence"],
        "tests_required": spec["tests"],
        "reviewer_requirement": spec["reviewer"],
        "completion_sentinel": "SUCCESS:%s in the receipt AND %s" % (uid, spec["postcond"]),
        "retry_policy": spec["retry"],
        "failure_classification": spec["fail"],
        "owner_approval_required": spec["owner"],
    })

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(units, fh, indent=2, ensure_ascii=True)
    fh.write("\n")

print("wrote", OUT, len(units))
