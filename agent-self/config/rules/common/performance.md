---
paths:
  - "**/*"
---
# Performance Optimization

## Model Selection Strategy

This user values **quality over cost** — usage is not a constraint. Default **substantive
subagents to Opus** (memory: `feedback_opus_not_sonnet_subagents`); Sonnet's bare-minimum
output wastes more time than it saves. This overrides any generic cost-routing advice.

**Opus 4.8 / Fable 5** (deepest reasoning — the default for real work):
- ALL substantive subagents: coding, review, research, orchestration
- Complex architecture, maximum-reasoning, and analysis tasks

**Haiku 4.5** (fast + cheap — ONLY for trivial, high-frequency, mechanical steps):
- Throwaway lookups, simple format/lint passes, log triage
- NOT for coding, review, or any task where output quality matters

## Context Window Management

Avoid last 20% of context window for:
- Large-scale refactoring
- Feature implementation spanning multiple files
- Debugging complex interactions

Lower context sensitivity tasks:
- Single-file edits
- Independent utility creation
- Documentation updates
- Simple bug fixes

## Extended Thinking + Plan Mode

Extended thinking is enabled by default, reserving up to 31,999 tokens for internal reasoning.

Control extended thinking via:
- **Toggle**: Option+T (macOS) / Alt+T (Windows/Linux)
- **Config**: Set `alwaysThinkingEnabled` in `~/.claude/settings.json`
- **Budget cap**: `export MAX_THINKING_TOKENS=10000`
- **Verbose mode**: Ctrl+O to see thinking output

For complex tasks requiring deep reasoning:
1. Ensure extended thinking is enabled (on by default)
2. Enable **Plan Mode** for structured approach
3. Use multiple critique rounds for thorough analysis
4. Use split role sub-agents for diverse perspectives

## Build Troubleshooting

If build fails:
1. Use **build-error-resolver** agent
2. Analyze error messages
3. Fix incrementally
4. Verify after each fix
