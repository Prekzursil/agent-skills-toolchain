---
name: Iterative Deferral Keeps Velocity
description: When a deliverable has a heavy production-language port + a lighter scripting-language
  prototype, ship the prototype FIRST every iter and defer the port. After 5-6 iters
  the CLI toolkit becomes the functional product; the prod-lang port becomes optional
  UX polish.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-iterative-deferral-keeps-velocity
---

**Rule**: When a multi-step deliverable has TWO viable shapes —
- a "heavy" production-language implementation (e.g., C# project added to a .NET solution + WPF UI), AND
- a "lighter" scripting-language prototype (e.g., Python CLI script) —
**ship the lighter prototype FIRST every iter, defer the heavier port to AFTER the algorithm is proven across multiple iters.**

**Why:**

- **iter-287 → iter-292 incident** (2026-05-07, Thread C savegame editor): the iter-286 design spec called for a C# `SwfocTrainer.Savegame.csproj` + 5 classes + WPF tab + 6 unit tests, all in iter-287. Instead, iter-287 shipped a Python `parser.py` (~280 LoC) AS the parser scaffolding. iter-288 shipped Python `fixer.py`. iter-289 shipped PowerShell wrapper. iter-290 shipped `objtype_lister.py`. iter-291 shipped `validate_mod.py`. iter-292 shipped `fixer.py strip-missing-types`. Across 6 iters the deliverable converged into a complete CLI toolkit — and the C# port + WPF tab moved from "must ship" to "optional UX polish."

- **Cycle cost ratio**: a Python prototype iter takes ~30-60 min (CLI script + smoke against real files). A C# port iter would take 3-4 hours (new .csproj, modify .sln, ~250 LoC translation, build editor — slow, run tests). **Per-iter cost: 6×.**

- **Course-correction cost matters**: across iter-287 → iter-290, the format definition was revised 4 times based on running the Python parser against real files. Each correction was free in Python. In C#, each would have required an editor rebuild + test re-run. **Iterative deferral converted 4 expensive course-corrections into 4 cheap ones.**

- **Operator value compounds**: at iter-287 the operator could parse saves. At iter-288 they could diff + inspect. At iter-289 they had a friendly wrapper. At iter-291 they could validate. At iter-292 they could strip-fix. Every iter SHIPS something usable, not just "30% closer to the WPF tab."

- **The port often becomes optional**: by iter-292, the CLI toolkit handles 100% of the user's actual savegame-editor needs. The C# port now serves only "in-trainer-tab UX" — pure polish, not functionality. iter-294+ becomes a discretionary follow-up rather than a blocker.

**How to apply:**

1. **At iter-1 (kickoff)**: spec both the prototype shape AND the prod port shape. Note which uses fewer files / smaller diff / faster cycle time.
2. **Ship prototype iter-1, prototype iter-2, ...**: each iter extends the prototype with the next user-facing capability. Operator can use it today.
3. **Defer the prod port until 3-5 iters in OR until algorithm-stability is proven.** "Algorithm-stable" = 3+ consecutive iters add no corrections.
4. **At convergence iter, EVALUATE**: is the prod port still needed? Often the answer is "no, the CLI is the product." If yes, port becomes mechanical translation — fast.
5. **Document what the prototype DOESN'T cover** (e.g., "no in-trainer-tab UX") so the deferred port has a clear scope when/if it ships.

**When NOT to apply:**

- The prod port has UX requirements the prototype CAN'T satisfy (e.g., real-time interactive UI, hardware integration, GPU compute). Then ship prod from iter-1.
- The deliverable is for end-users who can't run scripting tools (e.g., a customer-facing GUI app). Then prod is the product.
- Two-language parity has hidden gotchas (threading model differences, encoding pitfalls). Then prototype-first slows you down.
- The cycle-cost ratio is < 2x. If prod and prototype iters take similar time, just ship prod.

**Shape signals**:

- ≥3 file new project? → defer.
- Build pipeline > 1 min? → defer.
- Algorithm needs ≥ 2 corrective cycles? → STRONGLY defer.
- Operator can use the prototype standalone? → defer hard.
- All of the above? → 90% chance the prod port becomes optional polish.

**Empirical anchor**: Thread C iter 286-292 — 6 iters, 9 CLI tools, 0 prod-lang LoC shipped during the arc, savegame editor functionally COMPLETE. Pattern HOLDS.

**Cross-references**:
- `feedback_empirical_first_for_format_re.md` — sibling pattern; iterative deferral works BECAUSE empirical-first is cheap to iterate.
- iter-292 close-out: `knowledge-base/iter292_savegame_strip_fix_complete.md`
- Operator changelog: `knowledge-base/operator_changelog_2026-05-07_thread_c.md`