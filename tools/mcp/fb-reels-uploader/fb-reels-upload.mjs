#!/usr/bin/env node
/**
 * fb-reels-upload — upload local vertical videos to Facebook as Reels, IN ORDER,
 * one per post (not bundled). Built for the Opus shorts batch, reusable generally.
 *
 * Usage:
 *   node fb-reels-upload.mjs <folder> [options]
 *   node fb-reels-upload.mjs "C:\\Users\\Prekzursil\\Downloads\\razvan_gandu" --start 2
 *
 * Options:
 *   --start N        1-based index of the first clip to upload (default 1).
 *   --limit M        Upload at most M clips this run (default: all remaining).
 *   --delay-sec S    Extra pause between posts, to avoid spam flags (default 20).
 *   --profile DIR    Browser profile dir (stores the FB login). Default <tool>/.profile
 *   --glob EXT       File extension to pick up (default mp4).
 *   --audience X     public | friends | onlyme  (default public; only changes if not already set)
 *   --headless       Run without a window (only after you've logged in once).
 *   --help
 *
 * Order guarantee: files are sorted by name (01_, 02_, ... → 1,2,3,...) and uploaded
 * strictly sequentially; it will NOT start clip N+1 until clip N is confirmed posted.
 * A state file (<folder>/.fb-posted.json) records finished files so re-runs resume
 * without duplicating or reordering.
 *
 * AUTH: Facebook can't be posted to a personal profile via any official API, so this
 * drives a real browser. First run opens a window — log into Facebook once; the session
 * is saved in the profile dir for later runs.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CREATE_URL = 'https://www.facebook.com/reels/create/';
export const DEFAULT_PROFILE = path.join(__dirname, '.profile');

function parseArgs(argv) {
  const o = { folder: null, start: 1, limit: Infinity, delaySec: 20, profile: path.join(__dirname, '.profile'),
              ext: 'mp4', audience: 'public', headless: false, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') o.help = true;
    else if (a === '--start') o.start = parseInt(argv[++i], 10) || 1;
    else if (a === '--limit') o.limit = parseInt(argv[++i], 10) || Infinity;
    else if (a === '--delay-sec') o.delaySec = parseInt(argv[++i], 10) || 0;
    else if (a === '--profile') o.profile = argv[++i];
    else if (a === '--glob') o.ext = (argv[++i] || 'mp4').replace(/^\./, '');
    else if (a === '--audience') o.audience = (argv[++i] || 'public').toLowerCase();
    else if (a === '--headless') o.headless = true;
    else if (a.startsWith('--')) { console.error('Unknown option:', a); process.exit(2); }
    else o.folder = a;
  }
  return o;
}

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

export async function dismissNagging(page) {
  for (const name of ['Not now', 'Not Now', 'Cancel']) {
    const b = page.getByRole('button', { name, exact: true });
    if (await b.first().isVisible().catch(() => false)) await b.first().click().catch(() => {});
  }
}

// Wait until the Create-reel composer is reachable (i.e. we're logged in).
// IMPORTANT: do NOT re-navigate while the user is on a login/checkpoint page, or
// the reload would wipe their half-typed credentials. Navigate once; only re-load
// the composer after they've left the auth flow.
export async function waitForLogin(page, timeoutMs = 600000) {
  const start = Date.now();
  let prompted = false;
  let navedAfterAuth = true; // we'll goto once below
  await page.goto(CREATE_URL, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await dismissNagging(page);
  while (Date.now() - start < timeoutMs) {
    const add = page.getByRole('button', { name: /Add Video/i });
    if (await add.first().isVisible().catch(() => false)) return true;
    const url = page.url();
    const onAuth = /login|checkpoint|two_factor|two_step|recover|auth|consent|privacy/i.test(url);
    if (onAuth) {
      if (!prompted) { log('🔐 Please log into Facebook in the open window. Waiting (up to 10 min)...'); prompted = true; }
      navedAfterAuth = false; // once they leave auth, navigate to the composer once
    } else if (!navedAfterAuth) {
      // logged in but landed elsewhere (feed/home) — open the composer a single time
      await page.goto(CREATE_URL, { waitUntil: 'domcontentloaded' }).catch(() => {});
      await dismissNagging(page);
      navedAfterAuth = true;
    }
    await sleep(3000);
  }
  return false;
}

export async function setAudience(page, audience) {
  if (audience === 'public') return; // Reels default to Public already
  // Open the audience selector (button labelled with current audience, e.g. "Public ...")
  const sel = page.getByRole('button', { name: /^(Public|Friends|Only me)/i }).first();
  if (!(await sel.isVisible().catch(() => false))) return;
  await sel.click().catch(() => {});
  await sleep(800);
  const want = audience === 'friends' ? /^Friends/i : /^Only me/i;
  const opt = page.getByRole('radio', { name: want }).first();
  if (await opt.isVisible().catch(() => false)) { await opt.click().catch(() => {}); await sleep(400); }
  // confirm the audience dialog if there's a Done button
  const done = page.getByRole('button', { name: /^(Done|Save)$/i }).first();
  if (await done.isVisible().catch(() => false)) await done.click().catch(() => {});
  await sleep(600);
}

export async function uploadOneReel(page, filePath, audience) {
  await page.goto(CREATE_URL, { waitUntil: 'domcontentloaded' });
  await dismissNagging(page);

  // 1) Add video -> file chooser
  const addBtn = page.getByRole('button', { name: /Add Video/i }).first();
  await addBtn.waitFor({ state: 'visible', timeout: 30000 });
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    addBtn.click(),
  ]);
  await chooser.setFiles(filePath);

  // 2) wait until processed: the "Next" button becomes available
  const next = page.getByRole('button', { name: 'Next', exact: true });
  await next.waitFor({ state: 'visible', timeout: 180000 });
  await sleep(2000);
  await next.click();                         // -> edit step
  await sleep(2500);

  // second Next -> settings/audience step
  await next.waitFor({ state: 'visible', timeout: 60000 });
  await next.click();
  await sleep(2500);

  // 3) audience (default Public)
  await setAudience(page, audience);

  // 4) publish
  const post = page.getByRole('button', { name: 'Post', exact: true });
  await post.waitFor({ state: 'visible', timeout: 60000 });
  await post.click();

  // 5) confirm: the Post button should disappear (dialog closes) within timeout
  await post.waitFor({ state: 'hidden', timeout: 120000 }).catch(() => {});
  await sleep(3000);
  // sanity: if a Post button is still sitting there, treat as not-confirmed
  if (await post.isVisible().catch(() => false)) {
    throw new Error('Post button still visible after publish — upload not confirmed');
  }
}

const HELP = `fb-reels-upload — upload local vertical videos to Facebook as Reels, in order.

  node fb-reels-upload.mjs <folder> [--start N] [--limit M] [--delay-sec S] [--headless]

First run opens a browser — log into Facebook once (session is then remembered).
Uploads *.mp4 sorted by filename, strictly in order, one Reel per post, Public, no caption.`;

/**
 * Reusable batch driver shared by the CLI and the MCP wrapper. Library-safe:
 * it never calls process.exit and returns a structured result. Order guarantee
 * is preserved — it stops at the first failure rather than skipping ahead.
 *
 * @param {{folder?:string, files?:string[], start?:number, limit?:number,
 *   delaySec?:number, profile?:string, audience?:string, headless?:boolean,
 *   ext?:string}} opts
 * @param {(msg:string)=>void} [emit] progress callback
 * @returns {Promise<{ok:number, done:number, posted:string[], failed:string[], total:number}>}
 */
export async function runBatch(opts, emit = () => {}) {
  const {
    folder, files, start = 1, limit = Infinity, delaySec = 20,
    profile = DEFAULT_PROFILE, audience = 'public', headless = false, ext = 'mp4',
  } = opts || {};

  let list;
  if (Array.isArray(files) && files.length) {
    list = files.map((f) => ({ name: path.basename(f), full: path.resolve(f) }));
  } else {
    if (!folder) throw new Error('runBatch requires a folder or an explicit files[] list');
    if (!fs.existsSync(folder)) throw new Error(`Folder not found: ${folder}`);
    list = fs.readdirSync(folder)
      .filter((f) => f.toLowerCase().endsWith('.' + ext))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
      .map((name) => ({ name, full: path.join(folder, name) }));
  }
  if (!list.length) throw new Error(`No .${ext} files to upload`);

  const stateDir = folder || path.dirname(list[0].full);
  const stateFile = path.join(stateDir, '.fb-posted.json');
  let state = { posted: [] };
  if (fs.existsSync(stateFile)) { try { state = JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch {} }
  const posted = new Set(state.posted);

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

  let ok = 0; let done = 0; const failed = [];
  try {
    if (!(await waitForLogin(page))) throw new Error('Not logged into Facebook in time.');
    emit('Logged in. Starting uploads.');
    for (let i = 0; i < list.length; i++) {
      const n = i + 1;
      const { name, full } = list[i];
      if (n < start) continue;
      if (posted.has(name)) { emit(`SKIP  ${n}/${list.length} ${name} (already posted)`); continue; }
      if (done >= limit) { emit(`Reached limit ${limit}; stopping.`); break; }
      emit(`POST  ${n}/${list.length} ${name} ...`);
      try {
        await uploadOneReel(page, full, audience);
        posted.add(name);
        state.posted = [...posted];
        fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
        ok++; done++;
        emit(`OK    ${n}/${list.length} ${name}  (posted ${ok})`);
      } catch (e) {
        failed.push(name);
        emit(`FAIL  ${n}/${list.length} ${name}: ${e.message}`);
        break; // order guarantee: do not skip ahead past a failure
      }
      if (delaySec && done < limit) { emit(`(pausing ${delaySec}s before next)`); await sleep(delaySec * 1000); }
    }
  } finally {
    await ctx.close();
  }
  return { ok, done, posted: [...posted], failed, total: list.length };
}

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help || !o.folder) { console.log(HELP); process.exit(o.help ? 0 : 2); }
  try {
    const r = await runBatch(o, log);
    log(`\nDONE posted=${r.ok} failed=[${r.failed}]`);
    process.exit(r.failed.length ? 1 : 0);
  } catch (e) {
    console.error('Fatal:', e.message);
    process.exit(3);
  }
}

// Only launch the browser when run directly, not when imported by the MCP wrapper.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.error('Fatal:', e); process.exit(1); });
}
