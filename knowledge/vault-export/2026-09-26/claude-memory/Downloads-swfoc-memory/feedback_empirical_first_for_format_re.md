---
name: Empirical-First Format RE
description: When reverse-engineering a binary format, ship a Python parser ASAP and
  run it on multiple real files. IDA decompile tells you WHY; real files tell you
  WHAT. Format is converged when 3+ consecutive iters add no new corrections.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-empirical-first-for-format-re
---

**Rule**: When RE'ing an unknown binary format:

1. **Ship a Python parser first** (Day 1, ~100-300 LoC). Don't wait for design docs.
2. **Run the parser on multiple real files** spanning the variation space (vanilla / modded / corrupted / different game versions / etc.).
3. **Each run reveals corrections** — wrong field offsets, missed structures, format quirks. Update the parser, re-run.
4. **The format is CONVERGED when 3+ consecutive iters add no new corrections.**
5. **THEN** write the design doc / port to production language.

**Why:**

- **Thread C iter 286-290 incident** (2026-05-07): RE'ing the SWFOC `.PetroglyphFoC64Save` format. iter-286 produced a design doc based on IDA decompile + agent research. iter-287 shipped Python parser → discovered the IDA-derived format was wrong: a BMP thumbnail was wedged between header and chunks. iter-288 found "mod-CRC32 hash" at bytes 17-20 of 0x3E8 — but iter-290 proved this WRONG when the running game rewrote the autosave and bytes changed. iter-290 found the REAL mod-fingerprint: ObjectType reference strings inside chunk 0x3EA. **Four corrective cycles, all driven by parser output against real files.**

- **IDA tells you WHY, real files tell you WHAT**: IDA decompile shows the loader logic — `Open_Chunk`, switch statement on chunk_id, etc. That's WHY the format works. But IDA doesn't tell you what's actually IN a real file. The agent #1 IDA walk concluded "single-root chunk 0x3E8" — technically true (it IS the only top-level chunk after the BMP), but missed the BMP entirely because the loader code doesn't manage it (the renderer does, separately).

- **Multi-file coverage matters**: vanilla `a.save` and vanilla `b.save` had DIFFERENT bytes at 17-20 of 0x3E8. Two vanilla saves can't differ in mod-id; ergo bytes 17-20 are NOT mod-id. This kind of "field varies where it shouldn't" is invisible from IDA decompile and obvious from running the parser on 3+ files.

- **Cycle time is everything**: each Python parser revision cycle was ~5-15 min (edit → run → see new output). Each "stop and update IDA understanding + design doc" cycle would have been 30-60 min minimum. **6× cycle-time advantage** for empirical-first across the arc.

**How to apply:**

1. **Day 1, before any design doc**: implement a parser that:
   - Reads the header.
   - Walks the structure with reasonable defaults.
   - Emits a chunk inventory + diagnostics (OVERFLOW errors, suspicious sizes).
   - Has a `--diagnose` mode that tries multiple walking strategies.
2. **Run against ≥ 3 real files** — make sure to span variation: different versions, different mods, different sizes.
3. **For each parse failure or suspicious output**: add a diagnostic line + revise the parser. Keep iterating until output is sane.
4. **AFTER the parser converges**: now write the design doc. The doc reflects empirical truth + IDA decompile insight, not just guesses.
5. **Port to production language LAST** — when the algo is proven (see `feedback_iterative_deferral_keeps_velocity.md`).

**Convergence signal:**

- 3+ consecutive iters running the parser on real files reveal NO new corrections.
- Output matches expectations cross-version (vanilla a.save and vanilla b.save produce structurally-identical reports).
- Edge cases (modded files, corrupt files) parse cleanly OR fail with clear errors that map to known issues.

**Anti-patterns:**

- "I'll write the design doc first based on IDA, then implement the parser to match." → BAD. The design doc encodes assumptions the parser would have caught.
- "I'll port to C# now since I have the IDA layout figured out." → BAD if you haven't run a Python parser against real files yet.
- "The agent's research says it's single-root 0x3E8." → BAD as a primary source. The agent's research is INPUT to your empirical investigation, not the answer.

**When NOT to apply:**

- The format is well-documented externally (e.g., zlib, PNG, gzip) — just use the spec.
- Format is trivial (e.g., line-delimited JSON). Empirical-first overkill.
- Real files unavailable (RE'ing a hypothetical or future format).

**Cross-references**:
- `feedback_iterative_deferral_keeps_velocity.md` — sibling pattern; empirical-first works BECAUSE iterative deferral keeps cycle costs low.
- `feedback_aob_drift_across_binary_versions.md` — direction A of "claims about binary may be wrong."
- `feedback_infra_claim_drift_bidirectional.md` — direction B of same.
- iter-286 to iter-290 close-outs — 5-iter chain documenting the 4 corrective cycles.