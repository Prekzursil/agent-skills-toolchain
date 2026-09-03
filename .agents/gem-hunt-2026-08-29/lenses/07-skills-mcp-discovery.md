# Lens 07 — multi-registry skills, MCP, CLI and library discovery

**Date:** 29.08.2026  
**Scope:** discovery only; no package, skill, MCP, daemon, or hook was installed or enabled.

## Executive result

Ten candidates survived deduplication, but **no new MCP server should be registered**. The best
returns are on-demand CLIs and small pattern borrows that ride the existing skill, CI, and MCP
audit surfaces:

1. add official MCP conformance tests and Inspector CLI diagnostics to the existing MCP audit;
2. use `gh skill` and the official MCP Registry API as read-only discovery/provenance inputs;
3. fold Hugging Face Jobs and its generated CLI reference into `hosted-model-agents`;
4. trial `rumdl`, `lychee`, and `prek` as single-process quality tools;
5. borrow provenance gates from `github/awesome-copilot` and evaluation mechanics from
   `huggingface/upskill` without adopting either as another runtime.

The official registry searches were also useful negative evidence: skill-search MCPs duplicate
`skill-scout`, Markdown MCPs duplicate local file/document tooling, and a Markdown-vault server
would violate both the duplicate-vector-store and always-on-daemon walls.

## Ground and dedup set

Read before discovery:

- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`;
- `C:\Users\Prekzursil\.agents\agents.json` (40-server-class estate, including GitHub, Context7,
  Firecrawl, Hugging Face Hub, Playwright, basic-memory, agent-mail, quality tools, and specialist
  servers);
- all **380** `SKILL.md` files under `C:\Users\Prekzursil\.agents\skills`;
- relevant local implementations: `mcpctl`, `mcp-manager`, `agentspec`, seven
  `ci/check_skill_*.py` gates, `skill-scout`, `skill-stocktake`, `writing-skills`,
  `mcp-fleet-curation`, `mcp-server-patterns`, and `hosted-model-agents`.

Important dedup findings:

- OpenAlex/Crossref/Unpaywall are already covered by `citation-mapping`, scholarly-research
  skills, ToolUniverse, and direct REST guidance.
- MCP Inspector is mentioned in `chatgpt-apps`, but there is no estate-wide, pinned Inspector or
  protocol-conformance gate.
- Hugging Face Hub MCP and `hosted-model-agents` already exist; the missing delta is the current
  `hf` CLI/Jobs surface, not another Hub server.
- The repository has no `.pre-commit-config.yaml`, `rumdl`, `lychee`, or `prek` integration.
- Skill authoring already has custom render, description-budget, dual-write, inventory, deploy,
  and vendor-substitution gates. A generic validator must therefore add a distinct check rather
  than replace these estate-specific controls.

## Sources swept

- GitHub-native structure and changelogs: GitHub CLI `gh skill`, `github/awesome-copilot`,
  `huggingface/skills`, and candidate repositories.
- Package registries: npm, PyPI, and crates.io release metadata.
- MCP discovery: official Registry v0.1 API queries for `skills` and `markdown`, official Registry
  docs, Inspector, and conformance repositories.
- Hugging Face: Hub/CLI/Jobs documentation, `huggingface_hub`, `huggingface/skills`, and
  `huggingface/upskill`.
- Vendor/early signal: GitHub and Hugging Face changelogs, official MCP release notes, upstream
  CI/test manifests, and registry metadata. Registry entries were treated as self-reported
  metadata, not endorsements.

## Ranked decision queue

| Rank | Candidate | Kind | REC | Value × effort | Confidence |
|---:|---|---|---|---|---|
| 1 | MCP conformance runner | CLI/test library | ADOPT-PINNED | very high × medium | high |
| 2 | `gh skill` discovery + validation | native CLI | ADOPT-DELTA | high × low | high |
| 3 | HF CLI skill + Jobs commands | skill/CLI | ADOPT-AS-FOLD | very high × low | high |
| 4 | Official MCP Registry incremental feed | API/discovery substrate | ADOPT-AS-LENS | high × low | high |
| 5 | `rumdl` | CLI | TRIAL | high × low | high |
| 6 | `lychee` | CLI/library | TRIAL | high × low | high |
| 7 | MCP Inspector v2 CLI | CLI | ADOPT-ON-DEMAND | medium-high × low | high |
| 8 | `prek` | CLI | TRIAL-NARROW | medium-high × medium | high |
| 9 | Awesome Copilot intake gates | pattern donor | BORROW-ONLY | high × low | high |
| 10 | Hugging Face `upskill` eval mechanics | pattern donor | BORROW-ONLY | medium-high × medium | medium |

## Candidate dossiers

### 1. Official MCP conformance runner

- **What:** `@modelcontextprotocol/conformance`, the steering-project scenario suite for clients
  and servers, with suites, protocol-version selection, expected-failure baselines, and machine
  artifacts.
- **Maintenance:** official Model Context Protocol project; frequent 0.1.x releases and active
  0.2 alpha work. Stable `0.1.16` and the 0.2 alpha line were visible on 29.08.2026.
- **License:** MCP project transition: existing MIT code, new code Apache-2.0; documentation
  CC-BY-4.0.
- **Tests/examples:** the repository is itself an executable conformance corpus; docs show server
  and client scenarios, `--suite`, `--spec-version`, `--requirements`, output directories, and
  expected-failure YAML. Releases include Windows-compatibility fixes.
- **Maturity:** useful but pre-1.0. Stable 0.1.x principally covers the previous dated protocol;
  2026-07-28 coverage is in the 0.2 alpha line, so current-spec enforcement should begin as a
  pinned advisory matrix.
- **Concrete borrow line:** add a disposable-server job to `.github/workflows/mcp-audit.yml`:
  pinned stable suite as the baseline, plus a pinned 0.2-alpha current-spec advisory lane. Store
  raw output and reviewed expected failures. A newly failing scenario **and a stale expected
  failure that starts passing** must both be visible. Do not claim “MCP certified.”
- **Why this estate:** `mcpctl` measures inventory/topology and `agents mcp test --runtime`
  measures runtime reachability; neither proves wire-protocol behavior.
- **Source:** <https://github.com/modelcontextprotocol/conformance>

### 2. GitHub CLI `gh skill`

- **What:** GitHub-native skill search, preview, install, update, provenance pinning, and publish
  validation, available in GitHub CLI 2.90+.
- **Maintenance:** part of `github/gh-cli`; v2.97.0 documentation was current, releases are
  immutable from v2.93.0, and release artifacts carry build provenance attestations.
- **License:** MIT (GitHub CLI); dependency licenses are embedded and inspectable with
  `gh licenses`.
- **Tests/examples:** Go unit tests plus black-box acceptance tests; official examples cover
  `search`, `preview`, pinned install, custom `--dir`, and `publish --dry-run`.
- **Maturity:** public preview since 16.04.2026; interface can still change.
- **Concrete borrow line:** extend `skill-scout` to use `gh skill search` and
  `gh skill preview` before generic web search. Stage any chosen donor with
  `gh skill install ... --dir <temporary-review-dir> --pin <tag-or-SHA>`; never install directly
  into the live or canonical skill roots. Add `gh skill publish --dry-run <repo>` as a packaging
  preflight, while retaining all custom estate gates.
- **Why this estate:** it adds provenance and GitHub-native discovery without a new MCP or daemon.
- **Source:** <https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/>

### 3. Hugging Face CLI skill and Jobs surface

- **What:** official `hf` CLI reference skill plus `hf jobs` for Docker/UV jobs, logs, stats,
  waiting, timeouts, secrets, scheduling, and resource-group cost attribution.
- **Maintenance:** `huggingface_hub` is the official client; PyPI 1.29.0 was current on
  29.08.2026. `huggingface/skills` is vendor-maintained and the CLI skill is generated from the
  installed command surface.
- **License:** Apache-2.0 for both `huggingface_hub` and `huggingface/skills`.
- **Tests/examples:** `huggingface_hub` has a mature pytest suite and extensive command docs;
  Jobs guides include blocking/non-blocking failure semantics, `wait --timeout`, logs, stats,
  Docker and UV examples. The skills repository has validation/publishing automation and examples.
- **Maturity:** core client is mature; Jobs and skill management are active, vendor-supported
  surfaces. Account/compute costs and tier availability remain external constraints.
- **Concrete borrow line:** diff the generated `hf-cli` skill against the local installed CLI and
  fold only the Jobs/cache/Spaces deltas into `hosted-model-agents` references. Add a fail-closed
  recipe: detached job ID → `hf jobs wait --timeout ...` → logs/stats → artifact existence check.
  Do **not** run `hf skills add --global`, because `.agents\skills` is the estate SSOT and automated
  vendor writes would create drift.
- **Why this estate:** remote jobs directly relieve the machine's RAM constraint and reuse the
  existing HF token/control plane.
- **Sources:** <https://huggingface.co/docs/huggingface_hub/en/guides/cli> and
  <https://huggingface.co/docs/huggingface_hub/guides/jobs>

### 4. Official MCP Registry v0.1 incremental feed

- **What:** unauthenticated canonical metadata API for MCP server names, packages, remotes,
  status, and update timestamps.
- **Maintenance:** official MCP working-group repository, roughly 7k GitHub stars, active releases,
  and backing from the MCP project.
- **License:** Registry code follows the MCP MIT→Apache-2.0 transition; documentation is
  CC-BY-4.0; submitted registry metadata is CC0.
- **Tests/examples:** upstream exposes unit, integration, endpoint, publish, and all-test Make
  targets. Official docs show cursor pagination, `search`, `version=latest`, `updated_since`, and
  deletion reconciliation.
- **Maturity:** Registry is still preview, but v0.1 has an API-freeze history. It explicitly
  provides no curation, uptime, or durability guarantee.
- **Concrete borrow line:** add a **per-hunt, one-shot** registry collector to the gem-hunt
  research workflow. Persist the prior `_meta.updatedAt` high-water mark, page with
  `updated_since`, retain `include_deleted=true`, and write a raw JSON receipt beside the lens.
  Rank only after repository/package/license/test verification. Use direct HTTP/stdlib; do not add
  the young third-party `mcp-registry-sdk` or run a local registry.
- **Why this estate:** gives repeatable MCP delta discovery without another MCP in the catalogue
  and without an always-on aggregator.
- **Source:** <https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md>

### 5. `rumdl`

- **What:** Rust Markdown linter/formatter with GFM, MkDocs, MDX, Quarto, and MyST awareness,
  distributed as a single Windows binary and on PyPI/crates.io.
- **Maintenance:** v0.2.62 released on 29.08.2026; about 1.3k GitHub stars, active changelog and
  release cadence.
- **License:** MIT.
- **Tests/examples:** blocking CI, cargo-nextest profiles, roughly 110 test binaries consolidated
  into a faster suite, formatter idempotency/property tests, usage docs, and a GitHub Action.
- **Maturity:** explicitly beta, although the core CLI/rules are described as production-usable.
  Rapid release cadence means pinning is mandatory.
- **Concrete borrow line:** trial a pinned Windows binary in **check-only** mode over canonical
  Markdown, initially excluding generated projections and disabling line-length/table rules that
  conflict with long skill references. Establish and review a baseline before making it blocking;
  do not run bulk `--fix` over the 380-skill vault.
- **Why this estate:** Markdown is the estate's executable configuration language, but current
  gates mostly validate frontmatter, drift, and bespoke traps rather than general Markdown
  integrity.
- **Source:** <https://github.com/rvben/rumdl>

### 6. `lychee`

- **What:** fast async link checker for Markdown, HTML, reStructuredText, websites, and mail
  addresses; available as CLI, Rust library, and Action.
- **Maintenance:** v0.24.2 published 01.05.2026; about 3.8k GitHub stars, 42 releases, active image
  and package distribution.
- **License:** Apache-2.0 OR MIT.
- **Tests/examples:** CI; `cargo nextest` across targets/features plus doc tests; seven example
  groups; pre-commit and Action examples.
- **Maturity:** established since 2020 and cross-platform, including Windows binaries/WinGet.
- **Concrete borrow line:** add two non-daemon phases: blocking local relative-link validation on
  changed canonical skills, then a scheduled/nonblocking external-URL audit with caching, retries,
  and explicit allowlists for login/paywall/429 endpoints. Promote external failures to blocking
  only after a reviewed baseline.
- **Why this estate:** 380 skills carry many external and internal references; stale links silently
  degrade future agent behavior.
- **Source:** <https://github.com/lycheeverse/lychee>

### 7. MCP Inspector v2 CLI

- **What:** official MCP web, TUI, and scriptable CLI inspector; only the CLI mode is proposed.
- **Maintenance:** about 9k GitHub stars; v2.2.0 released 12.08.2026; active v2 roadmap and
  milestone branch.
- **License:** MCP MIT→Apache-2.0 transition; docs CC-BY-4.0.
- **Tests/examples:** unit tests plus launcher, CLI/TUI, production-web, Chromium, MCP Apps, and
  elicitation smoke tests.
- **Maturity:** v2 released and active; richer web/TUI modes are unnecessary for routine estate
  checks.
- **Concrete borrow line:** pin `@modelcontextprotocol/inspector@2.2.0` and expose a documented
  one-shot CLI diagnostic from the existing MCP audit for a server that fails runtime health.
  Start no persistent Inspector web process and add no Inspector entry to `agents.json`.
- **Why this estate:** complements conformance with fast interactive/agent-readable diagnosis,
  while preserving the no-daemon rule.
- **Source:** <https://github.com/modelcontextprotocol/inspector>

### 8. `prek`

- **What:** Rust, single-binary, pre-commit-compatible hook runner with shared toolchains,
  monorepo mode, and Windows support.
- **Maintenance:** v0.4.14 published 17.08.2026; about 8.2k GitHub stars; adopted by CPython,
  Airflow, FastAPI, and other substantial projects.
- **License:** MIT.
- **Tests/examples:** large cargo-nextest/cargo-llvm-cov CI matrix including Windows, Codecov,
  quickstart/cookbook, a pinned GitHub Action, and signed/attested container images.
- **Maturity:** still pre-1.0 but has meaningful production adoption and active releases.
- **Concrete borrow line:** trial `prek run --all-files` as a **project-local command runner** for
  `agent-skills-toolchain` checks after first creating a minimal reviewed config. Do not install
  global Git shims, replace Claude/Cursor lifecycle hooks, or auto-update revisions. Use
  `--cooldown-days` and immutable hook SHAs when update automation is later considered.
- **Why this estate:** a single process can coordinate heterogeneous existing checks with less
  startup and disk cost on a memory-constrained Windows host.
- **Source:** <https://github.com/j178/prek>

### 9. `github/awesome-copilot` intake and provenance gates

- **What:** GitHub-maintained community collection; the candidate is its intake discipline, not
  its large content catalogue.
- **Maintenance:** about 36k GitHub stars and active August 2026 changes.
- **License:** MIT for repository/community contributions.
- **Tests/examples:** generated-index drift checks, content validators, external-plugin smoke
  tests, immutable locator rules, and recent tests for SemVer, SPDX expressions, unknown fields,
  and committed-registry regressions.
- **Maturity:** mature catalogue mechanics; individual community entries still vary and need
  independent review.
- **Concrete borrow line:** extend `skill-scout`/marketplace intake records with source repo,
  immutable tag/full SHA, tree hash, SemVer, SPDX expression, and unknown-field warnings. Require
  a reviewed diff between old and new refs before updating a donor. Do not install
  `awesome-copilot` wholesale.
- **Why this estate:** the canonical vault already has provenance/drift incidents; immutable donor
  locators close a real supply-chain and reproducibility gap.
- **Source:** <https://github.com/github/awesome-copilot>

### 10. Hugging Face `upskill` evaluation mechanics

- **What:** skill generation/evaluation CLI with baseline-vs-skill comparisons, repeated runs,
  multi-model benchmarks, custom test cases, and HF Jobs artifact capture.
- **Maintenance:** Hugging Face repository remains active; PyPI 0.2.1 is from 28.01.2026, so
  package cadence lags repository work.
- **License:** Apache-2.0.
- **Tests/examples:** pytest plus Ruff, `ty`, complexity and duplication checks; repository includes
  tests, smoke scripts, sample configuration, and detailed eval examples.
- **Maturity:** early, Python 3.13-only package range, and it depends on `fast-agent-mcp`.
- **Concrete borrow line:** copy only the evaluation design into the existing
  `writing-skills`/`agentspec.evals` path: explicit no-skill baseline, N repeated trials,
  per-model result matrix, and disk-verified artifacts. **Do not install the runtime**: its
  `fast-agent-mcp` dependency would introduce a second agent execution stack and overlap the
  existing TDD/eval harness.
- **Why this estate:** it strengthens the current qualitative skill-pressure tests without
  violating the orchestrator wall.
- **Source:** <https://github.com/huggingface/upskill>

## MCP registry verdict: no server registration

The official Registry returned 30 `skills` matches and 23 `markdown` matches. None survives:

- `skills-search`, `skill-of-skills`, `getskills`, `qaskills`, `local-skills-mcp`, and similar
  servers duplicate native file loading, `skill-scout`, GitHub search, and the new `gh skill`
  path. They add catalogue/tool-schema tax and several can install content directly.
- `markdown-vault-mcp` includes FTS/embeddings, persistence, file watching, background jobs, and
  optional Ollama/FastEmbed: a direct duplicate of basic-memory plus a resident daemon.
- Markdown conversion/render/share servers duplicate local file operations, Firecrawl/Docling/
  reframe/document skills, or add SaaS keys/pay-per-call. Small local lint/links CLIs are cheaper
  and inspectable.
- Registry publication proves namespace ownership, not maintenance, safety, or quality. Many
  results were 0.1/1.0 single-publisher entries with no repository, license, or tests.

## Explicit skip-wall decisions

| Rejected | Reason |
|---|---|
| `gh-aw`, agent-harness packages, orchestration MCPs | second orchestrator/runtime |
| `markdown-vault-mcp`, local-skills vector indexes | duplicate vector DB/memory and/or daemon |
| Langfuse or another observability service | standing skip; existing local evidence paths |
| OpenRouter MCP, LiteLLM, Cursor BYOK | standing routing wall |
| `skills-ref` from PyPI | upstream labels it demonstration-only; PyPI ownership/version history was disputed; `gh skill publish --dry-run` plus estate-specific gates is safer |
| `mcp-registry-sdk` 0.1.0 | five-line direct REST use is sufficient; no need for another dependency or persistent sync store |
| Hugging Face Hub MCP/inference MCP | Hub MCP already exists; inference URLs remain runtimes, not MCPs |
| `upskill` runtime | depends on another agent stack; borrow mechanics only |
| `markdownlint-cli2` | credible mature alternative, but `rumdl` is a lower-runtime-cost Windows trial; do not install both |
| Offensive-security directories and servers | explicitly out of scope |

## Recommended adoption order

1. **No-install folds:** update `skill-scout` with `gh skill` preview/pinning and immutable donor
   metadata; update gem-hunt with official Registry incremental receipts; fold HF Jobs into
   `hosted-model-agents`.
2. **Protocol quality:** pinned MCP conformance advisory lane, then Inspector CLI as the
   diagnosis path for failures.
3. **Content quality trials:** `rumdl` check-only, then `lychee` local links; baseline before
   either blocks.
4. **Execution-cost trial:** use `prek` only after the existing checks have a reviewed project
   config; no global hook installation.
5. **Later borrow:** add repeated baseline/multi-model skill evals without installing `upskill`.

UNIT-COMPLETE: lens-07
