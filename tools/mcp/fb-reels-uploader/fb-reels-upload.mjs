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
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CREATE_URL = 'https://www.facebook.com/reels/create/';

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

async function dismissNagging(page) {
  for (const name of ['Not now', 'Not Now', 'Cancel']) {
    const b = page.getByRole('button', { name, exact: true });
    if (await b.first().isVisible().catch(() => false)) await b.first().click().catch(() => {});
  }
}

// Wait until the Create-reel composer is reachable (i.e. we're logged in).
// IMPORTANT: do NOT re-navigate while the user is on a login/checkpoint page, or
// the reload would wipe their half-typed credentials. Navigate once; only re-load
// the composer after they've left the auth flow.
async function waitForLogin(page, timeoutMs = 600000) {
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

async function setAudience(page, audience) {
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

async function uploadOneReel(page, filePath, audience) {
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

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help || !o.folder) { console.log(HELP); process.exit(o.help ? 0 : 2); }
  if (!fs.existsSync(o.folder)) { console.error('Folder not found:', o.folder); process.exit(2); }

  const files = fs.readdirSync(o.folder)
    .filter((f) => f.toLowerCase().endsWith('.' + o.ext))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  // nosemgrep: javascript.lang.security.audit.unsafe-formatstring.unsafe-formatstring -- internal CLI log message; o.ext is a developer-supplied CLI flag, not untrusted input
  if (!files.length) { console.error('No .' + o.ext + ' files in', o.folder); process.exit(2); }

  const stateFile = path.join(o.folder, '.fb-posted.json');
  /** @type {{posted:string[]}} */
  let state = { posted: [] };
  if (fs.existsSync(stateFile)) { try { state = JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch {} }
  const posted = new Set(state.posted);

  const { chromium } = await import('playwright').catch(() => {
    console.error(`\nPlaywright not installed. Run:\n  cd "${__dirname}"\n  npm install\n`);
    process.exit(3);
  });
  fs.mkdirSync(o.profile, { recursive: true });
  const ctx = await chromium.launchPersistentContext(o.profile, {
    headless: o.headless,
    viewport: { width: 1366, height: 900 },
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  let ok = 0; let done = 0; const failed = [];
  try {
    if (!(await waitForLogin(page))) throw new Error('Not logged into Facebook in time.');
    log('Logged in. Starting uploads.');

    for (let i = 0; i < files.length; i++) {
      const n = i + 1;            // 1-based clip number
      const file = files[i];
      if (n < o.start) continue;
      if (posted.has(file)) { log(`SKIP  ${n}/${files.length} ${file} (already posted)`); continue; }
      if (done >= o.limit) { log(`Reached --limit ${o.limit}; stopping.`); break; }

      const full = path.join(o.folder, file);
      log(`POST  ${n}/${files.length} ${file} ...`);
      try {
        await uploadOneReel(page, full, o.audience);
        posted.add(file);
        state.posted = [...posted];
        fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
        ok++; done++;
        log(`OK    ${n}/${files.length} ${file}  (posted ${ok})`);
      } catch (e) {
        failed.push(n);
        log(`FAIL  ${n}/${files.length} ${file}: ${e.message}`);
        log('Stopping to preserve order (fix the issue, then re-run — it resumes from here).');
        break;   // order guarantee: do not skip ahead past a failure
      }
      if (o.delaySec) { log(`(pausing ${o.delaySec}s before next)`); await sleep(o.delaySec * 1000); }
    }
  } finally {
    await ctx.close();
  }
  log(`\nDONE posted=${ok} failed=[${failed}]`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error('Fatal:', e); process.exit(1); });
