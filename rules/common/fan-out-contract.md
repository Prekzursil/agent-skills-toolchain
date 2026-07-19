# Fan-Out Contract (spawn prompts and fan-in gates)

Measured over 50 agents / 6 workflows, 2026-07-18. Element presence in the prompt predicts
compliance almost perfectly; nothing is inherited from the global contract.

## A. AGENT-FACING — what every fan-out prompt MUST carry

1. **Re-state the honesty instrumentation every time. It does NOT spill over.**
   The 8 lens docs (~190 KB) whose prompt omitted it scored **0 UNVERIFIED tags, 0 URLs**;
   named fields scored 26-62 hits each. Zero inheritance from AGENTS.md §7 was measured.

2. **Enumerate the vocabulary; never ship a bare tag name.**
   Sherman-Kent bands listed inline → **20/21 (95%)** adoption. `NATIVE-vs-BUILD` as a bare tag
   with no value set → **7/21 (33%)**, the most-dropped field in the corpus despite being
   load-bearing. Either enumerate the values or delete the field.

3. **UNVERIFIED must be INLINE, adjacent to the claim.**
   127 real flags, but **40% (51) sit in the final 15%** of their document. Measured damage:
   `D2-harness-queue.md:31` promoted a Tier-0 build item on a "double-fire confirmed" premise
   that line 293 admits was never checked — and an adversarial reviewer disproved it. Required
   wording: *"Attach UNVERIFIED inline to the sentence it qualifies. A limitations section at the
   end does not satisfy this. If a recommendation's premise is UNVERIFIED, the recommendation
   inherits the tag in its heading."* Every UNVERIFIED names the experiment that would settle it.

4. **A briefed fact needs a probe tag, a timestamp, and a MECHANICALLY DIFFERENT re-probe rule.**
   Disclosing that a fact might be stale is not enough: on "`mon` is NOT on PATH", 4 agents
   correctly refuted it while **2 "CONFIRMED" it by re-running the orchestrator's own broken
   Git-Bash `which`** — complete with dutiful evidence tags. Evidence-tag theatre. Require: *"To
   confirm OR refute you MUST use a different shell, a different data field, or a different
   measurement. Re-running the tagged probe does NOT count and must not be reported as
   CONFIRMED."* Four briefed "VERIFIED GROUND TRUTH" facts were false in one run.

5. **A path must carry its access method** whenever it is not readable by `Read` at that literal
   path. `tools/monitorcore` (main-only) cost **7 agents** independent rediscovery. One line
   fixes it: *"exists ONLY on origin/main — read via `git show origin/main:<path>`."*

6. **Specify the output MECHANISM, not vendor-specific syntax**, and cap the chunk size. A
   PowerShell here-string contract is vendor-fragile: 21/21 for Claude agents, but a direct
   contributor to the Codex-rail transport failure.

7. **Keep the ≤350/400-word digest cap.** It was NOT lossy — median 340 words, 4/40 over (worst
   +12%), and **4/4 correcting agents led their digest with the correction.** The cap forced
   prioritisation and agents prioritised correctly.

8. **Long ground-truth blocks earn their tokens.** A ~1,100-word block correlates with 18-44 tool
   calls and 2-49 citations per agent; a 3.8 KB prompt with no ground-truth block correlates with
   2-7 tool calls and **zero** citations. The cost ceiling is transport, not attention.

9. **Split the evidence standard by lens type.** GROUNDED lenses must cite `file:line`; IDEATION
   lenses must cite an external domain source and be told explicitly NOT to ground in the repo
   (5.0 tool calls/agent, zero duplicate reads, 177 KB usable output). Holding an ideation lens to
   a repo standard, or accepting ungrounded prose from a grounded one, is the failure.

10. **Freeze the preamble and launcher once the first unit launches.** Editing mid-run leaves
    contradictory instructions live (one run had `PLAN.md:26` "UNDER ~30 tool calls" against a
    revised launcher saying "there is NO tool-call cap"). To revise: kill cleanly, delete
    partials, restart.

11. **Inject a shared grounding pack.** 16/25 agents read the same `codex_monitor.py`; 13/25 the
    same `codex-monitor.md`; one agent re-read `hub.py` **×22**. One grounding agent producing a
    pinned digest removes an estimated 60-90 tool calls in a single 39-agent workflow — and kills
    the mid-flight split-brain that let 8 agents ship a premise fixed while they ran. Cap
    intra-agent re-reads of one path at ~4, then read it wide once.

12. **Pin the artifact root and `ls` it in the prompt** — 10 `Read` failures were pure cwd
    confusion.

## B. ORCHESTRATOR-FACING — fan-in gates

1. **`Test-Path` every contracted output BEFORE reading any digest.** 3/3 Codex agents returned
   plausible digests for files that do not exist. A digest is a claim, not a receipt.
2. **Reject any result containing `started in the background` or `Check /codex:status`.** Cheap
   regex; catches the entire fire-and-forget class outright.
3. **Require an `EVIDENCE:` block of 3-5 `file:line`/URL anchors, EXEMPT from the word cap.**
   87% of file:line refs and 100% of URLs currently die at the digest boundary.
4. **On a split verdict about a briefed fact, the specific probe wins over the agent count.**
   Read the probes; do not vote. (2 agents "CONFIRMED" a false fact with a broken detector.)
5. **Digest silence is not absence of caveats** — 18 UNVERIFIED tags survive into 30 digests
   against 127 in the docs. Open the doc before treating a claim as unqualified.
6. **Give adversarial reviewers the siblings' FULL text, not digests.** This was the single
   highest-value structural choice in the corpus — the only mechanism that caught the false
   double-fire premise and duplicate-skill bloat. Also give reviewers a durable artifact contract:
   540,583 tokens of adversarial review currently leave **zero** on-disk artifact.
7. **Never score agents on output volume.** The best verification agent in the corpus is near the
   bottom on KB/token. Any productivity gate must exempt falsification work or it selects against
   exactly the behaviour the harness most needs.
