# Self-Calibration Plan — research-backed, 2026-06-11

Evidence-graded research (9-agent workflow `wf_57f0beff-dcf`) + adversarial critique, grounded in the *actual* hook source on this machine.

## The one design law (T1 — the finding everything else hangs on)
**Intrinsic, same-context self-correction does NOT work and often *degrades* reasoning** ("LLMs Cannot Self-Correct Reasoning Yet", Huang et al., ICLR 2024, [arXiv:2310.01798](https://arxiv.org/abs/2310.01798)).
→ Every self-check must anchor to an **external signal the model cannot fake**: a tool/execution result, an *independently sampled* question, a *fresh-context* reviewer, or a *written rubric*.
→ Honest boundary: **hooks TRIGGER + supply the external signal; only a separate model call JUDGES.** A hook that just injects "are you sure?" is a proven placebo — sometimes worse than nothing.

## The four failure modes → honest coverage
| Mode | Real case | What actually fixes it | Residual (nothing catches) |
|---|---|---|---|
| **F1** tunnel / no simplest-first | 10-hr vision pipeline on a PDF with no text layer; live-hook instead of static RE | **A deterministic cheap-probe BEFORE the expensive path** (PDF→`pdffonts`/`pdftotext`; RE→static-decompile-before-live-hook; perf→profile-first). NOT a self-prompt to "consider the simplest option" (that's same-context = unreliable). | — |
| **F2** no falsify / sunk-cost | 2-day Ralph grind reversing the wrong spot on a wrong value | Tool-spin fingerprint (mechanical loops) + budget cap (bounds clock) + **self-consistency** (sample a sub-question 3×, disagreement = wrong anchor) + **fresh-context verifier** | A plausible-but-wrong anchor that hasn't produced contradictions *yet* → only a fresh-context model call or a human "reconsider" breaks it. **Irreducible.** |
| **F3** no prior-art / recall | starts from zero; re-cracks solved problems | **Recall-first**: hook queries basic-memory on the prompt, injects prior art before I propose (ExpeL, T1, +11-19 pts). External-anchored. | — |
| **F4** no durable capture | doesn't write down what worked | **Success-gated** capture into `.beads/knowledge/*.jsonl` (already exists) + basic-memory. **Add-all DEGRADES** (T1) — must gate on success + self-prune. | "Did it truly work?" is a model/human judgment; mis-gated success → replays wrong captures (r≈1). |

## Starter set — build this week (critic-approved, all reuse, all fail-open)
> **STATUS: all 3 wired + verified 2026-06-11.** #1 matcher applies on next reload; #2 recall-first + #3 skill are live. Backups: `_config-backups/sota_2026-06-11_055957/{settings.json,prompt-guard.py}.pre-selfcalib`. Undo #3 = remove the `~/.claude/skills/simplest-probe-first` junction.
1. **Anti-degen fingerprint → MCP/RE tools.** One-line `settings.json` matcher: `"Bash"` → `"Bash|mcp__ida-pro-mcp__.*|mcp__ghidra-mcp__.*|mcp__frida-mcp__.*"`. `fingerprint.py` needs **zero code change** (already hashes `(tool,args,output)`, output-aware so RE polling won't false-positive). Fixes F2 **tool-spin only** — NOT the wrong-value grind. Cheapest meaningful change on the list.
2. **Recall-first injection** on the existing `inquisitiveness/prompt-guard.py`. On prompts > N chars: `search_notes` the salient nouns, **exclude `tags=compaction-checkpoint`** (fixes a real bug where checkpoints bury runbooks), inject top 1-3 as `additionalContext`. Fixes F3. ~30 lines. (Ship injection only.)
3. **"Simplest-probe-first" checklist skill** (the critic's gem — the *real* F1 fix). A small skill that, per domain, names the deterministic cheap probe to run before committing: PDF→text-layer check; RE→static-decompile before live-hook; perf→profile before rewrite; "have I solved this?"→memory check. Deterministic, non-nagging, external-anchored.

## Deferred — do NOT build until the starter proves insufficient
- **OATS selection-logging self-learning** (`oats.py` is inert, waits for a `kind='selection'` PostToolUse writer) — needs 100 events + an embeddings backend. Multi-week payoff; unbundle from #2.
- **Fresh-context supervisor verifier** (periodically re-derives the load-bearing value from a clean context) — the *real* fix for the Ralph wrong-value residue, but heavier (a `Task()` spawn). Promote if Ralph-style grinds recur.
- **Self-consistency stop-signal** for F2 wrong-value — cheap-ish, promote alongside the verifier.
- **Budget/feasibility checkpoint** for autonomous loops (80%-spent → "is the goal still reachable?"). Build only if running Ralph/Workflow loops.

## DON'T build (anti-overfit ceiling: ~6 hooks total, not 95)
- **Re-enable `gateguard`** — its +2.25-pt claim is self-reported (T4); it was disabled for a reason; "fires on new structure" needs a model call → becomes the nagging you hate.
- Knowledge-graph / vector memory engine (filesystem + basic-memory already win; you already DROPPED FalkorDB/Docker).
- Tree/Graph-of-Thoughts as a default (10×+ latency, plateaus; reserve for genuinely search-shaped tasks).
- Log-everything memory (faithfully replays your *wrong* captures, r≈1 — actively harmful).
- "Proactive anticipatory agent" / 95-hook "agent OS" (vendor hype; reintroduces nagging).

## Orchestration router (so you never pick the flow)
One rule: **trivial → just do it · spec'd multi-file → metaswarm gates · known repeatable pipeline → Workflow DAG · unknown/search-shaped (RE, novel design) → parallel agents + council · high-stakes go/no-go → codex-council (cross-model).** Evidence: deterministic skeleton beats LLM-orchestrator on tail-risk + 3.5× fewer tokens; router hits ~95% quality using the expensive path 26% of the time. The router *must* be allowed to say "trivial → no gates" (that's the escape hatch against over-engineering).

## Sources
Huang et al. ICLR 2024 [2310.01798] · PlanSearch [2409.03733] (note: its 77% is **pass@200**, not pass@1 — supports diversity on *search* tasks, not cheap-first) · ExpeL (experiential learning) · Chain-of-Verification · CRITIC (tool-grounded critique).
