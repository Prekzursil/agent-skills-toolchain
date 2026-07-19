// Tests for the fan-out schema module (B6).
// Run: node --test tools/fanout-schema/
//
// Every assertion here is anchored to a measured number from the 10.65 GB transcript scan
// (11,693 files, 3,735 StructuredOutput calls, 849 errors). The numbers are quoted inline so
// a future reader can falsify them rather than trust them.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  fanoutSchema,
  findingsSchema,
  lintSchema,
  lintSource,
  validate,
  RULES,
} from './fanout_schema.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURE = JSON.parse(
  readFileSync(join(HERE, 'historical-rejection.fixture.json'), 'utf8'),
)

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
