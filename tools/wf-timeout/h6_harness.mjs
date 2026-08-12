// h6_harness.mjs -- executable red-proof harness for the H6 timeout helper.
//
// Runs the helper source EXTRACTED FROM the skill template inside a Node `vm`
// context configured like the real Claude Code Workflow sandbox, and drives it
// through scenarios that include the KNOWN-BROKEN control. Prints one JSON
// object on stdout; exits 0 whenever the scenario ran (the verdict is in the
// JSON, not the exit code, so the caller can assert on a deliberate hang).
//
// Sandbox fidelity (measured, docs/workflow-sota/GROUNDING-NOTES.md §3):
//   * new vm.Script(..., {filename: 'workflow.js'})
//   * codeGeneration: { strings: false, wasm: false }   -> no eval / new Function
//   * setTimeout + clearTimeout injected from the host
//   * Date.now() / argless new Date() / Math.random() SHIMMED TO THROW
//   * no require, no import, no fs
//
// Usage:
//   node h6_harness.mjs --source <file.js> --scenario <name> [--timeout-ms N]
//                       [--watchdog-ms N] [--hang-index N] [--count N]

import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function parseArgv(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const tok = argv[i];
    if (tok.startsWith('--')) {
      const key = tok.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) {
        out[key] = true;
      } else {
        out[key] = next;
        i += 1;
      }
    }
  }
  return out;
}

const opts = parseArgv(process.argv.slice(2));
const SOURCE = String(opts.source);
const SCENARIO = String(opts.scenario);
const TIMEOUT_MS = Number(opts['timeout-ms'] ?? 150);
const WATCHDOG_MS = Number(opts['watchdog-ms'] ?? 1500);
const HANG_INDEX = Number(opts['hang-index'] ?? 2);
const COUNT = Number(opts['count'] ?? 5);
const WITH_TIMERS = opts['no-timers'] !== true;

// --- the fake workflow substrate -------------------------------------------
// `agent` stubs: index HANG_INDEX never resolves; index 4 throws when asked to.
const calls = { agent: 0, parallelBarriers: 0 };

function makeAgent(i, mode) {
  return function stubAgent() {
    calls.agent += 1;
    if (mode === 'hang' && i === HANG_INDEX) {
      return new Promise(() => {}); // never settles -- the synthetic hung agent
    }
    if (mode === 'throw' && i === HANG_INDEX) {
      return Promise.reject(new Error('synthetic agent failure'));
    }
    return Promise.resolve({ unit: i, verdict: 'ok' });
  };
}

// Mirrors the real parallel(): a BARRIER. Settles only when every thunk settles;
// a throwing thunk resolves to null. This is the shape that deadlocks.
function parallelStub(thunks) {
  calls.parallelBarriers += 1;
  return Promise.all(
    thunks.map((t) =>
      Promise.resolve()
        .then(t)
        .then(
          (v) => v,
          () => null,
        ),
    ),
  );
}

const logLines = [];

function buildContext() {
  const shimDate = function Date() {
    throw new Error('new Date() is banned in workflow JS');
  };
  shimDate.now = function now() {
    throw new Error('Date.now() is banned in workflow JS');
  };
  const shimMath = Object.create(Math);
  Object.defineProperty(shimMath, 'random', {
    value: function random() {
      throw new Error('Math.random() is banned in workflow JS');
    },
  });

  const sandbox = {
    __proto__: null,
    console: { log: () => {} },
    log: (msg) => {
      logLines.push(String(msg));
    },
    phase: () => {},
    budget: { total: 1000, spent: () => 0, remaining: () => 1000 },
    parallel: parallelStub,
    Date: shimDate,
    Math: shimMath,
  };
  if (WITH_TIMERS) {
    sandbox.setTimeout = setTimeout;
    sandbox.clearTimeout = clearTimeout;
  }
  return vm.createContext(sandbox, {
    codeGeneration: { strings: false, wasm: false },
  });
}

// --- drivers ----------------------------------------------------------------
// Each driver is appended to the helper source and evaluated as ONE script, the
// way an author pastes the block at the top of their own workflow.
const DRIVERS = {
  // FIXED state: the settled barrier survives one never-resolving unit.
  wrapped: `
    (async () => {
      const thunks = __THUNKS__;
      const results = await settle(thunks, ${TIMEOUT_MS}, __LABELS__);
      return {
        settled: true,
        length: results.length,
        endReasons: results.map((r) => (r && r.__h6 ? r.__endReason : null)),
        survivors: h6Survivors(results).map((r) => r.unit),
        drops: h6Drops(results).map((r) => ({ label: r.label, why: r.__endReason })),
      };
    })()`,

  // KNOWN-BROKEN control: the bare barrier. Must NOT settle.
  unwrapped: `
    (async () => {
      const results = await parallel(__THUNKS__);
      return { settled: true, length: results.length };
    })()`,

  // Runtime-drift guard: no timers injected -> plain await, typed 'threw' receipt.
  degraded: `
    (async () => {
      const thunks = __THUNKS__;
      const results = await settle(thunks, ${TIMEOUT_MS}, __LABELS__);
      return {
        settled: true,
        length: results.length,
        endReasons: results.map((r) => (r && r.__h6 ? r.__endReason : null)),
      };
    })()`,

  // Proves the sandbox shims are live: the helper must not touch them.
  'shims-fire': `
    (async () => {
      const seen = [];
      try { Date.now(); } catch (e) { seen.push('Date.now'); }
      try { new Date(); } catch (e) { seen.push('new Date'); }
      try { Math.random(); } catch (e) { seen.push('Math.random'); }
      return { settled: true, shimsThatThrew: seen };
    })()`,
};

const MODE = SCENARIO === 'degraded' ? 'throw' : 'hang';
const thunkSrc =
  '[' +
  Array.from({ length: COUNT }, (_v, i) => `__AGENT_${i}__`).join(', ') +
  ']';
const labelSrc =
  '[' + Array.from({ length: COUNT }, (_v, i) => `'u${i}'`).join(', ') + ']';

function main() {
  const helper = readFileSync(SOURCE, 'utf8');
  const driver = DRIVERS[SCENARIO];
  if (driver === undefined) {
    process.stdout.write(
      JSON.stringify({ error: `unknown scenario: ${SCENARIO}` }) + '\n',
    );
    return 2;
  }
  const ctx = buildContext();
  for (let i = 0; i < COUNT; i += 1) {
    ctx[`__AGENT_${i}__`] = makeAgent(i, MODE);
  }
  const body = driver
    .replaceAll('__THUNKS__', thunkSrc)
    .replaceAll('__LABELS__', labelSrc);

  const started = process.hrtime.bigint();
  let promise;
  try {
    promise = new vm.Script(helper + '\n' + body, {
      filename: 'workflow.js',
    }).runInContext(ctx);
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ scenario: SCENARIO, syntaxError: String(err) }) + '\n',
    );
    return 3;
  }

  // NOTE: the watchdog timer is deliberately NOT unref()'d. A never-resolving
  // `new Promise(() => {})` does not hold the Node event loop open, so with an
  // unref'd watchdog the process exited immediately and printed NOTHING -- the
  // harness looked silent in the broken state, which is precisely the
  // "probe silent in both states" failure it exists to prevent. Measured.
  let watchdogTimer = null;
  const watchdog = new Promise((resolve) => {
    watchdogTimer = setTimeout(() => resolve({ settled: false }), WATCHDOG_MS);
  });

  return Promise.race([Promise.resolve(promise), watchdog]).then(
    (res) => {
      const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
      if (watchdogTimer !== null) clearTimeout(watchdogTimer);
      process.stdout.write(
        JSON.stringify(
          {
            scenario: SCENARIO,
            hung: res.settled !== true,
            elapsedMs,
            timeoutMs: TIMEOUT_MS,
            watchdogMs: WATCHDOG_MS,
            agentCalls: calls.agent,
            parallelBarriers: calls.parallelBarriers,
            logLines,
            ...res,
          },
          null,
          2,
        ) + '\n',
      );
      process.exitCode = 0;
    },
    (err) => {
      if (watchdogTimer !== null) clearTimeout(watchdogTimer);
      process.stdout.write(
        JSON.stringify({ scenario: SCENARIO, threw: String(err) }, null, 2) + '\n',
      );
      process.exitCode = 4;
    },
  );
}

const rc = main();
if (typeof rc === 'number') process.exit(rc);
