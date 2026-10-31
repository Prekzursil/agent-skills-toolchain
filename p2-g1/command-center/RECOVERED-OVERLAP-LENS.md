# Recovered overlap lens -- are the 328 skills actually duplicates?

RECOVERED, not re-run. The sixth lens of the fleet audit was stopped before it journalled a
result, so by the workflow's own record it produced nothing. It had already written its probe
output to `C:\Users\Prekzursil\.claude\_lens_overlap_pairs.json` -- 8,049 bytes of measured pair data. A journal row
proves an agent finished; it does not bound what the agent left on disk.

## Verdict

**No textual duplication exists in the fleet.** Across all 57 candidate pairs the
maximum body overlap is **0.185** and the median is **0.006**, against a
merge floor of 0.30 -- so **0 pairs** clear that floor.
The floor sits 0.115 above the highest value actually measured, which is what makes
the zero meaningful rather than a threshold artefact.

Meanwhile **34 pairs** score >= 0.35 on description similarity.
That is the trap: the pairs LOOK like duplicates in the always-loaded index and then diverge
almost completely in what they contain. Consolidating on description similarity would destroy
content instead of removing redundancy.

The owner's condition was explicit -- make sure no ability is lost. On this evidence the
answer to "can they be consolidated into only one or so" is **no**, and the productive work
is description quality (a negative case naming the sibling to use instead), not consolidation.

## Honest limit, inline

`body_jac` is a token-level Jaccard index. A low value refutes **textual** duplication only.
Two skills could do the same job in different words and still score near zero, so this does
NOT prove functional non-redundancy. The settling experiment is reading both bodies -- which
the destructive-default rule already requires before any merge, and which this does not do.
Confidence: almost-certain (90-99%) on the arithmetic; likely (55-80%) that no pair in the
fleet is functionally redundant, since low token overlap is strong but indirect evidence.

## The pairs, ranked by how much they LOOK alike

| desc_cos | body_jac | lines A / B | pair |
|---|---|---|---|
| 0.868 | 0.105 | 5,528 / 3,619 | `claude-devfleet` <-> `source-command-devfleet` |
| 0.691 | 0.018 | 1,666 / 2,836 | `source-command-instinct-export` <-> `source-command-instinct-import` |
| 0.640 | 0.080 | 7,108 / 2,024 | `cloudflare-deploy` <-> `vercel-deploy` |
| 0.616 | 0.028 | 1,666 / 1,290 | `source-command-instinct-export` <-> `source-command-promote` |
| 0.554 | 0.081 | 2,836 / 1,290 | `source-command-instinct-import` <-> `source-command-promote` |
| 0.511 | 0.065 | 6,993 / 2,024 | `netlify-deploy` <-> `vercel-deploy` |
| 0.498 | 0.028 | 17,782 / 2,024 | `render-deploy` <-> `vercel-deploy` |
| 0.490 | 0.006 | 5,484 / 2,940 | `reverse-engineering-toolkit` <-> `swfoc-reverse-engineering` |
| 0.478 | 0.004 | 16,390 / 7,133 | `python-patterns` <-> `source-command-python-review` |
| 0.458 | 0.032 | 1,666 / 1,547 | `source-command-instinct-export` <-> `source-command-instinct-status` |
| 0.454 | 0.047 | 7,108 / 6,993 | `cloudflare-deploy` <-> `netlify-deploy` |
| 0.454 | 0.024 | 7,108 / 17,782 | `cloudflare-deploy` <-> `render-deploy` |
| 0.434 | 0.006 | 10,221 / 4,253 | `schrodinger-maestro-driver` <-> `structure-based-screening` |
| 0.423 | 0.012 | 1,066 / 1,122 | `ghidra-mcp` <-> `ida-pro-mcp` |
| 0.414 | 0.005 | 1,159 / 1,864 | `hexstrike-ai-setup` <-> `ralph-orchestrator-setup` |
| 0.412 | 0.071 | 2,836 / 1,547 | `source-command-instinct-import` <-> `source-command-instinct-status` |
| 0.407 | 0.120 | 1,547 / 1,290 | `source-command-instinct-status` <-> `source-command-promote` |
| 0.403 | 0.004 | 1,802 / 24,960 | `design-review-loop` <-> `design-studio` |
| 0.403 | 0.000 | 3,612 / 3,250 | `source-command-plan` <-> `writing-plans` |
| 0.401 | 0.000 | 1,348 / 1,159 | `hexstrike-ai-mcp` <-> `hexstrike-ai-setup` |
| 0.399 | 0.000 | 2,686 / 2,100 | `social-dm-search` <-> `social-find-post` |
| 0.398 | 0.006 | 1,137 / 1,216 | `binary-ninja-mcp` <-> `frida-mcp` |
| 0.395 | 0.001 | 2,798 / 8,052 | `capa-triage` <-> `malware-analysis-triage` |
| 0.395 | 0.000 | 706 / 1,526 | `nanoclaw-repl` <-> `source-command-claw` |
| 0.389 | 0.022 | 2,480 / 10,056 | `executing-plans` <-> `subagent-driven-development` |
| 0.379 | 0.018 | 1,137 / 1,122 | `binary-ninja-mcp` <-> `ida-pro-mcp` |
| 0.371 | 0.001 | 18,398 / 12,064 | `agentic-humanizer` <-> `slop-check` |
| 0.368 | 0.005 | 1,178 / 3,216 | `sec-corpora-update` <-> `secsearch` |
| 0.363 | 0.022 | 6,993 / 17,782 | `netlify-deploy` <-> `render-deploy` |
| 0.362 | 0.009 | 1,216 / 1,066 | `frida-mcp` <-> `ghidra-mcp` |
| 0.362 | 0.003 | 1,216 / 1,122 | `frida-mcp` <-> `ida-pro-mcp` |
| 0.362 | 0.000 | 3,658 / 3,663 | `playwright` <-> `webapp-testing` |
| 0.356 | 0.005 | 1,447 / 1,159 | `digitalocean-mcp-setup` <-> `hexstrike-ai-setup` |
| 0.355 | 0.015 | 3,763 / 3,695 | `oa-pdf-retrieval` <-> `scholarly-literature-review` |
| 0.348 | 0.034 | 1,337 / 3,216 | `hacktricks` <-> `secsearch` |
| 0.348 | 0.021 | 4,426 / 4,553 | `code-security` <-> `llm-security` |
| 0.346 | 0.000 | 24,500 / 1,351 | `autonomous-loops` <-> `ralphinho-rfc-pipeline` |
| 0.345 | 0.005 | 1,297 / 2,807 | `chatgpt5-web` <-> `codex-consult` |
| 0.339 | 0.000 | 32,155 / 3,663 | `playwright-interactive` <-> `webapp-testing` |
| 0.334 | 0.011 | 1,216 / 1,310 | `frida-mcp` <-> `mcp-graphql` |
| 0.329 | 0.000 | 3,226 / 10,093 | `notion-spec-to-implementation` <-> `test-driven-development` |
| 0.328 | 0.000 | 1,734 / 1,447 | `digitalocean-app-platform-ops` <-> `digitalocean-mcp-setup` |
| 0.326 | 0.000 | 1,371 / 1,348 | `hexstrike-ai-authorized-engagement` <-> `hexstrike-ai-mcp` |
| 0.324 | 0.015 | 1,313 / 1,113 | `binary-ninja-diff-signatures` <-> `binja-sigmaker` |
| 0.321 | 0.011 | 1,447 / 1,864 | `digitalocean-mcp-setup` <-> `ralph-orchestrator-setup` |
| 0.317 | 0.000 | 1,344 / 2,940 | `cheat-engine-x64dbg-ida-handoff` <-> `swfoc-reverse-engineering` |
| 0.317 | 0.000 | 3,658 / 32,155 | `playwright` <-> `playwright-interactive` |
| 0.315 | 0.013 | 9,742 / 7,986 | `voice-analyze` <-> `voice-create` |
| 0.313 | 0.001 | 967 / 5,484 | `binexport` <-> `reverse-engineering-toolkit` |
| 0.311 | 0.000 | 4,385 / 22,888 | `skill-scout` <-> `writing-skills` |
| 0.310 | 0.000 | 1,216 / 1,864 | `frida-mcp` <-> `ralph-orchestrator-setup` |
| 0.309 | 0.003 | 1,122 / 1,310 | `ida-pro-mcp` <-> `mcp-graphql` |
| 0.308 | 0.009 | 1,066 / 1,310 | `ghidra-mcp` <-> `mcp-graphql` |
| 0.307 | 0.000 | 1,371 / 1,159 | `hexstrike-ai-authorized-engagement` <-> `hexstrike-ai-setup` |
| 0.305 | 0.000 | 1,337 / 1,417 | `hacktricks` <-> `hacktricks-api` |
| 0.303 | 0.146 | 9,635 / 7,029 | `imagegen` <-> `speech` |
| 0.000 | 0.185 | 880 / 1,290 | `source-command-projects` <-> `source-command-promote` |

## Reading the top rows

* `claude-devfleet` / `source-command-devfleet` -- the most similar descriptions in the fleet
  (0.868) share only 10.5% of their bodies across 5,528 and 3,619 lines.
* The four `*-deploy` skills target four different vendors. `render-deploy` is 17,782 lines and
  `vercel-deploy` is 2,024; they share 2.8%. A merge would be a rewrite, not a dedup.
* `playwright` / `webapp-testing` and `source-command-plan` / `writing-plans` both measure
  **0.000** body overlap while reading as near-siblings in the index.

