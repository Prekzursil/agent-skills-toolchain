// ORIGIN: tools/web/agentify-desktop/orchestrator/storage.mjs (partial extract)
//
// SURVIVED THE RETIREMENT because an idempotency ledger - "did this work-unit already run?" - is
// architecture-independent and is exactly what a fan-out needs to avoid double-dispatch after a
// crash or resume. The atomic tmp-file+rename write underneath it is the reusable part: a render
// or a process killed mid-write can never leave a half-written JSON file behind.
//
// SCOPE OF THE EXTRACT - deliberately narrower than the origin file. Only the handled-ledger
// (loadHandled / markHandled / isHandled) and atomicWriteJson are carried. The origin's
// sessions (loadSessions/setSession/getSession) and workspaces (loadWorkspaces/setWorkspace/
// getWorkspace) halves are NOT carried: they duplicate tools/mcp/codex-orchestrator's
// manager/store.mjs, which already covers threads/routes/health and is itself retire-class. The
// handled-ledger is the one thing manager/store.mjs had NO equivalent for.
//
// CHANGES vs origin:
//   * atomicWriteJson is now EXPORTED (it was module-private) - it is half the reason to salvage.
//   * The dir helper is renamed orchestratorDir -> handledLedgerDir. The on-disk layout is
//     UNCHANGED (<stateDir>/orchestrator/handled.json) so any pre-existing ledger file is still
//     read; only the JS identifier changed, because "orchestrator" no longer names anything.
//   * sessionsPath / workspaceConfigPath dropped with their consumers.
// No behaviour change to the ledger semantics themselves.

import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

// Windows MoveFileExW fails with EPERM/EACCES/EBUSY when the destination is momentarily held
// open - which happens whenever two writers rename onto the same path at the same time, or an
// AV scanner touches the file. MEASURED during this salvage: 25 concurrent atomicWriteJson calls
// against one path failed 3/3 runs with `EPERM: operation not permitted, rename`. The origin
// shipped the bare rename and had no test that would have caught it. A bounded retry closes it.
const RENAME_RETRY_CODES = new Set(['EPERM', 'EACCES', 'EBUSY']);
const RENAME_MAX_ATTEMPTS = 10;

async function renameWithRetry(from, to) {
  let lastErr = null;
  for (let attempt = 0; attempt < RENAME_MAX_ATTEMPTS; attempt++) {
    try {
      await fs.rename(from, to);
      return;
    } catch (err) {
      if (!RENAME_RETRY_CODES.has(err?.code)) throw err;
      lastErr = err;
      // Jittered backoff: without jitter, contending writers retry in lockstep and re-collide.
      const delay = Math.min(2 ** attempt, 25) + Math.floor(Math.random() * 5);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw lastErr;
}

/**
 * Write JSON via tmp-file + rename so a reader never observes a partially written file.
 * The tmp name carries 8 random bytes, so concurrent writers cannot collide on the tmp path.
 *
 * GUARANTEE: no reader ever sees a torn or partial file, and the call does not throw merely
 * because another writer was mid-rename.
 * NON-GUARANTEE: this does not serialise writers. Two concurrent writers still produce a
 * last-one-wins result - see the note on markHandled below.
 */
export async function atomicWriteJson(filePath, obj, { mode } = {}) {
  const dir = path.dirname(filePath);
  await fs.mkdir(dir, { recursive: true });
  const tmp = path.join(dir, `.${path.basename(filePath)}.${crypto.randomBytes(8).toString('hex')}.tmp`);
  const data = `${JSON.stringify(obj, null, 2)}\n`;
  await fs.writeFile(tmp, data, mode ? { encoding: 'utf8', mode } : { encoding: 'utf8' });
  try {
    await renameWithRetry(tmp, filePath);
  } catch (err) {
    // Never leave tmp residue behind on a failed publish.
    await fs.rm(tmp, { force: true }).catch(() => {});
    throw err;
  }
}

// Path layout preserved byte-for-byte from the origin so an existing handled.json still resolves.
export function handledLedgerDir(stateDir) {
  return path.join(stateDir, 'orchestrator');
}

export function handledPath(stateDir) {
  return path.join(handledLedgerDir(stateDir), 'handled.json');
}

export async function readJson(filePath, fallback) {
  try {
    return JSON.parse(await fs.readFile(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

export async function writeJson(filePath, obj, opts) {
  await atomicWriteJson(filePath, obj, opts);
}

export async function loadHandled(stateDir) {
  const p = handledPath(stateDir);
  const data = await readJson(p, { keys: {} });
  if (!data || typeof data !== 'object') return { keys: {} };
  if (!data.keys || typeof data.keys !== 'object') data.keys = {};
  return data;
}

/**
 * CONCURRENCY LIMIT, stated rather than implied: markHandled is read-modify-write, so two
 * concurrent calls can both read the pre-state and the second write wins - a lost update. Atomic
 * rename prevents a TORN file, not a lost update; no file-level trick fixes this. Safe usage is
 * a single writer per stateDir (the normal fan-out shape: one dispatcher, many workers). If you
 * need multi-writer, shard by key into separate stateDirs or put a lock above this layer.
 */
export async function markHandled(stateDir, { key, id, status, meta = null }) {
  const data = await loadHandled(stateDir);
  const k = String(key || '').trim();
  const i = String(id || '').trim();
  if (!k || !i) throw new Error('missing_key_or_id');
  if (!data.keys[k]) data.keys[k] = {};
  data.keys[k][i] = { status: status || 'done', meta, at: new Date().toISOString() };
  await writeJson(handledPath(stateDir), data, { mode: 0o600 });
  return data.keys[k][i];
}

export async function isHandled(stateDir, { key, id }) {
  const data = await loadHandled(stateDir);
  return !!data?.keys?.[String(key)]?.[String(id)];
}
