import { test } from 'node:test';
import assert from 'node:assert/strict';

import { GATES, GATE_ORDER, nextGate, isGate, revertDecision } from '../gates.mjs';
import { initPass, renderGate, advancePass, runRevert } from '../loop.mjs';

test('all 8 gates G0..G7 are defined with the required shape', () => {
  assert.equal(GATE_ORDER.length, 8);
  for (const g of GATE_ORDER) {
    assert.ok(isGate(g), `${g} is a gate`);
    const def = GATES[g];
    assert.equal(def.id, g);
    assert.ok(def.name && def.method && def.skill && def.emits, `${g} fully described`);
    assert.ok(Array.isArray(def.questions) && def.questions.length >= 3, `${g} has a question bank`);
  }
});

test('gate names match the canonical TCR sequence', () => {
  const names = GATE_ORDER.map((g) => GATES[g].name);
  assert.deepEqual(names, ['PRIME', 'AUDIT', 'TRANSPOSE', 'CRITIQUE', 'DIRECT', 'ITERATE', 'RECONCILE', 'VERIFY']);
});

test('the three TCR edges are tagged on the right gates', () => {
  // transpose = G2, discuss = G3 (+G4 decide), revert = G6
  assert.equal(GATES.G2.edge, 'transpose');
  assert.equal(GATES.G3.edge, 'discuss');
  assert.equal(GATES.G4.edge, 'discuss');
  assert.equal(GATES.G6.edge, 'revert');
});

test('question banks contain no HTML-like tags (text arrows like -> are fine)', () => {
  for (const g of GATE_ORDER) {
    for (const q of GATES[g].questions) {
      // forbid tag-like <word ...> ; allow ASCII arrows (->) used as prose
      assert.ok(!/<\s*[a-zA-Z/]/.test(q), `${g} question free of HTML-like tags: ${q}`);
    }
  }
});

test('nextGate cycles G0..G7 then wraps G7 -> G1 (G0 runs once)', () => {
  assert.equal(nextGate('G0'), 'G1');
  assert.equal(nextGate('G5'), 'G6');
  assert.equal(nextGate('G7'), 'G1');
  assert.throws(() => nextGate('G9'));
});

test('initPass starts at G0 with repo as the default source of truth', () => {
  const s = initPass({ app: 'reframe', flow: '/editor' });
  assert.equal(s.currentGate, 'G0');
  assert.equal(s.pass, 1);
  assert.equal(s.sourceOfTruth, 'repo');
  assert.match(s.id, /^design-review-/);
});

test('advancePass walks the full cycle and bumps pass on wrap', () => {
  let s = initPass({ app: 'bilbo' });
  for (const expected of ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7']) {
    s = advancePass(s);
    assert.equal(s.currentGate, expected);
    assert.equal(s.pass, 1);
  }
  s = advancePass(s); // from G7 -> G1, new cycle
  assert.equal(s.currentGate, 'G1');
  assert.equal(s.pass, 2);
  assert.equal(s.history.length, 8);
});

test('renderGate emits method, leaf skill, and the question bank', () => {
  const s = initPass({ app: 'x' });
  const { text } = renderGate(s, 'G1');
  assert.match(text, /AUDIT/);
  assert.match(text, /ui-audit/);
  assert.match(text, /Nielsen-10/);
});

// ---- the load-bearing revert-gate (G6) ----

test('revert KEEPs a strictly improving, logic-clean apply-back', () => {
  const d = revertDecision({ compositeBefore: 62, compositeAfter: 81, criticalBefore: 2, criticalAfter: 0 });
  assert.equal(d.decision, 'KEEP');
  assert.equal(d.regressed, false);
  assert.ok(d.reasons.some((r) => /improved/.test(r)));
});

test('revert REVERTs a composite regression', () => {
  const d = revertDecision({ compositeBefore: 80, compositeAfter: 74 });
  assert.equal(d.decision, 'REVERT');
  assert.ok(d.reasons.some((r) => /regressed/.test(r)));
});

test('revert REVERTs when a new critical error appears even if composite rose', () => {
  const d = revertDecision({ compositeBefore: 60, compositeAfter: 90, criticalBefore: 0, criticalAfter: 1 });
  assert.equal(d.decision, 'REVERT');
});

test('revert REVERTs an unapproved logic/state/routing/data touch', () => {
  const d = runRevert({ compositeBefore: 60, compositeAfter: 70, logicTouched: true, logicApproved: false });
  assert.equal(d.decision, 'REVERT');
  assert.ok(d.reasons.some((r) => /state\/routing\/data/.test(r)));
});

test('revert KEEPs an approved logic touch that otherwise improves', () => {
  const d = runRevert({ compositeBefore: 60, compositeAfter: 70, logicTouched: true, logicApproved: true });
  assert.equal(d.decision, 'KEEP');
});

test('revert REVERTs on a red contrast/focus/token gate or red tests', () => {
  assert.equal(revertDecision({ compositeBefore: 60, compositeAfter: 80, gatesGreen: false }).decision, 'REVERT');
  assert.equal(revertDecision({ compositeBefore: 60, compositeAfter: 80, testsGreen: false }).decision, 'REVERT');
});
