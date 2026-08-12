# "38 delivered" is "38 substantive" — Prompt Two has 2 delivered units, not 38

**Written 2026-08-12 to stop a false number propagating.** The 13.3-hour build wave
(`wf_9cb1a66a-36f`, 78 agents, 21,557,747 subagent tokens, 4,716 tool uses) returned:

```json
{"attempted":40,"returned":38,"delivered_verified":38,"rejected":0,"fabrication_suspected":[]}
```

`ready_units.py` measured, in the same minute, `delivered 1` and later `2`. Both cannot be right.
This resolves it from source rather than picking the more pleasant number.

## The measurement is correct. The label is not.

The wave's filter is one line:

```js
const delivered = alive.filter((r) => r.verdict && r.verdict.artifact_exists && r.verdict.substantive)
```

`artifact_exists && substantive`. It never reads `receipt.status`. So what it proved is that **38
artifacts exist and contain real, non-fabricated, measured content** — which is true, valuable, and
exactly the anti-fabrication job it was built for. `fabrication_suspected: []` is a real result.

What it did **not** prove is that any unit is delivered. Checked directly against each unit's own
declared `output_path`:

| unit | size | at declared path | own `state` |
|---|---|---|---|
| ADV-0001 | 34,814 B | yes | **BLOCKED** |
| ADV-0014 | 98,999 B | yes | **BLOCKED** |
| ADV-0025 | 30,881 B | yes | **BLOCKED** |

Fleet-wide, `artifact_delivered()` reports:

```
1958  absent
  46  self-declared:BLOCKED
   2  DELIVERED
   1  self-declared:FAILED
```

**True count: 2 delivered of 2,007.**

## Why this is an overclaim and not a bug

Three details make the distinction precise, and they matter because "the verifier had a hole" would
be the wrong lesson:

1. The receipt schema already carries `status: ['DELIVERED','PARTIAL','BLOCKED','FAILED']`.
2. The verifier prompt is *shown* the value — `CLAIMED STATUS: ${receipt.status}` — and simply does
   not gate on it.
3. **The wave's own log line is honest**: it prints `verified-substantive ${delivered.length}`. Only
   the internal variable name `delivered` leaked into the returned key `delivered_verified`.

So the code is right and the sentence is wider than its evidence — the same 5:3 overclaim-to-defect
ratio measured across this program's adversarial reviews. The fix is the name, not the filter.

## What is actually true

- 38 artifacts, 24–99 KB each, exist at their declared paths with real measured content and no
  suspected fabrication. That is a genuine result of a 13.3-hour wave.
- Those artifacts **honestly declare themselves BLOCKED**. A unit that reports BLOCKED with its
  evidence attached is a *success* of the contract, not a failure of it — the failure would be a
  unit that claimed DELIVERED without the work behind it, and there are none of those.
- The two casualties, ADV-0021 and ADV-0022, failed with `API Error: Connection closed
  mid-response` — server-side. Earlier notes in this session attributed them to "a driver update"
  and then to "interrupted by user"; both were inferences from transcript tails and both were
  wrong. The workflow's own `<failures>` block is the authoritative record.

## Reproduce

```
python command-center/why_not_delivered.py ADV-0001 ADV-0014 ADV-0025
python command-center/ready_units.py
```

`why_not_delivered.py` prints the predicate's own reason string per unit — that string already
existed and nobody was printing it, which is why the contradiction went unnoticed for hours.

## Consequence for whoever reads the wave result next

Do not cite `delivered_units` (38 entries) as delivered work. Cite it as *substantive artifacts
produced*. The gating question for Prompt Two progress is `artifact_delivered()`, which reads the
receipt instead of stat-ing the file — that predicate was itself only fixed at `03e565ea`, and
before that fix the program reported 4 delivered on the same evidence that now yields 2.

UNVERIFIED, inline: I have not established *why* 46 units self-declare BLOCKED — whether their
contracts require an unavailable dependency, an owner decision, or something else. Settling
experiment: extract the blocker text from each receipt (IMP-0433 documents its blocker in nine
places, so the data is present) and histogram the causes. That is the next question worth asking,
and it is a different question from the one this document answers.
