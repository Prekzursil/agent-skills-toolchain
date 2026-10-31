# ADV-0002 (and ADV-0038) — accounting

Measured 2026-08-12, build round 1, lane CASUALTY. Every number below came from a probe with
a passing two-sided detector control; nothing here is inferred from a filename.

## Verdict: NEVER DISPATCHED. Not a casualty, not a lost artifact.

**Scope of that verdict, stated up front (round-2 correction).** Round 1 wrote "NEVER DISPATCHED"
unqualified while its probe read exactly two runs of one session. The adversarial audit was right
to call that wider than its evidence. Round 2 did not narrow the sentence — it **widened the
measurement** with a mechanically different tool and the verdict survived:

| probe | tool | corpus | ADV-0002 | ADV-0038 |
|---|---|---|---|---|
| round 1 | python, parses each transcript's own first user message | 2 runs, 100 transcripts, 1 session | dispatched=False | dispatched=False |
| round 2 | `rg` over raw bytes (`_r2_adv0002_recheck.py`) | **every `*.jsonl` in every session of every project** under `~/.claude/projects` | occurrences exist, **all MENTIONS**; 0 transcripts own it | **0 occurrences at all** |

Detector control for the round-2 sweep: the same matcher with the wildcard id returns **152
occurrences across 52 files**, and ADV-0021 six times — so a zero is a real absence and not a
broken pattern. Full record: `R2-ADV0002-RECHECK.json`.

**Residual, inline:** both probes assume a dispatch always carries the literal `YOUR WORK UNIT:`
marker. That held 40/40 in this wave. A launcher using a different template is invisible to both.
*Settling experiment:* read the workflow launcher that composes the spawn prompt and confirm the
marker is unconditional.

`python command-center/casualty/_probe_dispatch_census.py` reads the literal
`YOUR WORK UNIT: <ID>` line out of every spawn prompt across the run. Re-run in round 2 — the
`98` below was already stale when round 1 pasted it; the live value is `100`, and the file is the
live output:

```
CONTROL: positive(finds known-dispatched ADV-0021+ADV-0022)=True negative(does not invent ADV-9999)=True
transcripts scanned: 100; distinct units dispatched: 40
ADV units DISPATCHED in these runs: 40
ADV artifacts ON DISK now:          40
DISPATCHED but NO artifact on disk: (none)
artifact on disk but NOT dispatched in these runs: (none)
ADV-0002: dispatched=False (no transcript) artifact_on_disk=False
ADV-0038: dispatched=False (no transcript) artifact_on_disk=False
```

A perfect 1:1 between dispatch and delivery. There is no unit that was dispatched and produced
nothing, and no artifact without a dispatch. **Sherman-Kent: almost-certain (95-99%).**

## The sharper framing the earlier brief did not have

The catalog contains **144** ADV units (ADV-0001 … ADV-0144), not 42. This wave's dispatch set was
the range **ADV-0001 … ADV-0042 minus {ADV-0002, ADV-0038} = 40 units**. The 102 units from
ADV-0043 upward have no artifacts either, and were simply never in this wave's scope.

So ADV-0002 and ADV-0038 are not "missing artifacts" — they are **the only two gaps inside an
otherwise contiguous dispatched range**. That is a dispatch-set fact.

## I am REVISING the grounding lane's explanation downward, because of new evidence

The grounding lane proposed that READY was snapshotted once at launch, so ADV-0002 became eligible
only after its dependency ADV-0001 completed in-wave. It rated this *likely (65%)* and correctly
tagged it UNVERIFIED. I tested it (`_r1_why_undispatched.py`) and it does not survive:

| test | result |
|---|---|
| ADV-0002 deps | `['B07', 'ADV-0001']` — ADV-0001 **did** complete in-wave, consistent with the hypothesis |
| ADV-0038 deps | `['B07', 'B13']` — **no ADV-\* dependency at all**, so nothing could have "become ready late" |
| dispatched units that also depend on an in-wave ADV unit | **3 counterexamples**: ADV-0013 (dep ADV-0007), ADV-0016 (dep ADV-0011), ADV-0018 (dep ADV-0012) — all dispatched anyway |

Either leg alone weakens it; together they refute it as *the* explanation. An in-wave ADV
dependency demonstrably does not prevent dispatch, and ADV-0038 has none to begin with.

**Revised verdict on the WHY: NOT-CHECKED** (down from *likely 65%*). I am revising because the
counterexamples and ADV-0038's dependency list are new evidence, not because the earlier reasoning
was poorly argued — it was a reasonable inference from the one unit it examined.

Note also that `B07` and `B13` cannot be evaluated as bucket completions: every ADV unit carries
`bucket: "B10"`, and **zero** catalog units have `bucket` equal to `B07` or `B13`, so those tokens
in `dependencies` refer to a different plane than the `bucket` field. That is itself a small
integrity smell worth an owner glance.

**Settling experiment (named, as required):** read the wave's dispatch-selection code or log and
determine how the 40-unit set was chosen — specifically whether the range was hand-authored, and
whether ADV-0002/ADV-0038 were excluded deliberately (e.g. an owner drop) or by a bug. Until that
is read, no causal claim should be made.

## Recommendation to the owner

Re-evaluate READY after each wave rather than snapshotting once at launch. This is worth doing
**regardless** of whether it explains these two units: ADV-0002's dependency ADV-0001 completed
inside this very wave, so under a snapshot regime it could never have run, and the same shape will
recur on every future wave whose units depend on each other.

Neither unit should be counted as a casualty in any recovery accounting. The wave's true casualty
count is **2** (ADV-0021, ADV-0022), both of which this lane has now recovered.
