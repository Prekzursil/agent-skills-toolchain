---
title: h6-timeout-heartbeat
type: note
permalink: dqverify-repo-20261013/skills/workflow-authoring/templates/h6-timeout-heartbeat
---

# Template — H6: per-agent timeout + stall heartbeat (barrier-deadlock escape)

**What this is.** The implementation of design item **H6** from
`docs/audit-design-2026-07-13/B2-RFC-operational.md:360-400` (`H6 ★ = per-agent timeout +
stall heartbeat (barrier-deadlock escape)`), scheduled as wave item **W1.5, effort LOW
(helper)** in `docs/audit-design-2026-07-13/B3-migration-verification.md:150`. Its exit
criterion, verbatim from `B3:156`, is *"H6 proven to break a synthetic barrier hang."*

**Why it is a paste-in template and not a library.** A saved Workflow runs inside a Node
`vm` context with `codeGeneration.strings = false` and no module loader: `require()` is
undefined and `import()` throws. There is no way to `import` a helper. So the helper ships
as a source block you paste at the top of your workflow.

**The measured problem.** Across the 10 saved workflows on this box there are 15
`parallel(` barrier calls, 38 `agent(` calls, and **zero** `Promise.race`, `setTimeout`, or
`AbortController` (`docs/workflow-sota/GROUNDING-NOTES.md` §2). `parallel()` is a barrier:
it settles only when every thunk settles. One agent that never returns therefore freezes the
whole phase — a 13-hour deadlock and an 11-lane stall behind one hung reviewer are both on
the record, and `platform/workflows/shared-prod-shard-fanout-build.json` records an 11-hour
hung unit in production.

---

## THE HONEST SCOPE — read this before you cite the helper

`Promise.race` unblocks **the barrier**. It does **not** kill the agent.

The losing promise keeps running. The hung agent keeps one of the ~14 concurrency slots
(`min(16, cores - 2)`) and keeps spending `budget` until it dies on its own. `B3:262` words
falsifier #21 as the hung node being *"timed-out and **killed**"* — that word is an
overclaim against this mechanism and must not be reused. The correct sentence is:

> **dropped from the barrier; the agent keeps running and keeps its slot.**

Settling experiment for anyone who wants to check: read `budget.spent()` immediately after a
timeout receipt appears and again after the workflow returns. A rise proves the agent lived on.

Two more limits, stated inline rather than in a trailing caveats section:

- The **heartbeat is an observation, not a stall verdict.** `h6Heartbeat` reports *"still
  waiting on `<label>` after `STALL_MS`"*. It cannot distinguish a genuinely hung agent from
  a slow-but-healthy one; that needs orchestrator state the sandbox cannot see.
- `withTimeout` protects a **thunk**, so it bounds one `agent()` call (or one small
  composite). It does not bound a `pipeline()` stage boundary — `pipeline()` has no barrier
  between stages, which is exactly why the runtime says *"DEFAULT TO pipeline()"* and why
  H6 is the fix for the barriers you genuinely cannot avoid.

---

## Defaults, and where each number comes from

| constant | value | source |
|---|---|---|
| `H6_TIMEOUT_MS` | `1800000` (30 min) | `dispatch_timeout_seconds` default 1800 in `platform/workflows/*.json` (min 300, max 3600) |
| `H6_STALL_MS` | `90000` (90 s) | `B3-migration-verification.md:263` falsifier #22, `STALL_MS = 90 s` |

Both are plain `const`s — override them per workflow. Keep `H6_STALL_MS < H6_TIMEOUT_MS`;
a heartbeat that fires after the drop tells you nothing.

---

## The helper — paste this block verbatim

Everything between the two markers is the canonical source. It is extracted and
**executed** by `tools/wf-timeout/test_h6_timeout.py`, so the block below is the tested
artifact, not a transcription of one. Do not edit it here without re-running that suite.

<!-- H6-BEGIN -->
```js
// ---------------------------------------------------------------------------
// H6 — per-agent timeout + stall heartbeat. Paste at the top of the workflow.
// Sandbox-safe: uses only injected globals (setTimeout/clearTimeout/log/parallel).
// No Date.now / Math.random / new Date() -> stays workflow_lint clean.
// SCOPE: unblocks the BARRIER. Does NOT kill the agent -- the dropped agent keeps
// running and keeps its concurrency slot until it dies on its own.
// ---------------------------------------------------------------------------
const H6_TIMEOUT_MS = 1800000; // 30 min; blueprint dispatch_timeout_seconds default
const H6_STALL_MS = 90000; // 90 s; B3 falsifier #22

// A typed drop-receipt (design item H3). NEVER return a bare null from a barrier:
// null is produced for at least three different causes -- user skipped the agent,
// the subagent died on a terminal error, and (here) our own timeout -- and
// .filter(Boolean) throws that distinction away, making "12 of 15 returned"
// unauditable.
function h6Receipt(endReason, label, ms, detail) {
  return {
    __h6: true,
    __endReason: endReason, // 'timeout' | 'threw' | 'null'
    label: label,
    ms: ms,
    detail: detail === undefined ? null : detail,
  };
}

function h6IsDrop(r) {
  return !!r && r.__h6 === true;
}
function h6Survivors(results) {
  return results.filter(function (r) {
    return !h6IsDrop(r);
  });
}
function h6Drops(results) {
  return results.filter(h6IsDrop);
}

// Emit one heartbeat line if the unit is still outstanding at H6_STALL_MS.
// Returns a canceller. This is an OBSERVATION ("still waiting"), not a verdict
// that the agent is hung -- the sandbox cannot see orchestrator state.
function h6Heartbeat(label, stallMs) {
  if (typeof setTimeout !== 'function') return function () {};
  const t = setTimeout(function () {
    if (typeof log === 'function') {
      log('H6 heartbeat: still waiting on ' + label + ' after ' + stallMs + 'ms');
    }
  }, stallMs);
  return function () {
    if (typeof clearTimeout === 'function') clearTimeout(t);
  };
}

// Bound ONE thunk. Always resolves -- never rejects, never returns undefined --
// so a barrier over wrapped thunks can no longer be poisoned by one unit.
async function withTimeout(thunk, ms, label, stallMs) {
  const lbl = label === undefined ? 'unit' : label;
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms;
  // Runtime-drift guard: if a future build stops injecting timers, degrade to a
  // plain await instead of dying with a ReferenceError at fan-out time.
  if (typeof setTimeout !== 'function') {
    try {
      return await thunk();
    } catch (err) {
      return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
    }
  }
  const stopBeat = h6Heartbeat(lbl, stallMs === undefined ? H6_STALL_MS : stallMs);
  let timer = null;
  const expiry = new Promise(function (resolve) {
    timer = setTimeout(function () {
      resolve(h6Receipt('timeout', lbl, budgetMs, null));
    }, budgetMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(thunk), expiry]);
  } catch (err) {
    return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
  } finally {
    // ALWAYS clear on the winning path too: an un-cleared timer stays in the
    // runtime's abort set and can hold the workflow open past its last agent.
    if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
    stopBeat();
  }
}

// A SETTLED barrier: same shape as parallel(), but one hung unit costs you that
// unit instead of the phase. Output is index-aligned with `thunks` and every
// slot is either a real result or a typed drop-receipt -- no nulls, no holes.
async function settle(thunks, ms, labels) {
  const nameOf = function (i) {
    return labels && labels[i] !== undefined ? labels[i] : 'unit-' + i;
  };
  const raw = await parallel(
    thunks.map(function (t, i) {
      return function () {
        return withTimeout(t, ms, nameOf(i));
      };
    }),
  );
  return raw.map(function (r, i) {
    // The runtime still yields null for a cause we never saw (a user skip).
    // Type it rather than filtering it away.
    return r === null || r === undefined ? h6Receipt('null', nameOf(i), ms, null) : r;
  });
}
```
<!-- H6-END -->

---

## Using it

```js
const results = await settle(
  units.map((u) => () => agent(promptFor(u), { schema: UNIT_SCHEMA, phase: 'review' })),
  600000,
  units.map((u) => u.id),
);

const ok = h6Survivors(results);
const dropped = h6Drops(results);
log(`phase settled: ${ok.length} ok, ${dropped.length} dropped`);
for (const d of dropped) log(`  DROPPED ${d.label}: ${d.__endReason}`);
// Terminal state, never silence (AGENTS.md §4 / failure_policy.never_silent):
if (ok.length === 0) return `FAILED:review every unit dropped (${dropped.length})`;
```

`settle()` returns no nulls, so `.filter(Boolean)` after it is unnecessary (though harmless).

A note on the linter, because the first version of this sentence was an overclaim and was
measured false: `workflow_lint`'s `parallel-filter-boolean` rule **did** fire on the helper's
internal `parallel(` — the helper hands nulls to `.map()` rather than deleting them with
`.filter(Boolean)`, which is *stronger* (it types the drop instead of erasing it, design item
H3), but the rule could not see that. Rather than reword the claim, the rule was fixed: it now
accepts a `.map(...)` that names `null` as null-tolerant, with a both-states test
(`test_parallel_null_typing_map_is_accepted_both_states`) proving a `.map()` that does *not*
mention null still warns. Keep the helper block verbatim and the lint stays quiet.

## Prefer this to a barrier only when you actually need a barrier

`settle()` makes a barrier survivable. It does not make a barrier *right*. The runtime's own
guidance is **"DEFAULT TO pipeline()"**; a barrier is correct in exactly three shapes:

1. you must dedup/merge across the **full** set before expensive downstream work,
2. you need an early exit when the total count is zero,
3. stage N's prompt references *"the other findings"*.

Anything else should be a `pipeline()`, where there is no barrier to deadlock in the first
place. See `skills/workflow-foundry/SKILL.md` L4.

## Red-proof

`tools/wf-timeout/test_h6_timeout.py` extracts the block above, runs it inside a Node `vm`
context configured like the real sandbox (`codeGeneration.strings = false`, `Date.now` and
`Math.random` shimmed to throw), and asserts **both** states:

- **known-broken control:** a bare `parallel()` over the same 5 thunks, one of which never
  resolves, does **not** settle inside the watchdog → the probe reports `hung: true`. If this
  ever reports `hung: false` the harness is broken and no green result below may be cited.
- **fixed:** `settle()` over the same thunks returns 5 index-aligned entries well inside
  2× the timeout, with exactly one `__endReason: 'timeout'` receipt and the other four
  results intact.