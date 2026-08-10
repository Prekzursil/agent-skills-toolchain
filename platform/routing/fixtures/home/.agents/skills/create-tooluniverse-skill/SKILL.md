---
name: create-tooluniverse-skill
description: Create high-quality ToolUniverse skills following test-driven, implementation-agnostic methodology. Integrates tools from ToolUniverse's 1,264+ tool library, creates missing tools when needed, tests thoroughly, and produces skills with Python SDK + MCP support.
---

# Create ToolUniverse Skill

Systematic workflow for creating production-ready ToolUniverse skills.

## Core Principles

Build on the 10 pillars from `devtu (optimize-skills mode)`:
1. TEST FIRST - never document untested tools
2. Verify tool contracts - don't trust function names
3. Handle SOAP tools - add `operation` parameter
4. Implementation-agnostic docs - no Python/MCP code in SKILL.md
5. Foundation first - query aggregators before specialized tools
6. Disambiguate carefully - resolve IDs properly
7. Implement fallbacks - Primary -> Fallback -> Default
8. Grade evidence - T1-T4 tiers on claims
9. Quantified completeness - numeric minimums per section
10. Synthesize - models and hypotheses, not just lists

See `OPTIMIZE_INTEGRATION.md` for detailed application of each pillar.

## 7-Phase Workflow

| Phase | Duration | Description |
|-------|----------|-------------|
| 1. Domain Analysis | 15 min | Understand use cases, data types, analysis phases |
| 2. Tool Discovery | 30-45 min | Search, read configs, test tools (MANDATORY) |
| 3. Tool Creation | 0-60 min | Create missing tools via devtu (create-tool mode) |
| 4. Implementation | 30-45 min | Write python_implementation.py with tested tools |
| 5. Documentation | 30-45 min | Write SKILL.md (agnostic) + QUICK_START.md |
| 6. Validation | 15-30 min | Run test suite, validate checklist, manual verify |
| 7. Packaging | 15 min | Create summary, update tracking |

**Total**: ~1.5-2 hours (without tool creation).

### Phase 1: Domain Analysis

### Phase 2: Tool Discovery and Testing
### Phase 3: Tool Creation (If Needed)
### Phase 4: Implementation
### Phase 5: Documentation
### Phase 6: Validation
### Phase 7: Packaging
### Skill Integration
### Quality Indicators
### Reference Files
