# Fan-out schema design guide

`StructuredOutput` is the fan-in surface of every Claude Code Workflow in this workspace. It
fails **22.7% of the time**, and the failures are ours: our own schemas rejecting our own
agents' work. This directory holds the measurement, the rules it produced, and a module that
makes the dominant failure unrepresentable.

Run the tests: `node --test tools/fanout-schema/`
Lint the schemas you already have: import `lintSource` (see *Auditing what you already wrote*).

---

## 1. What was measured

Scan of **11,693 transcripts / 10.65 GB** under `~/.claude/projects`, joined to the **637
schema literals** declared across **435 workflow scripts** in `*/workflows/scripts/*.js`.

| | calls | errors | rate |
|---|---|---|---|
| StructuredOutput, all | 3,735 | 849 | **22.7%** |

The distilled corpus reports 3,694 / 846 / 22.9% from an independent implementation. Two
mechanically different miners agreeing within 1.1% is the reason these numbers are quoted as
fact rather than estimate.

### Failure taxonomy (n = 849)

| class | n | share |
|---|---|---|
| missing required property | 616 | 72.6% |
| unparseable JSON | 176 | 20.7% |
| `additionalProperties: false` rejection | 30 | 3.5% |
| wrong type | 14 | 1.6% |
| other / non-schema | 13 | 1.5% |
| enum mismatch | 0 | 0% |
| too deep / too many items / too long | 0 | 0% |

Nothing failed for nesting depth, item count or length. **Depth and size limits are not a
real failure surface in this workspace** — do not spend design effort on them.

### The mechanism

Resolving each of the **1,193 individually omitted properties** to its declared type:

| declared type of the omitted field | n | share |
|---|---|---|
| string | 691 | **57.9%** |
| array | 457 | 38.3% |
| boolean | 26 | 2.2% |
| object | 19 | 1.6% |

Models omit **ancillary** fields — anything that is not the answer itself — regardless of
type. The two most-omitted fields were `kg_triples` (array, 342) and `confidence`
(string enum, 314).

The modal failing payload carried **exactly one key** (597 of 849) and was **smaller** than
the average successful payload (mean 4,391 chars vs 6,072). Agents were not running out of
room; they wrote the answer and stopped.

---

## 2. The rules, with the number that produced each

### R1 — Require exactly one field, and make it a string. (the whole ballgame)

| schema shape | calls | errors | rate |
|---|---|---|---|
| `required` = one string field | 130 | **0** | **0.0%** |
| anything else | 2,742 | 727 | 26.5% |

Zero failures in 130 calls. By the rule of three the true rate is under ~2.3% at 95%
confidence. An independent measurement that never looked at the schema files — detecting a
`*_markdown` catch-all from the transcripts alone — found **7/239 = 2.9%** against
**842/3,497 = 24.1%**. Two different methods, same conclusion.

### R2 — Never put an array-typed field in `required`.

| | calls | errors | rate |
|---|---|---|---|
| an array appears in `required` | 1,342 | 628 | **46.8%** |
| no array in `required` | 1,530 | 99 | 6.5% |

Still 25.0% vs 3.9% with the single dominant workflow excluded, so this is not one bad
schema driving the statistic.

**But R2 alone is not enough, and shipping only R2 would have fixed almost nothing.** The
worst schema in the corpus required `['summary', 'kg_triples', 'confidence']`. Making only
the array optional leaves `confidence` required — and `confidence` is missing in 294 of
those 335 failures. R2 without R1 would have recovered 41 of 335.

### R3 — Do not set `additionalProperties: false`.

30 measured rejections for *containing more than was asked for*. Discarding a complete
result because the model added a helpful key is a bad trade.

### R4 — Do NOT cap the number of properties, and do not lint schema width.

| `required` count | calls | errors | rate |
|---|---|---|---|
| 1 | 184 | 5 | 2.7% |
| 2 | 831 | 18 | 2.2% |
| 3 | 819 | 437 | **53.4%** |
| 4 | 199 | 35 | 17.6% |
| 5 | 311 | 56 | 18.0% |
| 6 | 212 | 68 | 32.1% |
| 7 | 71 | 2 | 2.8% |
| 8 | 151 | 102 | **67.6%** |
| 9 | 64 | 4 | 6.3% |
| 10 | 30 | **0** | **0.0%** |

Not monotonic. A 3-required schema scored 53.4% and a 10-required schema scored 0.0%. Any
rule of the form "cap `required` at N" is a coincidence, not a mechanism.

The practical consequence is liberating: **rich `properties` are free.** Descriptions steer
the model and cost nothing. Only `required` is rejection surface, and the two are
independent. You do not have to choose between a typed schema and a reliable one — declare
everything, require one thing.

### R5 — Every required name must exist in `properties`.

2 schemas on disk require a field they never declare. Those reject every payload
unconditionally.

---

## 3. Does this mean "always use a single `findings_markdown` string"?

The standing guidance in this workspace is that broad or deep lenses should use a loose
schema — one `findings_markdown` string — rather than a strict typed one. **The data
supports it**, by 8.2x on one measurement and by 0-vs-26.5% on another.

But the data also sharpens it, and the sharpened version is strictly better:

> The win comes from the `required` set, not from giving up typed fields.

A schema with one required string and twelve described optional fields is measured-safe
(`required`=1 → 2.7%; ten optional-heavy schemas → 0/30) **and** still gives the
orchestrator machine-readable fields whenever the agent fills them. Collapsing to a single
opaque string throws away structure you could have had for free.

So: **loose in `required`, rich in `properties`.** Reach for a bare
`{ findings_markdown }` only when there genuinely is no recurring structure worth naming.

---

## 4. Using the module

```js
import { findingsSchema, fanoutSchema } from '../../tools/fanout-schema/fanout_schema.mjs'

// House default for a lens / discovery / review fan-out.
const LENS = findingsSchema({
  lens: 'string',
  citations: 'string[]',
  confidence: ['high', 'medium', 'low', 'unverified'],
})
// -> required: ['findings_markdown'], additionalProperties: true

// Or name your own narrative field.
const REVIEW = fanoutSchema({
  narrative: 'review_markdown',
  narrativeDescription: 'Your full review. The ONLY required field.',
  optional: { verdict: ['PASS', 'FAIL'], blocking: 'string[]', wu: 'string' },
})

await agent(prompt, { label: 'lens:x', schema: LENS })
```

`fanoutSchema` **throws** rather than building a schema that violates R1: you cannot pass
`required`, and the narrative field cannot be array-typed. The failure mode is
unrepresentable, not merely detectable.

Field-spec shorthand: `'string'` · `'number'` · `'boolean'` · `'object'` · `'array'` ·
`'string[]'` · `['enum','values']` · or a raw JSON Schema fragment, passed through untouched.

### Checking a payload before you ship the fan-out

```js
import { validate } from '.../fanout_schema.mjs'
validate(LENS, { findings_markdown: '# found' })   // { valid: true, errors: [] }
```

`validate` covers the JSON Schema subset the harness actually uses — `type`, `properties`,
`required`, `items`, `enum`, `additionalProperties`. It is not a general JSON Schema engine
and is not trying to be; it exists so you can unit-test a real sample payload against your
schema instead of discovering the mismatch across 40 agents.

### Auditing what you already wrote

```js
import { lintSource } from '.../fanout_schema.mjs'
for (const s of lintSource(readFileSync(script, 'utf8'))) {
  for (const v of s.violations) console.log(v.rule, v.property, v.message)
}
```

Run over all 435 workflow scripts currently on disk:

```
schema literals found : 637
schemas with >=1 violation: 619 (97.2%)
    1982  multi-required
     562  no-additional-properties
     433  array-in-required
      88  narrative-not-string
      20  no-required
       2  undeclared-required
```

Every violation carries the measurement that justifies it in its `evidence` field, so a
reviewer can argue with the number rather than the opinion.

---

## 5. The unparseable-JSON class (20.7%) — what is and is not known

176 failures were malformed JSON rather than schema mismatches. Recovering 197 raw payloads
from `__unparsedToolInput.raw`:

- **46.2% (91/197) contain an unquoted bare value after a key** — e.g.
  `"kg_triples": ASP8062 | is | GABA-B receptor PAM` and `"files": C:/Users/...`. The model
  writes the content where a JSON string or array belonged.
- **10.2% (20/197) leaked XML tool-call syntax into the JSON** — a `<parameter name="...">`
  block opening inside a string value.
- **Size is not the cause.** True payload lengths (recorded in `__unparsedToolInput.len`):
  median 4,036, max 29,134, **none at or above 32,768** — while *successful* payloads reach
  58,653 chars. The "output got too big and was truncated mid-JSON" hypothesis is refuted.

**UNVERIFIED — how much of this class R1 fixes.** The mechanism is suggestive (the bare-value
failures cluster on exactly the array-typed ancillary fields R1 makes optional, so a model
that may omit them should not need to mis-serialise them), but no controlled comparison was
run and this is a plausible story, not a measurement. Because 74.6% of stored payloads are
truncated at a 2,048-byte transcript cap, the two sub-percentages above are **lower bounds**
and the residual cannot be classified from the transcripts at all. The experiment that
settles it: convert one high-volume fan-out to `findingsSchema`, re-run it, and compare the
unparseable-JSON rate before and after on the same prompt.

---

## 6. `preflight()` — abort a fan-out whose work-list silently collapsed

Sections 1-5 are about the **shape of the answer** a subagent returns. This section is about
the **shape of the launch** — a distinct failure that the schema rules cannot see, because it
happens before a single agent is spawned.

### The measured failure (2026-07-29, one 51-agent workflow)

The script opened `const P = args`. The runtime delivers `args` as a **JSON-encoded string**,
so every `P.<field>` read `undefined`. Consequently:

- `Array.from({length: P.nClusters})` became `Array.from({length: undefined})` = `[]`, and the
  work-list collapsed from 49 units to 1;
- every interpolated `${P.path}` rendered as the literal four-letter text `undefined`.

**Nothing threw.** The run spent 38 minutes and 324k tokens fanning out a single garbage unit
and reported completion. Corroborating measurement, taken per-file so a `grep -c` exit code
cannot lie: of the 10 saved workflows in `~/.claude/workflows`, **`throw new Error` count = 0
in every one**, and the only 3 `throw` matches that exist at all are inside comments
(`// a throwing reviewer resolves to null`). Not one saved fan-out could abort itself.

The guard idiom that *would* have caught it already existed in the corpus —
`const ARGS = typeof args === 'string' ? args : ''` at
`~/.claude/workflows/codex-auth-research-fanout.mjs:143` — but prose in one file is not a
guard in the others, and that file has 0 throws too.

### Using it

```js
import { preflight } from '../../tools/fanout-schema/fanout_schema.mjs'

const units = buildWorkList(config)
const prompts = units.map((u) => renderPrompt(u))

preflight({ units, expected: config.nClusters, prompts, argsRaw: config })
// -> { units: 49, expected: 49, prompts: 49 }, or THROWS

await parallel(units.map((u, i) => () => agent(prompts[i], { schema: LENS })))
```

Call it **after** the work-list and prompts are built and **before** the first spawn. It
throws an `Error` carrying a stable `err.rule` from the exported `PREFLIGHT` map:

| `err.rule` | fires when |
|---|---|
| `preflight/args-not-object` | `argsRaw` is a string (the measured root cause), `null`, an array, or a scalar |
| `preflight/units-not-array` | `units` is not an array — otherwise `units.length` is `undefined` |
| `preflight/expected-not-positive-int` | `expected` is not a positive integer |
| `preflight/collapsed-work-list` | `units` is empty, or `units.length < 2` while `expected > 1` |
| `preflight/undefined-in-prompt` | a prompt matches `/\bundefined\b/` — a failed interpolation |
| `preflight/prompts-not-array` | `prompts` is not an array of strings |

Pass `argsRaw` **only** after you have turned `args` into an object; handing over the raw
string is itself the bug and is what throws. A workflow that deliberately treats `args` as a
flat string (the `codex-auth-research-fanout.mjs:143` idiom) should simply omit the field.

### Why the two shape checks are not optional polish

`expected` is normally derived from the same args object that broke — `expected: P.nClusters`.
If `expected` arrives `undefined`, then `expected > 1` is `false`, so a guard written only as

```js
if (units.length < 2 && expected > 1) throw new Error('collapsed')   // INERT
```

**never fires on the exact bug it was written for**. `undefined < 2` is likewise `false`, so a
non-array `units` disarms it too. Both are therefore hard throws in `preflight`, and both are
covered by their own mutant in `test_preflight_mutations.mjs`.

### Guard coverage is proven, not asserted

`npm test` runs the unit suite **and** `test_preflight_mutations.mjs`, which removes each of
the five guards in turn and requires the suite to go **red**. A surviving mutant fails the
gate. Measured on this commit: `BASELINE pass=36 fail=0`, then `M1..M5 KILLED`,
`SUCCESS:preflight-mutations 5/5 killed`. A green suite alone would not have shown that any
guard was reachable.

**Known false positive, accepted deliberately.** A prompt whose *prose* uses the English word
("behaviour here is undefined") also throws; the fix is to reword the prompt. There is no
opt-out, because the trade is one-sided — a reworded adjective costs seconds, the missed
interpolation cost 38 minutes and 324k tokens.

**UNVERIFIED — the adoption effect.** No saved workflow calls `preflight()` yet, so its
real-world catch rate is unmeasured; the only evidence is the one reproduced failure plus the
five killed mutants. The experiment that settles it: wire `preflight()` into the next
multi-cluster fan-out and record whether it ever fires in anger.

---

Run the tests: `npm --prefix tools/fanout-schema test`
(unit suite + the preflight mutation probe; both must pass)

Lint checked-in workflows: `node tools/fanout-schema/lint_fanout_schemas.mjs workflows`
