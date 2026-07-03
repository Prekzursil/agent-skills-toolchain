# Live Truth Caveats

These notes are derived from controller and GitHub audits on 2026-03-23. Treat them as drift-prone and refresh them live before making claims.

### 2026-03-23 - mixed rollout state

- Source class: workflow review | controller repo audit | derived session summary
- Reusable lesson:
  - `quality-zero-platform` main is at `07703d5eb1a6c7a2a9a478f2b1cea9702788ad63`, but controller rollout is still partial.
  - The controller repo itself had no live GitHub ruleset at audit time.
  - Many enrolled repos also had no live ruleset yet.
  - Wrapper adoption and wrapper refs were mixed across the enrolled fleet.
- Guardrail or prompt consequence:
  - Always audit live rulesets and wrapper refs before claiming a repo is governed.
  - Do not infer fleet-wide success from local `bash scripts/verify` in the controller repo.
- Scope notes:
  - `Airline-Reservations-System` and `env-inspector` showed recent successful platform and gate runs.
  - `quality-zero-platform`, `DevExtreme-Filter-Go-Language`, and `Star-Wars-Galactic-Battlegrounds-Save-Game-Editor` still showed recent failing platform or gate runs.

### 2026-03-23 - provider and runner blockers are not code failures

- Source class: workflow review | repo postmortem | derived session summary
- Reusable lesson:
  - Local controller verification can pass tests and profile validation while provider-backed gates remain blocked by missing `SONAR_TOKEN` or `CODACY_API_TOKEN`.
  - Trusted-runner Codex auth and provider browser bootstrap are separate rollout lanes.
- Guardrail or prompt consequence:
  - Report provider/runner gaps as `blocked`.
  - Do not route those blockers into product-code remediation.
- Scope notes:
  - Use `docs/codex-private-runner-auth.md` and `docs/provider-browser-bootstrap.md` when the audit reaches those lanes.
