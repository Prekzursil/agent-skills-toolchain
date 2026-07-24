---
name: recall-workflow-agent
description: Use when you need the exact input PROMPT or final OUTPUT of a specific subagent from a past Workflow / ultracode fan-out run - reviewing or recovering what one fanned-out agent (a lens, a verifier, the synthesizer) actually received or returned after the run scrolled off screen or the session compacted. Identify it by a distinctive phrase, the workflow name, or by listing the run's agents.
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
```
Prompt is saved to `<slug>-PROMPT.md`, output to `<slug>-OUTPUT.md`. The tool takes the output from the journal `result` (the authoritative captured return), so it's clean even for tool-using agents.

## Identify by (most→least reliable)
1. A phrase from the **OUTPUT you saw** in the UI — unique, best.
2. **`--list`** the workflow's agents (each previewed by its report headline) → pick.
3. A phrase from the **PROMPT / lens task** — works, but read the synthesizer gotcha below.

## Common mistakes
- **Grepping the agent label** (`synthesize:multiai-decision`): it is NOT in the transcript or journal — journal stores a hashed `key`; labels live only in the `.js` script. Grep a content phrase instead.
- **Searching only under the script's project dir** → 0 files. Grep across ALL of `~/.claude/projects` (the tool does).
- **Fanning out the Grep TOOL across `~/.claude/projects`:** on Windows it can die with `ENAMETOOLONG` (giant argv over thousands of files). Use the bundled tool (Python glob + line scan) or `rg` via Bash — not the Grep tool.
- **A lens phrase matching two agents:** a SYNTHESIZER's prompt embeds every upstream agent's report verbatim, so a lens name/tag hits the lens agent AND the synthesizer. Use a phrase from that lens's OWN narration/output, or `--list` and pick by preview. The tool reports every match so you can narrow.
- **Decoy — your OWN current session's subagents:** Agent-tool subagents live at `subagents/agent-*.jsonl` (NO `workflows/<wf_id>/` layer). If your task text quotes the workflow name/phrase they self-match. The tool's glob requires `.../subagents/workflows/<wf_id>/agent-*.jsonl`, so it excludes them — a manual grep won't.
- **Treating joined assistant turns as "the output":** tool-using agents interleave narration between tool batches. The real output is journal `result` (final return) — what the tool uses.
- **content is a string OR a list of `{type:text}` blocks** — handle both (the tool does).
```
