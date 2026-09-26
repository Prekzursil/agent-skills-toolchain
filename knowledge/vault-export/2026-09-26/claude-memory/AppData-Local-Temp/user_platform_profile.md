---
name: drug-discovery-research-platform
description: User is building integrated drug-discovery research platform combining
  chemistry APIs, paper extraction, and social integrations
metadata:
  node_type: memory
  type: user
  originSessionId: d1df7745-a5b2-4780-9d24-2322ee655d44
permalink: main/claude-memory/app-data-local-temp/user-platform-profile
---

User building sophisticated multi-component research platform:

## Core Domains
- **Chemistry computing**: Schrödinger API, RDKit, SMILES↔3D conversion, molecular descriptors
- **Biomedical research**: ToolUniverse integration (2206+ tools), DDI/ADMET/CYP prediction
- **Literature extraction**: Paper retrieval, DOI→OA pipeline, Consensus.app data extraction
- **MCP server development**: Custom Schrödinger MCP, social MCPs (IG/FB/WA), ToolUniverse as stdio MCP
- **Agent skills**: Drug-discovery skills, research skills with evidence-grading, harm-reduction caveats

## Technical Infrastructure
- **Schrödinger** installed at `D:\Program Files\Schrodinger 2022-4` (env var: `$SCHRODINGER`)
- **ToolUniverse** v1.2.4/2.x pinned, 2206 biomedical tools
- **RDKit** v2026.3.3 for chemistry
- **Byteful proxy** (Romania, DIGI ISP) for sticky endpoints (100+ verified)
- **Classroom OAuth** for data access (round-trip verified, 3 courses)
- Social MCPs: Instagram (2FA session), Facebook, WhatsApp

## Execution Patterns
- Deterministic HTTP extraction (SSR JSON parsing)
- Round-trip verification (test with known compounds: ibuprofen descriptors, aspirin 3D)
- Background job pipelines (506+ papers, 260+ DOI→OA resolved)
- Resource optimization (aggressive RAM cleanup: freed 1.8GB+ via grep/Discord kill)
- Agent-skills-toolchain workflow for staging/committing

## Key Files/Locations
- `proof_empty/` workspace for paper extraction outputs
- `agent-skills-toolchain` repo for skills/docs staging
- Consensus searches: 515+ papers extracted via SSR, 19 interactions tracked