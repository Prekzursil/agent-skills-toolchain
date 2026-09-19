# Judge rubric — comparing design-A1 / A2 / A3 (read with DESIGN_BRIEF.md)

Score each design 1-5 on every criterion WITH evidence (section/line references into the design). A score without a traced
mechanism is not a score. Then do three pairwise comparisons (A1 vs A2, A2 vs A3, A1 vs A3), each a paragraph naming the decisive
difference, and a final ranking. Position-bias control: read the designs in the order A2, A3, A1; after ranking, re-read the
strongest section of the design you ranked last and state whether it changes anything.

Criteria (weights for the overall score):
1. Coverage reality (30 %) — every F-1..F-47 and every anti-pattern has a REAL mechanism (gate line, schema field, JS predicate,
   agent role with a concrete prompt contract), not a sentence. Trace at least 12 rows end to end; the red-team judge traces all 47.
2. Workflow-tool contract (20 %) — the JS would actually run: `meta` pure literal, no Date.now/Math.random, `agent()` null handling,
   schema validity (required ⊆ properties), pipeline vs parallel used correctly, concurrency assumptions (cap 2 / 14), resume
   purity (prompts pure in args + sorted results), per-agent effort and label discipline, log() of every drop.
3. Termination and replay guarantees (15 %) — every loop bounded with typed exhaustion; oscillation/dry detection; resumable mid-run
   without re-doing or double-applying work; cache invalidation on code change.
4. Owner checkpoints and secret hygiene (10 %) — every outward action is a checkpoint object executed by the owner/CI between runs;
   approvals are data; no secret can reach a prompt, log, journal, commit or artifact; durable paths; cwd repo never mutated.
5. Program fit (15 %) — implements the DECISIONS (especially the five made against the recommendation), uses the CORRECTED lines
   from the findings, follows the module layout / seam / PR order / ship-but-flag / characterisation-first from the simplification
   retry, represents staging + promotion + canary correctly, respects the persona boundary, the catalog eval gate, Python 3.12, LF.
6. Simplicity and anti-overfit (5 %) — no mechanism without a failure mode it closes; cost stated honestly; nothing gold-plated.
7. Cost realism (5 %) — agent counts and wall-clock derived from the observed timings, marked as estimates; fits the 1000-agent cap
   and a resumable invocation plan.

Deliver: per-design scores table (criterion → score → evidence refs); blocking defects per design (things that would make the run
fail or lie); pairwise paragraphs; final ranking with the overall weighted score; a GRAFT LIST — concrete sections/mechanisms the
synthesizer should take from the non-winners (with section refs), and mechanisms present in the winner that should be dropped;
and "what none of them handles" (gaps common to all three).
