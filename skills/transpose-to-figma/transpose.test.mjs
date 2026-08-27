// Tests for the transpose.mjs upgrades (C-transpose-upgrades).
// Zero-dep: Node built-in test runner. Run: node --test transpose.test.mjs
// Exercises (1) the 5th 'surgical' altitude and (2) the Code Connect honesty patch.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = join(HERE, 'transpose.mjs');

function run(argsArr) {
  // execFileSync throws on non-zero exit; capture both paths.
  try {
    const stdout = execFileSync(process.execPath, [CLI, ...argsArr], { encoding: 'utf8' });
    return { code: 0, stdout };
  } catch (e) {
    return { code: e.status ?? 1, stdout: (e.stdout || '').toString() };
  }
}

function lastLine(s) {
  const lines = s.trim().split(/\r?\n/);
  return lines[lines.length - 1];
}

function jsonBlock(stdout) {
  // The record subcommands print "wrote ..." lines + a JSON blob on select/resolve.
  const start = stdout.indexOf('{');
  const end = stdout.lastIndexOf('}');
  return JSON.parse(stdout.slice(start, end + 1));
}

// ---------- Edit 1: the 5th 'surgical' altitude ----------

test('select --target surgical returns the surgical altitude via use_figma in-place', () => {
  const r = run(['select', '--target', 'surgical', '--url', 'https://figma.com/design/ABC123/App?node-id=12-34']);
  assert.equal(r.code, 0);
  assert.match(lastLine(r.stdout), /^SUCCESS:transpose-select-/);
  const rec = jsonBlock(r.stdout);
  assert.equal(rec.chosenAltitude, 'surgical');
  assert.match(rec.tool, /use_figma/);
  assert.equal(rec.granularity, 'node');
  assert.equal(rec.driftClass, 'low');
  assert.equal(rec.nodeUrl, 'https://figma.com/design/ABC123/App?node-id=12-34');
});

test('surgical wins even when --has-storybook is set (explicit in-place edit)', () => {
  const r = run(['select', '--target', 'surgical', '--has-storybook']);
  const rec = jsonBlock(r.stdout);
  assert.equal(rec.chosenAltitude, 'surgical');
});

test('surgical caveat mandates the /figma-use gate before use_figma', () => {
  const r = run(['select', '--target', 'surgical']);
  const rec = jsonBlock(r.stdout);
  assert.match(rec.caveat, /figma-use/);
});

test('the 4 legacy altitudes are unchanged (no regression)', () => {
  const live = jsonBlock(run(['select', '--target', 'live']).stdout);
  assert.equal(live.chosenAltitude, 'live');
  assert.equal(live.driftClass, 'medium');
  const audit = jsonBlock(run(['select', '--target', 'audit']).stdout);
  assert.equal(audit.chosenAltitude, 'audit');
  const sys = jsonBlock(run(['select', '--target', 'localhost', '--has-storybook']).stdout);
  assert.equal(sys.chosenAltitude, 'system-loop');
});

test('an unknown target still fails and lists surgical as a valid option', () => {
  const r = run(['select', '--target', 'bogus']);
  assert.equal(r.code, 1);
  assert.match(lastLine(r.stdout), /FAILED:transpose-select-.*surgical/);
});

// ---------- Edit 2: Code Connect honesty patch ----------

function recordIn(argsArr) {
  const out = mkdtempSync(join(tmpdir(), 'transpose-'));
  const r = run(['record', '--out', out, ...argsArr]);
  const rec = JSON.parse(readFileSync(join(out, 'transpose-record.json'), 'utf8'));
  return { out, r, rec };
}

test('Education Full seat (default): --code-connect does NOT make systemLoopReady true', () => {
  const { r, rec } = recordIn(['--code-connect', '--token-refs', '--path', 'live']);
  assert.equal(r.code, 0);
  assert.equal(rec.seat, 'education-full');
  assert.equal(rec.codeConnectRequested, true);
  assert.equal(rec.codeConnectEntitled, false);
  assert.equal(rec.codeConnectActive, false);
  // The dishonest old behavior (codeConnect && tokenRefs) would be TRUE here.
  assert.equal(rec.systemLoopReady, false);
  // ...and the honest downgrade note fires.
  assert.match(r.stdout, /NOT Code-Connect-entitled/);
});

test('token-refs + components produces a local .design/code-map.json parity substitute', () => {
  const { out, rec } = recordIn(['--token-refs', '--components', 'Button,Card', '--path', 'live']);
  assert.equal(rec.tokenBound, true);
  assert.equal(rec.nodeNamingParity, true);
  assert.equal(rec.localParityReady, true);
  assert.equal(rec.codeMapPath, join('.design', 'code-map.json'));
  const mapFile = join(out, '.design', 'code-map.json');
  assert.ok(existsSync(mapFile), 'code-map.json should exist');
  const map = JSON.parse(readFileSync(mapFile, 'utf8'));
  assert.equal(map.codeConnectEntitled, false);
  assert.equal(map.parity.length, 2);
  assert.deepEqual(map.parity[0], { component: 'Button', figmaNodeName: 'Button', verified: false });
  // Honest: unverified name parity by default.
  assert.equal(map.verifiedCount, 0);
});

test('an entitled seat (enterprise) CAN reach the real system loop', () => {
  const { rec } = recordIn(['--code-connect', '--token-refs', '--seat', 'enterprise', '--path', 'live']);
  assert.equal(rec.codeConnectEntitled, true);
  assert.equal(rec.codeConnectActive, true);
  assert.equal(rec.systemLoopReady, true);
});

test('an owner-authored --code-map file overrides component-derived parity', () => {
  const out = mkdtempSync(join(tmpdir(), 'transpose-'));
  const mapPath = join(out, 'authored.json');
  execFileSync(process.execPath, ['-e',
    `require('fs').writeFileSync(${JSON.stringify(mapPath)}, JSON.stringify([{component:'Button',figmaNodeName:'btn/Primary',verified:true}]))`]);
  const r = run(['record', '--out', out, '--token-refs', '--components', 'Button', '--code-map', mapPath, '--path', 'live']);
  assert.equal(r.code, 0);
  const map = JSON.parse(readFileSync(join(out, '.design', 'code-map.json'), 'utf8'));
  const btn = map.parity.find(p => p.component === 'Button');
  assert.equal(btn.figmaNodeName, 'btn/Primary');
  assert.equal(btn.verified, true);
  assert.equal(map.verifiedCount, 1);
});

test('no token-refs + no components -> audit-only, no code-map, honest note', () => {
  const { out, r, rec } = recordIn(['--path', 'audit']);
  assert.equal(rec.tokenBound, false);
  assert.equal(rec.nodeNamingParity, false);
  assert.equal(rec.localParityReady, false);
  assert.equal(rec.systemLoopReady, false);
  assert.equal(rec.codeMapPath, null);
  assert.ok(!existsSync(join(out, '.design', 'code-map.json')));
  assert.match(r.stdout, /AUDIT loop only/);
});
