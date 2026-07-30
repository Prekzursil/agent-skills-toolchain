// Tests for the fan-out schema module (B6).
// Run: npm --prefix tools/fanout-schema test
//
// Every assertion here is anchored to a measured number from the 10.65 GB transcript scan
// (11,693 files, 3,735 StructuredOutput calls, 849 errors). The numbers are quoted inline so
// a future reader can falsify them rather than trust them.

import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
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
  return spawnSync(process.execPath, [LINTER, ...paths], { encoding: 'utf8' })
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
  assert.match(packageJson.scripts.test, /node --test test_fanout_schema\.mjs/)
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
