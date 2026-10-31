#!/usr/bin/env node
// TST-0168 live-target refute driver (shard17-w4).
//
// History: the archived handled-ledger PROXY was REFUTED at 3/20 race cuts
// (receipt written BEFORE the ledger row => a suspend between the two writes
// double-executes the child on resume). The live B07 target
// tools/lib/handled-ledger.mjs now exists. This driver re-runs the refute
// against the LIVE ledger using the crash-window-free discipline it enables:
// the child receipt is embedded as the markHandled `meta`, so one atomic
// write publishes both. Any kill point leaves a resumable state with
// exactly-once semantics.
//
// Modes:
//   dispatcher --state-dir D [--cut K] [--kill-after-ms MS]
//       Walk children-00..23; per child: if handled -> skip, else "execute"
//       and markHandled(key, id, meta=receipt). --cut K hard-exits(137) after
//       K completed children; --kill-after-ms self-KILLs after MS ms (chaos).
//   verify --state-dir D
//       Reads the live ledger from disk and reports the exactly-once state.
import { markHandled, loadHandled, isHandled } from '../../../../tools/lib/handled-ledger.mjs';

const N_CHILDREN = 24;
const KEY = 'fanout';
const args = process.argv.slice(2);
function arg(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
}
const mode = arg('--mode');
const stateDir = arg('--state-dir');

const childId = (i) => `child-${String(i).padStart(2, '0')}`;

if (mode === 'dispatcher') {
  const cut = arg('--cut') !== null ? parseInt(arg('--cut'), 10) : null;
  const killAfter = arg('--kill-after-ms') !== null ? parseInt(arg('--kill-after-ms'), 10) : null;
  if (killAfter !== null) {
    setTimeout(() => { try { process.kill(process.pid, 'SIGKILL'); } catch { process.exit(137); } }, killAfter);
  }
  const mutant = args.includes('--mutant-ignore-handled');
  const prior = await loadHandled(stateDir);
  const priorRuns = (id) => prior?.keys?.[KEY]?.[id]?.meta?.runs ?? 0;
  let completed = 0;
  for (let i = 0; i < N_CHILDREN; i++) {
    if (cut !== null && completed >= cut) process.exit(137);
    const id = childId(i);
    if (!mutant && (await isHandled(stateDir, { key: KEY, id }))) continue; // resume skip
    // The "work": the receipt IS the ledger meta - one atomic write, no window.
    // Mutant: ignores handled state and INCREMENTS runs, so a double execution
    // becomes visible to verify (the honest writer never rewrites a row).
    await markHandled(stateDir, {
      key: KEY,
      id,
      status: 'done',
      meta: { child: id, runs: mutant ? priorRuns(id) + 1 : 1, executed_at: new Date().toISOString() },
    });
    completed++;
  }
  process.exit(0);
}

if (mode === 'verify') {
  const ledger = await loadHandled(stateDir);
  const rows = (ledger.keys && ledger.keys[KEY]) || {};
  const ids = Object.keys(rows).sort();
  const expected = Array.from({ length: N_CHILDREN }, (_, i) => childId(i));
  const duplicates = ids.filter((id) => (rows[id]?.meta?.runs ?? 0) !== 1);
  const missing = expected.filter((id) => !ids.includes(id));
  const orphans = ids.filter((id) => !expected.includes(id));
  process.stdout.write(JSON.stringify({
    marked_count: ids.length,
    exactly_once: missing.length === 0 && orphans.length === 0 && duplicates.length === 0,
    missing,
    orphans,
    duplicates,
  }, null, 1) + '\n');
  process.exit(0);
}

process.stderr.write('usage: --mode dispatcher|verify --state-dir D [--cut K] [--kill-after-ms MS]\n');
process.exit(2);
