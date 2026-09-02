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
//   * LOSSLESS INTEGERS (TST-0056). A JS number is an IEEE-754 double: any integer token above
//     Number.MAX_SAFE_INTEGER (2^53-1 = 9007199254740991) is silently rounded by JSON.parse, so a
//     uint64 work-unit id, an epoch-nanosecond timestamp (above 2^53 since 2001) or an oversize
//     byte_count read back as a DIFFERENT number with no error. readJson therefore goes through
//     parseLossless: a string-aware tokenizer (rewriteUnsafeIntegerTokens) quotes every bare
//     integer token that cannot be held exactly, and only then is JSON.parse run. Safe integers
//     stay numbers; wide ones arrive as decimal strings, which is also how the ledger record
//     schema (handled-ledger.schema.json) encodes id / timestamp_ns / byte_count, with seq the
//     one integer field and bounded to MAX_SAFE_INTEGER.
// No behaviour change to the ledger semantics themselves.

import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';

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

// ---------------------------------------------------------------------------------------------
// Lossless integer parsing
// ---------------------------------------------------------------------------------------------

/** Decimal form of Number.MAX_SAFE_INTEGER; the widest integer a JS number holds exactly. */
export const MAX_SAFE_INTEGER_DECIMAL = String(Number.MAX_SAFE_INTEGER); // "9007199254740991"

/** Ledger record fields that may exceed 2^53-1 and are therefore carried as decimal strings. */
export const WIDE_LEDGER_FIELDS = Object.freeze(['id', 'timestamp_ns', 'byte_count']);

const DECIMAL_RE = /^-?(0|[1-9][0-9]*)$/;

/**
 * True when `token` is a bare JSON integer token whose magnitude exceeds Number.MAX_SAFE_INTEGER.
 * Decided on the DIGITS, never on a parsed number (parsing is exactly the lossy step): more than
 * 16 digits is always unsafe, 16 digits compares lexicographically against 9007199254740991.
 */
export function isUnsafeIntegerToken(token) {
  if (typeof token !== 'string' || !DECIMAL_RE.test(token)) return false;
  const digits = token[0] === '-' ? token.slice(1) : token;
  if (digits.length !== MAX_SAFE_INTEGER_DECIMAL.length) {
    return digits.length > MAX_SAFE_INTEGER_DECIMAL.length;
  }
  return digits > MAX_SAFE_INTEGER_DECIMAL;
}

function isDigit(ch) {
  return ch >= '0' && ch <= '9';
}

// Scan one JSON number token starting at `i` (which holds '-' or a digit). Returns the index just
// past the token and whether it is a pure integer (no fraction, no exponent).
function scanNumber(text, i) {
  let j = i;
  if (text[j] === '-') j++;
  while (j < text.length && isDigit(text[j])) j++;
  let integer = true;
  if (text[j] === '.') {
    integer = false;
    j++;
    while (j < text.length && isDigit(text[j])) j++;
  }
  if (text[j] === 'e' || text[j] === 'E') {
    integer = false;
    j++;
    if (text[j] === '+' || text[j] === '-') j++;
    while (j < text.length && isDigit(text[j])) j++;
  }
  return { end: j, integer };
}

// Index just past the string literal that opens at `i` (text[i] === '"'), honouring escapes.
function skipString(text, i) {
  let j = i + 1;
  while (j < text.length) {
    const ch = text[j];
    if (ch === '\\') {
      j += 2;
      continue;
    }
    j++;
    if (ch === '"') break;
  }
  return Math.min(j, text.length);
}

/**
 * Rewrite every bare integer token that JSON.parse would round into a quoted decimal string.
 * String literals are skipped by a real tokenizer (not a regex), so digits inside strings and
 * keys are never touched; fractions, exponents and safe integers pass through byte-for-byte.
 * The output is still valid JSON, so JSON.parse on it is lossless for the wide fields.
 */
export function rewriteUnsafeIntegerTokens(text) {
  const src = String(text);
  let out = '';
  let i = 0;
  let last = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '"') {
      i = skipString(src, i);
      continue;
    }
    if (ch === '-' || isDigit(ch)) {
      const { end, integer } = scanNumber(src, i);
      const token = src.slice(i, end);
      if (integer && isUnsafeIntegerToken(token)) {
        out += src.slice(last, i) + '"' + token + '"';
        last = end;
      }
      i = end;
      continue;
    }
    i++;
  }
  return out + src.slice(last);
}

/**
 * JSON.parse that cannot round: wide integer tokens come back as decimal strings, everything
 * else exactly as JSON.parse would return it. Throws the ordinary SyntaxError on invalid JSON.
 */
export function parseLossless(text, reviver) {
  return JSON.parse(rewriteUnsafeIntegerTokens(text), reviver);
}

/**
 * Normalise one ledger record to the schema encoding: wide fields as decimal strings, seq a
 * safe non-negative integer. Wide fields given as safe JS numbers are converted (they are still
 * exact); wide fields given as unsafe numbers are refused, because the precision is already
 * gone by the time this code sees them - that is the whole reason parseLossless exists.
 */
export function normalizeLedgerRecord(record) {
  if (!record || typeof record !== 'object' || Array.isArray(record)) {
    throw new TypeError('ledger record must be an object');
  }
  const out = { ...record };
  for (const field of WIDE_LEDGER_FIELDS) {
    if (!(field in out) || out[field] === undefined) continue;
    const value = out[field];
    if (typeof value === 'bigint') {
      if (value < 0n) throw new RangeError(`${field} must be non-negative`);
      out[field] = value.toString();
    } else if (typeof value === 'number') {
      if (!Number.isSafeInteger(value) || value < 0) {
        throw new RangeError(`${field}=${value} is not an exact non-negative safe integer; pass it as a decimal string`);
      }
      out[field] = String(value);
    } else if (typeof value === 'string') {
      if (!/^(0|[1-9][0-9]*)$/.test(value)) {
        throw new RangeError(`${field}=${JSON.stringify(value)} is not a decimal integer string`);
      }
    } else {
      throw new TypeError(`${field} must be a decimal string, got ${typeof value}`);
    }
  }
  if ('seq' in out && out.seq !== undefined) {
    const seq = typeof out.seq === 'string' && /^(0|[1-9][0-9]*)$/.test(out.seq) ? Number(out.seq) : out.seq;
    if (!Number.isSafeInteger(seq) || seq < 0) {
      throw new RangeError(`seq=${String(out.seq)} must be an integer in [0, ${MAX_SAFE_INTEGER_DECIMAL}]`);
    }
    out.seq = seq;
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Atomic JSON files and the handled ledger
// ---------------------------------------------------------------------------------------------

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

/** Read a JSON file losslessly (see parseLossless); any read or parse failure yields `fallback`. */
export async function readJson(filePath, fallback) {
  try {
    return parseLossless(await fs.readFile(filePath, 'utf8'));
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

// ---------------------------------------------------------------------------------------------
// CLI: `node handled-ledger.mjs <roundtrip|naive|rewrite|normalize> < document.json`
//   roundtrip  parseLossless then JSON.stringify - wide integers survive as decimal strings
//   naive      JSON.parse then JSON.stringify - the negative control that shows the rounding
//   rewrite    print the rewritten JSON text without parsing it
//   normalize  parseLossless, then normalizeLedgerRecord (exit 2 on a malformed record)
// ---------------------------------------------------------------------------------------------

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

export async function runCli(argv, input) {
  const cmd = argv[0];
  const text = input === undefined ? await readStdin() : String(input);
  switch (cmd) {
    case 'roundtrip':
      return { code: 0, out: JSON.stringify(parseLossless(text)) };
    case 'naive':
      return { code: 0, out: JSON.stringify(JSON.parse(text)) };
    case 'rewrite':
      return { code: 0, out: rewriteUnsafeIntegerTokens(text) };
    case 'normalize':
      try {
        return { code: 0, out: JSON.stringify(normalizeLedgerRecord(parseLossless(text))) };
      } catch (err) {
        return { code: 2, out: '', err: `${err?.name || 'Error'}: ${err?.message || err}` };
      }
    default:
      return {
        code: 64,
        out: '',
        err: `usage: node handled-ledger.mjs <roundtrip|naive|rewrite|normalize> < document.json (got ${JSON.stringify(cmd ?? null)})`
      };
  }
}

const invokedAsScript =
  typeof process !== 'undefined' &&
  process.argv?.[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedAsScript) {
  runCli(process.argv.slice(2)).then(
    (res) => {
      if (res.out) process.stdout.write(`${res.out}\n`);
      if (res.err) process.stderr.write(`${res.err}\n`);
      process.exitCode = res.code;
    },
    (err) => {
      process.stderr.write(`${err?.name || 'Error'}: ${err?.message || err}\n`);
      process.exitCode = 1;
    }
  );
}
