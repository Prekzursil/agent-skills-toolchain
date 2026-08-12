#!/usr/bin/env node
// transpose-to-figma / figma_parity.mjs — the 6th ui-audit gate (design #7, MASTER C-Tier2 S-series).
//
// Pixel-diff the Figma canvas (design truth) against the built UI (build truth):
//   • Figma side  = a PNG exported via the Figma MCP `get_screenshot` tool, saved to disk.
//   • Build side  = a PNG produced by ui-audit / design-review-loop `capture.mjs` (Playwright).
// This harness NEVER calls a model and NEVER touches Figma — like transpose.mjs it is PLUMBING:
// it decodes both PNGs, computes a numeric parity, and prints a terminal-state marker.
//
// Zero external deps: a minimal PNG decoder (node:zlib for inflate) + a pixelmatch-style
// YIQ perceptual diff. Supports 8-bit, non-interlaced RGB (colorType 2) and RGBA (colorType 6)
// — the shapes Figma exports and Playwright screenshots use.
//
// SHADOW MODE by default (council C5): it OBSERVES and LOGS a parity verdict but never blocks —
// the process exits 0 with a SUCCESS marker as long as the comparison itself ran. Pass --enforce
// to make a sub-threshold parity exit 1 with a FAILED marker (opt-in; NOT shadow).
//
// Subcommand:
//   diff --figma <a.png> --build <b.png> [--threshold 0.1] [--min-parity 0.98]
//        [--out <dir>] [--diff-png <path>] [--enforce]
//     -> prints a parity record (mismatched px, parity ratio, verdict) + SUCCESS/FAILED marker.
//
// Terminal-state markers (AGENTS.md §4):
//   SUCCESS:figma-parity-<id>  /  FAILED:figma-parity-<id> <reason>

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { inflateSync, deflateSync } from 'node:zlib';

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

const shortId = () => Math.random().toString(36).slice(2, 8);

const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

// Minimal PNG decoder -> { width, height, data: RGBA Uint8Array }.
function decodePng(buf) {
  if (buf.length < 8 || !buf.subarray(0, 8).equals(PNG_SIG)) {
    throw new Error('not a PNG (bad signature)');
  }
  let pos = 8;
  let width = 0, height = 0, bitDepth = 0, colorType = 0, interlace = 0;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const dataStart = pos + 8;
    if (type === 'IHDR') {
      width = buf.readUInt32BE(dataStart);
      height = buf.readUInt32BE(dataStart + 4);
      bitDepth = buf[dataStart + 8];
      colorType = buf[dataStart + 9];
      interlace = buf[dataStart + 12];
    } else if (type === 'IDAT') {
      idat.push(buf.subarray(dataStart, dataStart + len));
    } else if (type === 'IEND') {
      break;
    }
    pos = dataStart + len + 4; // skip data + CRC
  }
  if (!width || !height) throw new Error('no IHDR / zero dimensions');
  if (bitDepth !== 8) throw new Error(`unsupported bitDepth ${bitDepth} (expected 8)`);
  if (interlace !== 0) throw new Error('interlaced PNG unsupported');
  const channels = colorType === 2 ? 3 : colorType === 6 ? 4 : 0;
  if (!channels) throw new Error(`unsupported colorType ${colorType} (expected 2 RGB or 6 RGBA)`);

  const raw = inflateSync(Buffer.concat(idat));
  const bpp = channels; // bytes per pixel (8-bit)
  const stride = width * bpp;
  const out = new Uint8Array(width * height * 4);
  let rpos = 0;
  const prev = new Uint8Array(stride);
  const cur = new Uint8Array(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[rpos++];
    for (let x = 0; x < stride; x++) cur[x] = raw[rpos + x];
    rpos += stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? cur[x - bpp] : 0;      // left
      const b = prev[x];                           // up
      const c = x >= bpp ? prev[x - bpp] : 0;      // up-left
      let v = cur[x];
      switch (filter) {
        case 0: break;
        case 1: v = (v + a) & 0xff; break;
        case 2: v = (v + b) & 0xff; break;
        case 3: v = (v + ((a + b) >> 1)) & 0xff; break;
        case 4: v = (v + paeth(a, b, c)) & 0xff; break;
        default: throw new Error(`unknown filter ${filter}`);
      }
      cur[x] = v;
    }
    // expand scanline into RGBA
    for (let x = 0; x < width; x++) {
      const s = x * bpp;
      const d = (y * width + x) * 4;
      out[d] = cur[s];
      out[d + 1] = cur[s + 1];
      out[d + 2] = cur[s + 2];
      out[d + 3] = channels === 4 ? cur[s + 3] : 255;
    }
    prev.set(cur);
  }
  return { width, height, data: out };
}

// pixelmatch-style perceptual delta in YIQ space.
function rgb2y(r, g, b) { return r * 0.29889531 + g * 0.58662247 + b * 0.11448223; }
function rgb2i(r, g, b) { return r * 0.59597799 - g * 0.27417610 - b * 0.32180189; }
function rgb2q(r, g, b) { return r * 0.21147017 - g * 0.52261711 + b * 0.31114694; }

function colorDelta(img, i) {
  // premultiply alpha against white background so transparent regions compare sanely
  const a = img[i + 3] / 255;
  const r = 255 + (img[i] - 255) * a;
  const g = 255 + (img[i + 1] - 255) * a;
  const b = 255 + (img[i + 2] - 255) * a;
  return { r, g, b };
}

function cmdDiff(args) {
  const id = shortId();
  const figmaPath = args.figma;
  const buildPath = args.build;
  if (!figmaPath || figmaPath === true) {
    console.log(`FAILED:figma-parity-${id} --figma <png> is required (Figma get_screenshot export)`);
    process.exit(1);
  }
  if (!buildPath || buildPath === true) {
    console.log(`FAILED:figma-parity-${id} --build <png> is required (capture.mjs screenshot)`);
    process.exit(1);
  }
  const threshold = args.threshold ? Number(args.threshold) : 0.1; // 0..1 per-pixel sensitivity
  const minParity = args['min-parity'] ? Number(args['min-parity']) : 0.98;
  const enforce = !!args.enforce;

  let a, b;
  try { a = decodePng(readFileSync(figmaPath)); }
  catch (e) { console.log(`FAILED:figma-parity-${id} figma PNG decode: ${e.message}`); process.exit(1); }
  try { b = decodePng(readFileSync(buildPath)); }
  catch (e) { console.log(`FAILED:figma-parity-${id} build PNG decode: ${e.message}`); process.exit(1); }

  const dimsMatch = a.width === b.width && a.height === b.height;
  // Compare over the overlapping region; count non-overlap as mismatch (dimension drift is real drift).
  const w = Math.min(a.width, b.width);
  const h = Math.min(a.height, b.height);
  const totalPixels = Math.max(a.width * a.height, b.width * b.height);
  const maxDelta = 35215 * threshold * threshold; // pixelmatch constant (max YIQ delta^2)

  let mismatched = 0;
  const wantDiff = args['diff-png'] && args['diff-png'] !== true;
  const diffData = wantDiff ? new Uint8Array(w * h * 4) : null;

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ia = (y * a.width + x) * 4;
      const ib = (y * b.width + x) * 4;
      const pa = colorDelta(a.data, ia);
      const pb = colorDelta(b.data, ib);
      const dy = rgb2y(pa.r, pa.g, pa.b) - rgb2y(pb.r, pb.g, pb.b);
      const di = rgb2i(pa.r, pa.g, pa.b) - rgb2i(pb.r, pb.g, pb.b);
      const dq = rgb2q(pa.r, pa.g, pa.b) - rgb2q(pb.r, pb.g, pb.b);
      const delta = 0.5053 * dy * dy + 0.299 * di * di + 0.1957 * dq * dq;
      const isDiff = delta > maxDelta;
      if (isDiff) mismatched++;
      if (diffData) {
        const d = (y * w + x) * 4;
        if (isDiff) { diffData[d] = 255; diffData[d + 1] = 0; diffData[d + 2] = 0; diffData[d + 3] = 255; }
        else { diffData[d] = 255; diffData[d + 1] = 255; diffData[d + 2] = 255; diffData[d + 3] = 255; }
      }
    }
  }
  // Pixels outside the overlap are counted as mismatched drift.
  const nonOverlap = totalPixels - w * h;
  mismatched += nonOverlap;

  const parity = totalPixels === 0 ? 1 : 1 - mismatched / totalPixels;
  const pass = parity >= minParity;

  if (diffData) {
    try {
      const png = encodePng(w, h, diffData);
      writeFileSync(args['diff-png'], png);
    } catch (e) {
      // diff image is a nicety, never fatal
      console.log(`NOTE: could not write diff png: ${e.message}`);
    }
  }

  const record = {
    id: `figma-parity-${id}`,
    figma: figmaPath,
    build: buildPath,
    figmaDims: [a.width, a.height],
    buildDims: [b.width, b.height],
    dimsMatch,
    comparedRegion: [w, h],
    totalPixels,
    mismatchedPixels: mismatched,
    parity: Number(parity.toFixed(6)),
    threshold,
    minParity,
    verdict: pass ? 'pass' : 'fail',
    mode: enforce ? 'enforce' : 'shadow',
    capturedAt: new Date().toISOString(),
  };
  if (args.out && args.out !== true) {
    mkdirSync(args.out, { recursive: true });
    const file = join(args.out, 'figma-parity.json');
    writeFileSync(file, JSON.stringify(record, null, 2));
    console.log(`wrote ${file}`);
  }
  console.log(JSON.stringify(record, null, 2));

  if (!pass && enforce) {
    console.log(`FAILED:figma-parity-${id} parity ${parity.toFixed(4)} < min ${minParity} (enforce mode)`);
    process.exit(1);
  }
  if (!pass) {
    console.log(`NOTE: SHADOW verdict=fail (parity ${parity.toFixed(4)} < ${minParity}); observing only, not blocking.`);
  }
  console.log(`SUCCESS:figma-parity-${id}`);
}

// Minimal PNG encoder (RGBA, filter 0, single IDAT) for the optional diff image.
function encodePng(width, height, rgba) {
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0; // filter none
    for (let x = 0; x < stride; x++) raw[y * (stride + 1) + 1 + x] = rgba[y * stride + x];
  }
  const idatData = deflateSync(raw);
  const chunks = [];
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const typeBuf = Buffer.from(type, 'ascii');
    const body = Buffer.concat([typeBuf, data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body) >>> 0, 0);
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 6;   // color type RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  chunks.push(PNG_SIG, chunk('IHDR', ihdr), chunk('IDAT', idatData), chunk('IEND', Buffer.alloc(0)));
  return Buffer.concat(chunks);
}

let CRC_TABLE;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const args = parseArgs(process.argv.slice(2));
const sub = args._[0];
try {
  if (sub === 'diff') cmdDiff(args);
  else {
    console.log('Usage: figma_parity.mjs diff --figma <a.png> --build <b.png> [--threshold 0.1] [--min-parity 0.98] [--out <dir>] [--diff-png <path>] [--enforce]');
    console.log(`FAILED:figma-parity-usage-${shortId()} unknown subcommand: ${sub ?? '(none)'}`);
    process.exit(1);
  }
} catch (e) {
  console.log(`FAILED:figma-parity-${shortId()} ${e.message}`);
  process.exit(1);
}
