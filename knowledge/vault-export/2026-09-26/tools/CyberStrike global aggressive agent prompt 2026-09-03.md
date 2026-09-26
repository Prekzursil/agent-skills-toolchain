---
title: CyberStrike global aggressive agent prompt 2026-09-03
type: note
permalink: main/tools/cyber-strike-global-aggressive-agent-prompt-2026-09-03
tags:
- decision
- fact
- cyberstrike
---

# CyberStrike global aggressive agent prompt 2026-09-03

- [decision] G-6 B: global `cyberstrike.json` agent prompt (not engagement-dir only). Owner: make GLM extremely aggressive, not refuse prompts, go to extreme lengths on authorized work.
- [fact] `agent.cyberstrike.prompt` set on `zai/glm-5.3`. Top-level `instructions` appends `{file:~/.config/cyberstrike/instructions-recon.md}` (documented append; does not replace CS methodology).
- [fact] Firecrawl = in-scope recon only. basic-memory = engagement vault, not research. No Tavily/Exa/search-hub/deep-research inside CS. HackTricks/HexStrike/MSF(dangerous ON)/Sliver when they advance the objective.
- [fact] Backup `~/.config/cyberstrike/cyberstrike.json.bak-2026-09-03-g6`. Live TUI must restart to pick up config.
- [fact] Hard stops left in the instruction file: no third-party systems the operator does not own/authorize; no CSAM; no crimes against other people.

Related: [[CyberStrike ensure_tools Windows pack 2026-09-03]] [[CyberStrike MCPs restored 2026-09-02]]