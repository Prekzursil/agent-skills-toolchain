import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { assemblePanel, synthesizePanelFiles } from '../critique_panel.mjs';
import { PERSONA_IDS, assemblePersonaBrief } from '../panel_schema.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SAMPLE = join(HERE, '..', 'fixtures', 'audit.sample.json');

function fillDim(dimension, score = 3) {
  return {
    dimension, score, confidence: 'medium', critical: false,
    iLike: ['win a', 'win b'],
    iWish: [{ severity: 'medium', evidence: `${dimension} ev`, evidenceRefs: [], recommendation: 'fix' }],
    whatIf: ['dir'],
  };
}

test('assemblePanel writes a brief (.json + .md) for each of the four personas', () => {
  const dir = mkdtempSync(join(tmpdir(), 'panel-'));
  const { paths, briefs } = assemblePanel({ auditPath: SAMPLE, screenshots: 'home.png', out: dir });
  assert.equal(paths.length, 4);
  assert.deepEqual(paths.map((p) => p.persona).sort(), [...PERSONA_IDS].sort());
  for (const p of paths) {
    assert.ok(existsSync(p.json) && existsSync(p.md), `${p.persona} brief files exist`);
  }
  assert.ok(briefs.every((b) => b.audit_id === 'ui-audit-sample'));
});

test('synthesizePanelFiles consumes per-persona outputs and produces a valid synthesis', () => {
  const dir = mkdtempSync(join(tmpdir(), 'panel-'));
  const files = [];
  for (const id of PERSONA_IDS) {
    const owned = assemblePersonaBrief({ auditPath: SAMPLE, persona: id, audit: JSON.parse(readFileSync(SAMPLE, 'utf8')) }).ownedDimensions;
    const out = { id: `critique-panel-${id}-t`, persona: id, audit_id: 'ui-audit-sample', scope: ['home'], dimensions: owned.map((d) => fillDim(d)) };
    const f = join(dir, `panel-${id}.out.json`);
    writeFileSync(f, JSON.stringify(out));
    files.push(f);
  }
  const { synth, synthPath, personaCount } = synthesizePanelFiles({ inputs: files.join(','), auditPath: SAMPLE, out: dir });
  assert.equal(personaCount, 4);
  assert.ok(existsSync(synthPath));
  assert.equal(synth.audit_id, 'ui-audit-sample');
  assert.ok(synth.id.startsWith('critique-panel-'));
  assert.ok(synth.prioritizedFindings.length > 0);
});

test('synthesizePanelFiles rejects an invalid (quota-violating) persona file', () => {
  const dir = mkdtempSync(join(tmpdir(), 'panel-'));
  const bad = { id: 'critique-panel-a11y-t', persona: 'a11y', scope: ['home'], dimensions: [fillDim('color-contrast')] };
  bad.dimensions[0].iLike = []; // breaks quota
  const f = join(dir, 'bad.out.json');
  writeFileSync(f, JSON.stringify(bad));
  assert.throws(() => synthesizePanelFiles({ inputs: f, out: dir }), /is invalid/);
});
