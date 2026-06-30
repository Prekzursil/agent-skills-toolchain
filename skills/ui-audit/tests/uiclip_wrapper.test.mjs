/**
 * uiclip_wrapper.test.mjs — the OPTIONAL UIClip prior's safety contract.
 *
 * Spawns uiclip_score.py and asserts the non-negotiable guarantees the user asked
 * for after an OOM: opt-in scoring, NO auto-download, RAM-guard, graceful degradation
 * (clean JSON + exit 0 on every not-ok path). stdout must be a single JSON object.
 *
 * Skips cleanly when no python interpreter is on PATH so the suite stays green there.
 */

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(__dirname, '..', 'uiclip_score.py');
const SHOT = join(__dirname, '..', 'fixtures', 'sample_home.png');

function pickPython() {
  for (const exe of ['python', 'py', 'python3']) {
    try {
      const r = spawnSync(exe, ['--version'], { encoding: 'utf8' });
      if (r.status === 0 || (r.stdout + r.stderr).toLowerCase().includes('python')) return exe;
    } catch { /* try next */ }
  }
  return null;
}

const PY = pickPython();
function run(args) {
  const r = spawnSync(PY, [SCRIPT, ...args], { encoding: 'utf8' });
  let json = null;
  try { json = JSON.parse(r.stdout); } catch { /* leave null so the test fails loudly */ }
  return { ...r, json };
}

describe('uiclip_score.py safety contract', { skip: PY ? false : 'no python interpreter on PATH' }, () => {
  before(() => {
    assert.ok(existsSync(SCRIPT), 'uiclip_score.py exists');
  });

  test('--check reports readiness as pure JSON, exit 0, no load', () => {
    const r = run(['--check']);
    assert.equal(r.status, 0);
    assert.ok(r.json, `stdout must be JSON, got: ${r.stdout?.slice(0, 120)}`);
    assert.equal(r.json.tool, 'uiclip_score');
    assert.equal(r.json.status, 'ok');
    assert.equal(typeof r.json.ready_to_score, 'boolean');
    assert.ok(r.json.deps && typeof r.json.deps === 'object');
    assert.ok(r.json.ram && 'available_gb' in r.json.ram);
  });

  test('--self-test forces the unavailable branch (graceful, score null, exit 0)', () => {
    const r = run(['--self-test', '--screenshot', SHOT]);
    assert.equal(r.status, 0);
    assert.equal(r.json.status, 'unavailable');
    assert.equal(r.json.score, null);
  });

  test('default screenshot path is OPT-IN gated: skipped, no download, exit 0', () => {
    const r = run(['--screenshot', SHOT]);
    assert.equal(r.status, 0, 'never crashes');
    assert.equal(r.json.status, 'skipped');
    assert.equal(r.json.score, null);
    assert.match(r.json.reason.toLowerCase(), /opt-in|allow-download|use-cache/);
  });

  test('--use-cache without a cached model never downloads (unavailable|skipped, exit 0)', () => {
    const r = run(['--screenshot', SHOT, '--use-cache']);
    assert.equal(r.status, 0);
    assert.ok(['unavailable', 'skipped'].includes(r.json.status), `got ${r.json.status}`);
    assert.equal(r.json.score, null, 'no score without an explicitly enabled, present model');
  });

  test('--out also writes the JSON result to disk', () => {
    const out = join(mkdtempSync(join(tmpdir(), 'uiclip-')), 'uiclip.json');
    const r = run(['--screenshot', SHOT, '--out', out]);
    assert.equal(r.status, 0);
    assert.ok(existsSync(out), 'result file written');
    const onDisk = JSON.parse(readFileSync(out, 'utf8'));
    assert.equal(onDisk.tool, 'uiclip_score');
  });
});
