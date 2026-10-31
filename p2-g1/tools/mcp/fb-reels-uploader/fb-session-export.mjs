#!/usr/bin/env node
/**
 * fb-session-export — export the owner's LIVE authenticated Facebook cookies to a
 * `cookies.json` in the exact shape `fbchat_muqit` (the fb-messenger backend)
 * expects, so the Messenger / whoami / E2EE-DM tools authenticate again.
 *
 * This is the FACEBOOK analogue of Instagram's login-once + session.json model:
 * a persistent Playwright profile holds the FB session; the owner logs in ONCE
 * (in the window this opens — no password is ever typed by this script), and the
 * session is then reused headlessly. Re-run this whenever the session lapses;
 * that makes the auth SELF-HEALING instead of rotting silently for weeks.
 *
 * By default it reuses the SAME persistent profile as fb-reels-upload.mjs, so a
 * single Facebook login serves Reel posting, cookie refresh, and Messenger.
 *
 * Usage:
 *   node fb-session-export.mjs --out <cookies.json> [options]
 *
 * Options:
 *   --out PATH       Where to write cookies.json (REQUIRED; the fb backend's
 *                    FB_COOKIES_PATH). Written atomically.
 *   --profile DIR    Persistent browser profile dir. Default: the shared
 *                    fb-reels `.profile` (one FB login for reels + cookies).
 *   --headless       Run without a window. Only works once already logged in;
 *                    if the session lapsed it FAILS fast telling you to re-run
 *                    windowed to log in.
 *   --timeout SEC    Max seconds to wait for a human login (default 600).
 *   --help
 *
 * SECURITY: this script NEVER prints, logs, or echoes a cookie value or token.
 * It reports cookie NAMES and counts only. `cookies.json` is radioactive: it is
 * gitignored and must never be committed.
 *
 * Output: a single terminal line `SUCCESS:fb-session <n> cookies -> <path>` or
 * `FAILED:fb-session <reason>`, plus progress on stderr.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';
import { dismissNagging, DEFAULT_PROFILE } from './fb-reels-upload.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HOME_URL = 'https://www.facebook.com/';

function parseArgs(argv) {
  const o = { out: null, profile: DEFAULT_PROFILE, headless: false, timeout: 600, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') o.help = true;
    else if (a === '--out') o.out = argv[++i];
    else if (a === '--profile') o.profile = argv[++i];
    else if (a === '--headless') o.headless = true;
    else if (a === '--timeout') o.timeout = parseInt(argv[++i], 10) || 600;
    else { console.error('Unknown option:', a); process.exit(2); }
  }
  return o;
}

const log = (...a) => console.error(new Date().toISOString().slice(11, 19), ...a);

/** True once the context holds a facebook.com `c_user` cookie with a value —
 *  the definitive "this browser is logged in" signal (no DOM scraping). */
async function isLoggedIn(context) {
  const cookies = await context.cookies(HOME_URL);
  return cookies.some((c) => c.name === 'c_user' && c.value && c.value.length > 0);
}

/** Map a Playwright cookie to the fbchat_muqit 7-key element shape. */
function toShape(c, nowIso) {
  const host = (c.domain || 'facebook.com').replace(/^\./, '');
  return {
    creation: nowIso,
    domain: host,
    hostOnly: !(c.domain || '').startsWith('.'),
    key: c.name,
    lastAccessed: nowIso,
    path: c.path || '/',
    value: c.value,
  };
}

/** Atomic write: tmp file + rename, restrictive perms. */
function writeAtomic(outPath, data) {
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const tmp = `${outPath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), { mode: 0o600 });
  fs.renameSync(tmp, outPath);
  try { fs.chmodSync(outPath, 0o600); } catch { /* Windows honours only the RO bit */ }
}

export async function exportSession(opts) {
  const { out, profile, headless, timeout } = opts;
  if (!out) throw new Error('--out <cookies.json path> is required');

  const { chromium } = await import('playwright').catch(() => {
    throw new Error(`Playwright not installed. Run: cd "${__dirname}" && npm install`);
  });
  fs.mkdirSync(profile, { recursive: true });
  const ctx = await chromium.launchPersistentContext(profile, {
    headless,
    viewport: { width: 1366, height: 900 },
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  try {
    await page.goto(HOME_URL, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await dismissNagging(page);

    if (!(await isLoggedIn(ctx))) {
      if (headless) {
        throw new Error(
          'not logged in and --headless set. Re-run WITHOUT --headless and log ' +
          'into Facebook once in the window that opens.',
        );
      }
      log('Log into Facebook in the open window. Waiting up to ' + timeout + 's...');
      const start = Date.now();
      while (Date.now() - start < timeout * 1000) {
        await sleep(3000);
        await dismissNagging(page).catch(() => {});
        if (await isLoggedIn(ctx)) break;
      }
      if (!(await isLoggedIn(ctx))) throw new Error('login not detected within timeout');
    }

    // Pull cookies for facebook.com (+ messenger.com, which the backend also uses).
    const raw = await ctx.cookies(['https://www.facebook.com', 'https://www.messenger.com']);
    const fb = raw.filter((c) => /(^|\.)facebook\.com$/.test(c.domain || ''));
    const nowIso = new Date().toISOString();
    const shaped = fb.map((c) => toShape(c, nowIso));

    const names = new Set(shaped.map((c) => c.key));
    // The auth triad fbchat_muqit needs to load a valid session.
    for (const need of ['c_user', 'xs']) {
      if (!names.has(need)) throw new Error(`exported jar is missing the '${need}' cookie`);
    }
    writeAtomic(out, shaped);
    return { ok: true, count: shaped.length, names: [...names].sort() };
  } finally {
    await ctx.close();
  }
}

const HELP = `fb-session-export — export live Facebook cookies to a cookies.json fbchat_muqit can load.

  node fb-session-export.mjs --out <path> [--profile DIR] [--headless] [--timeout SEC]

Opens a browser; log into Facebook ONCE (no password is typed by this script).
Reuses the shared fb-reels .profile by default, so one login serves reels + cookies.
Re-run whenever the session lapses — the auth is then self-healing.`;

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help || !o.out) { console.log(HELP); process.exit(o.help ? 0 : 2); }
  try {
    const r = await exportSession(o);
    log(`exported cookie names: ${r.names.join(', ')}`);
    console.log(`SUCCESS:fb-session ${r.count} cookies -> ${o.out}`);
    process.exit(0);
  } catch (e) {
    console.log(`FAILED:fb-session ${e.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.log(`FAILED:fb-session ${e && e.message}`); process.exit(1); });
}
