# Fleet Autonomy Pointer (2026-09-04)

AST pointer-only per **G-21B**. Do not treat this file as fleet SSOT.

## Canonical SSOT (QZP)

- Decision log: `quality-zero-platform/docs/plans/2026-09-04-fleet-autonomy-decision-log.md`
- Orchestration contract: `quality-zero-platform/docs/plans/2026-09-04-coverage-orchestration-contract.md`

## Coverage / e2e / loop lane (momentstudio)

- Coverage command: `momentstudio/.claude/commands/add-100-percent-behavioral-test-coverage-for-component.md`
- Paired e2e: `momentstudio/.claude/commands/run-component-paired-e2e.md`
- Matrix: `momentstudio/docs/plans/2026-09-04-component-coverage-e2e-matrix.md`
- Loop: `momentstudio/docs/plans/2026-09-04-coverage-autonomous-loop.md`

## Compose surfaces (do not rename)

- Keep `mcp-fleet-curation` as operator/local hygiene (G-17).
- `codex-fleet-github` remains one adapter.
- Future health skill id: **`repo-fleet-health`** (never `mcp-fleet-*`).

## Phase gate

Docs/commands only until G-20 flip. No fleet worker implementation from this pointer.
