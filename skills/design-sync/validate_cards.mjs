#!/usr/bin/env node
// validate_cards.mjs — design-sync card self-check (mirrors the claude.ai/design app self-check).
// Scans a dir of @dsCard preview HTML files, validates each marker + self-containment + size,
// and writes _ds_manifest.json. Terminal-state marker on the last line.
//
// Usage:
//   node validate_cards.mjs --dir ./ds-bundle [--out ./ds-bundle/_ds_manifest.json]
//   node validate_cards.mjs --selftest
//
// Marker (first line of each preview HTML):
//   <!-- @dsCard group="Buttons" name="Primary buttons" subtitle="..." viewport="480x240" -->
// Only `group` is documented verbatim by DesignSync; name/subtitle/viewport mirror the
// register_assets asset schema. This validator is the single source of truth for the spelling.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const MAX_BYTES = 256 * 1024;            // write_files / get_file cap
const EXTERNAL_RE = /\b(?:src|href)\s*=\s*["']https?:\/\//i; // CDN/network dep in a preview

function parseArgs(argv) {
  const a = { dir: null, out: null, selftest: false };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--selftest') a.selftest = true;
    else if (k === '--dir') a.dir = argv[++i];
    else if (k === '--out') a.out = argv[++i];
  }
  return a;
}

function parseMarker(firstLine) {
  // returns {ok, attrs, error}
  const m = /^\s*<!--\s*@dsCard\b([^>]*?)-->\s*$/.exec(firstLine || '');
  if (!m) return { ok: false, error: 'first line is not a <!-- @dsCard ... --> marker' };
  const attrs = {};
  const re = /(\w+)\s*=\s*"([^"]*)"/g;
  let g;
  while ((g = re.exec(m[1])) !== null) attrs[g[1]] = g[2];
  if (!attrs.group) return { ok: false, error: 'missing required attribute: group' };
  if (attrs.group.length > 64) return { ok: false, error: 'group exceeds 64 chars' };
  if (attrs.name && attrs.name.length > 255) return { ok: false, error: 'name exceeds 255 chars' };
  let viewport = null;
  if (attrs.viewport) {
    const v = /^(\d+)(?:x(\d+))?$/.exec(attrs.viewport.trim());
    if (!v) return { ok: false, error: `viewport must be WxH (got "${attrs.viewport}")` };
    viewport = { width: Number(v[1]) };
    if (v[2]) viewport.height = Number(v[2]);
  }
  return { ok: true, attrs, viewport };
}

async function* walk(dir) {
  for (const e of await fs.readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (e.isFile() && /\.html?$/i.test(e.name)) yield p;
  }
}

async function validateDir(dir, outPath) {
  const errors = [];
  const cards = [];
  const seenPaths = new Set();
  let count = 0;
  for await (const file of walk(dir)) {
    count++;
    const rel = path.relative(dir, file).split(path.sep).join('/');
    const buf = await fs.readFile(file);
    if (buf.byteLength > MAX_BYTES) {
      errors.push(`${rel}: ${(buf.byteLength / 1024).toFixed(0)} KiB exceeds 256 KiB cap`);
      continue;
    }
    const text = buf.toString('utf8');
    const firstLine = text.split(/\r?\n/, 1)[0];
    const parsed = parseMarker(firstLine);
    if (!parsed.ok) { errors.push(`${rel}: ${parsed.error}`); continue; }
    if (EXTERNAL_RE.test(text)) {
      errors.push(`${rel}: preview is not self-contained (external http(s) src/href — inline or data-URI it)`);
      continue;
    }
    if (seenPaths.has(rel)) { errors.push(`${rel}: duplicate card path`); continue; }
    seenPaths.add(rel);
    const card = { path: rel, group: parsed.attrs.group };
    if (parsed.attrs.name) card.name = parsed.attrs.name;
    if (parsed.attrs.subtitle) card.subtitle = parsed.attrs.subtitle;
    if (parsed.viewport) card.viewport = parsed.viewport;
    cards.push(card);
  }
  if (count === 0) errors.push(`no .html preview files found under ${dir}`);
  const manifest = { version: 1, generatedAt: new Date().toISOString(), cards };
  if (errors.length === 0 && outPath) {
    await fs.writeFile(outPath, JSON.stringify(manifest, null, 2));
  }
  return { errors, cards, manifest, count };
}

async function selftest() {
  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'ds-selftest-'));
  const good = (group, name) =>
    `<!-- @dsCard group="${group}" name="${name}" subtitle="x / y" viewport="400x200" -->\n` +
    `<!doctype html><html><head><style>.b{padding:8px}</style></head><body><button class="b">Go</button></body></html>\n`;
  await fs.mkdir(path.join(tmp, 'components', 'button'), { recursive: true });
  await fs.mkdir(path.join(tmp, 'foundations'), { recursive: true });
  await fs.writeFile(path.join(tmp, 'components', 'button', 'index.html'), good('Buttons', 'Primary buttons'));
  await fs.writeFile(path.join(tmp, 'foundations', 'colors.html'), good('Colors', 'Palette'));

  const pass = await validateDir(tmp, path.join(tmp, '_ds_manifest.json'));
  if (pass.errors.length !== 0) throw new Error('selftest: well-formed bundle failed: ' + pass.errors.join('; '));
  if (pass.cards.length !== 2) throw new Error('selftest: expected 2 cards, got ' + pass.cards.length);
  if (pass.cards[0].viewport.width !== 400) throw new Error('selftest: viewport not parsed');

  // negative: strip the marker -> must fail
  await fs.writeFile(path.join(tmp, 'foundations', 'colors.html'),
    '<!doctype html><html><body>no marker</body></html>\n');
  const fail = await validateDir(tmp, null);
  if (fail.errors.length === 0) throw new Error('selftest: marker-less card was not rejected');

  // negative: external CDN dep -> must fail
  await fs.writeFile(path.join(tmp, 'foundations', 'colors.html'),
    `<!-- @dsCard group="Colors" name="P" -->\n<html><head><link href="https://cdn.example/x.css"></head></html>\n`);
  const fail2 = await validateDir(tmp, null);
  if (!fail2.errors.some((e) => /self-contained/.test(e))) throw new Error('selftest: external dep not rejected');

  await fs.rm(tmp, { recursive: true, force: true });
  console.log(`SUCCESS:design-sync-validate selftest (2 cards built, marker-strip + CDN-dep rejected)`);
}

async function main() {
  const a = parseArgs(process.argv);
  try {
    if (a.selftest) return await selftest();
    if (!a.dir) { console.log('FAILED:design-sync-validate --dir <bundle> required (or --selftest)'); process.exit(1); }
    const out = a.out || path.join(a.dir, '_ds_manifest.json');
    const r = await validateDir(a.dir, out);
    if (r.errors.length) {
      for (const e of r.errors) console.error('  - ' + e);
      console.log(`FAILED:design-sync-validate ${r.errors.length} error(s) across ${r.count} file(s)`);
      process.exit(1);
    }
    console.log(`manifest -> ${out}`);
    console.log(`SUCCESS:design-sync-validate ${r.cards.length} cards`);
  } catch (err) {
    console.log(`FAILED:design-sync-validate ${err.message}`);
    process.exit(1);
  }
}

main();
