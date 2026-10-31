---
name: recall-workflow-agent
description: Use when you need the exact input PROMPT or final OUTPUT of a specific subagent from a past Workflow / ultracode fan-out run — reviewing or recovering what one fanned-out agent (a lens, a verifier, the synthesizer) actually received or returned after the run scrolled off screen or the session compacted. Identify it by a distinctive phrase from its prompt or output, the workflow name, or by listing the run's agents.
---

# recall-workflow-agent

## Overview
Every Workflow subagent's full transcript is written to disk as JSONL. To get one agent's prompt + output you locate its `agent-<id>.jsonl` and read it — you do NOT re-run the workflow or ask the user. **The reliable locator is a distinctive PHRASE, because the readable agent label is not stored on disk.**

## Where it lives
```
~/.claude/projects/<project>/<session>/subagents/workflows/<wf_id>/
    journal.jsonl          # per agent: {type, key:<HASH>, agentId, result:<the OUTPUT>}
    agent-<agentId>.jsonl  # per agent: full transcript (prompt = its user msg; + turns)
~/.claude/projects/<OTHER-project>/<session>/workflows/scripts/<name>-<wf_id>.js   # the script (holds the labels)
```
**Gotcha:** the transcript dir is under the SESSION's project, which is frequently a *different* `<project>` than where the `.js` script lives. Never assume co-location — a phrase grep finds it wherever it is.

## Do this — the bundled tool locates + extracts + saves the files
```bash
S=~/.agents/skills/recall-workflow-agent/scripts/extract_workflow_agent.py
# best: a phrase you SAW in the output, or a phrase from the prompt/lens task:
python "$S" --phrase "Vaporware-filtered maturity table" --slug decision --print
# don't know a phrase? list every agent in the run (previewed by its report HEADLINE), then pick:
python "$S" --workflow multiai-orchestration-research --list
# scope a phrase to one run if it's ambiguous:
python "$S" --workflow <name> --phrase "<distinctive>"

### Identify by (most→least reliable)
### Common mistakes
