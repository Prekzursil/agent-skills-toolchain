// Tests for the fan-out schema module (B6).
// Run: npm --prefix tools/fanout-schema test
//
// Every assertion here is anchored to a measured number from the 10.65 GB transcript scan
// (11,693 files, 3,735 StructuredOutput calls, 849 errors). The numbers are quoted inline so
// a future reader can falsify them rather than trust them.

import test from 'node:test'
import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  fanoutSchema,
  findingsSchema,
  lintSchema,
  lintSource,
  preflight,
  validate,
  PREFLIGHT,
  RULES,
} from './fanout_schema.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURE = JSON.parse(
  readFileSync(join(HERE, 'historical-rejection.fixture.json'), 'utf8'),
)
const REPO_ROOT = join(HERE, '..', '..')
const LINTER = join(HERE, 'lint_fanout_schemas.mjs')
const PRODUCTION_WORKFLOWS = join(REPO_ROOT, 'workflows')
const QUALITY_WORKFLOW = join(REPO_ROOT, '.github', 'workflows', 'quality.yml')
const TOOL_PACKAGE = join(HERE, 'package.json')

const AUTHORITATIVE_SKILLS = join(REPO_ROOT, '.agents', 'skills')

function matchingLines(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => {
    const line = source.slice(0, match.index).split('\n').length
    return `${line}:${match[0]}`
  })
}

function runLint(...paths) {
  const args = [LINTER, ...paths]
  return spawnSync(process.execPath, args, { encoding: 'utf8', shell: true })
}

// ---------------------------------------------------------------------------
// KNOWN-POSITIVE CONTROL for the validator itself.
// Before any "now it passes" claim means anything, the validator must be shown to
// REPRODUCE the original rejection. A validator that accepts everything would make
// every other test in this file pass vacuously.
// ---------------------------------------------------------------------------

test('CONTROL: validator reproduces the harness rejection of the historical payload', () => {
  const r = validate(FIXTURE.legacy_schema, FIXTURE.rejected_payload)
  assert.equal(r.valid, false, 'legacy schema must still reject the historical payload')
  const missing = r.errors.filter((e) => e.kind === 'missing_required').map((e) => e.property)
  assert.deepEqual(missing.sort(), ['confidence', 'kg_triples'])
})

test('CONTROL: validator can REJECT, not just accept - narrative absent is invalid', () => {
  const s = fanoutSchema({ narrative: 'summary' })
  const r = validate(s, { confidence: 'high' })
  assert.equal(r.valid, false)
  assert.equal(r.errors[0].kind, 'missing_required')
  assert.equal(r.errors[0].property, 'summary')
})

test('CONTROL: validator enforces the narrative TYPE (not vacuous)', () => {
  const s = fanoutSchema({ narrative: 'summary' })
  assert.equal(validate(s, { summary: 42 }).valid, false)
  assert.equal(validate(s, { summary: 'ok' }).valid, true)
})

// ---------------------------------------------------------------------------
// THE DELIVERABLE'S CORE CLAIM
// ---------------------------------------------------------------------------

test('the historical payload that FAILED now validates against the house schema', () => {
  // Same fields, same descriptions - only the `required` set changes.
  const house = fanoutSchema({
    narrative: 'summary',
    optional: {
      data_rows: 'string[]',
      kg_triples: 'string[]',
      tools_used: 'string[]',
      citations: 'string[]',
      confidence: ['high', 'medium', 'low', 'unverified'],
      new_angles: 'string[]',
    },
  })
  const r = validate(house, FIXTURE.rejected_payload)
  assert.equal(r.valid, true, JSON.stringify(r.errors))
})

test('the house schema keeps every property the legacy schema declared', () => {
  const house = fanoutSchema({
    narrative: 'summary',
    optional: {
      data_rows: 'string[]',
      kg_triples: 'string[]',
      tools_used: 'string[]',
      citations: 'string[]',
      confidence: ['high', 'medium', 'low', 'unverified'],
      new_angles: 'string[]',
    },
  })
  for (const k of Object.keys(FIXTURE.legacy_schema.properties)) {
    assert.ok(house.properties[k], `lost property ${k} - properties steer the model, keep them`)
  }
  assert.deepEqual(house.required, ['summary'])
})

// ---------------------------------------------------------------------------
// LINT RULES - each encodes a measured failure mode
// ---------------------------------------------------------------------------

test('lint flags the legacy schema and names the array-in-required rule', () => {
  const v = lintSchema(FIXTURE.legacy_schema)
  const ids = v.map((x) => x.rule)
  assert.ok(ids.includes(RULES.ARRAY_IN_REQUIRED), 'kg_triples is a required array')
  assert.ok(ids.includes(RULES.MULTI_REQUIRED), 'required has 3 entries, not 1')
})

test('lint flags a required NON-array ancillary field too (strings are omitted MORE)', () => {
  // 691 of 1,193 property omissions were string-typed vs 457 array-typed.
  // A lint that only bans arrays would miss the majority of the damage.
  const v = lintSchema({
    type: 'object',
    properties: { summary: { type: 'string' }, confidence: { type: 'string' } },
    required: ['summary', 'confidence'],
  })
  assert.ok(v.some((x) => x.rule === RULES.MULTI_REQUIRED))
  assert.ok(v.some((x) => x.property === 'confidence'))
})

test('lint flags additionalProperties:false (30 measured rejections)', () => {
  const v = lintSchema({
    type: 'object',
    additionalProperties: false,
    properties: { summary: { type: 'string' } },
    required: ['summary'],
  })
  assert.ok(v.some((x) => x.rule === RULES.NO_ADDITIONAL_PROPERTIES))
})

test('lint flags a required field the schema never declared', () => {
  const v = lintSchema({
    type: 'object',
    properties: { summary: { type: 'string' } },
    required: ['summary', 'ghost'],
  })
  assert.ok(v.some((x) => x.rule === RULES.UNDECLARED_REQUIRED && x.property === 'ghost'))
})

test('lint PASSES a schema built by fanoutSchema (the module is self-consistent)', () => {
  const s = fanoutSchema({
    narrative: 'findings_markdown',
    optional: { lens: 'string', citations: 'string[]', confidence: ['high', 'low'] },
  })
  assert.deepEqual(lintSchema(s), [])
})

test('lint does NOT flag a wide schema - required-count is not the driver', () => {
  // Measured: required=10 -> 0/30 errors; required=3 -> 437/819. Width is not the defect,
  // so a width-based lint would be wrong. Only `required` is linted.
  const wide = fanoutSchema({
    narrative: 'summary',
    optional: Object.fromEntries(
      ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l'].map((k) => [k, 'string']),
    ),
  })
  assert.equal(Object.keys(wide.properties).length, 13)
  assert.deepEqual(lintSchema(wide), [])
})

// ---------------------------------------------------------------------------
// CONSTRUCTION GUARDS - make the failure unrepresentable, not just detectable
// ---------------------------------------------------------------------------

test('fanoutSchema refuses a non-string narrative field', () => {
  assert.throws(() => fanoutSchema({ narrative: 'items', narrativeType: 'array' }), /string/i)
})

test('fanoutSchema refuses to mark an optional field required', () => {
  assert.throws(
    () => fanoutSchema({ narrative: 'summary', optional: { x: 'string' }, required: ['x'] }),
    /required/i,
  )
})

test('fanoutSchema requires a narrative field name', () => {
  assert.throws(() => fanoutSchema({}), /narrative/i)
})

// ---------------------------------------------------------------------------
// VALIDATOR SUBSET - the JSON Schema features the harness actually uses
// ---------------------------------------------------------------------------

test('validator checks enum on an optional field when present', () => {
  const s = fanoutSchema({ narrative: 'summary', optional: { confidence: ['high', 'low'] } })
  assert.equal(validate(s, { summary: 'x', confidence: 'high' }).valid, true)
  assert.equal(validate(s, { summary: 'x', confidence: 'maybe' }).valid, false)
  assert.equal(validate(s, { summary: 'x' }).valid, true, 'absent optional is fine')
})

test('validator checks array item types', () => {
  const s = fanoutSchema({ narrative: 'summary', optional: { rows: 'string[]' } })
  assert.equal(validate(s, { summary: 'x', rows: ['a', 'b'] }).valid, true)
  assert.equal(validate(s, { summary: 'x', rows: 'a' }).valid, false)
  assert.equal(validate(s, { summary: 'x', rows: [1] }).valid, false)
})

test('validator accepts undeclared extra keys by default (models add keys)', () => {
  // 30 measured rejections were "must NOT have additional properties".
  const s = fanoutSchema({ narrative: 'summary' })
  assert.equal(validate(s, { summary: 'x', surprise: 'y' }).valid, true)
})

test('validator rejects a non-object payload', () => {
  const s = fanoutSchema({ narrative: 'summary' })
  assert.equal(validate(s, ['not', 'an', 'object']).valid, false)
  assert.equal(validate(s, null).valid, false)
})

// ---------------------------------------------------------------------------
// findingsSchema - the house default
// ---------------------------------------------------------------------------

test('findingsSchema requires exactly findings_markdown and lints clean', () => {
  const s = findingsSchema({ lens: 'string', citations: 'string[]' })
  assert.deepEqual(s.required, ['findings_markdown'])
  assert.equal(s.properties.findings_markdown.type, 'string')
  assert.ok(s.properties.findings_markdown.description)
  assert.deepEqual(lintSchema(s), [])
  assert.equal(validate(s, { findings_markdown: '# found' }).valid, true)
})

// ---------------------------------------------------------------------------
// lintSource - run the rules over schemas already written in workflow SOURCE
// ---------------------------------------------------------------------------

test('CONTROL: lintSource finds the real culprit schema in real workflow source', () => {
  // Verbatim shape of phenibut-program-build-wf_27298efb-dc9.js.
  const src = `
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string', description: 'what was found, 2-5 sentences' },
    kg_triples: { type: 'array', items: { type: 'string' }, description: 'subject | relation | object' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low', 'unverified'] },
  },
  required: ['summary', 'kg_triples', 'confidence'],
}
`
  const found = lintSource(src)
  assert.equal(found.length, 1, 'exactly one schema literal expected')
  assert.deepEqual(found[0].required, ['summary', 'kg_triples', 'confidence'])
  const rules = found[0].violations.map((v) => v.rule)
  assert.ok(rules.includes(RULES.ARRAY_IN_REQUIRED))
  assert.ok(rules.includes(RULES.MULTI_REQUIRED))
})

test('lintSource returns no violations for a compliant schema literal', () => {
  const src = `
const S = {
  type: 'object',
  additionalProperties: true,
  properties: { findings_markdown: { type: 'string' }, lens: { type: 'string' } },
  required: ['findings_markdown'],
}
`
  const found = lintSource(src)
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].violations, [])
})

test('lintSource is not fooled by a brace inside a string literal', () => {
  const src = `
const S = {
  type: 'object',
  properties: { a: { type: 'string', description: 'use { and } freely' } },
  required: ['a'],
}
`
  const found = lintSource(src)
  assert.equal(found.length, 1)
  assert.deepEqual(found[0].violations, [])
})

test('lintSource tolerates source with no schema at all', () => {
  assert.deepEqual(lintSource('const x = 1'), [])
  assert.deepEqual(lintSource(null), [])
})

// ---------------------------------------------------------------------------
// 100%-COVERAGE PASS (2026-09-19) - constructor guards, every lint rule, the full
// type checker, and the lintSource scanner edges. House standard: 100 lines +
// branches (agentspec-js already gates itself there; this workspace now matches).
// ---------------------------------------------------------------------------

test('fanoutSchema rejects an optional field spec it cannot expand', () => {
  assert.throws(
    () => fanoutSchema({ narrative: 'summary', optional: { x: 'blob' } }),
    /unknown type 'blob' for field 'x'/,
  )
  // A number and a null are neither array, object nor string - the unsupported-spec throw.
  assert.throws(() => fanoutSchema({ narrative: 'summary', optional: { x: 42 } }), /unsupported spec for field 'x'/)
  assert.throws(() => fanoutSchema({ narrative: 'summary', optional: { x: null } }), /unsupported spec for field 'x'/)
})

test('fanoutSchema refuses the narrative repeated in optional', () => {
  assert.throws(
    () => fanoutSchema({ narrative: 'summary', optional: { summary: 'string' } }),
    /'summary' is the narrative; do not repeat it in optional/,
  )
})

test('fanoutSchema emits schema- and narrative-level descriptions when given', () => {
  const s = fanoutSchema({ narrative: 'summary', description: 'schema doc', narrativeDescription: 'field doc' })
  assert.equal(s.description, 'schema doc')
  assert.equal(s.properties.summary.description, 'field doc')
})

test('lint flags a schema with NO required field at all', () => {
  const out = lintSchema({ type: 'object', properties: { summary: { type: 'string' } } })
  assert.deepEqual(out.map((v) => v.rule), [RULES.NO_REQUIRED])
  assert.match(out[0].message, /cannot tell a real answer from an empty object/)
})

test('lint flags a non-string first required field even when it is the only one', () => {
  const out = lintSchema({
    type: 'object',
    properties: { count: { type: 'number' } },
    required: ['count'],
  })
  assert.deepEqual(out.map((v) => v.rule), [RULES.NARRATIVE_NOT_STRING])
  assert.equal(out[0].property, 'count')
})

test('multi-required keeper falls back to the first field when no required field is a string', () => {
  const out = lintSchema({
    type: 'object',
    properties: { a: { type: 'number' }, b: { type: 'boolean' } },
    required: ['a', 'b'],
  })
  // keeper = null -> required[0] 'a' is kept, 'b' is flagged; 'a' also fires narrative-not-string.
  assert.deepEqual(out.map((v) => v.rule), [RULES.MULTI_REQUIRED, RULES.NARRATIVE_NOT_STRING])
  assert.equal(out[0].property, 'b')
  assert.match(out[0].message, /only 'a' needs to be required/)
})

test('validator flags additional properties only when the schema forbids them', () => {
  const s = {
    type: 'object',
    properties: { a: { type: 'string' } },
    required: [],
    additionalProperties: false,
  }
  const r = validate(s, { a: 'x', rogue: 1 })
  assert.equal(r.valid, false)
  assert.deepEqual(r.errors, [{ kind: 'additional_property', property: 'rogue' }])
})

test('validator without a usable schema accepts any object payload', () => {
  assert.deepEqual(validate(null, { a: 1 }), { valid: true, errors: [] })
})

test('validator checks every scalar type and passes unknown types through', () => {
  const s = {
    type: 'object',
    required: [],
    properties: {
      n: { type: 'number' },
      i: { type: 'integer' },
      b: { type: 'boolean' },
      o: { type: 'object' },
      u: { type: 'mystery' },
      e: { enum: ['x', 'y'] },
      list: { type: 'array' },
    },
  }
  const bad = validate(s, { n: NaN, i: 1.5, b: 'true', o: [], u: 7, e: 'z', list: [1, 'two'] })
  assert.equal(bad.valid, false)
  const kinds = Object.fromEntries(bad.errors.map((err) => [err.property, err.kind]))
  assert.equal(kinds.n, 'wrong_type') // NaN is not a finite number
  assert.equal(kinds.i, 'wrong_type') // 1.5 is not an integer
  assert.equal(kinds.b, 'wrong_type')
  assert.equal(kinds.o, 'wrong_type') // [] is not a plain object
  assert.equal(kinds.e, 'enum_mismatch')
  assert.equal(kinds.u, undefined) // unknown type name: matchesType defaults to true
  assert.equal(kinds.list, undefined) // array without `items`: no per-item recursion

  const good = validate(s, { n: 1.5, i: 2, b: false, o: { k: 1 }, u: 'anything', e: 'x', list: [] })
  assert.equal(good.valid, true)
})

test('validator recurses into nested object properties and skips undeclared nested keys', () => {
  const s = {
    type: 'object',
    required: [],
    properties: {
      outer: {
        type: 'object',
        properties: { inner: { type: 'string' }, count: { type: 'integer' } },
      },
    },
  }
  const r = validate(s, { outer: { inner: 42, count: 'many', undeclared: true } })
  assert.equal(r.valid, false)
  assert.deepEqual(
    r.errors.map((err) => [err.property, err.kind]),
    [
      ['outer.inner', 'wrong_type'],
      ['outer.count', 'wrong_type'],
    ],
  )
})

test('lintSource skips matches with no enclosing brace, no close, no properties, or a seen open', () => {
  // No '{' anywhere before the match.
  assert.deepEqual(lintSource("type: 'object', properties: { a: { type: 'string' } }"), [])
  // The enclosing brace never closes (matchBrace returns -1).
  assert.deepEqual(
    lintSource('const S = {\n  type: \'object\',\n  properties: {\n    summary: { type: \'string\' }\n'),
    [],
  )
  // type:'object' present but no `properties:` inside the braces.
  assert.deepEqual(lintSource("const S = { type: 'object', required: ['x'] }"), [])
  // Untrusted source can repeat keys: two matches share one nearest '{', second is skipped.
  assert.deepEqual(
    lintSource(
      "const S = { type: 'object', type: 'object', properties: { s: { type: 'string' } }, required: ['s'] }",
    ),
    [{ index: 10, required: ['s'], violations: [] }],
  )
})

test('lintSource carries additionalProperties:false through to the lint rule', () => {
  const out = lintSource(
    "const S = { type: 'object', properties: { s: { type: 'string' } }, required: ['s'], additionalProperties: false }",
  )
  assert.equal(out.length, 1)
  assert.deepEqual(out[0].violations.map((v) => v.rule), [RULES.NO_ADDITIONAL_PROPERTIES])
})

test('lintSource treats a missing required array as NO_REQUIRED and an empty one the same', () => {
  const noRequired = lintSource("const S = { type: 'object', properties: { s: { type: 'string' } } }")
  assert.deepEqual(noRequired[0].required, [])
  assert.deepEqual(noRequired[0].violations.map((v) => v.rule), [RULES.NO_REQUIRED])

  const emptyRequired = lintSource(
    "const S = { type: 'object', properties: { s: { type: 'string' } }, required: [] }",
  )
  assert.deepEqual(emptyRequired[0].required, [])
  assert.deepEqual(emptyRequired[0].violations.map((v) => v.rule), [RULES.NO_REQUIRED])
})

test('lintSource is not fooled by escaped quotes inside string literals', () => {
  const src =
    'const S = { type: "object", properties: { s: { type: "string" } }, required: ["s"], note: "a \\"quoted } brace\\"" }'
  const out = lintSource(src)
  assert.equal(out.length, 1)
  assert.deepEqual(out[0].violations, [])
})

test('lintSource is not fooled by braces inside template literals', () => {
  const src =
    "const S = { type: 'object', properties: { s: { type: 'string' } }, required: ['s'], note: `curly } inside backtick` }"
  const out = lintSource(src)
  assert.equal(out.length, 1)
  assert.deepEqual(out[0].violations, [])
})

test('lintSchema and validate tolerate schemas missing keys or property types', () => {
  // lintSchema(null) / lintSchema({}) / no properties key / no required key.
  assert.deepEqual(lintSchema(null), [])
  assert.deepEqual(lintSchema({ type: 'object' }).map((v) => v.rule), [RULES.NO_REQUIRED])
  // A required property declared WITHOUT a type key must not fire narrative-not-string.
  assert.deepEqual(lintSchema({ type: 'object', properties: { s: {} }, required: ['s'] }), [])
  // validate: a schema without properties/required accepts any object payload.
  assert.deepEqual(validate({ type: 'object' }, { anything: 1 }), { valid: true, errors: [] })
})

test('validator skips object-typed properties that declare no nested properties', () => {
  const r = validate(
    { type: 'object', required: [], properties: { blob: { type: 'object' } } },
    { blob: { x: 1 } },
  )
  assert.deepEqual(r, { valid: true, errors: [] })
})

// ---------------------------------------------------------------------------
// ADOPTION WIRING - the library must gate a real workflow in the real CI lane
// ---------------------------------------------------------------------------

test('CONTROL: lint CLI rejects required inline confidence and accepts it as optional', (t) => {
  // Known-broken before adoption: no CLI entrypoint existed to exercise this rule as a gate.
  const dir = mkdtempSync(join(tmpdir(), 'fanout-schema-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const path = join(dir, 'confidence.js')
  writeFileSync(
    path,
    `const S = {
  type: 'object',
  properties: { summary: { type: 'string' }, confidence: { type: 'string' } },
  required: ['summary', 'confidence'],
}\n`,
  )

  const broken = runLint(path)
  assert.equal(broken.status, 1, broken.stdout + broken.stderr)
  assert.match(broken.stderr, /multi-required \[confidence\]/)

  writeFileSync(
    path,
    `const S = {
  type: 'object',
  properties: { summary: { type: 'string' }, confidence: { type: 'string' } },
  required: ['summary'],
}\n`,
  )
  const fixed = runLint(path)
  assert.equal(fixed.status, 0, fixed.stdout + fixed.stderr)
  assert.match(fixed.stdout, /fanout-schema lint: OK \(1 schema\(s\), 1 file\(s\)\)/)
})

test('lint CLI refuses missing inputs and zero-schema targets', (t) => {
  // Known-broken before adoption: no CLI existed to fail closed on an unscanned target.
  const noInput = runLint()
  assert.equal(noInput.status, 2, noInput.stdout + noInput.stderr)
  assert.match(noInput.stderr, /usage:/)

  const dir = mkdtempSync(join(tmpdir(), 'fanout-schema-empty-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const path = join(dir, 'no-schema.js')
  writeFileSync(path, 'const answer = 42\n')
  const empty = runLint(path)
  assert.equal(empty.status, 1, empty.stdout + empty.stderr)
  assert.match(empty.stderr, /no object schema literals found/)

  const missing = runLint(join(dir, 'missing.js'))
  assert.equal(missing.status, 2, missing.stdout + missing.stderr)
})

test('lint CLI recurses into nested subdirectories and only reads .js/.mjs sources', (t) => {
  // Known gap (measured 2026-09-19: lint_fanout_schemas.mjs branch coverage 42.86%): the
  // directory walker only ever saw a flat production workflows/ directory, so the recursion
  // step and the extension filter were untested branches.
  const dir = mkdtempSync(join(tmpdir(), 'fanout-schema-nested-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const schema = `const S = {
  type: 'object',
  properties: { summary: { type: 'string' } },
  required: ['summary'],
}
`
  mkdirSync(join(dir, 'sub', 'deeper'), { recursive: true })
  writeFileSync(join(dir, 'top.js'), schema)
  writeFileSync(join(dir, 'sub', 'mid.mjs'), schema)
  writeFileSync(join(dir, 'sub', 'deeper', 'bottom.js'), schema)
  writeFileSync(join(dir, 'sub', 'notes.txt'), 'not source')
  writeFileSync(join(dir, 'sub', 'deeper', 'data.json'), '{}')

  const result = runLint(dir)
  assert.equal(result.status, 0, result.stdout + result.stderr)
  assert.match(result.stdout, /OK \(3 schema\(s\), 3 file\(s\)\)/)
})

test('lint CLI survives a file that fails to READ mid-run (exit 2, not a crash)', (t) => {
  // The readFileSync catch is the TOCTOU guard between collectSourcePaths (stat) and the
  // read. Deterministic triggers per platform (both measured on this box):
  //   win32: a PowerShell FileStream byte-range Lock(0,1) - stat still succeeds, read
  //          fails EBUSY. (FileShare-based denial does NOT block Node reads - measured
  //          against FileShare.Write and FileShare.None holders before falling back to
  //          byte-range locks.)
  //   POSIX: mode 000 blocks open-for-read while stat still succeeds.
  const dir = mkdtempSync(join(tmpdir(), 'fanout-schema-unreadable-'))
  const schema = `const S = {
  type: 'object',
  properties: { summary: { type: 'string' } },
  required: ['summary'],
}
`
  writeFileSync(join(dir, 'good.js'), schema)
  const lockedPath = join(dir, 'locked.js')
  writeFileSync(lockedPath, schema)

  if (process.platform === 'win32') {
    const script = [
      '$fs = [System.IO.File]::Open($env:LOCKFILE, "Open", "Read", "ReadWrite")',
      '$fs.Lock(0, 1)',
      'Start-Sleep -Seconds 120',
      '$fs.Unlock(0, 1)',
      '$fs.Close()',
    ].join('; ')
    const holder = spawn('powershell.exe', ['-NoProfile', '-Command', script], {
      stdio: ['ignore', 'ignore', 'ignore'],
      env: { ...process.env, LOCKFILE: lockedPath },
    })
    t.after(() => {
      holder.kill()
      const killDeadline = Date.now() + 5_000
      while (holder.exitCode === null && holder.signalCode === null && Date.now() < killDeadline) {
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 25)
      }
      try {
        rmSync(dir, { recursive: true, force: true })
      } catch {
        // Lock release can lag holder teardown by milliseconds on Windows; the OS
        // tmpdir owns the residue rather than failing the test run.
      }
    })
    // Poll the lock itself rather than trusting a holder-side "ready" string: readFileSync
    // succeeding means the lock is not held yet (powershell.exe cold start can take tens
    // of seconds under memory pressure).
    const lockDeadline = Date.now() + 60_000
    let lockHeld = false
    while (Date.now() < lockDeadline) {
      try {
        readFileSync(lockedPath, 'utf8')
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100)
      } catch (error) {
        // Only a sharing violation proves the lock; any other error (ENOENT, EACCES...)
        // would let the test pass for the wrong reason.
        if (error?.code === 'EBUSY' || error?.code === 'EPERM' || error?.code === 'EACCES') {
          lockHeld = true
          break
        }
        throw error
      }
    }
    if (!lockHeld) {
      return t.skip('byte-range lock never took effect within 60s; read-failure state unverifiable')
    }
  } else {
    if (typeof process.getuid === 'function' && process.getuid() === 0) {
      return t.skip('root bypasses mode 000, so the read would succeed and the assertion would be vacuous')
    }
    chmodSync(lockedPath, 0o000)
    t.after(() => {
      chmodSync(lockedPath, 0o666)
      rmSync(dir, { recursive: true, force: true })
    })
  }

  const result = runLint(dir)
  assert.equal(result.status, 2, result.stdout + result.stderr)
  assert.match(result.stderr, /locked\.js: /)
})

test('lint CLI ignores inputs that are neither file nor directory (character devices)', (t) => {
  // statSync('/dev/null') is a char device: isFile() false, isDirectory() false - the early
  // return in collectSourcePaths. Windows has no stat-able device path (statSync('nul')
  // throws ENOENT, statSync('\\\\.\\NUL') reports isFile=true - both measured), so this
  // too is POSIX-only.
  if (process.platform === 'win32') return t.skip('no stat-able char-device path on Windows')

  const result = runLint('/dev/null')
  assert.equal(result.status, 1, result.stdout + result.stderr)
  assert.match(result.stderr, /no object schema literals found/)
})

test('lint CLI prints property-less rules without an empty bracket suffix', (t) => {
  // NO_ADDITIONAL_PROPERTIES and NO_REQUIRED carry no `property` - the CLI's
  // `violation.property ? ...` false side, which must not print "rule []: ...".
  const dir = mkdtempSync(join(tmpdir(), 'fanout-schema-propless-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const path = join(dir, 'ap-false.js')
  writeFileSync(
    path,
    `const S = {
  type: 'object',
  properties: { summary: { type: 'string' } },
  required: ['summary'],
  additionalProperties: false,
}
`,
  )

  const result = runLint(path)
  assert.equal(result.status, 1, result.stdout + result.stderr)
  assert.match(result.stderr, /ap-false\.js:1: no-additional-properties: /)
  assert.doesNotMatch(result.stderr, /\[\]/)
})

test('production workflow schemas pass the fanout lint', () => {
  // Known-broken before adoption: rtv-pdr.js produced 19 violations across four schemas and its
  // approach field was only a high-level summary, not the complete required narrative.
  const result = runLint(PRODUCTION_WORKFLOWS)
  assert.equal(result.status, 0, result.stdout + result.stderr)
  assert.match(result.stdout, /fanout-schema lint: OK \(4 schema\(s\), 1 file\(s\)\)/)
  const source = readFileSync(join(PRODUCTION_WORKFLOWS, 'rtv-pdr.js'), 'utf8')
  assert.match(source, /required: \['approach'\]/)
  assert.match(source, /complete solution narrative/i)
  assert.match(source, /COMPLETE solution in approach/)
})

test('quality CI invokes the production fanout lint', () => {
  // Known-broken before adoption: neither the package script nor the CI package step existed.
  const packageJson = JSON.parse(readFileSync(TOOL_PACKAGE, 'utf8'))
  assert.equal(packageJson.scripts.lint, 'node lint_fanout_schemas.mjs')
  const workflow = readFileSync(QUALITY_WORKFLOW, 'utf8')
  assert.match(
    workflow,
    /working-directory: tools\/fanout-schema\r?\n\s+run: \|\r?\n\s+npm test\r?\n\s+npm run lint -- \.\.\/\.\.\/workflows/,
  )
})

// ---------------------------------------------------------------------------
// T0 STRUCTURE - authoritative workflow-facing skills
// ---------------------------------------------------------------------------

test('T0: saved-workflow references use the live Claude workflow directory', () => {
  const wrongWorkflowHome = /~\/\.Codex\/workflows\/[^`\s)]+\.mjs/g
  const knownBroken = [
    '`~/.Codex/workflows/plan-gate.mjs`',
    '`~/.Codex/workflows/design-gate.mjs`',
  ].join('\n')
  const correctedReferences = [
    '~/.claude/workflows/plan-gate.mjs',
    '~/.claude/workflows/design-gate.mjs',
  ]

  // Positive and negative controls: prove the detector sees both historical typos and
  // distinguishes the correct provider-specific home before trusting a zero.
  assert.deepEqual(matchingLines(knownBroken, wrongWorkflowHome), [
    '1:~/.Codex/workflows/plan-gate.mjs',
    '2:~/.Codex/workflows/design-gate.mjs',
  ])
  assert.deepEqual(
    matchingLines('`~/.claude/workflows/plan-gate.mjs`', wrongWorkflowHome),
    [],
  )

  // Known broken before C12: this authoritative file contained both controlled typos.
  const source = readFileSync(join(AUTHORITATIVE_SKILLS, 'workflow-authoring', 'SKILL.md'), 'utf8')
  const wrongReferences = matchingLines(source, wrongWorkflowHome)
  assert.deepEqual(
    wrongReferences,
    [],
    `wrong saved-workflow references: ${wrongReferences.join(', ')}`,
  )
  assert.deepEqual(correctedReferences.filter((reference) => !source.includes(reference)), [])
})

test('T0: agent-as-judge has no hardcoded path to another provider home', () => {
  const wrongProviderHome = /\.Codex(?=[/"'])/g
  const knownBroken = ['`~/.Codex/event-ledger/x`', 'HOME / ".Codex" / "hooks"'].join('\n')
  const correctedPaths = [
    '~/.claude/event-ledger/<slug>/events.jsonl',
    '~/.claude/learnings-queue.json',
    '~/.claude/shadow-sinks/agent-as-judge.jsonl',
    'HOME / ".claude" / "hooks" / "event-ledger"',
    'HOME / ".claude" / "learnings-queue.json"',
    'HOME / ".claude" / "shadow-sinks" / "agent-as-judge.jsonl"',
    'HOME / ".claude" / "skills" / "passk-stats" / "SKILL.md"',
    'HOME / ".claude" / "skills" / "pass-k-stats" / "SKILL.md"',
    'HOME / ".claude" / "hooks" / "passk_stats.py"',
  ]

  // A case-sensitive detector catches the wrong Claude-home spelling without banning the
  // legitimate lowercase ~/.codex home used by OpenAI Codex.
  assert.deepEqual(matchingLines(knownBroken, wrongProviderHome), ['1:.Codex', '2:.Codex'])
  assert.deepEqual(matchingLines('`~/.codex/auth.json`', wrongProviderHome), [])

  // Known broken before C12: this authoritative file contained nine wrong-provider paths.
  const source = readFileSync(join(AUTHORITATIVE_SKILLS, 'agent-as-judge', 'SKILL.md'), 'utf8')
  const wrongPaths = matchingLines(source, wrongProviderHome)
  assert.deepEqual(wrongPaths, [], `wrong-provider paths: ${wrongPaths.join(', ')}`)
  assert.deepEqual(correctedPaths.filter((path) => !source.includes(path)), [])
})

// ---------------------------------------------------------------------------
// preflight() - abort a fan-out whose work-list silently collapsed.
//
// Anchored to the measured 2026-07-29 failure: a 51-agent workflow opened
// `const P = args`, `args` arrived as a JSON-ENCODED STRING, every `P.<field>`
// read undefined, `Array.from({length: P.nClusters})` collapsed 49 -> 1, and every
// `${P.path}` rendered the literal text "undefined". Nothing threw; 38 min and
// 324k tokens were lost. Independently corroborated: a per-file grep over the 10
// saved workflows in ~/.claude/workflows counts 0 `throw new Error` in every one,
// and the only 3 `throw` hits at all are inside comments.
// ---------------------------------------------------------------------------

// node:assert/strict's assert.throws() returns undefined, so it cannot hand back the error
// for inspection. These two helpers do, and both FAIL LOUDLY when nothing is thrown - a
// silent `return null` here would let a disarmed preflight pass its own tests.
function caught(fn) {
  try {
    fn()
  } catch (err) {
    return err
  }
  throw new assert.AssertionError({ message: 'expected preflight to throw, it returned' })
}

function rethrownRule(fn) {
  return caught(fn).rule
}

test('preflight: HAPPY PATH - a well-formed fan-out returns counts and does not throw', () => {
  const units = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
  const counts = preflight({
    units,
    expected: 3,
    prompts: units.map((u) => `work unit ${u.id} in C:/repo`),
    argsRaw: { nClusters: 3, path: 'C:/repo' },
  })
  assert.deepEqual(counts, { units: 3, expected: 3, prompts: 3 })

  // A deliberately single-unit fan-out is legal when the author says so.
  assert.deepEqual(preflight({ units: [{ id: 'solo' }], expected: 1 }), {
    units: 1,
    expected: 1,
    prompts: 0,
  })

  // prompts/argsRaw are optional; omitting them must not synthesise a failure.
  assert.deepEqual(preflight({ units: [1, 2], expected: 2 }), {
    units: 2,
    expected: 2,
    prompts: 0,
  })
})

test('preflight: THROW 1 - collapsed work-list (the exact 49 -> 1 measured failure)', () => {
  // Reproduce the shape verbatim: nClusters undefined => Array.from({length: undefined}) => [].
  const P = {}
  const collapsed = Array.from({ length: P.nClusters ?? 0 }, (_, i) => i)
  assert.equal(collapsed.length, 0, 'control: the measured collapse must actually reproduce')

  const err = caught(() => preflight({ units: collapsed, expected: 49 }))
  assert.ok(err instanceof Error)
  assert.equal(err.rule, PREFLIGHT.COLLAPSED_WORK_LIST)
  assert.match(err.message, /work-list collapsed: built 0 unit\(s\) but expected 49/)

  // 1 unit where 49 were expected is the same defect one step later.
  assert.equal(
    rethrownRule(() => preflight({ units: [{ id: 'x' }], expected: 49 })),
    PREFLIGHT.COLLAPSED_WORK_LIST,
  )

  // An empty work-list is never intentional, even when expected === 1.
  assert.equal(
    rethrownRule(() => preflight({ units: [], expected: 1 })),
    PREFLIGHT.COLLAPSED_WORK_LIST,
  )
})

test('preflight: THROW 2 - a prompt carrying the literal token "undefined"', () => {
  const P = {}
  const prompt = `Analyse the tree at ${P.path} and report findings`
  assert.match(prompt, /undefined/, 'control: the failed interpolation must actually reproduce')

  const err = caught(() => preflight({ units: [1, 2], expected: 2, prompts: ['fine', prompt] }))
  assert.ok(err instanceof Error)
  assert.equal(err.rule, PREFLIGHT.UNDEFINED_IN_PROMPT)
  assert.match(err.message, /prompts\[1\] contains the literal token "undefined"/)
  // The message must localise the failure, or an author still has to hunt for it.
  assert.match(err.message, /Analyse the tree at undefined/)

  // Word-boundary, not substring: a legitimate identifier must not trip the check.
  assert.deepEqual(preflight({ units: [1, 2], expected: 2, prompts: ['use isUndefinedish()'] }), {
    units: 2,
    expected: 2,
    prompts: 1,
  })

  // Non-string prompt entries are their own defect, not a silent skip.
  assert.equal(
    rethrownRule(() => preflight({ units: [1, 2], expected: 2, prompts: [null] })),
    PREFLIGHT.PROMPTS_NOT_ARRAY,
  )
  assert.equal(
    rethrownRule(() => preflight({ units: [1, 2], expected: 2, prompts: 'not an array' })),
    PREFLIGHT.PROMPTS_NOT_ARRAY,
  )
})

test('preflight: THROW 3 - args arriving as a string where an object is destructured', () => {
  // The measured root cause: the runtime hands over a JSON-ENCODED STRING.
  const argsRaw = JSON.stringify({ nClusters: 49, path: 'C:/repo' })
  assert.equal(typeof argsRaw, 'string', 'control: the runtime shape is a string, not an object')
  const P = argsRaw
  assert.equal(P.nClusters, undefined, 'control: a string has no such field')

  const err = caught(() => preflight({ units: [1, 2], expected: 2, argsRaw }))
  assert.ok(err instanceof Error)
  assert.equal(err.rule, PREFLIGHT.ARGS_NOT_OBJECT)
  assert.match(err.message, /JSON-ENCODED STRING/)
  assert.match(err.message, /JSON\.parse\(args\) before destructuring/)

  // A flat (non-JSON) args string gets the other actionable hint, not the parse one.
  const flat = rethrownRule(() => preflight({ units: [1, 2], expected: 2, argsRaw: 'wave=all' }))
  assert.equal(flat, PREFLIGHT.ARGS_NOT_OBJECT)
  assert.throws(
    () => preflight({ units: [1, 2], expected: 2, argsRaw: 'wave=all' }),
    /flat string - scan it with a regex/,
  )

  // Empty string is the commonest degenerate case and must still throw.
  assert.equal(
    rethrownRule(() => preflight({ units: [1, 2], expected: 2, argsRaw: '' })),
    PREFLIGHT.ARGS_NOT_OBJECT,
  )
  // Arrays and null are not the destructurable object the caller believes it has.
  for (const bad of [null, [1, 2], 42]) {
    assert.equal(
      rethrownRule(() => preflight({ units: [1, 2], expected: 2, argsRaw: bad })),
      PREFLIGHT.ARGS_NOT_OBJECT,
      `argsRaw=${JSON.stringify(bad)} must be rejected`,
    )
  }
})

test('preflight: INERTNESS PROBE - a bad `expected` or `units` cannot silently disarm it', () => {
  // This is the mutation that matters. `expected` is normally derived from the SAME broken
  // args object, so the naive guard body `units.length < 2 && expected > 1` evaluates to
  // false when expected is undefined, and would never fire on the bug it was written for.
  const naiveGuardWouldFire = (units, expected) => units.length < 2 && expected > 1
  assert.equal(naiveGuardWouldFire([], undefined), false, 'control: the naive guard IS inert')
  assert.equal(naiveGuardWouldFire({}, 49), false, 'control: non-array units also disarm it')

  // preflight must refuse both instead of returning a clean bill of health.
  assert.equal(
    rethrownRule(() => preflight({ units: [], expected: undefined })),
    PREFLIGHT.EXPECTED_NOT_POSITIVE_INT,
  )
  for (const bad of [undefined, null, '49', 0, -3, 2.5, NaN]) {
    assert.equal(
      rethrownRule(() => preflight({ units: [1, 2], expected: bad })),
      PREFLIGHT.EXPECTED_NOT_POSITIVE_INT,
      `expected=${String(bad)} must be rejected`,
    )
  }
  for (const bad of [undefined, null, {}, 'units', 3]) {
    assert.equal(
      rethrownRule(() => preflight({ units: bad, expected: 49 })),
      PREFLIGHT.UNITS_NOT_ARRAY,
      `units=${String(bad)} must be rejected`,
    )
  }
  // No options at all must throw, not default to a vacuous pass.
  assert.equal(rethrownRule(() => preflight()), PREFLIGHT.UNITS_NOT_ARRAY)
  assert.equal(rethrownRule(() => preflight('args-as-string')), PREFLIGHT.UNITS_NOT_ARRAY)
})

test('preflight: the mutation probe is actually WIRED into the CI-invoked npm test', () => {
  // A test file not named by something CI runs never runs at all. quality.yml invokes
  // `npm test` in this directory, so the probe must hang off that script - otherwise the
  // guard-coverage evidence silently stops being produced.
  const packageJson = JSON.parse(readFileSync(TOOL_PACKAGE, 'utf8'))
  // The script runs the suite via `node --test` (coverage-gate flags may sit in between) and
  // then the mutation probe - both must stay on the CI-invoked `npm test`.
  assert.match(packageJson.scripts.test, /node --test .*test_fanout_schema\.mjs/)
  assert.match(packageJson.scripts.test, /&& node test_preflight_mutations\.mjs/)
  const workflow = readFileSync(QUALITY_WORKFLOW, 'utf8')
  assert.match(workflow, /working-directory: tools\/fanout-schema\r?\n\s+run: \|\r?\n\s+npm test/)
  // And the probe file exists with all five guard anchors it claims to mutate.
  const probe = readFileSync(join(HERE, 'test_preflight_mutations.mjs'), 'utf8')
  const module = readFileSync(join(HERE, 'fanout_schema.mjs'), 'utf8')
  const ids = [...probe.matchAll(/'(M\d [a-z-]+)'/g)].map((m) => m[1])
  assert.equal(ids.length, 5, `expected 5 mutants, found ${ids.join(', ')}`)
  for (const guard of [
    'if (units.length !== expected) {',
    'const m = UNDEFINED_TOKEN.exec(p)',
    "if (typeof argsRaw === 'string') {",
    'if (!Number.isInteger(expected) || expected < 1) {',
    'if (!Array.isArray(units)) {',
  ]) {
    assert.ok(probe.includes(guard), `probe lost its anchor for: ${guard}`)
    assert.ok(module.includes(guard), `module lost the guard: ${guard}`)
  }
})

// Both cases below were green-lit by the first version of preflight(), which is how they were
// found: an adversarial review passed `units=5, expected=49` and `prompts=[]` and neither threw.
// The original guard only fired below 2 units, so it caught a TOTAL collapse and missed a partial
// one - the harder case, because 5 running agents look like progress while 44 are never dispatched.
test('preflight: THROW 4 - a PARTIAL collapse (5 of 49) is not survivable', () => {
  const units = [1, 2, 3, 4, 5]
  assert.throws(
    () => preflight({ units, expected: 49 }),
    (e) => e.rule === PREFLIGHT.COLLAPSED_WORK_LIST && /built 5 unit\(s\) but expected 49/.test(e.message),
    'a 5-of-49 work-list must throw, not just a 0- or 1-unit one',
  )
  // and the reverse mismatch is equally a defect - the author's declared count is the contract
  assert.throws(
    () => preflight({ units: [1, 2, 3], expected: 2 }),
    (e) => e.rule === PREFLIGHT.COLLAPSED_WORK_LIST,
    'over-expansion must throw too',
  )
  // control: the matching case must still pass, or this test proves nothing
  assert.deepEqual(preflight({ units, expected: 5 }), { units: 5, expected: 5, prompts: 0 })
})

test('preflight: THROW 5 - an empty prompts array cannot silently skip the scan', () => {
  assert.throws(
    () => preflight({ units: [1, 2], expected: 2, prompts: [] }),
    (e) => e.rule === PREFLIGHT.PROMPTS_NOT_ARRAY && /nothing would be scanned/.test(e.message),
    'opting in to the prompt scan with nothing to scan must throw',
  )
  // control: omitting `prompts` entirely is the documented opt-out and must stay silent
  assert.deepEqual(preflight({ units: [1, 2], expected: 2 }), { units: 2, expected: 2, prompts: 0 })
})

test('preflight: rule ids are stable, unique and namespaced', () => {
  const ids = Object.values(PREFLIGHT)
  assert.equal(new Set(ids).size, ids.length, 'rule ids must be unique')
  assert.deepEqual(ids.filter((id) => !id.startsWith('preflight/')), [])
  // Callers switch on these strings; renaming one is a breaking change.
  assert.deepEqual(ids.slice().sort(), [
    'preflight/args-not-object',
    'preflight/collapsed-work-list',
    'preflight/expected-not-positive-int',
    'preflight/prompts-not-array',
    'preflight/undefined-in-prompt',
    'preflight/units-not-array',
  ])
})
