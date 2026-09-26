---
name: QZP pre-existing platform gates — tolerated by admin-merge
description: The platform CI self-tests against its own zero-gate scanners; four gates
  always fail on every PR because the platform repo itself lacks the secrets and has
  an internal Codacy-reporter path bug
type: project
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/project-qzp-preexisting-gates
---

quality-zero-platform's CI runs the same zero-gate scanners it provides to consumer repos, but the platform repo itself is missing several secrets/configs, so 4-5 checks are permanently red on every PR regardless of the PR's content.

**Persistently failing on every PR (pre-existing, tolerated via admin-merge):**

- **SonarCloud Code Analysis** — "0.0% Coverage on New Code" fails because the SonarCloud scanner reads `coverage.xml` but CI writes `coverage/platform-coverage.xml`. Fixed in `sonar-project.properties` but SonarCloud's delta-coverage seems to still flag.
- **shared-scanner-matrix / Coverage 100 Gate** — fails because the Codacy Coverage Reporter step reads from workspace-root `coverage/platform-coverage.xml` but CI wrote it to `repo/coverage/platform-coverage.xml`. Path mismatch in the reusable-scanner-matrix workflow.
- **shared-scanner-matrix / DeepSource Visible Zero** — fails with "GITHUB_TOKEN or GH_TOKEN is required"; the zero-gate script needs a token the platform CI doesn't expose as an env var.
- **shared-quality-zero-gate / Quality Zero Gate** — rollup job that fails if any scanner-matrix lane fails, so always red when the above are red.

**Sometimes failing (config-dependent):**

- **shared-scanner-matrix / Codacy Zero** — "CODACY_API_TOKEN is missing"
- **shared-scanner-matrix / Sonar Zero** — "SONAR_TOKEN is missing"

**How to apply:** Phase 1 (PR #88) merged `--admin` with these same gates red. Phase 2 (PR #89) can do the same as long as NEW issues (Codacy issues delta, DeepSource Python/Secrets, qlty duplications) are all resolved. The 4-5 pre-existing gates don't block the phase-merge cadence.

**Eventual fix:** The platform's own CI workflows need a config refresh (fix the coverage path, provision the GitHub/Codacy/Sonar tokens as GitHub secrets) in a dedicated cleanup PR — not part of the QZP v2 rollout.