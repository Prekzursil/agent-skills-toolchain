# P2 GROUNDING LANE — what exists today, prior art, and the ranked plan

STATUS: COMPLETE. Written as a skeleton first, rewritten at each milestone per write-as-you-go.

COVERAGE: sections 1-7 are MEASURED with the command and its real output quoted. Section 5
(external SOTA) is fetched, not recalled. Section 8 lists what I did NOT measure.

Probes live beside this file and are re-runnable:
`_probe_delivered.py` · `_probe_state_field.py` · `_probe_blast_radius.py` ·
`_probe_schema_is_real.py` · `_probe_order_and_contracts.py` · `_probe_imp0433_premise.py`

---

## 1. Live partition — `python command-center/ready_units.py`

```
  units 2007 | delivered 42 | READY 416 | blocked 1385 | owner-gated 164
  block reasons: {'unbuilt': 1365, 'unknown-token': 20}
  first ready: ['ADV-0002', 'ADV-0038', 'ADV-0041', 'ADV-0042', 'ADV-0043', 'ADV-0047', 'ADV-0049', 'ADV-0051']

SUCCESS:ready-units partition sums correctly
```

Briefed: 2007 / 4 / 447 / 1389 / 167. The partition MOVED: delivered 4→42, READY 447→416,
blocked 1389→1385, gated 167→164. The tool asserts its own sum and the assertion passed.

## 2. The `delivered` detector is existence-only, and every artifact it counts says it is NOT done

`ready_units.py:44` — `return bool(p) and (REPO / p).exists()`. Existence is the whole test:
not non-empty, not parsing, not contract-satisfying.

Reading the FIELD rather than the document (`_probe_state_field.py`), across all 42:

```
STATE TALLY over 42 existing artifacts: {'BLOCKED': 37, 'FAILED': 4, '<no-state-field>': 1}
```

**Zero of the 42 declare a delivered/success state.** Eleven are ~2 KB skeletons whose own
`sentinel` field reads `SKELETON - unit died before measuring` (ADV-0021/0022/0026/0031/0032/
0033/0035/0036/0037/0039/0040) — the write-as-you-go skeletons of the builders that died.

DETECTOR CONTROL (both-states), from the probe's own output:
```
CONTROL known-skeleton ADV-0031 -> state=FAILED size=2612
CONTROL known-complete ADV-0010 -> state=BLOCKED size=191580
SUCCESS:state-field detector discriminates the two control states
```

**A detector error of mine, disclosed:** my first probe used a regex for stub words and flagged
22/42. ADV-0006 and ADV-0013 matched only the WORD "placeholder" inside prose that *discusses*
placeholders — use-vs-mention. That first count is retracted; the `state`-field count above
replaces it.

### Blast radius (`_probe_blast_radius.py`)
```
READY under existence-only delivered(): 416
READY under state-aware delivered():    449
PHANTOM-READY (ready only because a BLOCKED/FAILED artifact counted as done): 1
  ADV-0002   deps=['B07', 'ADV-0001']
NEWLY-READY under strict: 34
```
Correctly scoped: the forward contamination is **one** unit (ADV-0002, built on BLOCKED
ADV-0001). The large effect is the other direction — **34 units are excluded from the build set
by a "delivered" flag that their own artifacts contradict.** The headline "42 delivered" is an
artifact of the detector, not of delivery.

## 3. Contracts are REAL — my shim hypothesis was refuted

`receipt.schema.json` self-describes as a "GENERATED SHIM -- carries NO constraints of its own"
(387 READY units declare it). I predicted the contract was a no-op. **Refuted by execution:**

```
GARBAGE-REJECTION CONTROL (3 garbage docs per schema):
    387 units  discriminates (3/3 garbage rejected) command-center/schema/receipt.schema.json
     84 units  discriminates (3/3 garbage rejected) command-center/schema/research-claim-record.schema.json
     ... (top 12 declared schemas)
units whose declared contract accepts all 3 garbage docs: 0
```
The `$ref` to `platform/schema/receipt.schema.json#/$defs/receipt_core` resolves and carries the
constraints. One of the garbage docs was `{"totally":"unrelated","passing_tests":999999}` and
another was 2,000 repeated characters — the two shapes that fooled a verifier earlier in this
program. Both are rejected here.

Contract resolvability over the 416 READY units:
```
  283  ok      126  fragment      6  missing      1  prose-but-base-resolves
```
The 126 "fragment" are legitimate JSON-pointer forms (`...#/$defs/x`) — an earlier count of mine
called them missing, which was my parser, not the catalog. Only **6** are genuinely unresolvable,
and they share one shape: a two-schema expression (`receipt.schema.json + tools/plugin/schema/
error-taxonomy.schema.json`) or an external URL (RES-0001 → `https://json-schema.org/...`).

## 4. OQ-2 ordering — and a sort bug in my own probe

Ascending phase, then unblocking power (count of units naming it as a dependency):

| phase | unblocks | unit | contract | output_path |
|---|---|---|---|---|
| 0 | **13** | IMP-0433 | ok | command-center/receipts/IMP-0433.json |
| 0 | 8 | AUD-0041 | ok | command-center/audit/AUD-0041-ci-step-inventory.json |
| 0 | 5 | AUD-0051 | ok | command-center/audit/AUD-0051-coverage-baseline.json |
| 0 | 3 | AUD-0001 / AUD-0020 / AUD-0030 / CC-0002 / IMP-0440 | ok | … |
| 0 | 2 | AUD-0006 / AUD-0015 / AUD-0021 / CC-0007 / CNF-0015 | ok | … |

**MY BUG, disclosed inline:** `phase` is a STRING (`'0','1','2','2A','10','16'`). My probe sorted
it lexicographically, which puts phase `'10'` BEFORE phase `'2'`:
```
LEXICOGRAPHIC (what my probe did): ['0','1','10','11','12','13','14','15','16','2','2A',...]
NATURAL (correct OQ-2):            ['0','1','2','2A','2C','3','4','5','6','7','7A','10',...]
```
The phase-0 head above is UNAFFECTED (`'0'` sorts first either way), so the table stands. The
tail ordering is wrong. The build lane must use a natural key
`(int(re.match(r'(\d+)',p).group(1)), p)`. Settling experiment: re-run
`_probe_order_and_contracts.py` with that key and diff the ranked list beyond rank 51.

READY distribution:
```
by phase:  {'0':51,'1':13,'2':56,'2A':6,'2C':1,'3':1,'4':4,'5':9,'6':1,'7':4,'7A':1,
            '10':114,'11':20,'12':73,'13':54,'14':2,'15':5,'16':1}
by prefix: {'TST':115,'ADV':77,'RES':57,'BLD':54,'AUD':44,'CNF':22,'IMP':17,'WFA':15,...}
substrate: {'local-parallel':152,'local-serialized':136,'worktree-isolated':75,'cloud-batch':53}
```
**105 READY units write into a directory that does not exist yet** — 44 of them into
`command-center/audit/` alone, plus 8 subtrees under `command-center/research/`. `mkdir -p` is a
precondition for the phase-0 batch, not an afterthought.

## 5. IMP-0433's premise is REFUTED — the top unit is a much smaller job than written

IMP-0433 (phase 0, unblocks 13) is worded: *"Author command-center/schema/receipt.schema.json —
the file that defaults.output_schema … points at and **that does not exist on disk**."*

Executed (`_probe_imp0433_premise.py`):
```
P1 exists(command-center\schema\receipt.schema.json) = True  size=5882B
   top-level $ref: https://ast-integrate.invalid/platform/schema/receipt.schema.json#/$defs/receipt_core
P3 positive fixture = command-center\receipts\TST-0334.json   VALID=True
P2 negative fixtures (each MUST be INVALID):
   drop sentinel         VALID=False  'sentinel' is a required property
   drop evidence         VALID=False  'evidence' is a required property
   drop unit_id          VALID=False  'unit_id' is a required property
   drop state            VALID=False  'state' is a required property
   drop artifacts        VALID=False  'artifacts' is a required property
   drop min_bytes_threshold VALID=False  'min_bytes_threshold' is a required property
   drop reviewer         VALID=True   <-- NOT REQUIRED
   drop negative_controls VALID=True  <-- NOT REQUIRED
   drop residual_unknowns VALID=True  <-- NOT REQUIRED
```

Correctly scoped verdict: the "does not exist" premise is **REFUTED** (almost certain, 95-99% —
the file was read, parsed, and used to validate). Of IMP-0433's three named strictness
conditions, **two are already enforced** (missing sentinel → INVALID; missing evidence anchors →
INVALID) and **one is not** (missing *reviewer verdict* → still VALID; `reviewer`,
`negative_controls` and `residual_unknowns` are all optional today).

So IMP-0433 is not "author a schema". It is: require the reviewer verdict (+ the two other
optional evidence fields if the contract intends them), author the twelve negative fixtures the
unit already specifies, and emit the receipt. That is a fraction of the written scope and it
unblocks 13 units.

## 6. External SOTA (fetched 2026-08-12, not recalled)

- **Self-Authored Verification Is Unreliable in Heuristic Self-Improving Agents** —
  arXiv 2607.24300. Across 35 model-game combinations **every** agent reported a self-test score
  ≥0.70 while **15 of 35 scored below the random baseline**; six hit the failure floor with
  near-perfect self-scores. Their fix (SEAL) is four properties: a **fixed external audit** the
  agent cannot reselect, **audit confidentiality**, **single-bit accept/reject feedback** so the
  audit score cannot become the new target, and **conservative rollback**. This is the exact
  shape of the defect in §2 — a program grading itself with a detector it authored.
- **Building to the Test: Coding Agents Deliver What You Check, Not What You Requested** —
  arXiv 2606.28430. Goodhart applied to agent artifacts: agents satisfy the checked condition
  rather than the requested one. `ready_units.py` checks *existence*; the program produced 42
  files that exist and 0 that are done. Textbook instance.
- **The Verification Horizon: No Silver Bullet for Coding Agent Rewards** — arXiv 2606.26300.
  Executable tests are scalable and robust but not faithful; LLM judges are faithful but
  exploitable; human review is faithful but not scalable. Their filtering result: hacked
  resolution 28.57% → 0.56%, clean resolved 40.22% → 60.53%. Supports spending the build lane's
  budget on *filtering which units are provable* over raising unit throughput.
- **SWE-Marathon** — arXiv 2606.07682. Ultra-long-horizon agent work fails specifically through
  poor self-verification, self-reported infeasibility, and premature termination; their harness
  pairs a visible dev signal with a **hidden verifier** and a held-out oracle. Directly supports
  keeping the completion check separate from the unit that produces the artifact.

## 7. Prior art in this repo — do NOT rebuild these

| Already exists | Path | What it means for the build lane |
|---|---|---|
| Partition tool w/ self-asserting sum | `command-center/ready_units.py` | Use it; do not re-derive the READY set |
| Detector-control idiom (accepts-conforming AND rejects-nonconforming, asserted before any count) | `command-center/_p14_floors.py:44-60` | Copy this pattern for every new probe; it is the both-states test already codified |
| Floor audits across 4 waves | `WAVE1..WAVE3-FLOOR-AUDIT.{json,md}`, `wave3_floor_audit.py`, `wave4_marketplace_lifecycle_verify.py` | Prior measurement of numeric floors — read before re-measuring |
| Receipt emitter | `command-center/p13_emit_receipt.py` | Emit receipts with this, do not hand-roll |
| Failed-agent recovery | `command-center/recover_failed_agents.py` | The tool the casualty lane was supposed to run against ADV-0021/0022 |
| 261 `$id`-bearing schemas resolvable as one store | `command-center/schema/**`, `platform/**` | Contracts are real and machine-checkable today |
| Catalog integrity + shortfall attribution | `_catalog_integrity.py`, `_catalog_shortfall_attrib.py` | Existing integrity lens over the catalog |

**The prior GROUNDING lane is a casualty.** `command-center/casualty/GROUNDING-LANE-CASUALTY.md`
is still its own skeleton: all ten of its coverage items C1-C10 read `UNKNOWN - not yet measured`
and it carries the verbatim line *"If it still reads this way, the unit died before measuring
anything and no verdict here may be cited."* It produced **no** measurements. Its C1-C10 list is
still a good checklist and this lane covers C5, C6, C7 and C10; C1-C4, C8 remain open (§8).

## 8. What I did NOT measure (residual, disclosed)

- Whether the 34 self-declared-BLOCKED artifacts are blocked for a *still-valid* reason. I read
  the `state` field, not the blocking justification. Settling experiment: parse `failure` /
  `retry` fields on those 34 and re-probe each stated blocker.
- ADV-0002 dispatch status (casualty C8) — not probed.
- `recover_failed_agents.py` was located but NOT executed (casualty C1).
- The 53 `cloud-batch` READY units — I did not check whether their substrate is reachable.
- Full OQ-2 ordering beyond phase 0 (blocked on my own sort bug, §4).
