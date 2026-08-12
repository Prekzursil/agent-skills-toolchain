// Smallest real test: prove exemplars.json parses, its dimension keys EXACTLY match
// the nine SCORING_DIMENSIONS from critique_schema.mjs, weights agree, and every anchor
// is structurally sound (score in 0-4, band/critique/evidence/recommendation present,
// and the critical-error invariant score==0 holds). Additive — touches no live file.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { SCORING_DIMENSIONS, DIMENSION_WEIGHTS } from '../critique_schema.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const pack = JSON.parse(readFileSync(join(here, 'exemplars.json'), 'utf8'));
const errors = [];

const packDims = Object.keys(pack.dimensions);
const want = [...SCORING_DIMENSIONS].sort();
const got = [...packDims].sort();
if (JSON.stringify(want) !== JSON.stringify(got)) {
  errors.push(`dimension set mismatch:\n  want ${want.join(',')}\n  got  ${got.join(',')}`);
}

for (const [dim, spec] of Object.entries(pack.dimensions)) {
  if (spec.weight !== DIMENSION_WEIGHTS[dim]) {
    errors.push(`${dim}: weight ${spec.weight} != schema ${DIMENSION_WEIGHTS[dim]}`);
  }
  if (!Array.isArray(spec.anchors) || spec.anchors.length < 3) {
    errors.push(`${dim}: expected >=3 anchors, got ${spec.anchors?.length}`);
    continue;
  }
  const scores = spec.anchors.map(a => a.score).sort((x, y) => x - y);
  if (JSON.stringify(scores) !== JSON.stringify([0, 2, 4])) {
    errors.push(`${dim}: anchor scores ${scores.join(',')} != 0,2,4`);
  }
  for (const a of spec.anchors) {
    if (typeof a.id !== 'string' || !a.id) errors.push(`${dim}: anchor missing id`);
    if (typeof a.score !== 'number' || a.score < 0 || a.score > 4) errors.push(`${dim}/${a.id}: score out of 0-4`);
    for (const k of ['band', 'critique', 'evidence', 'recommendation']) {
      if (typeof a[k] !== 'string' || !a[k].trim()) errors.push(`${dim}/${a.id}: missing ${k}`);
    }
    // §2.3 invariant: a critical-error anchor MUST carry score 0.
    if (a.critical === true && a.score !== 0) errors.push(`${dim}/${a.id}: critical anchor must have score 0`);
  }
}

const nDims = packDims.length;
const nAnchors = Object.values(pack.dimensions).reduce((n, s) => n + s.anchors.length, 0);
if (errors.length) {
  for (const e of errors) console.error('  - ' + e);
  console.error(`FAILED:uicrit-fewshot-pack ${errors.length} violation(s)`);
  process.exitCode = 1;
} else {
  console.log(`[pack] dimensions=${nDims}  anchors=${nAnchors}  weights=OK  keys=match SCORING_DIMENSIONS`);
  console.log('SUCCESS:uicrit-fewshot-pack');
}
