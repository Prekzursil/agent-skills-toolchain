---
name: feedback-full-rigor
description: Maintain full rigor — high effort AND high prompt quality — for research,
  subagent prompts, and syntheses; don't coast into thin status-tables or passive
  'awaiting notification' turns
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/feedback-full-rigor
---

Keep effort and prompt-quality HIGH and consistent across a whole session — especially for research, subagent/Codex prompts, and analytical syntheses. Do not let the work degrade into terse status-tables or passive turns that just say "awaiting the background agent."

**Why:** On 2026-05-28 (BC trainer-GUI P2 work) the user called out that my work had become less "serious and thorough in both effort and prompt quality" than earlier in the same session — "did you forget how well you used to work?" The likely triggers: (1) several consecutive turns that were thin summary tables ending in "I'll pick up when the agents land," which read as coasting rather than driving; (2) subagent prompts that were adequate but not as deep/specific as my best. This came right after a cost-hook had been making me cautious — which the user had explicitly overridden ("full power").

**How to apply:**
- When waiting on background work, KEEP DRIVING relevant work (e.g. the genuine open research items, durable artifacts) instead of just narrating status. Don't end a turn passively if there is real work I can advance.
- Research = look-up-don't-guess: cite the actual source (file path + line, or doc), grade confidence, and write a durable deliverable — never hand-wave from memory. (This mirrors the [[battlecats-event-summoner]] discipline that worked well earlier.)
- Subagent/Codex prompts must be deep and specific: exact files to read, exact questions, required output shape, evidence-grading, anti-guessing. Treat prompt quality as load-bearing.
- Syntheses should carry real analytical depth, not just a table of who-said-what.
- **Don't PARK unknowns — RESOLVE them.** If something is externally knowable (game mechanics, an API, a protocol, community-documented behavior), deploy the FULL research arsenal to settle it instead of writing "unknown" in a doc: the `deep-research` skill, `WebSearch`/`WebFetch`, exa/tavily/firecrawl, the browser, and a parallel subagent ARMY. The user explicitly wants this ("why aren't you heavily deep-researching whatever you don't know... as you did before?", 2026-05-28). Leaving a resolvable unknown un-researched is the lapse to avoid.
- This is about sustained quality, not volume — more subagents ≠ more rigor. Do the work properly. (Caveat: gate genuinely heavy tools — esp. the Chrome browser — on available host RAM; a memory-starved host already OOM-cascaded once this session.)