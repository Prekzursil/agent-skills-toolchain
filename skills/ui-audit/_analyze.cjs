const fs = require('fs');
const OUT = process.argv[2];
const L = JSON.parse(fs.readFileSync(OUT + '/lint.json', 'utf8'));
const a = L.findings || L;
const r = JSON.parse(fs.readFileSync(OUT + '/results.json', 'utf8'));
const ds = a.filter((x) => x.screen.endsWith('.desktop'));
const areaTT = {}, areaSP = {};
for (const x of ds) {
  const s = x.screen.replace('.desktop', '');
  if (x.rule === 'tap-target') areaTT[s] = (areaTT[s] || 0) + 1;
  if (x.rule === 'off-scale-spacing') areaSP[s] = (areaSP[s] || 0) + 1;
}
console.log('TAP-TARGET desktop/area:', JSON.stringify(areaTT));
console.log('OFF-SCALE-SPACING desktop/area:', JSON.stringify(areaSP));
const rules = {};
for (const x of a) rules[x.rule] = (rules[x.rule] || 0) + 1;
console.log('ALL RULES (both vp):', JSON.stringify(rules));
console.log('AXE final desktop:');
for (const x of r) {
  if (x.viewport !== 'desktop' || !x.axe || !x.axe.length) continue;
  console.log('  ' + x.area + ': ' + x.axe.map((v) => v.impact + '/' + v.id + 'x' + v.nodes + (v.sample ? ' [' + v.sample.slice(0, 40) + ']' : '')).join(' | '));
}
const dash = JSON.parse(fs.readFileSync(OUT + '/dashboard.desktop.bundle.json', 'utf8'));
console.log('pageSignals(dashboard):', JSON.stringify(dash.pageSignals));
// smallest tap targets across all desktop bundles (unique by selector head)
const tt = ds.filter((x) => x.rule === 'tap-target' && x.value && /\d/.test(x.value));
const parsed = tt.map((x) => { const m = (x.value || '').match(/([\d.]+)×([\d.]+)/); return m ? { w: +m[1], h: +m[2], sel: x.selector.slice(0, 55), area: x.screen } : null; }).filter(Boolean).filter((x) => x.w > 0 && x.h > 0);
parsed.sort((p, q) => (p.w * p.h) - (q.w * q.h));
console.log('SMALLEST real tap targets:');
const seen = new Set();
for (const p of parsed) { const k = p.sel.split('.').slice(0, 2).join('.'); if (seen.has(k)) continue; seen.add(k); console.log('  ' + p.w + 'x' + p.h + '  ' + p.sel); if (seen.size >= 10) break; }
