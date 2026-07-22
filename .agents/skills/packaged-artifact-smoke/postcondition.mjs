#!/usr/bin/env node
// packaged-artifact-smoke / postcondition.mjs
// Reusable packaged-artifact / effect-assertion smoke runner.
//
// Runs 3-5 "golden journeys" against a BUILT deliverable (not the source tree):
// each journey RUNS a command (e.g. drive the packaged Electron binary, or
// `pip install dist/*.whl` in a fresh venv then invoke the CLI) and then ends in
// a deterministic POSTCONDITION PROBE on the artifact it produced on disk:
//   - media : ffprobe -> container / codec / width x height / duration
//   - exists: filesystem existence + minimum byte size
//
// Why: CI-green source trees routinely hide PACKAGING gaps (missing runtime dep,
// electron-builder mis-map, wheel that imports but cannot run). Reframe v1.4 is
// the local precedent -- see gem-hunt MASTER A-Tier2 packaged-artifact gate,
// council C5 line: "deterministic ffprobe assertion -> FAST track".
//
// This is a HELPER / LIBRARY first (importable by A2-golden-journey-oracle and
// any pain app) and a CLI second. It has NO third-party deps: node stdlib +
// the system `ffprobe`/`ffmpeg` binaries only.
//
// SHADOW-MODE DISCIPLINE (council C5): by default the CLI runs in SHADOW mode --
// it OBSERVES, logs a structured report, and EXITS 0 regardless of assertion
// outcome, so it can never block a build or nag. A caller opts in to blocking
// with `--enforce` (or `enforce:true` in the API), which the council fast-tracks
// only for this class (deterministic, near-zero-false-positive) after burn-in.

import { spawnSync } from 'node:child_process';
import { existsSync, statSync, mkdtempSync, readFileSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

// ----------------------------------------------------------------------------
// Core probe
// ----------------------------------------------------------------------------

/**
 * Probe a media file with ffprobe. Returns a normalized descriptor.
 * Throws if ffprobe is missing or the file is unreadable/not media.
 */
export function probeMedia(file, { ffprobe = process.env.FFPROBE || 'ffprobe' } = {}) {
  if (!existsSync(file)) throw new Error(`probeMedia: file does not exist: ${file}`);
  const r = spawnSync(
    ffprobe,
    ['-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', file],
    { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 },
  );
  if (r.error) throw new Error(`probeMedia: cannot run ffprobe (${r.error.message})`);
  if (r.status !== 0) {
    throw new Error(`probeMedia: ffprobe exit ${r.status} on ${file}: ${(r.stderr || '').trim()}`);
  }
  let j;
  try {
    j = JSON.parse(r.stdout);
  } catch (e) {
    throw new Error(`probeMedia: unparseable ffprobe JSON for ${file}: ${e.message}`);
  }
  const streams = Array.isArray(j.streams) ? j.streams : [];
  const v = streams.find((s) => s.codec_type === 'video') || null;
  const a = streams.find((s) => s.codec_type === 'audio') || null;
  const fmt = j.format || {};
  const num = (x) => (x == null || x === 'N/A' ? null : Number(x));
  const dur =
    num(fmt.duration) ??
    (v ? num(v.duration) : null) ??
    (a ? num(a.duration) : null);
  return {
    file,
    container: fmt.format_name || null, // e.g. "mov,mp4,m4a,3gp,3g2,mj2"
    durationSec: dur,
    sizeBytes: num(fmt.size) ?? (existsSync(file) ? statSync(file).size : null),
    videoCodec: v?.codec_name ?? null,
    audioCodec: a?.codec_name ?? null,
    width: v?.width ?? null,
    height: v?.height ?? null,
    fps: v ? parseFps(v.avg_frame_rate || v.r_frame_rate) : null,
    nbStreams: streams.length,
    raw: j,
  };
}

function parseFps(s) {
  if (!s || s === '0/0') return null;
  const [n, d] = String(s).split('/').map(Number);
  if (!d) return null;
  return Math.round((n / d) * 1000) / 1000;
}

// ----------------------------------------------------------------------------
// Assertions -> deterministic, structured checks
// ----------------------------------------------------------------------------

function pushCheck(checks, name, expected, actual, pass) {
  checks.push({ name, expected, actual, pass });
}

/**
 * Assert a produced media artifact matches `expect`.
 * expect fields (all optional): container (substring, case-insensitive),
 *   videoCodec, audioCodec (exact), width, height (exact),
 *   minWidth, minHeight, minDurationSec, maxDurationSec, minBytes, hasAudio(bool).
 * Returns { ok, checks:[{name,expected,actual,pass}], probe }.
 */
export function assertMedia(file, expect = {}, opts = {}) {
  const checks = [];
  let probe = null;
  try {
    probe = probeMedia(file, opts);
  } catch (e) {
    pushCheck(checks, 'probe', 'ffprobe-ok', `ERROR: ${e.message}`, false);
    return { ok: false, checks, probe: null };
  }
  const e = expect || {};
  if (e.container != null) {
    const actual = probe.container || '';
    pushCheck(checks, 'container', `~${e.container}`, actual,
      actual.toLowerCase().includes(String(e.container).toLowerCase()));
  }
  if (e.videoCodec != null) pushCheck(checks, 'videoCodec', e.videoCodec, probe.videoCodec, probe.videoCodec === e.videoCodec);
  if (e.audioCodec != null) pushCheck(checks, 'audioCodec', e.audioCodec, probe.audioCodec, probe.audioCodec === e.audioCodec);
  if (e.hasAudio != null) pushCheck(checks, 'hasAudio', e.hasAudio, probe.audioCodec != null, (probe.audioCodec != null) === !!e.hasAudio);
  if (e.width != null) pushCheck(checks, 'width', e.width, probe.width, probe.width === e.width);
  if (e.height != null) pushCheck(checks, 'height', e.height, probe.height, probe.height === e.height);
  if (e.minWidth != null) pushCheck(checks, 'minWidth', `>=${e.minWidth}`, probe.width, probe.width != null && probe.width >= e.minWidth);
  if (e.minHeight != null) pushCheck(checks, 'minHeight', `>=${e.minHeight}`, probe.height, probe.height != null && probe.height >= e.minHeight);
  if (e.minDurationSec != null) pushCheck(checks, 'minDuration', `>=${e.minDurationSec}s`, probe.durationSec, probe.durationSec != null && probe.durationSec >= e.minDurationSec);
  if (e.maxDurationSec != null) pushCheck(checks, 'maxDuration', `<=${e.maxDurationSec}s`, probe.durationSec, probe.durationSec != null && probe.durationSec <= e.maxDurationSec);
  if (e.minBytes != null) pushCheck(checks, 'minBytes', `>=${e.minBytes}`, probe.sizeBytes, probe.sizeBytes != null && probe.sizeBytes >= e.minBytes);
  if (checks.length === 0) pushCheck(checks, 'probe', 'ffprobe-ok', 'ok (no field assertions)', true);
  return { ok: checks.every((c) => c.pass), checks, probe };
}

/**
 * Assert a produced file exists and is non-trivial.
 * expect: { minBytes=1 }. Returns { ok, checks, sizeBytes }.
 */
export function assertExists(file, expect = {}) {
  const checks = [];
  const minBytes = expect.minBytes ?? 1;
  const exists = existsSync(file);
  pushCheck(checks, 'exists', true, exists, exists);
  let size = null;
  if (exists) {
    size = statSync(file).size;
    pushCheck(checks, 'minBytes', `>=${minBytes}`, size, size >= minBytes);
  }
  return { ok: checks.every((c) => c.pass), checks, sizeBytes: size };
}

// ----------------------------------------------------------------------------
// Journey runner
// ----------------------------------------------------------------------------

/**
 * Run one golden journey against a BUILT artifact.
 * journey = {
 *   id: string,
 *   run?: { cmd, args?:[], cwd?, env?:{}, timeoutMs?, shell?:bool },  // optional: probe-only journeys omit it
 *   postcondition: { type:'media'|'exists', file, expect?:{} },
 * }
 * Returns a terminal receipt:
 *   { id, outcome:'PASS'|'FAIL', run?:{status,ok,signal,ms}, assertion:{ok,checks,...} }
 */
export function runJourney(journey, opts = {}) {
  const id = journey.id || 'journey';
  const receipt = { id, outcome: 'FAIL', run: null, assertion: null };

  if (journey.run && journey.run.cmd) {
    const { cmd, args = [], cwd, env, timeoutMs = 120000, shell = false } = journey.run;
    const t0 = Date.now();
    const r = spawnSync(cmd, args, {
      cwd,
      env: env ? { ...process.env, ...env } : process.env,
      timeout: timeoutMs,
      shell,
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    });
    const ms = Date.now() - t0;
    const runOk = !r.error && r.status === 0;
    receipt.run = {
      status: r.status,
      signal: r.signal || null,
      ok: runOk,
      ms,
      error: r.error ? r.error.message : null,
      stderrTail: (r.stderr || '').split('\n').slice(-8).join('\n'),
    };
    if (!runOk) {
      // Build step itself failed -> journey fails without probing.
      receipt.assertion = { ok: false, checks: [{ name: 'run', expected: 'exit 0', actual: r.error ? r.error.message : `exit ${r.status}${r.signal ? '/' + r.signal : ''}`, pass: false }] };
      return receipt;
    }
  }

  const pc = journey.postcondition || {};
  const file = resolveFile(pc.file, journey.run && journey.run.cwd);
  let assertion;
  if (pc.type === 'media') assertion = assertMedia(file, pc.expect || {}, opts);
  else if (pc.type === 'exists') assertion = assertExists(file, pc.expect || {});
  else assertion = { ok: false, checks: [{ name: 'postcondition', expected: 'media|exists', actual: pc.type ?? '(none)', pass: false }] };

  receipt.assertion = assertion;
  receipt.outcome = assertion.ok ? 'PASS' : 'FAIL';
  return receipt;
}

function resolveFile(file, cwd) {
  if (!file) return file;
  if (isAbsolute(file)) return file;
  return join(cwd || process.cwd(), file);
}

/**
 * Run a manifest of journeys.
 * manifest = { app?, journeys:[journey...] } (3-5 journeys recommended).
 * opts = { enforce:false (shadow default), ffprobe }.
 * Returns { app, total, passed, failed, ok, receipts, enforce }.
 * Prints per-journey terminal-state markers and a summary line.
 */
export function runManifest(manifest, opts = {}) {
  const enforce = !!opts.enforce;
  const journeys = manifest.journeys || [];
  const receipts = journeys.map((j) => runJourney(j, opts));
  const passed = receipts.filter((r) => r.outcome === 'PASS').length;
  const failed = receipts.length - passed;
  const ok = failed === 0;

  const log = opts.log || console.log;
  for (const r of receipts) {
    if (r.outcome === 'PASS') {
      log(`SUCCESS:${r.id} (${summarizeChecks(r.assertion)})`);
    } else {
      log(`FAILED:${r.id} ${summarizeChecks(r.assertion)}`);
    }
  }
  const mode = enforce ? 'ENFORCE' : 'SHADOW';
  log(`packaged-artifact-smoke[${mode}] ${passed}/${receipts.length} journeys passed`);
  return { app: manifest.app || null, total: receipts.length, passed, failed, ok, receipts, enforce };
}

function summarizeChecks(assertion) {
  if (!assertion || !assertion.checks) return 'no-assertion';
  return assertion.checks
    .map((c) => `${c.name}=${c.pass ? 'ok' : `FAIL(${JSON.stringify(c.actual)}!~${JSON.stringify(c.expected)})`}`)
    .join(' ');
}

// ----------------------------------------------------------------------------
// Convenience: fresh-venv wheel install (for pip-packaged pain apps)
// ----------------------------------------------------------------------------

/**
 * Create a fresh venv and `pip install` a wheel into it. Returns the venv's
 * python executable path (so journeys can invoke the installed CLI/module).
 * Deterministic packaging check: proves the wheel installs from clean, not just
 * that the source tree imports. Throws on failure.
 */
export function installWheelFreshVenv(wheelPath, { python = process.env.PYTHON || 'python', venvDir } = {}) {
  if (!existsSync(wheelPath)) throw new Error(`installWheelFreshVenv: wheel not found: ${wheelPath}`);
  const dir = venvDir || mkdtempSync(join(tmpdir(), 'pas-venv-'));
  const mk = spawnSync(python, ['-m', 'venv', dir], { encoding: 'utf8' });
  if (mk.status !== 0) throw new Error(`venv create failed: ${(mk.stderr || '').trim()}`);
  const py = process.platform === 'win32' ? join(dir, 'Scripts', 'python.exe') : join(dir, 'bin', 'python');
  const pip = spawnSync(py, ['-m', 'pip', 'install', '--no-cache-dir', wheelPath], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (pip.status !== 0) throw new Error(`pip install failed: ${(pip.stderr || '').trim()}`);
  return { python: py, venvDir: dir };
}

// ----------------------------------------------------------------------------
// CLI
// ----------------------------------------------------------------------------

function parseFlags(argv) {
  const flags = {};
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) flags[key] = true;
      else { flags[key] = next; i++; }
    } else rest.push(a);
  }
  return { flags, rest };
}

async function selftest() {
  // Real end-to-end self-test: synthesize a portrait mp4 with ffmpeg, then
  // exercise probe / assertMedia (pass+fail) / assertExists / runManifest.
  const ffmpeg = process.env.FFMPEG || 'ffmpeg';
  const dir = mkdtempSync(join(tmpdir(), 'pas-selftest-'));
  const out = join(dir, 'clip.mp4');
  const gen = spawnSync(ffmpeg, [
    '-y', '-f', 'lavfi', '-i', 'testsrc=size=1080x1920:rate=30:duration=1',
    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', out,
  ], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (gen.status !== 0) {
    console.log(`FAILED:selftest could not synthesize fixture: ${(gen.stderr || '').trim().split('\n').slice(-3).join(' ')}`);
    process.exit(1);
  }

  const results = [];
  const check = (name, cond, detail = '') => { results.push({ name, cond }); console.log(`${cond ? 'ok' : 'NOT-ok'} - ${name}${detail ? ' :: ' + detail : ''}`); };

  const p = probeMedia(out);
  check('probe reads 1080x1920', p.width === 1080 && p.height === 1920, `${p.width}x${p.height}`);
  check('probe reads h264 video', p.videoCodec === 'h264', p.videoCodec);
  check('probe reads aac audio', p.audioCodec === 'aac', p.audioCodec);
  check('probe reads ~1s duration', p.durationSec != null && p.durationSec >= 0.5 && p.durationSec <= 2, String(p.durationSec));

  const good = assertMedia(out, { container: 'mp4', videoCodec: 'h264', width: 1080, height: 1920, minDurationSec: 0.5, hasAudio: true, minBytes: 1000 });
  check('assertMedia PASS on correct spec', good.ok === true, summarizeChecks(good));

  const bad = assertMedia(out, { width: 1920, height: 1080 }); // wrong orientation
  check('assertMedia FAIL on wrong resolution', bad.ok === false, summarizeChecks(bad));

  const missing = assertMedia(join(dir, 'nope.mp4'), { width: 1080 });
  check('assertMedia FAIL on missing file', missing.ok === false);

  const ex = assertExists(out, { minBytes: 1000 });
  check('assertExists PASS', ex.ok === true, `${ex.sizeBytes}B`);
  const exMissing = assertExists(join(dir, 'nope.mp4'));
  check('assertExists FAIL on missing', exMissing.ok === false);

  // runManifest: one run-then-probe journey (ffmpeg re-encode to a 2nd file) + one exists journey.
  const out2 = join(dir, 'reencode.mov');
  const lines = [];
  const summary = runManifest({
    app: 'selftest',
    journeys: [
      {
        id: 'reencode-produces-mov',
        run: { cmd: ffmpeg, args: ['-y', '-i', out, '-c', 'copy', out2] },
        postcondition: { type: 'media', file: out2, expect: { container: 'mov', width: 1080, height: 1920 } },
      },
      { id: 'source-clip-exists', postcondition: { type: 'exists', file: out, expect: { minBytes: 1000 } } },
    ],
  }, { enforce: false, log: (l) => lines.push(l) });
  lines.forEach((l) => console.log('   ' + l));
  check('runManifest all journeys pass', summary.ok === true && summary.passed === 2);
  check('shadow mode reported', summary.enforce === false);

  const failed = results.filter((r) => !r.cond);
  if (failed.length) {
    console.log(`FAILED:selftest ${failed.length}/${results.length} checks failed: ${failed.map((f) => f.name).join('; ')}`);
    process.exit(1);
  }
  console.log(`SUCCESS:selftest ${results.length}/${results.length} checks passed`);
}

async function main() {
  const [, , sub, ...argv] = process.argv;
  const { flags, rest } = parseFlags(argv);

  if (sub === 'selftest' || flags.selftest) return selftest();

  if (sub === 'probe') {
    const p = probeMedia(rest[0]);
    console.log(JSON.stringify({ ...p, raw: undefined }, null, 2));
    return;
  }

  if (sub === 'assert') {
    const file = rest[0];
    const expect = {};
    for (const k of ['container', 'videoCodec', 'audioCodec']) if (flags[k]) expect[k] = flags[k];
    for (const k of ['width', 'height', 'minWidth', 'minHeight', 'minBytes']) if (flags[k]) expect[k] = Number(flags[k]);
    for (const k of ['minDurationSec', 'maxDurationSec']) if (flags[k]) expect[k] = Number(flags[k]);
    const res = assertMedia(file, expect);
    console.log(res.ok ? `SUCCESS:assert ${summarizeChecks(res)}` : `FAILED:assert ${summarizeChecks(res)}`);
    process.exit(res.ok || !flags.enforce ? 0 : 1);
    return;
  }

  if (sub === 'run') {
    const manifestPath = rest[0];
    if (!manifestPath || !existsSync(manifestPath)) {
      console.log('FAILED:run manifest not found. Usage: node postcondition.mjs run <manifest.json> [--enforce]');
      process.exit(1);
    }
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    const summary = runManifest(manifest, { enforce: !!flags.enforce });
    // Shadow (default): always exit 0. Enforce: exit non-zero on any failure.
    process.exit(flags.enforce && !summary.ok ? 1 : 0);
    return;
  }

  console.log([
    'packaged-artifact-smoke / postcondition.mjs',
    '',
    'Usage:',
    '  node postcondition.mjs run <manifest.json> [--enforce]   run golden journeys (SHADOW by default)',
    '  node postcondition.mjs probe <file>                      dump ffprobe descriptor as JSON',
    '  node postcondition.mjs assert <file> [--width N --height N --videoCodec h264 ...]',
    '  node postcondition.mjs selftest                          synthesize a fixture and self-verify',
    '',
    'Import as a library:',
    "  import { probeMedia, assertMedia, assertExists, runJourney, runManifest, installWheelFreshVenv } from './postcondition.mjs'",
  ].join('\n'));
}

// Run CLI only when invoked directly (not when imported). Compare REAL paths:
// ~/.claude/skills is a symlink to skills.daily, so import.meta.url resolves the
// symlink while process.argv[1] does not -- a naive URL compare misfires.
function invokedDirectly() {
  try {
    if (!process.argv[1]) return false;
    return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]);
  } catch {
    return false;
  }
}
if (invokedDirectly()) {
  main().catch((e) => { console.log(`FAILED:cli ${e.message}`); process.exit(1); });
}
