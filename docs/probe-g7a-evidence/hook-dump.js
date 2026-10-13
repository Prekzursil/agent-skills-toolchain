// G-7a probe: append raw PreToolUse hook stdin (one JSON object per line) to $PROBE_HOOK_LOG.
// Fail-open by design: any error exits 0 silently so the probe never blocks the tool call.
let d = '';
process.stdin.on('data', c => d += c);
process.stdin.on('end', () => {
  try {
    const fs = require('fs');
    const p = process.env.PROBE_HOOK_LOG;
    if (p && d.trim()) fs.appendFileSync(p, d.trim() + '\n');
  } catch (e) { /* fail-open */ }
  process.exit(0);
});
// Safety net: never hang the harness if stdin never closes.
setTimeout(() => process.exit(0), 10000).unref();
