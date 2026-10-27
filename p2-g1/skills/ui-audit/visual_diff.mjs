#!/usr/bin/env node
/**
 * visual_diff.mjs — screenshot baseline comparison.
 *
 * CLI usage (after capture.mjs has been run):
 *   node visual_diff.mjs --bundle-dir ./ui-audit-out --baseline ./baselines [--out ./diffs]
 *
 * Programmatic usage:
 *   import { diffBuffersSync, compareScreens } from './visual_diff.mjs';
 *
 *   // Pure sync diff of two RGBA buffers (no browser, no I/O)
 *   const { percentDiff } = diffBuffersSync(buf1, buf2, width, height);
 *
 *   // Full file-based compare (reads PNGs, writes diffs)
 *   await compareScreens(bundleDir, baselineDir, diffOutDir);
 *
 * First run: baseline PNGs are written.
 * Subsequent runs: diff PNGs written + %changed emitted per screen.
 *
 * Degrades gracefully if pixelmatch / pngjs are absent — logs a warning and skips.
 */

import { createRequire } from 'node:module';
import {
  existsSync, mkdirSync, readdirSync, writeFileSync,
  copyFileSync, createReadStream,
} from 'node:fs';
import { join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// ---------------------------------------------------------------------------
// Optional CJS deps — loaded at startup, gracefully absent
// ---------------------------------------------------------------------------

const _require = createRequire(import.meta.url);

let _pixelmatch = null;
let _PNG = null;

try {
  _pixelmatch = _require('pixelmatch');
} catch { /* will warn at call-site */ }

try {
  _PNG = _require('pngjs').PNG;
} catch { /* will warn at call-site */ }

// ---------------------------------------------------------------------------
// Pure sync diff helper (exported — no browser, no I/O, no Playwright)
// ---------------------------------------------------------------------------

/**
 * Diff two RGBA flat buffers (Uint8Array or Buffer).
 * @param {Buffer|Uint8Array} buf1 - RGBA pixels of image A
 * @param {Buffer|Uint8Array} buf2 - RGBA pixels of image B (same dimensions)
 * @param {number} width
 * @param {number} height
 * @param {number} threshold - per-pixel colour distance threshold [0,1] (default 0.1)
 * @returns {{ numDiff: number, percentDiff: number, diff: Buffer }}
 */
export function diffBuffersSync(buf1, buf2, width, height, threshold = 0.1) {
  if (!_pixelmatch) {
    throw new Error('pixelmatch not installed — run: npm i pixelmatch pngjs');
  }
  const diff = Buffer.alloc(width * height * 4);
  const numDiff = _pixelmatch(
    Uint8Array.from(buf1),
    Uint8Array.from(buf2),
    diff,
    width,
    height,
    { threshold, includeAA: false },
  );
  const percentDiff = (numDiff / (width * height)) * 100;
  return { numDiff, percentDiff, diff, width, height };
}

// ---------------------------------------------------------------------------
// PNG I/O helpers
// ---------------------------------------------------------------------------

function readPng(filePath) {
  if (!_PNG) return Promise.reject(new Error('pngjs not installed — run: npm i pngjs'));
  return new Promise((res, rej) => {
    const png = new _PNG();
    createReadStream(filePath)
      .pipe(png)
      .on('parsed', function () {
        res({ data: this.data, width: this.width, height: this.height });
      })
      .on('error', rej);
  });
}

function writePng(filePath, data, width, height) {
  if (!_PNG) return Promise.reject(new Error('pngjs not installed'));
  return new Promise((res, rej) => {
    const png = new _PNG({ width, height });
    png.data = data;
    const chunks = [];
    png.pack()
      .on('data', c => chunks.push(c))
      .on('end', () => { writeFileSync(filePath, Buffer.concat(chunks)); res(); })
      .on('error', rej);
  });
}

// ---------------------------------------------------------------------------
// Full file-based compare
// ---------------------------------------------------------------------------

/**
 * Compare all PNG screenshots in bundleDir against baselines in baselineDir.
 * Writes diff PNGs to diffOutDir (optional).
 * @returns {Promise<Array<{screen,baselineExists,percentDiff,numDiff?,diffPath?}>>}
 */
export async function compareScreens(bundleDir, baselineDir, diffOutDir) {
  if (!_pixelmatch || !_PNG) {
    console.warn('[visual_diff] pixelmatch/pngjs not available — skipping visual diff gate');
    console.warn('[visual_diff] Install with: npm i pixelmatch pngjs');
    return [];
  }

  mkdirSync(baselineDir, { recursive: true });
  if (diffOutDir) mkdirSync(diffOutDir, { recursive: true });

  const pngs = readdirSync(bundleDir).filter(f => f.endsWith('.png'));
  const results = [];

  for (const pngFile of pngs) {
    const currentPath = join(bundleDir, pngFile);
    const baselinePath = join(baselineDir, pngFile);
    const screen = pngFile.replace('.png', '');

    if (!existsSync(baselinePath)) {
      copyFileSync(currentPath, baselinePath);
      console.log(`[visual_diff] "${screen}" — baseline written (first run)`);
      results.push({ screen, baselineExists: false, percentDiff: 0, diffPath: null });
      continue;
    }

    const [current, baseline] = await Promise.all([
      readPng(currentPath),
      readPng(baselinePath),
    ]);

    if (current.width !== baseline.width || current.height !== baseline.height) {
      console.warn(`[visual_diff] "${screen}" — size mismatch: ` +
        `current ${current.width}x${current.height} vs baseline ${baseline.width}x${baseline.height}`);
      results.push({ screen, baselineExists: true, percentDiff: 100, sizeChange: true });
      continue;
    }

    const { numDiff, percentDiff, diff } = diffBuffersSync(
      current.data, baseline.data, current.width, current.height,
    );

    let diffPath = null;
    if (diffOutDir && numDiff > 0) {
      diffPath = join(diffOutDir, `${screen}.diff.png`);
      await writePng(diffPath, diff, current.width, current.height);
    }

    const label = percentDiff > 5 ? 'REGRESSION' : percentDiff > 0 ? 'changed' : 'match';
    console.log(`[visual_diff] "${screen}" — ${label} (${percentDiff.toFixed(2)}% diff, ${numDiff}px)`);
    results.push({ screen, baselineExists: true, percentDiff, numDiff, diffPath });
  }

  return results;
}

// ---------------------------------------------------------------------------
// CLI entrypoint
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    options: {
      'bundle-dir': { type: 'string' },
      baseline: { type: 'string', default: './ui-audit-baselines' },
      out: { type: 'string', default: './ui-audit-diffs' },
    },
    strict: false,
  });

  if (!values['bundle-dir']) {
    console.error('[visual_diff] ERROR: --bundle-dir <dir> required');
    process.exit(1);
  }

  const results = await compareScreens(
    resolve(values['bundle-dir']),
    resolve(values.baseline),
    resolve(values.out),
  );

  const regressions = results.filter(r => r.percentDiff > 5);
  if (regressions.length > 0) {
    console.warn(`\n${regressions.length} visual regression(s) detected`);
    for (const r of regressions) {
      console.warn(`  REGRESSION  ${r.screen}: ${r.percentDiff.toFixed(1)}% changed`);
    }
  }

  console.log('\nSUCCESS:visual-diff');
}

const __filename = fileURLToPath(import.meta.url);
// Junction/symlink-safe main-module check. `~/.claude/skills` is a junction to
// `skills.daily`; Node resolves symlinks for ESM so import.meta.url reports the REAL
// path while resolve(argv[1]) stays lexical. A lexical compare therefore NEVER matched
// on the documented `~/.claude/skills/...` invocation and main() silently never ran
// (exit 0, no output, no artifacts). realpathSync.native also collapses 8.3 short
// names (PREKZU~1), which realpathSync does not.
const __isMain = (a, b) => {
  try { return realpathSync.native(a) === realpathSync.native(b); }
  catch { return resolve(a) === resolve(b); }
};
if (process.argv[1] && __isMain(process.argv[1], __filename)) {
  main().catch(err => {
    console.error(`FAILED:visual-diff ${err.message}`);
    process.exit(1);
  });
}
