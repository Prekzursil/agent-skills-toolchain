// fanout_schema.mjs - schema constructor, linter and validator for Claude Code fan-outs.
//
// WHY THIS EXISTS (all figures measured, not estimated)
// ----------------------------------------------------
// Scan of 11,693 transcripts / 10.65 GB under ~/.claude/projects, joined to the 631 schema
// literals declared across 434 workflow scripts:
//
//   StructuredOutput           3,735 calls   849 errors   22.7%
//     missing_required_property  616  72.6%
//     unparseable_json           176  20.7%
//     additionalProperties:false  30   3.5%
//     wrong_type                  14   1.6%
//     other                       13   1.5%
//
// Joining each call to the schema that governed it (2,872 matched, 42 unmatched):
//
//   required = exactly ONE string field .......    0 errors / 130 calls =  0.0%
//   anything else ............................  727 errors / 2,742     = 26.5%
//   an array-typed field appears in `required`  628 errors / 1,342     = 46.8%
//   no array in `required` ...................   99 errors / 1,530     =  6.5%
//
// Independent second measurement (reconstructed from transcripts alone, different code path):
//   schema exposes a *_markdown catch-all ....    7 errors / 239 calls =  2.9%
//   schema does not .......................... 842 errors / 3,497      = 24.1%
//
// The count of required fields is NOT the driver and must not be linted:
//   required=1  2.7% | required=2  2.2% | required=3 53.4% | required=7  2.8%
//   required=8 67.6% | required=9  6.3% | required=10 0.0%
//
// Mechanism, resolved to the DECLARED TYPE of each of the 1,193 individually omitted
// properties: string 691 (57.9%), array 457 (38.3%), boolean 26, object 19. Models omit
// *ancillary* fields - the ones that are not the answer - regardless of type. "Never require
// an array" is therefore a useful marker but an incomplete rule: it would leave the single
// most-omitted string field (`confidence`, 314 omissions) still required.
//
// THE RULE THAT SURVIVES EVERY CUT: require exactly one string field - the narrative.
// Keep every other property declared but OPTIONAL. Descriptions steer the model at no cost
// (required=10 scored 0/30); `required` is pure rejection surface.

/** Lint rule ids. Stable strings - callers may switch on them. */
export const RULES = {
  ARRAY_IN_REQUIRED: 'array-in-required',
  MULTI_REQUIRED: 'multi-required',
  NO_ADDITIONAL_PROPERTIES: 'no-additional-properties',
  UNDECLARED_REQUIRED: 'undeclared-required',
  NARRATIVE_NOT_STRING: 'narrative-not-string',
  NO_REQUIRED: 'no-required',
}

const SCALARS = new Set(['string', 'number', 'integer', 'boolean', 'object', 'array'])

/**
 * Expand a terse field spec into a JSON Schema fragment.
 *   'string' | 'number' | 'boolean' | 'object' | 'array'  -> { type }
 *   'string[]'                                            -> array of string
 *   ['a','b']                                             -> string enum
 *   { ...fragment }                                       -> passed through untouched
 */
function expand(spec, name) {
  if (Array.isArray(spec)) return { type: 'string', enum: [...spec] }
  if (spec && typeof spec === 'object') return { ...spec }
  if (typeof spec === 'string') {
    if (spec.endsWith('[]')) {
      const inner = spec.slice(0, -2)
      if (!SCALARS.has(inner)) throw new TypeError(`unknown item type '${inner}' for '${name}'`)
      return { type: 'array', items: { type: inner } }
    }
    if (SCALARS.has(spec)) return { type: spec }
    throw new TypeError(`unknown type '${spec}' for field '${name}'`)
  }
  throw new TypeError(`unsupported spec for field '${name}'`)
}

/**
 * Build a fan-out schema that cannot express the measured failure mode.
 *
 * @param {object}  opts
 * @param {string}  opts.narrative   name of the single required string field
 * @param {string} [opts.narrativeType='string']  only 'string' is accepted; present so a
 *                                    mistaken 'array' throws instead of silently shipping
 * @param {string} [opts.narrativeDescription]
 * @param {object} [opts.optional={}] every other field - declared, described, NOT required
 * @param {string} [opts.description] schema-level description
 * @returns {object} a JSON Schema object with `required` of length exactly 1
 */
export function fanoutSchema(opts = {}) {
  const {
    narrative,
    narrativeType = 'string',
    narrativeDescription,
    optional = {},
    description,
  } = opts

  if (typeof narrative !== 'string' || !narrative) {
    throw new TypeError('fanoutSchema: a `narrative` field name is required')
  }
  if (narrativeType !== 'string') {
    throw new TypeError(
      `fanoutSchema: the narrative field must be a string, got '${narrativeType}'. ` +
        'Array-typed required fields scored 46.8% rejection vs 6.5%.',
    )
  }
  if ('required' in opts) {
    throw new TypeError(
      'fanoutSchema: `required` is not settable. Exactly one field - the narrative - is ' +
        'required by construction; a second required field is the measured defect ' +
        '(0/130 vs 727/2,742).',
    )
  }
  if (Object.prototype.hasOwnProperty.call(optional, narrative)) {
    throw new TypeError(`fanoutSchema: '${narrative}' is the narrative; do not repeat it in optional`)
  }

  const properties = {
    [narrative]: {
      type: 'string',
      ...(narrativeDescription ? { description: narrativeDescription } : {}),
    },
  }
  for (const [name, spec] of Object.entries(optional)) properties[name] = expand(spec, name)

  return {
    type: 'object',
    ...(description ? { description } : {}),
    // Explicitly permissive: 30 measured rejections were "must NOT have additional
    // properties". A model adding a key it thought was useful is not an error worth
    // discarding the whole result over.
    additionalProperties: true,
    properties,
    required: [narrative],
  }
}

/**
 * The house default for a discovery / lens / review fan-out: one markdown narrative,
 * everything else optional.
 */
export function findingsSchema(optional = {}, opts = {}) {
  return fanoutSchema({
    narrative: 'findings_markdown',
    narrativeDescription:
      'Your complete findings as markdown. This is the ONLY required field - put the ' +
      'substance here even if you cannot fill any other field.',
    optional,
    ...opts,
  })
}

/**
 * Lint an existing schema against the measured rules.
 * @returns {Array<{rule:string, property?:string, message:string, evidence:string}>}
 */
export function lintSchema(schema) {
  const out = []
  if (!schema || typeof schema !== 'object') return out
  const props = schema.properties && typeof schema.properties === 'object' ? schema.properties : {}
  const required = Array.isArray(schema.required) ? schema.required : []

  if (schema.additionalProperties === false) {
    out.push({
      rule: RULES.NO_ADDITIONAL_PROPERTIES,
      message: 'additionalProperties:false rejects a result for containing MORE than asked.',
      evidence: '30 of 849 measured StructuredOutput errors were "must NOT have additional properties".',
    })
  }

  if (required.length === 0) {
    out.push({
      rule: RULES.NO_REQUIRED,
      message: 'No required field: the fan-in cannot tell a real answer from an empty object.',
      evidence: 'Require exactly one narrative field - measured 0 errors / 130 calls.',
    })
  }

  for (const name of required) {
    const p = props[name]
    if (!p) {
      out.push({
        rule: RULES.UNDECLARED_REQUIRED,
        property: name,
        message: `required '${name}' is not declared in properties; it can never be satisfied.`,
        evidence: 'Undeclared required names reject every payload unconditionally.',
      })
      continue
    }
    if (p.type === 'array') {
      out.push({
        rule: RULES.ARRAY_IN_REQUIRED,
        property: name,
        message: `required '${name}' is array-typed; give it no required status and default [].`,
        evidence: 'array in required: 628/1,342 = 46.8% rejection vs 99/1,530 = 6.5% without.',
      })
    }
  }

  if (required.length > 1) {
    // Report the narrative as the keeper and each additional required field as the defect,
    // so a caller can act per-property rather than on the schema as a whole.
    const keeper = required.find((n) => props[n] && props[n].type === 'string') ?? required[0]
    for (const name of required) {
      if (name === keeper) continue
      out.push({
        rule: RULES.MULTI_REQUIRED,
        property: name,
        message: `'${name}' should be optional; only '${keeper}' needs to be required.`,
        evidence:
          'exactly-one-required-string: 0/130 (0.0%); anything else: 727/2,742 (26.5%). ' +
          'The single most-omitted field was the string `confidence` (314 omissions).',
      })
    }
  }

  const first = required[0]
  if (first && props[first] && props[first].type && props[first].type !== 'string') {
    out.push({
      rule: RULES.NARRATIVE_NOT_STRING,
      property: first,
      message: `the required field '${first}' is '${props[first].type}', not a string.`,
      evidence: 'Only a single required STRING field measured 0% rejection.',
    })
  }

  return out
}

/**
 * Validate a payload against the JSON Schema subset the harness actually uses:
 * type, properties, required, items, enum, additionalProperties.
 *
 * Deliberately NOT a general JSON Schema implementation - it exists so a workflow author can
 * unit-test a real sample payload against their schema before shipping the fan-out.
 *
 * @returns {{valid:boolean, errors:Array<object>}}
 */
export function validate(schema, payload) {
  const errors = []
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    return { valid: false, errors: [{ kind: 'not_an_object', got: typeofOf(payload) }] }
  }
  if (!schema || typeof schema !== 'object') return { valid: true, errors: [] }

  const props = schema.properties && typeof schema.properties === 'object' ? schema.properties : {}
  const required = Array.isArray(schema.required) ? schema.required : []

  for (const name of required) {
    if (!(name in payload)) errors.push({ kind: 'missing_required', property: name })
  }

  for (const [name, value] of Object.entries(payload)) {
    const p = props[name]
    if (!p) {
      if (schema.additionalProperties === false) {
        errors.push({ kind: 'additional_property', property: name })
      }
      continue
    }
    checkValue(p, value, name, errors)
  }

  return { valid: errors.length === 0, errors }
}

function typeofOf(v) {
  if (v === null) return 'null'
  if (Array.isArray(v)) return 'array'
  return typeof v
}

/** Stable `err.rule` ids thrown by preflight(). Callers may switch on them. */
export const PREFLIGHT = {
  UNITS_NOT_ARRAY: 'preflight/units-not-array',
  EXPECTED_NOT_POSITIVE_INT: 'preflight/expected-not-positive-int',
  COLLAPSED_WORK_LIST: 'preflight/collapsed-work-list',
  PROMPTS_NOT_ARRAY: 'preflight/prompts-not-array',
  UNDEFINED_IN_PROMPT: 'preflight/undefined-in-prompt',
  ARGS_NOT_OBJECT: 'preflight/args-not-object',
}

function fail(rule, message) {
  const err = new Error(`preflight: ${message}`)
  err.rule = rule
  throw err
}

// Word-boundary match on the literal token a failed `${...}` interpolation leaves behind.
// KNOWN FALSE POSITIVE, accepted deliberately: a prompt whose PROSE uses the English word
// ("behaviour here is undefined") also throws. The fix is to reword the prompt. The trade is
// one-sided - a reworded adjective costs seconds, the missed interpolation cost 38 minutes
// and 324k tokens - so this check has no opt-out.
const UNDEFINED_TOKEN = /\bundefined\b/

/**
 * Abort a fan-out BEFORE spawning, when the work-list has silently collapsed.
 *
 * MEASURED FAILURE THIS GUARD EXISTS FOR (2026-07-29, one 51-agent workflow):
 * the script opened `const P = args`, but the runtime delivers `args` as a JSON-encoded
 * STRING, so every `P.<field>` read `undefined`. `Array.from({length: P.nClusters})`
 * became `Array.from({length: undefined})` = `[]`, the work-list collapsed 49 -> 1, and
 * every interpolated `${P.path}` became the literal text "undefined". NOTHING THREW:
 * 38 minutes and 324k tokens were spent fanning out a single garbage unit.
 * Corroborating measurement: `grep -c 'throw new Error'` over the 10 saved workflows in
 * ~/.claude/workflows returns 0 for every one of them - the 3 `throw` hits that do exist
 * are all inside COMMENTS ("a throwing reviewer resolves to null"), so as of this commit
 * not a single saved fan-out can abort itself.
 *
 * WHY THE TWO SHAPE CHECKS ARE NOT OPTIONAL POLISH. `expected` is normally derived from
 * the same args object that broke - e.g. `expected: P.nClusters`. If `expected` arrives
 * `undefined`, then `expected > 1` is `false`, and a guard written only as
 * `units.length < 2 && expected > 1` NEVER FIRES on the exact bug it was written for.
 * Likewise a non-array `units` makes `units.length` `undefined`, and `undefined < 2` is
 * also `false`. Both are therefore hard throws, not warnings: without them this function
 * would silently reproduce the defect it guards.
 *
 * @param {object}   opts
 * @param {Array}    opts.units     the built work-list, one entry per agent to spawn.
 * @param {number}   opts.expected  how many units the author believes they built.
 * @param {string[]} [opts.prompts] the fully-interpolated prompt strings, if built already.
 * @param {object}   [opts.argsRaw] the workflow's `args`. Pass it ONLY after you have
 *   turned it into an object; passing the raw string is itself the bug and throws. If the
 *   workflow parses `args` as a flat string (the `typeof args === 'string' ? args : ''`
 *   idiom at ~/.claude/workflows/codex-auth-research-fanout.mjs:143), omit this field.
 * @returns {{units:number, expected:number, prompts:number}} counts, for logging.
 * @throws {Error} with a stable `.rule` from {@link PREFLIGHT}.
 */
export function preflight(opts = {}) {
  if (opts === null || typeof opts !== 'object' || Array.isArray(opts)) {
    fail(PREFLIGHT.UNITS_NOT_ARRAY, `expected an options object, got ${typeofOf(opts)}`)
  }
  const { units, expected, prompts, argsRaw } = opts

  // `argsRaw` first: when it is wrong every other field is downstream garbage, so this
  // message is the one an author actually needs to see.
  if (argsRaw !== undefined) {
    if (typeof argsRaw === 'string') {
      let hint = 'the runtime delivers `args` as a string, not an object'
      try {
        const parsed = JSON.parse(argsRaw)
        if (parsed !== null && typeof parsed === 'object') {
          hint = 'argsRaw is a JSON-ENCODED STRING - JSON.parse(args) before destructuring it'
        }
      } catch {
        hint = 'argsRaw is a flat string - scan it with a regex instead of destructuring it'
      }
      fail(PREFLIGHT.ARGS_NOT_OBJECT, `${hint} (got ${JSON.stringify(argsRaw.slice(0, 80))})`)
    }
    if (argsRaw === null || typeof argsRaw !== 'object' || Array.isArray(argsRaw)) {
      fail(PREFLIGHT.ARGS_NOT_OBJECT, `argsRaw must be an object, got ${typeofOf(argsRaw)}`)
    }
  }

  if (!Array.isArray(units)) {
    fail(PREFLIGHT.UNITS_NOT_ARRAY, `units must be an array, got ${typeofOf(units)}`)
  }
  if (!Number.isInteger(expected) || expected < 1) {
    fail(
      PREFLIGHT.EXPECTED_NOT_POSITIVE_INT,
      `expected must be a positive integer, got ${typeofOf(expected)} ${String(expected)}` +
        ' - an undefined `expected` would make the collapse check silently inert',
    )
  }
  // ANY size mismatch fails, not just a collapse to 0 or 1.
  //
  // The first version of this check was `units.length === 0 || (units.length < 2 && expected > 1)`,
  // which green-lit the exact defect class this function exists to stop: a PARTIAL collapse.
  // `units=5, expected=49` passed silently. The originating incident was a 51-agent fan-out whose
  // work-list collapsed because `args` arrived as a JSON-encoded string - and a partial collapse is
  // strictly harder to notice than a total one, because 5 running agents look like progress while
  // 44 units are simply never dispatched. `expected` is the author's own declared count, so any
  // disagreement with it is a defect; there is no legitimate reason to build a different number.
  if (units.length !== expected) {
    const how = units.length < expected ? 'collapsed' : 'over-expanded'
    fail(
      PREFLIGHT.COLLAPSED_WORK_LIST,
      `work-list ${how}: built ${units.length} unit(s) but expected ${expected}` +
        (units.length > 0 && units.length < expected
          ? ` - ${expected - units.length} unit(s) would never be dispatched`
          : ''),
    )
  }

  if (prompts !== undefined) {
    if (!Array.isArray(prompts)) {
      fail(PREFLIGHT.PROMPTS_NOT_ARRAY, `prompts must be an array, got ${typeofOf(prompts)}`)
    }
    // An EMPTY prompts array passed silently: the scan loop below simply never ran, so a caller
    // that opted in to prompt checking got none, and got no warning either. Passing `prompts` is a
    // request to scan; having nothing to scan while units exist means the prompts were not
    // actually collected. Omit the field entirely to opt out.
    if (prompts.length === 0 && units.length > 0) {
      fail(
        PREFLIGHT.PROMPTS_NOT_ARRAY,
        `prompts is an empty array while ${units.length} unit(s) exist - nothing would be` +
          ' scanned. Omit `prompts` to opt out of the scan; pass the real prompts to opt in.',
      )
    }
    for (let i = 0; i < prompts.length; i++) {
      const p = prompts[i]
      if (typeof p !== 'string') {
        fail(PREFLIGHT.PROMPTS_NOT_ARRAY, `prompts[${i}] must be a string, got ${typeofOf(p)}`)
      }
      const m = UNDEFINED_TOKEN.exec(p)
      if (m) {
        const from = Math.max(0, m.index - 30)
        fail(
          PREFLIGHT.UNDEFINED_IN_PROMPT,
          `prompts[${i}] contains the literal token "undefined" at char ${m.index} - a` +
            ` failed interpolation: ...${p.slice(from, m.index + 40)}...`,
        )
      }
    }
  }

  return { units: units.length, expected, prompts: prompts === undefined ? 0 : prompts.length }
}

function checkValue(p, value, path, errors) {
  if (p.type && !matchesType(p.type, value)) {
    errors.push({ kind: 'wrong_type', property: path, expected: p.type, got: typeofOf(value) })
    return
  }
  if (Array.isArray(p.enum) && !p.enum.includes(value)) {
    errors.push({ kind: 'enum_mismatch', property: path, allowed: p.enum, got: value })
  }
  if (p.type === 'array' && p.items && Array.isArray(value)) {
    value.forEach((item, i) => checkValue(p.items, item, `${path}[${i}]`, errors))
  }
  if (p.type === 'object' && p.properties && value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) {
      if (p.properties[k]) checkValue(p.properties[k], v, `${path}.${k}`, errors)
    }
  }
}

function matchesType(type, value) {
  switch (type) {
    case 'string':
      return typeof value === 'string'
    case 'number':
      return typeof value === 'number' && Number.isFinite(value)
    case 'integer':
      return Number.isInteger(value)
    case 'boolean':
      return typeof value === 'boolean'
    case 'array':
      return Array.isArray(value)
    case 'object':
      return value !== null && typeof value === 'object' && !Array.isArray(value)
    default:
      return true
  }
}

/**
 * Extract every `type:'object'` schema literal from a workflow script's SOURCE and lint each.
 * Lets the rules be run over the 631 schemas already on disk without executing untrusted JS.
 *
 * @param {string} source  the .js/.mjs text
 * @returns {Array<{index:number, required:string[], violations:Array<object>}>}
 */
export function lintSource(source) {
  const out = []
  if (typeof source !== 'string') return out
  const re = /type\s*:\s*['"]object['"]/g
  const seen = new Set()
  let m
  while ((m = re.exec(source)) !== null) {
    const open = source.lastIndexOf('{', m.index)
    if (open < 0 || seen.has(open)) continue
    seen.add(open)
    const end = matchBrace(source, open)
    if (end < 0) continue
    const body = source.slice(open, end)
    if (!/properties\s*:/.test(body)) continue
    const required = readRequiredArray(body)
    const props = readPropTypes(body)
    const schema = {
      type: 'object',
      properties: props,
      required,
      ...(/additionalProperties\s*:\s*false/.test(body) ? { additionalProperties: false } : {}),
    }
    out.push({ index: open, required, violations: lintSchema(schema) })
  }
  return out
}

function matchBrace(src, start) {
  let depth = 0
  for (let i = start; i < src.length; i++) {
    const c = src[i]
    if (c === '"' || c === "'" || c === '`') {
      const q = c
      i++
      while (i < src.length) {
        if (src[i] === '\\') { i += 2; continue }
        if (src[i] === q) break
        i++
      }
      continue
    }
    if (c === '{') depth++
    else if (c === '}') {
      depth--
      if (depth === 0) return i + 1
    }
  }
  return -1
}

// Hardcoded literal regex (no dynamic construction) - the only key ever read is `required`,
// and a static pattern sidesteps the ReDoS surface a computed RegExp would open.
function readRequiredArray(body) {
  const m = /required\s*:\s*\[([^\]]*)\]/.exec(body)
  if (!m) return []
  return [...m[1].matchAll(/['"]([^'"]+)['"]/g)].map((x) => x[1])
}

function readPropTypes(body) {
  const props = {}
  for (const m of body.matchAll(/([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{\s*type\s*:\s*['"](\w+)['"]/g)) {
    props[m[1]] = { type: m[2] }
  }
  return props
}
