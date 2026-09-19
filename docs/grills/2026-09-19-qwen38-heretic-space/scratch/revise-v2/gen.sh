#!/usr/bin/env bash
# gen.sh — rebuild the assembled artefacts from script.js + schemas.js (the §13 + §9 texts of the design).
# assembled.mjs       = module factory makeScript(H) for the drive (meta outside the async body, everything from the
#                       args contract on inside `return (async function main(){ ... })()` — exactly the layout node accepted).
# assembled.js        = the plain body (meta + helpers + schemas + body), for the record; contains top-level await.
# assembled-check.js  = assembled.js wrapped in one async IIFE so `node --check` (CJS) passes.
set -eu
cd "$(dirname "$0")"
python3 - <<'PYEOF'
import pathlib
s = pathlib.Path('script.js').read_text()
assert s.startswith('export const meta = {')
marker = "// SCHEMAS: §9 pasted verbatim here (LEVELS, COMMON, COMMON_REQ, CMD, GATE_STEP, ROW_STATE, SETUP, CARD, CARD_INDEX, TESTS, BUILD, FINDING, VERDICT, MERGE, REPORT).\n"
assert marker in s, 'SCHEMAS marker not found'
pre, post = s.split(marker, 1)
pre = pre.replace('export const meta = {', 'const meta = {', 1)
# split the meta object from the helpers: meta ends with a line that is exactly '}'
lines = pre.split('\n')
close = next(i for i, l in enumerate(lines) if l == '}')
meta = '\n'.join(lines[:close + 1])
helpers = '\n'.join(lines[close + 1:])
schemas = pathlib.Path('schemas.js').read_text()
full = meta + '\n' + helpers + schemas + post          # meta + helpers + §9 + body = the whole §13 text (un-exported)
mjs = ('export function makeScript(H) {\n'
       '  const { agent, pipeline, parallel, log, phase, args, budget } = H;\n'
       + meta + '\n'
       '  return (async function main(){\n'
       + helpers + schemas + post +
       '  })();\n'
       '}\n')
pathlib.Path('assembled.mjs').write_text(mjs)
pathlib.Path('assembled.js').write_text(full)
pathlib.Path('assembled-check.js').write_text('(async () => {\n' + full + '\n})();\n')
print('gen: assembled.mjs / assembled.js / assembled-check.js written',
      len(mjs.splitlines()), len(full.splitlines()), len(full.splitlines()) + 2)
PYEOF
