#!/usr/bin/env node
/**
 * gates.mjs — the 8-gate TCR Loop definition + the revert-gate decision logic.
 *
 * This is the DATA spine of the design-review-loop orchestrator. It encodes, for
 * each gate G0..G7: its canonical named method (primary-sourced), the leaf skill /
 * tool that implements it, what it emits, and its standard question bank. The loop
 * harness (loop.mjs) and the tests both import from here so the gate contract has a
 * single source of truth.
 *
 * Implements DESIGN-WORKFLOW.md §0 (the 8-gate table) + §2 (per-gate method +
 * standard questions) + §3 (transpose -> discuss -> revert micro-loop) and
 * DESIGN-SKILLS-AND-EVAL.md §1.2/§3 (orchestrator role, revert is first-class).
 *
 * Pure data + pure functions. No model calls, no pixel measuring, no I/O.
 */

/** Canonical gate order. The loop runs G0 once, then cycles G1..G7 -> back to G1. */
export const GATE_ORDER = ['G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7'];

/**
 * The 8 gates. Each: name, canonical named method, the leaf skill/tool that
 * implements it, what it emits, the "edge" it owns in the transpose->discuss->revert
 * micro-loop (if any), and its standard question bank (verbatim intent from
 * DESIGN-WORKFLOW.md §2).
 */
export const GATES = {
  G0: {
    id: 'G0',
    name: 'PRIME',
    method: 'Scope-setting + source-of-truth decision (loop-altitude: system loop vs audit loop)',
    skill: 'prime / design-system (Mode 2 Visual Audit) ; design-sync (@dsCard repo->Claude Design)',
    emits: 'scope + persona + "where is truth: repo or Figma?" + loop altitude (system vs audit)',
    edge: null,
    questions: [
      'Who is the user and what is the top job in this flow?',
      'Where is the source of truth — repo or Figma library? (default: repo-native for code-first apps)',
      'Which ONE flow is in scope this pass? (narrow scope — do not boil the ocean)',
      'Loop altitude: system loop (components + tokens exist -> bind to them) or audit loop (greenfield -> extract tokens first)? The lens rewards maturity, it does not manufacture it.',
    ],
  },
  G1: {
    id: 'G1',
    name: 'AUDIT',
    method: 'NN/g Heuristic Evaluation (Prepare -> Evaluate -> Consolidate); Nielsen 10 + severity 0-4',
    skill: 'ui-audit (Track-A deterministic numbers + Track-B VLM critique)',
    emits: 'severity-ranked, de-duped findings list (audit.json + screenshots)',
    edge: null,
    questions: [
      'Nielsen-10 yes/no gates: system-status feedback? match to real world? user control/undo/exit? consistency & standards? error prevention? recognition over recall? flexibility for power users? aesthetic/minimalist? error recovery? help/docs?',
      'A11y gate: AA contrast (>=4.5:1 body, >=3:1 large), focus order, >=44px/48dp tap targets, alt text?',
      'Token gate: is every value bound to a token (no raw hex / off-token spacing)?',
      'What does each violation cost -> severity 0-4 (severity = frequency x impact x persistence)?',
      'Functional-broken vs merely sub-optimal? (VLMs are a recall amplifier, NOT a judge — ~21% expert overlap, ~24% false-positive; you + app-driving own flow/state.)',
    ],
  },
  G2: {
    id: 'G2',
    name: 'TRANSPOSE',
    method: 'code -> Figma capture ("Code to Canvas") — altitude-selected',
    skill: 'transpose-to-figma (generate_figma_design live/localhost ; story.to.design system loop ; html.to.design audit-only)',
    emits: 'editable Figma frames carrying Code Connect IDs + token refs (system loop) OR flat audit-only layers',
    edge: 'transpose', // the first transpose edge
    questions: [
      'Does the imported frame match the live render — fonts, spacing, and REAL states (empty / error / loading too, not just the happy path)?',
      'Which screens CARRY the experience? Focus there; do not transpose the whole app.',
      'Do nodes carry Code Connect IDs + token refs (system loop) or are they flat layers (audit only)? If flat, say so — it is not a second source of truth.',
      'Where is the source of truth — repo or Figma library? (default repo-native; Figma is a detail workshop fed from code)',
    ],
  },
  G3: {
    id: 'G3',
    name: 'CRITIQUE',
    method: 'NN/g Design Critique (silent-first -> "I Like / I Wish / What If" -> CDS-30 across 6 perspectives -> "ask why"); optional multi-agent persona panel',
    skill: 'critique-panel (Nielsen / Refactoring-UI / WCAG / Brand-consistency personas) ; Figma comments',
    emits: 'typed, severity-rated verdict list (deduped + ranked); enforced quota >=2 wins + 1 fix per screen',
    edge: 'discuss', // the discuss edge
    questions: [
      'Framing (always): What problem are we solving? Who is the user? What constraints? What SPECIFIC feedback am I seeking today?',
      'I Like: what is working and must be PROTECTED?',
      'I Wish: what fails a heuristic-or-goal? (tie to heuristic # + severity 0-4)',
      'What If: what alternative serves the goal better?',
      'CDS-30 — 6 perspectives (go broad before pixels): User · Environment · Interface · Components · Design · Visual Marks. Ban "I like / I do not like" -> require "for THIS user and task the risk is...".',
      'Ask WHY on every reactive opinion — every comment ties to a persona / scenario / goal. (Panel TRIAGES; the human is the decider.)',
    ],
  },
  G4: {
    id: 'G4',
    name: 'DIRECT',
    method: 'severity-prioritized decision; define "good" (Judge / Evaluate / Iterate); Impact/Effort or RICE',
    skill: 'frontend-design-direction / make-interfaces-feel-better (direction) — HUMAN is the decider here',
    emits: 'ONE committed direction + explicit out-of-scope',
    edge: 'discuss', // G4 decide closes the discuss edge
    questions: [
      'What are the must-fix sev-3/4 vs nice-to-have sev-1/2?',
      'What SINGLE direction do we commit to? (collapse conflicting opinions into one)',
      'What is the success criterion — how will we KNOW it is better? (define "good" before building)',
      'What is explicitly OUT OF SCOPE this round?',
      'DECIDER CHECK: did a human pick the direction? (VLMs are near-random at PICKING the better design — WiserUI-Bench. Agents enumerate + rank; the user chooses.)',
    ],
  },
  G5: {
    id: 'G5',
    name: 'ITERATE',
    method: 'Figma branch off main (the safe iterate-then-revert mechanism); token changes via Tokens Studio',
    skill: 'figma (use_figma) ; design-tokens-pipeline / Tokens Studio for structural token changes',
    emits: 'Figma node-diff + token-diff on a branch (main untouched)',
    edge: null,
    questions: [
      'Does the branch resolve the sev-3/4 items WITHOUT introducing new violations?',
      'Page-grouped diff vs main — is every change intentional?',
      'Does each change stay ON-SYSTEM (auto-correct / lint catches drift)?',
      'Merge, or DISCARD the branch (= the clean Figma-side revert) and re-branch?',
      'Are token changes structural (through Tokens Studio), not one-off pixel tweaks?',
    ],
  },
  G6: {
    id: 'G6',
    name: 'RECONCILE',
    method: 'Dev Mode handoff + Code Connect; token PR; THE REVERT-GATE (every apply-back is a reversible commit)',
    skill: 'figma-implement-design (1:1 node->code, reuse project tokens) ; Style Dictionary token PR ; verification-before-completion',
    emits: 'code diff on a branch — KEPT only if it passes the revert-gate',
    edge: 'revert', // the revert edge
    questions: [
      '1:1 parity vs the Figma intent?',
      'Tokens/components reused via Code Connect — NO new hardcoded values / NO new icon packs?',
      'Are ALL states implemented (empty / error / loading / focus), not just the happy path?',
      'Did the round-trip touch state / routing / data — and if so, is that change KEPT or REVERTED? (round-trip is lossy for logic — revert logic touches.)',
      'Did contrast / focus / token gates stay green AND the audit score improve (or at least not worsen)?',
      'REVERT-GATE: commit the variant BEFORE measuring -> re-run G1 + a11y/lint + test/coverage -> AUTO-REVERT if any tracked axis regresses or any logic/state/routing/data was re-touched.',
    ],
  },
  G7: {
    id: 'G7',
    name: 'VERIFY',
    method: 're-audit delta; capture learnings (do NOT self-certify — peer-review law)',
    skill: 're-run ui-audit (G1) ; /self-reflect + basic-memory for durable capture',
    emits: 'before/after rubric delta (per-dimension D on 0-4 + critical-error burndown) + durable decisions',
    edge: null,
    questions: [
      'Did the change move the rubric score? (per-dimension Delta on 0-4; critical-error burndown is the most defensible single claim)',
      'Any regression on a tracked axis?',
      'Does the live app match the Figma intent?',
      'What design decisions are now durable? (capture them so the next loop does not re-litigate)',
      'PEER-REVIEW: has >=1 independent reviewer confirmed before "done"? (never self-certify)',
    ],
  },
};

/** The next gate in the cycle. After G7 you loop back to G1 (G0 PRIME runs once). */
export function nextGate(gate) {
  if (gate === 'G7') return 'G1';
  const i = GATE_ORDER.indexOf(gate);
  if (i < 0) throw new Error(`unknown gate: ${gate}`);
  return GATE_ORDER[i + 1] || 'G1';
}

/** Validate a requested gate id. */
export function isGate(gate) {
  return Object.prototype.hasOwnProperty.call(GATES, gate);
}

/**
 * The G6 revert-gate decision (load-bearing). Every apply-back is a reversible
 * commit; we KEEP it only if it improves (or holds) every tracked axis AND did not
 * re-touch logic/state/routing/data. Otherwise REVERT.
 *
 * Tracked axes (from DESIGN-WORKFLOW.md G6 + DESIGN-SKILLS-AND-EVAL.md §2.6):
 *   - composite audit score must not DROP (after >= before)
 *   - zero new critical errors (criticalAfter <= criticalBefore)
 *   - contrast / focus / token gates must stay GREEN
 *   - tests/coverage must stay GREEN
 *   - logicTouched (state/routing/data) -> REVERT that change (kept only if explicitly approved)
 *
 * @param {object} m
 * @param {number} [m.compositeBefore]  before composite 0-100
 * @param {number} [m.compositeAfter]   after composite 0-100
 * @param {number} [m.criticalBefore=0] before critical-error count
 * @param {number} [m.criticalAfter=0]  after critical-error count
 * @param {boolean} [m.gatesGreen=true] contrast/focus/token gates green?
 * @param {boolean} [m.testsGreen=true] tests + coverage gate green?
 * @param {boolean} [m.logicTouched=false] did the apply-back re-touch state/routing/data?
 * @param {boolean} [m.logicApproved=false] was a logic touch explicitly approved by the human?
 * @returns {{ decision:'KEEP'|'REVERT', reasons:string[], regressed:boolean }}
 */
export function revertDecision(m = {}) {
  const before = Number.isFinite(m.compositeBefore) ? m.compositeBefore : null;
  const after = Number.isFinite(m.compositeAfter) ? m.compositeAfter : null;
  const criticalBefore = m.criticalBefore ?? 0;
  const criticalAfter = m.criticalAfter ?? 0;
  const gatesGreen = m.gatesGreen !== false;
  const testsGreen = m.testsGreen !== false;
  const logicTouched = m.logicTouched === true;
  const logicApproved = m.logicApproved === true;

  const reasons = [];
  let regressed = false;

  if (before !== null && after !== null && after < before) {
    regressed = true;
    reasons.push(`composite regressed ${before} -> ${after} (after < before)`);
  }
  if (criticalAfter > criticalBefore) {
    regressed = true;
    reasons.push(`critical-error count rose ${criticalBefore} -> ${criticalAfter}`);
  }
  if (!gatesGreen) {
    regressed = true;
    reasons.push('contrast / focus / token gate is RED');
  }
  if (!testsGreen) {
    regressed = true;
    reasons.push('tests / coverage gate is RED');
  }
  if (logicTouched && !logicApproved) {
    regressed = true;
    reasons.push('round-trip re-touched state/routing/data (lossy for logic) and the touch was not explicitly approved');
  }

  if (!regressed) {
    if (before !== null && after !== null && after > before) {
      reasons.push(`composite improved ${before} -> ${after} (+${(((after / before) - 1) * 100).toFixed(0)}%)`);
    } else {
      reasons.push('no tracked axis regressed; visual delta is safe to keep');
    }
  }

  return { decision: regressed ? 'REVERT' : 'KEEP', reasons, regressed };
}
