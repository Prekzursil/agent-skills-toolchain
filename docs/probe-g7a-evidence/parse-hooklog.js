// Parse probe hook log JSONL: print per-entry key summary + identity-bearing fields.
const fs = require('fs');
const f = process.argv[2];
const lines = fs.readFileSync(f, 'utf8').split('\n').filter(l => l.trim());
const keySets = {};
for (const l of lines) {
  let o;
  try { o = JSON.parse(l); } catch (e) { console.log('UNPARSEABLE LINE: ' + l.slice(0, 120)); continue; }
  const ks = Object.keys(o).sort().join(',');
  keySets[ks] = (keySets[ks] || 0) + 1;
  const interesting = {};
  for (const k of Object.keys(o)) {
    if (/agent|parent|depth|spawn|session|transcript|tool_name|hook_event|permission|cwd/i.test(k)) {
      interesting[k] = typeof o[k] === 'string' ? o[k].replace(/\\/g, '/') : o[k];
    }
  }
  console.log(JSON.stringify(interesting));
}
console.log('---KEYSET SUMMARY---');
for (const [ks, n] of Object.entries(keySets)) console.log(n + 'x  ' + ks);
