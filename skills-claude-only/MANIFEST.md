---
title: MANIFEST
type: note
permalink: dqverify-repo-20261013/skills-claude-only/manifest
---

# Claude-Only Skills Manifest

Skills that exist in ~/.agents/skills/ but NOT in ~/.codex/skills/.
These are Claude Code exclusive skills without Codex equivalents.

**Count**: 35 skills
**Synced**: 2026-04-03 23:05 UTC

| Skill | Description |
|---|---|
| `azure-observability` | Azure Observability Services including Azure Monitor, Application Insights, Log Analytics, Alerts, and Workbooks. |
| `azure-postgres` | Create new Azure Database for PostgreSQL Flexible Server instances and configure passwordless authentication with Microsoft Entra ID. |
| `azure-rbac` | Helps users find the right Azure RBAC role for an identity with least privilege access, then generate CLI commands and Bicep code to assign it. |
| `azure-resource-lookup` | List, find, and show Azure resources. |
| `azure-resource-visualizer` | Analyze Azure resource groups and generate detailed Mermaid architecture diagrams showing the relationships between individual resources. |
| `azure-storage` | Azure Storage Services including Blob Storage, File Shares, Queue Storage, Table Storage, and Data Lake. |
| `azure-validate` | Pre-deployment validation for Azure readiness. |
| `codecov-cli` | Upload and analyze code coverage reports using the Codecov CLI. |
| `digitalocean-cli` | Deploy and manage DigitalOcean resources using the doctl CLI. |
| `docker-cli` | Manage Docker containers, images, volumes, and networks using the Docker CLI. |
| `docs-research` | Gather official, up-to-date documentation and convert it into a concise implementation checklist for the current coding task. |
| `entra-app-registration` | Guides Microsoft Entra ID app registration, OAuth 2.0 authentication, and MSAL integration. |
| `find-skills` | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or e... |
| `graphql-cli` | Query GraphQL endpoints using curl or graphql-cli. |
| `mcp-troubleshooting` | Diagnose and fix MCP configuration/runtime issues across supported integrations using agents CLI checks. |
| `metaswarm-brainstorming-extension` | Enforces design review gate after brainstorming — bridges superpowers:brainstorming into the metaswarm quality pipeline |
| `metaswarm-create-issue` | Create comprehensive GitHub issues with TDD plans, acceptance criteria, and agent instructions for autonomous PR lifecycle management |
| `metaswarm-design-review-gate` | Automatic review gate that runs after brainstorming completes - spawns PM, Architect, Designer, Security, and CTO agents in parallel, iterates until a... |
| `metaswarm-external-tools` | Delegate implementation and review tasks to external AI CLI tools (Codex, Gemini) with cross-model adversarial review |
| `metaswarm-handling-pr-comments` | Address PR review feedback systematically — fetch inline comments, review bodies, handle outside-diff-range comments, resolve threads with proper at |
| `metaswarm-migrate` | Migrate from npm-installed metaswarm to the marketplace plugin — removes redundant files with safety checks |
| `metaswarm-orchestrated-execution` | 4-phase execution loop for work units - IMPLEMENT, VALIDATE, ADVERSARIAL REVIEW, COMMIT |
| `metaswarm-plan-review-gate` | Automatic adversarial review gate that spawns 3 independent reviewers in parallel after any plan is drafted - all must PASS before presenting to user |
| `metaswarm-pr-shepherd` | Monitor a PR through to merge — handle CI failures, review comments, and thread resolution automatically until all checks pass |
| `metaswarm-setup` | Interactive project setup — detects your project, configures metaswarm, writes project-local files |
| `metaswarm-start` | Use when starting work on any task, when the user mentions metaswarm, or when the user wants to begin tracked development work |
| `metaswarm-status` | Diagnostic status report — shows metaswarm installation state, project setup, and potential issues |
| `metaswarm-visual-review` | Take screenshots of web pages and UI using Playwright for visual review and iteration |
| `microsoft-foundry` | Deploy, evaluate, and manage Foundry agents end-to-end: Docker build, ACR push, hosted/prompt agent create, container start, batch eval, prompt optimi... |
| `ralph-hats` | Create, inspect, validate, explain, and improve Ralph hat collections. |
| `ralph-loop` | Run, monitor, resume, merge, and debug Ralph loops. |
| `ralph-orchestrator-setup` | Use when installing, updating, validating, or troubleshooting the local Ralph Orchestrator CLI, its MCP server registration, or the mirrored Ralph ski... |
| `read-github` | Read and search GitHub repository documentation via gitmcp.io MCP service. |
| `skill-guide` | Explain how to create, organize, and maintain skills in .agents/skills when the user asks about skills. |
| `superpowers` | (no SKILL.md found) |