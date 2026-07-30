#!/usr/bin/env node
// Mutation probe for preflight()'s five guards.
//
// WHY THIS FILE EXISTS. A green suite is not evidence that a guard is protecting anything -
// the guard could be unreachable and every test could be passing for another reason. So each
// guard is REMOVED in turn and the suite must go RED. A mutation that SURVIVES is a hole in
// the tests, reported as a failure here. (rules/common/single-signal-verification.md 3b, the
// both-states test; same pattern as .agents/skills/claim-verify-gate's mutation step.)
//
// The M4/M5 mutants are the load-bearing ones. `expected` is normally derived from the same
// args object that broke, so a guard written only as `units.length < 2 && expected > 1` is
// INERT when `expected` is undefined - the collapse check would never fire on the very bug it
// was written for. M4/M5 prove the shape checks close that.
//
// Run: node test_preflight_mutations.mjs   (wired into `npm test` in package.json)

import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const MODULE = join(HERE, 'fanout_schema.mjs')
const SUITE = join(HERE, 'test_fanout_schema.mjs')

// [id, exact source anchor, replacement that disables the guard]
const MUTATIONS = [
  [
    'M1 collapsed-work-list',
    'if (units.length !== expected) {',
    'if (false) {',
  ],
  ['M2 undefined-in-prompt', 'const m = UNDEFINED_TOKEN.exec(p)', 'const m = null'],
  ['M3 args-not-object', "if (typeof argsRaw === 'string') {", 'if (false) {'],
  [
    'M4 expected-not-positive-int',
    'if (!Number.isInteger(expected) || expected < 1) {',
    'if (false) {',
  ],
  ['M5 units-not-array', 'if (!Array.isArray(units)) {', 'if (false) {'],
]

// Read as a Buffer so the file is restored byte-for-byte, line endings included.
const ORIGINAL = readFileSync(MODULE)
const source = ORIGINAL.toString('utf8')

/** @returns {{fail:number, pass:number, ok:boolean}} */
function runSuite() {
  const r = spawnSync(process.execPath, ['--test', SUITE], { encoding: 'utf8', cwd: HERE })
  const out = `${r.stdout || ''}${r.stderr || ''}`
  // Glyph-agnostic: node decorates the summary lines and a console codepage can mangle the
  // decoration. Anchor on the token, never on the glyph.
  const fail = /\bfail (\d+)\b/.exec(out)
  const pass = /\bpass (\d+)\b/.exec(out)
  return {
    fail: fail ? Number(fail[1]) : -1,
    pass: pass ? Number(pass[1]) : -1,
    ok: r.status === 0,
    tail: out.slice(-600),
  }
}

let survivors = 0
try {
  const base = runSuite()
  // DETECTOR CONTROL: an unparsed summary must not read as a pass.
  if (base.fail < 0 || base.pass < 0) {
    console.error(`FAILED:preflight-mutations unparsable test summary\n${base.tail}`)
    process.exit(1)
  }
  console.log(`BASELINE pass=${base.pass} fail=${base.fail}`)
  if (base.fail !== 0 || !base.ok) {
    console.error('FAILED:preflight-mutations baseline is not green - the probe measures nothing')
    process.exit(1)
  }

  for (const [id, anchor, replacement] of MUTATIONS) {
    if (!source.includes(anchor)) {
      console.error(`FAILED:preflight-mutations ${id} anchor not found - probe is broken, not the code`)
      process.exit(1)
    }
    writeFileSync(MODULE, source.replace(anchor, replacement))
    const r = runSuite()
    writeFileSync(MODULE, ORIGINAL)
    const killed = r.fail > 0
    if (!killed) survivors++
    console.log(`${id}: fail=${r.fail} ${killed ? 'KILLED' : 'SURVIVED - TESTS DO NOT COVER THIS'}`)
  }
} finally {
  // Never leave a mutated module behind, even on an unexpected throw.
  writeFileSync(MODULE, ORIGINAL)
}

if (!readFileSync(MODULE).equals(ORIGINAL)) {
  console.error('FAILED:preflight-mutations module not restored byte-identical')
  process.exit(1)
}

if (survivors > 0) {
  console.error(`FAILED:preflight-mutations ${survivors} surviving mutant(s)`)
  process.exit(1)
}
console.log(`SUCCESS:preflight-mutations ${MUTATIONS.length}/${MUTATIONS.length} killed`)
