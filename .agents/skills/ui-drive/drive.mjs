#!/usr/bin/env node
/**
 * ui-drive/drive.mjs — thin rail-router app/GUI driver.
 *
 * Rails (tried in this order for an ambiguous target): a11y-ref -> CDP(css) -> vision(xy).
 * Verbs: attach / drive / point / discuss / preview / apply / accept / revert / harvest.
 *
 * Rides the sibling `ui-audit` skill's VENDORED playwright@1.61.1 — no new browser dep
 * (Correction 3: near-zero-build). Resolved from ../ui-audit/node_modules/playwright/index.mjs
 * relative to this file (override with env UI_DRIVE_PLAYWRIGHT).
 *
 * SAFETY / SHADOW (COUNCIL C5): ui-drive NEVER edits application source. `drive` actuates the
 * LIVE app (that is a driver's job); preview/apply/accept inject only EPHEMERAL <style> overlays;
 * revert removes them; harvest EMITS a proposed CSS patch for a human/agent to translate to source
 * — it writes no source. Every mutating verb is logged to a bounded, rotating SHADOW sink
 * (observe-only, never blocks, never nags).
 *
 * PINNED HIGHLIGHT (empirically verified on the vendored 1.61.1 at build time):
 *   `await locator.highlight()` injects an <x-pw-glass> overlay that IS captured by
 *   `page.screenshot()`; `await page.hideHighlight()` clears it. There is NO
 *   `show --annotate/--highlight` CLI subcommand — that path was unconfirmed and is NOT used.
 *   For coordinate (vision) targets we draw our own #__ui_drive_box overlay instead.
 *
 * Usage — programmatic (primary; one node process holds the whole session):
 *   import { Driver } from './drive.mjs';
 *   const d = await Driver.attach({ url: 'http://localhost:5173' });   // or { cdp }, { electron }
 *   console.log(d.snapshot());                    // ref map of interactive elements
 *   await d.point('role:button|Save', { outDir: './out' });
 *   await d.drive('click', 'ref:3');
 *   await d.preview('.btn{background:#0a7}'); await d.apply(); await d.accept();
 *   console.log(await d.harvest({ outDir: './out' }));
 *   await d.close();
 *
 * Usage — CLI. `--cdp <ep>` attaches to an already-running app (cross-process, verbs reconnect
 * via a session file); `--url`/`--electron` run the verb ONESHOT (single process):
 *   node drive.mjs attach  --cdp http://localhost:9222
 *   node drive.mjs point   --cdp http://localhost:9222 --target ref:5 --out ./out
 *   node drive.mjs point   --url http://localhost:5173 --target "role:button|Save" --out ./out
 *   node drive.mjs drive   --cdp http://localhost:9222 --action click --target "text:Export"
 *   node drive.mjs harvest --cdp http://localhost:9222 --out ./out
 */

import { pathToFileURL, fileURLToPath } from 'node:url';
import { existsSync, mkdirSync, writeFileSync, appendFileSync, statSync, renameSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { parseArgs } from 'node:util';

const HERE = dirname(fileURLToPath(import.meta.url));

// --------------------------------------------------------------------------
// Vendored-playwright resolver (near-zero-build: reuse ui-audit's copy)
// --------------------------------------------------------------------------
export function playwrightCandidates() {
  const c = [];
  if (process.env.UI_DRIVE_PLAYWRIGHT) c.push(process.env.UI_DRIVE_PLAYWRIGHT);
  // sibling ui-audit skill, relative to this file
  c.push(resolve(HERE, '..', 'ui-audit', 'node_modules', 'playwright', 'index.mjs'));
  c.push(resolve(HERE, '..', 'ui-audit', 'node_modules', 'playwright-core', 'index.mjs'));
  // absolute fallbacks (known install)
  c.push('C:/Users/Prekzursil/.claude/skills/ui-audit/node_modules/playwright/index.mjs');
  c.push('C:/Users/Prekzursil/.claude/skills/ui-audit/node_modules/playwright-core/index.mjs');
  return c;
}

let _pwCache = null;
export async function resolvePlaywright() {
  if (_pwCache) return _pwCache;
  for (const cand of playwrightCandidates()) {
    try {
      if (!existsSync(cand)) continue;
      const mod = await import(pathToFileURL(cand).href);
      const chromium = mod.chromium || (mod.default && mod.default.chromium);
      if (chromium) { _pwCache = { chromium, _electron: mod._electron || (mod.default && mod.default._electron), from: cand }; return _pwCache; }
    } catch { /* try next */ }
  }
  throw new Error('ui-drive: could not resolve a vendored playwright. Set UI_DRIVE_PLAYWRIGHT to <playwright>/index.mjs, or install ui-audit deps.');
}

// --------------------------------------------------------------------------
// Shadow sink — observe-only, bounded, never throws (COUNCIL C5)
// --------------------------------------------------------------------------
const SHADOW_MAX = 256 * 1024;
export function shadowLogPath() {
  return process.env.UI_DRIVE_SHADOW_LOG || join(tmpdir(), 'ui-drive-shadow', 'actions.jsonl');
}
export function shadowLog(event) {
  try {
    const p = shadowLogPath();
    mkdirSync(dirname(p), { recursive: true });
    try { if (existsSync(p) && statSync(p).size > SHADOW_MAX) renameSync(p, p + '.1'); } catch { /* rotate best-effort */ }
    appendFileSync(p, JSON.stringify({ ts: new Date().toISOString(), ...event }) + '\n');
  } catch { /* shadow never blocks */ }
}

// --------------------------------------------------------------------------
// Target grammar + rail router
// --------------------------------------------------------------------------
const KNOWN_ROLES = new Set([
  'alert','alertdialog','application','article','banner','button','cell','checkbox','columnheader',
  'combobox','complementary','contentinfo','definition','dialog','directory','document','feed',
  'figure','form','grid','gridcell','group','heading','img','link','list','listbox','listitem',
  'log','main','marquee','math','menu','menubar','menuitem','menuitemcheckbox','menuitemradio',
  'navigation','none','note','option','presentation','progressbar','radio','radiogroup','region',
  'row','rowgroup','rowheader','scrollbar','search','searchbox','separator','slider','spinbutton',
  'status','switch','tab','table','tablist','tabpanel','term','textbox','timer','toolbar','tooltip',
  'tree','treegrid','treeitem',
]);

/** Parse a --target string into a structured spec. */
export function parseTarget(spec) {
  if (spec == null) return { kind: 'none' };
  const s = String(spec).trim();
  const m = s.match(/^([a-z-]+):([\s\S]*)$/i);
  if (m) {
    const kind = m[1].toLowerCase();
    const rest = m[2];
    switch (kind) {
      case 'ref': return { kind: 'ref', n: parseInt(rest, 10) };
      case 'role': {
        const pipe = rest.indexOf('|');
        if (pipe >= 0) return { kind: 'role', role: rest.slice(0, pipe).trim(), name: rest.slice(pipe + 1).trim() };
        return { kind: 'role', role: rest.trim(), name: undefined };
      }
      case 'text': return { kind: 'text', value: rest };
      case 'label': return { kind: 'label', value: rest };
      case 'placeholder': return { kind: 'placeholder', value: rest };
      case 'alt': return { kind: 'alt', value: rest };
      case 'title': return { kind: 'title', value: rest };
      case 'testid': return { kind: 'testid', value: rest };
      case 'css': return { kind: 'css', value: rest };
      case 'xy': {
        const [x, y] = rest.split(',').map(v => parseFloat(v.trim()));
        return { kind: 'xy', x, y };
      }
      default: return { kind: 'auto', value: s };
    }
  }
  return { kind: 'auto', value: s };
}

/** rail label for a parsed target kind (before cascade fallbacks). */
function railFor(kind) {
  if (['ref', 'role', 'text', 'label', 'placeholder', 'alt', 'title'].includes(kind)) return 'a11y-ref';
  if (['testid', 'css'].includes(kind)) return 'cdp';
  if (kind === 'xy') return 'vision';
  return 'auto';
}

// --------------------------------------------------------------------------
// Ref-map builder (a11y-ref rail backing store + attach snapshot)
// --------------------------------------------------------------------------
async function computeRefMap(page) {
  const raw = await page.evaluate((MAX) => {
    const INTERACTIVE = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']);
    const roleOf = (el) => {
      const explicit = el.getAttribute('role');
      if (explicit) return explicit;
      const tag = el.tagName;
      if (tag === 'A' && el.hasAttribute('href')) return 'link';
      if (tag === 'BUTTON') return 'button';
      if (tag === 'SELECT') return 'combobox';
      if (tag === 'TEXTAREA') return 'textbox';
      if (tag === 'INPUT') {
        const t = (el.getAttribute('type') || 'text').toLowerCase();
        if (['button', 'submit', 'reset', 'image'].includes(t)) return 'button';
        if (t === 'checkbox') return 'checkbox';
        if (t === 'radio') return 'radio';
        if (t === 'range') return 'slider';
        return 'textbox';
      }
      return null;
    };
    const nameOf = (el) => {
      const al = el.getAttribute('aria-label'); if (al) return al.trim();
      const lb = el.getAttribute('aria-labelledby');
      if (lb) {
        const t = lb.split(/\s+/).map(id => { const n = document.getElementById(id); return n ? n.textContent : ''; }).join(' ').trim();
        if (t) return t;
      }
      if (el.tagName === 'INPUT') {
        if (el.id) { const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (lab && lab.textContent.trim()) return lab.textContent.trim(); }
        const t = (el.getAttribute('type') || 'text').toLowerCase();
        const val = el.getAttribute('value');
        if (['button', 'submit', 'reset'].includes(t)) return (val || '').trim();
        const ph = el.getAttribute('placeholder'); if (ph) return ph.trim();
        return (val || '').trim();
      }
      const txt = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (txt) return txt.slice(0, 120);
      const ti = el.getAttribute('title'); if (ti) return ti.trim();
      const alt = el.getAttribute('alt'); if (alt) return alt.trim();
      return '';
    };
    const selOf = (el) => {
      if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return '#' + el.id;
      const tid = el.getAttribute('data-testid'); if (tid) return '[data-testid="' + tid + '"]';
      const parts = [];
      let node = el;
      for (let depth = 0; node && node.nodeType === 1 && depth < 4; depth++) {
        if (node.id && /^[A-Za-z][\w-]*$/.test(node.id)) { parts.unshift('#' + node.id); break; }
        let sName = node.tagName.toLowerCase();
        const parent = node.parentElement;
        if (parent) {
          const sameTag = Array.from(parent.children).filter(c => c.tagName === node.tagName);
          if (sameTag.length > 1) sName += ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')';
        }
        parts.unshift(sName);
        node = parent;
      }
      return parts.join(' > ');
    };
    const out = [];
    for (const el of Array.from(document.querySelectorAll('*'))) {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      const role = roleOf(el);
      const tabbable = el.hasAttribute('tabindex') && el.getAttribute('tabindex') !== '-1';
      const interactive = INTERACTIVE.has(el.tagName) || role === 'button' || role === 'link' ||
        tabbable || el.getAttribute('role') != null || typeof el.onclick === 'function';
      if (!interactive) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      out.push({
        role: role || el.getAttribute('role') || el.tagName.toLowerCase(),
        name: nameOf(el),
        tag: el.tagName.toLowerCase(),
        selector: selOf(el),
        rect: { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) },
      });
      if (out.length >= MAX) break;
    }
    return out;
  }, 250);

  // assign refs + per-(role,name) duplicate index
  const seen = new Map();
  return raw.map((e, i) => {
    const key = e.role + ' ' + e.name;
    const dupIndex = seen.get(key) || 0;
    seen.set(key, dupIndex + 1);
    return { ref: i + 1, dupIndex, ...e };
  });
}

// --------------------------------------------------------------------------
// Driver
// --------------------------------------------------------------------------
export class Driver {
  constructor({ pw, browser, context, page, mode, cdpEndpoint, recorders, ownsBrowser }) {
    this.pw = pw;
    this.browser = browser;
    this.context = context;
    this.page = page;
    this.mode = mode;                 // 'url' | 'electron' | 'cdp'
    this.cdpEndpoint = cdpEndpoint || null;
    this.recorders = recorders || { consoleMsgs: [], pageErrors: [], networkRequests: [] };
    this.ownsBrowser = ownsBrowser !== false;
    this.refMap = [];
    this.overlays = { preview: null, applied: [], accepted: [] };
    this._overlaySeq = 0;
  }

  static _attachRecorders(page) {
    const consoleMsgs = [], pageErrors = [], networkRequests = [];
    page.on('console', m => consoleMsgs.push({ type: m.type(), text: m.text() }));
    page.on('pageerror', e => { const r = { name: e.name || 'Error', message: e.message || String(e) }; pageErrors.push(r); consoleMsgs.push({ type: 'error', text: `[pageerror] ${r.name}: ${r.message}` }); });
    page.on('response', r => networkRequests.push({ url: r.url(), status: r.status(), flagged: r.status() >= 400 }));
    page.on('requestfailed', r => networkRequests.push({ url: r.url(), status: 0, flagged: true, failure: r.failure()?.errorText || 'failed' }));
    return { consoleMsgs, pageErrors, networkRequests };
  }

  static async attach(opts = {}) {
    const { url, electron, cdp, headed = false, waitSelector, settleMs = 300, sessionPath } = opts;
    const pw = await resolvePlaywright();
    let browser, context, page, mode, cdpEndpoint = null, ownsBrowser = true;

    if (cdp) {
      mode = 'cdp';
      cdpEndpoint = cdp;
      browser = await pw.chromium.connectOverCDP(cdp);
      context = browser.contexts()[0] || await browser.newContext();
      page = context.pages()[0] || await context.newPage();
      ownsBrowser = false; // the app owns its own life; we only disconnect
    } else if (electron) {
      mode = 'electron';
      if (!pw._electron) throw new Error('ui-drive: _electron not exported by the vendored playwright');
      const app = await pw._electron.launch({ args: [resolve(electron)] });
      browser = app;                       // ElectronApplication (has .close())
      page = await app.firstWindow();
      context = page.context();
    } else if (url) {
      mode = 'url';
      browser = await pw.chromium.launch({ headless: !headed });
      context = await browser.newContext();
      page = await context.newPage();
    } else {
      throw new Error('ui-drive attach: provide one of { url, electron, cdp }');
    }

    const recorders = Driver._attachRecorders(page);
    const d = new Driver({ pw, browser, context, page, mode, cdpEndpoint, recorders, ownsBrowser });
    d.sessionPath = sessionPath || null;

    if (mode === 'url') {
      try { await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 }); }
      catch (e) { recorders.pageErrors.push({ name: 'NavigationError', message: String(e.message).split('\n')[0] }); }
    }
    await d._settle({ waitSelector, settleMs });
    await d.refresh();
    return d;
  }

  async _settle({ waitSelector, settleMs = 300, networkIdleTimeout = 6000 } = {}) {
    try { await this.page.waitForLoadState('networkidle', { timeout: networkIdleTimeout }); } catch { /* ok */ }
    if (waitSelector) { try { await this.page.waitForSelector(waitSelector, { timeout: 8000, state: 'attached' }); } catch { /* ok */ } }
    if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
  }

  /** Re-read the interactive ref map from the current page. */
  async refresh() {
    try { this.refMap = await computeRefMap(this.page); } catch { this.refMap = []; }
    return this.refMap;
  }

  snapshot() {
    return {
      mode: this.mode,
      url: (() => { try { return this.page.url(); } catch { return null; } })(),
      refCount: this.refMap.length,
      refs: this.refMap.map(e => ({ ref: e.ref, role: e.role, name: e.name, tag: e.tag, rect: e.rect })),
      overlays: { preview: !!this.overlays.preview, applied: this.overlays.applied.length, accepted: this.overlays.accepted.length },
      pageErrors: this.recorders.pageErrors.length,
    };
  }

  // ---- rail router --------------------------------------------------------
  /** Resolve a target string to { rail, locator?, coord?, count, entry?, note }. */
  async resolve(target) {
    const t = parseTarget(target);
    const page = this.page;
    const mk = (rail, locator, count, extra = {}) => ({ rail, locator, count, ...extra });

    if (t.kind === 'xy') return mk('vision', null, 1, { coord: { x: t.x, y: t.y } });

    if (t.kind === 'ref') {
      const entry = this.refMap.find(e => e.ref === t.n);
      if (!entry) return mk('a11y-ref', null, 0, { note: `no ref ${t.n} in current snapshot (have ${this.refMap.length})` });
      let loc;
      if (entry.role && entry.name && KNOWN_ROLES.has(entry.role)) {
        loc = page.getByRole(entry.role, { name: entry.name, exact: true });
        const c = await loc.count();
        if (c === 0) loc = page.locator(entry.selector);
        else if (c > 1) loc = loc.nth(entry.dupIndex);
      } else {
        loc = page.locator(entry.selector);
      }
      return mk('a11y-ref', loc, await loc.count(), { entry });
    }

    if (t.kind === 'role') {
      if (!KNOWN_ROLES.has(t.role)) return mk('a11y-ref', null, 0, { note: `unknown ARIA role "${t.role}"` });
      const loc = t.name != null ? page.getByRole(t.role, { name: t.name }) : page.getByRole(t.role);
      return mk('a11y-ref', loc, await loc.count());
    }
    if (t.kind === 'text') { const loc = page.getByText(t.value); return mk('a11y-ref', loc, await loc.count()); }
    if (t.kind === 'label') { const loc = page.getByLabel(t.value); return mk('a11y-ref', loc, await loc.count()); }
    if (t.kind === 'placeholder') { const loc = page.getByPlaceholder(t.value); return mk('a11y-ref', loc, await loc.count()); }
    if (t.kind === 'alt') { const loc = page.getByAltText(t.value); return mk('a11y-ref', loc, await loc.count()); }
    if (t.kind === 'title') { const loc = page.getByTitle(t.value); return mk('a11y-ref', loc, await loc.count()); }
    if (t.kind === 'testid') { const loc = page.getByTestId(t.value); return mk('cdp', loc, await loc.count()); }
    if (t.kind === 'css') { const loc = page.locator(t.value); return mk('cdp', loc, await loc.count()); }

    // auto: cascade a11y-ref (text) -> cdp (css) -> vision(fail)
    if (t.kind === 'auto') {
      const byText = page.getByText(t.value);
      if (await byText.count() > 0) return mk('a11y-ref', byText, await byText.count(), { note: 'auto->text' });
      try {
        const byCss = page.locator(t.value);
        if (await byCss.count() > 0) return mk('cdp', byCss, await byCss.count(), { note: 'auto->css' });
      } catch { /* invalid selector */ }
      return mk('vision', null, 0, { note: 'no a11y/css match — supply xy:<x>,<y> for the vision rail' });
    }
    return mk('a11y-ref', null, 0, { note: 'unparsable target' });
  }

  async _boxAt(rect, label) {
    await this.page.evaluate(({ r, label }) => {
      const old = document.getElementById('__ui_drive_box'); if (old) old.remove();
      const o = document.createElement('div'); o.id = '__ui_drive_box';
      Object.assign(o.style, { position: 'fixed', left: r.x + 'px', top: r.y + 'px', width: (r.width || 24) + 'px', height: (r.height || 24) + 'px', border: '2px solid #ff00aa', background: 'rgba(255,0,170,0.15)', zIndex: 2147483647, pointerEvents: 'none', boxSizing: 'border-box' });
      if (label) { const t = document.createElement('div'); t.textContent = label; Object.assign(t.style, { position: 'absolute', top: '-16px', left: '0', font: '11px monospace', background: '#ff00aa', color: '#fff', padding: '0 3px', whiteSpace: 'nowrap' }); o.appendChild(t); }
      document.body.appendChild(o);
    }, { r: rect, label });
  }
  async _clearBox() { try { await this.page.evaluate(() => { const o = document.getElementById('__ui_drive_box'); if (o) o.remove(); }); } catch { /* ok */ } }

  // ---- point (read-only; PINNED highlight) --------------------------------
  async point(target, { outDir = null, wantBuffer = false, name } = {}) {
    const r = await this.resolve(target);
    const out = { verb: 'point', target: String(target), rail: r.rail, count: r.count, note: r.note || null };

    let usedVisionBox = false;
    let bbox = null;
    if (r.rail === 'vision' && r.coord) {
      bbox = { x: r.coord.x - 12, y: r.coord.y - 12, width: 24, height: 24 };
      await this._boxAt(bbox, `xy ${Math.round(r.coord.x)},${Math.round(r.coord.y)}`);
      usedVisionBox = true;
    } else if (r.locator && r.count > 0) {
      const first = r.locator.first();
      try { bbox = await first.boundingBox(); } catch { /* ok */ }
      try { out.accessibleName = (await first.textContent() || '').replace(/\s+/g, ' ').trim().slice(0, 120); } catch { /* ok */ }
      // PINNED: locator.highlight() draws the screenshot-visible <x-pw-glass> overlay.
      try { await r.locator.highlight(); out.highlighted = true; } catch (e) { out.highlighted = false; out.highlightError = e.message; }
    } else {
      out.error = 'target resolved to 0 elements';
    }
    out.bbox = bbox;

    let buf = null;
    if (outDir || wantBuffer) {
      try {
        const shot = {};
        if (outDir) { mkdirSync(outDir, { recursive: true }); shot.path = join(outDir, `point-${name || (r.entry ? 'ref' + r.entry.ref : 'target')}.png`); }
        buf = await this.page.screenshot(shot);
        if (shot.path) out.screenshotPath = shot.path;
      } catch (e) { out.screenshotError = e.message; }
    }
    // clean up overlays so subsequent captures/actions are pristine
    if (usedVisionBox) await this._clearBox();
    else if (typeof this.page.hideHighlight === 'function') { try { await this.page.hideHighlight(); } catch { /* ok */ } }

    if (wantBuffer) out._buffer = buf;
    return out;
  }

  // ---- discuss (read-only; point + element context) -----------------------
  async discuss(target, { outDir = null } = {}) {
    const p = await this.point(target, { outDir });
    const r = await this.resolve(target);
    const ctx = { verb: 'discuss', ...p };
    if (r.locator && r.count > 0) {
      const first = r.locator.first();
      try { ctx.ariaSnapshot = await first.ariaSnapshot(); } catch { /* ok */ }
      try {
        ctx.styles = await first.evaluate(el => {
          const cs = getComputedStyle(el);
          const pick = ['display', 'position', 'color', 'backgroundColor', 'fontSize', 'fontWeight', 'lineHeight', 'padding', 'margin', 'border', 'width', 'height', 'cursor', 'outlineStyle'];
          const o = {}; for (const k of pick) o[k] = cs[k]; return o;
        });
      } catch { /* ok */ }
      try { ctx.nearbyText = await first.evaluate(el => (el.closest('section,article,div,form,main,body') || el).textContent.replace(/\s+/g, ' ').trim().slice(0, 300)); } catch { /* ok */ }
    }
    return ctx;
  }

  // ---- drive (actuates the LIVE app; shadow-logged) -----------------------
  async drive(action, target, value, opts = {}) {
    const r = await this.resolve(target);
    const before = { url: this.page.url(), errCount: this.recorders.pageErrors.length };
    const out = { verb: 'drive', action, target: String(target), rail: r.rail, count: r.count };
    try {
      if (r.rail === 'vision' && r.coord) {
        const { x, y } = r.coord;
        if (action === 'click') await this.page.mouse.click(x, y);
        else if (action === 'hover') await this.page.mouse.move(x, y);
        else if (action === 'dblclick') await this.page.mouse.dblclick(x, y);
        else if (action === 'fill' || action === 'type') { await this.page.mouse.click(x, y); await this.page.keyboard.type(String(value ?? '')); }
        else throw new Error(`vision rail supports click/hover/dblclick/fill/type, not "${action}"`);
      } else {
        if (!r.locator || r.count === 0) throw new Error('target resolved to 0 elements');
        const loc = r.locator.first();
        switch (action) {
          case 'click': await loc.click({ timeout: opts.timeout || 8000 }); break;
          case 'dblclick': await loc.dblclick({ timeout: opts.timeout || 8000 }); break;
          case 'hover': await loc.hover({ timeout: opts.timeout || 8000 }); break;
          case 'fill': await loc.fill(String(value ?? ''), { timeout: opts.timeout || 8000 }); break;
          case 'type': await loc.pressSequentially(String(value ?? ''), { timeout: opts.timeout || 8000 }); break;
          case 'press': await loc.press(String(value ?? 'Enter'), { timeout: opts.timeout || 8000 }); break;
          case 'check': await loc.check({ timeout: opts.timeout || 8000 }); break;
          case 'uncheck': await loc.uncheck({ timeout: opts.timeout || 8000 }); break;
          case 'select': await loc.selectOption(value, { timeout: opts.timeout || 8000 }); break;
          case 'scroll': await loc.scrollIntoViewIfNeeded({ timeout: opts.timeout || 8000 }); break;
          case 'focus': await loc.focus({ timeout: opts.timeout || 8000 }); break;
          default: throw new Error(`unknown action "${action}"`);
        }
      }
      out.ok = true;
    } catch (e) { out.ok = false; out.error = String(e.message).split('\n')[0]; }

    await this._settle({ settleMs: opts.settleMs ?? 150 });
    // navigation may have wiped applied/accepted overlays -> reinject
    if (this.page.url() !== before.url) { await this._reinjectOverlays(); await this.refresh(); }
    out.after = { url: this.page.url(), newErrors: this.recorders.pageErrors.slice(before.errCount).map(e => `${e.name}: ${e.message}`) };
    shadowLog({ verb: 'drive', action, target: String(target), rail: r.rail, ok: out.ok, url: out.after.url });
    return out;
  }

  // ---- preview / apply / accept / revert (ephemeral overlays) -------------
  async _injectOverlay(css, id) {
    await this.page.evaluate(({ css, id }) => {
      let s = document.querySelector(`style[data-ui-drive-overlay="${id}"]`);
      if (!s) { s = document.createElement('style'); s.setAttribute('data-ui-drive-overlay', id); document.head.appendChild(s); }
      s.textContent = css;
    }, { css, id });
  }
  async _removeOverlay(id) {
    try { await this.page.evaluate((id) => { const s = document.querySelector(`style[data-ui-drive-overlay="${id}"]`); if (s) s.remove(); }, id); } catch { /* ok */ }
  }
  async _reinjectOverlays() {
    for (const o of [...this.overlays.applied, ...this.overlays.accepted]) { try { await this._injectOverlay(o.css, o.id); } catch { /* ok */ } }
  }

  /** Inject an EPHEMERAL <style> candidate (no source edit). Returns before/after screenshots. */
  async preview(css, { outDir = null } = {}) {
    const id = 'preview';
    let beforePath = null, afterPath = null;
    if (outDir) { mkdirSync(outDir, { recursive: true }); beforePath = join(outDir, 'preview-before.png'); try { await this.page.screenshot({ path: beforePath }); } catch { beforePath = null; } }
    this.overlays.preview = { id, css, state: 'preview', ts: Date.now() };
    await this._injectOverlay(css, id);
    await this._settle({ settleMs: 120 });
    if (outDir) { afterPath = join(outDir, 'preview-after.png'); try { await this.page.screenshot({ path: afterPath }); } catch { afterPath = null; } }
    shadowLog({ verb: 'preview', cssLen: css.length });
    return { verb: 'preview', css, beforePath, afterPath, active: true };
  }

  /** Promote the current preview to an APPLIED overlay (persists for the session; still overlay-only). */
  async apply() {
    if (!this.overlays.preview) return { verb: 'apply', ok: false, error: 'no active preview' };
    const o = this.overlays.preview;
    o.id = 'applied-' + (++this._overlaySeq); o.state = 'applied';
    await this._removeOverlay('preview');
    await this._injectOverlay(o.css, o.id);
    this.overlays.applied.push(o);
    this.overlays.preview = null;
    shadowLog({ verb: 'apply', id: o.id });
    return { verb: 'apply', ok: true, id: o.id, appliedCount: this.overlays.applied.length };
  }

  /** Mark the most-recent applied overlay as ACCEPTED (the change harvest will export). */
  async accept() {
    const o = this.overlays.applied.pop();
    if (!o) return { verb: 'accept', ok: false, error: 'no applied overlay to accept' };
    o.state = 'accepted';
    this.overlays.accepted.push(o);
    shadowLog({ verb: 'accept', id: o.id });
    return { verb: 'accept', ok: true, id: o.id, acceptedCount: this.overlays.accepted.length };
  }

  /** Remove an overlay, restoring the prior visual state. scope: 'preview'|'applied'|'accepted'|'all'. */
  async revert({ scope = 'preview' } = {}) {
    let removed = [];
    if (scope === 'preview' || scope === 'all') {
      if (this.overlays.preview) { await this._removeOverlay('preview'); removed.push(this.overlays.preview.id); this.overlays.preview = null; }
    }
    if (scope === 'applied' || scope === 'all') {
      const o = scope === 'all' ? null : this.overlays.applied.pop();
      if (scope === 'all') { for (const a of this.overlays.applied.splice(0)) { await this._removeOverlay(a.id); removed.push(a.id); } }
      else if (o) { await this._removeOverlay(o.id); removed.push(o.id); }
    }
    if (scope === 'accepted' || scope === 'all') {
      if (scope === 'all') { for (const a of this.overlays.accepted.splice(0)) { await this._removeOverlay(a.id); removed.push(a.id); } }
      else { const o = this.overlays.accepted.pop(); if (o) { await this._removeOverlay(o.id); removed.push(o.id); } }
    }
    shadowLog({ verb: 'revert', scope, removed });
    return { verb: 'revert', scope, removed, ok: removed.length > 0 };
  }

  // ---- harvest (emit proposed CSS patch; NEVER edits source) --------------
  parseCss(css) {
    // Best-effort: split "sel { decls }" blocks into { selector, declarations }.
    const blocks = [];
    const re = /([^{}]+)\{([^{}]*)\}/g; let m;
    while ((m = re.exec(css)) !== null) {
      const selector = m[1].trim();
      const declarations = m[2].split(';').map(d => d.trim()).filter(Boolean);
      if (selector) blocks.push({ selector, declarations });
    }
    if (blocks.length === 0 && css.trim()) blocks.push({ selector: '(raw)', declarations: [css.trim()] });
    return blocks;
  }

  async harvest({ outDir = null, includeApplied = false } = {}) {
    const src = includeApplied ? [...this.overlays.accepted, ...this.overlays.applied] : [...this.overlays.accepted];
    const patch = src.map(o => ({ id: o.id, state: o.state, css: o.css, blocks: this.parseCss(o.css) }));
    const cssText = src.map(o => `/* ui-drive ${o.state} ${o.id} */\n${o.css}`).join('\n\n');
    const result = {
      verb: 'harvest',
      note: 'PROPOSED CSS deltas only — ui-drive never edits application source. Translate these to the real stylesheet/component (see design-studio-session for element->source mapping).',
      count: patch.length,
      patch,
    };
    if (outDir) {
      mkdirSync(outDir, { recursive: true });
      const cssPath = join(outDir, 'ui-drive-harvest.css');
      const jsonPath = join(outDir, 'ui-drive-harvest.json');
      writeFileSync(cssPath, cssText + (cssText ? '\n' : ''));
      writeFileSync(jsonPath, JSON.stringify(result, null, 2));
      result.cssPath = cssPath; result.jsonPath = jsonPath;
    }
    shadowLog({ verb: 'harvest', count: patch.length });
    return result;
  }

  async close() {
    try {
      if (this.mode === 'cdp' && !this.ownsBrowser) { await this.browser.close().catch(() => {}); } // disconnect only
      else await this.browser.close().catch(() => {});
    } catch { /* ok */ }
  }
}

// --------------------------------------------------------------------------
// CLI-side session persistence (cdp cross-process)
// --------------------------------------------------------------------------
function sessionFile(flags) { return flags.session || process.env.UI_DRIVE_SESSION || join(tmpdir(), 'ui-drive-session.json'); }
function loadSession(flags) { try { return JSON.parse(readFileSync(sessionFile(flags), 'utf8')); } catch { return {}; } }
function saveSession(flags, data) { try { writeFileSync(sessionFile(flags), JSON.stringify(data, null, 2)); } catch { /* ok */ } }

async function cliAttach(flags) {
  const sess = loadSession(flags);
  const cdp = flags.cdp || (flags.url ? null : sess.cdpEndpoint);
  const d = await Driver.attach({
    url: flags.url, electron: flags.electron, cdp,
    headed: !!flags.headed, waitSelector: flags['wait-selector'],
    settleMs: flags.settle != null ? Number(flags.settle) : undefined,
    sessionPath: sessionFile(flags),
  });
  // restore overlays from session (cdp cross-process)
  if (d.mode === 'cdp' && sess.overlays) {
    d.overlays = { preview: null, applied: sess.overlays.applied || [], accepted: sess.overlays.accepted || [] };
    d._overlaySeq = sess.overlaySeq || 0;
    await d._reinjectOverlays();
  }
  return { d, sess };
}
function persist(flags, d, sess) {
  if (d.mode === 'cdp') {
    saveSession(flags, {
      cdpEndpoint: d.cdpEndpoint,
      overlays: { applied: d.overlays.applied, accepted: d.overlays.accepted },
      overlaySeq: d._overlaySeq,
      ts: new Date().toISOString(),
    });
  }
}

async function runCli(argv) {
  const verb = argv[2];
  const { values: flags } = parseArgs({
    args: argv.slice(3),
    options: {
      url: { type: 'string' }, electron: { type: 'string' }, cdp: { type: 'string' },
      target: { type: 'string' }, action: { type: 'string' }, value: { type: 'string' },
      css: { type: 'string' }, scope: { type: 'string' }, out: { type: 'string' },
      session: { type: 'string' }, headed: { type: 'boolean' },
      'wait-selector': { type: 'string' }, settle: { type: 'string' }, 'include-applied': { type: 'boolean' },
    },
    strict: false,
  });
  const outDir = flags.out ? resolve(flags.out) : null;
  if (!verb) { console.error('FAILED:ui-drive no verb (attach|drive|point|discuss|preview|apply|accept|revert|harvest)'); process.exit(1); }

  const { d, sess } = await cliAttach(flags);
  let result;
  try {
    switch (verb) {
      case 'attach': result = d.snapshot(); break;
      case 'point': result = await d.point(flags.target, { outDir }); break;
      case 'discuss': result = await d.discuss(flags.target, { outDir }); break;
      case 'drive': result = await d.drive(flags.action || 'click', flags.target, flags.value, {}); break;
      case 'preview': result = await d.preview(flags.css || '', { outDir }); break;
      case 'apply': result = await d.apply(); break;
      case 'accept': result = await d.accept(); break;
      case 'revert': result = await d.revert({ scope: flags.scope || 'preview' }); break;
      case 'harvest': result = await d.harvest({ outDir, includeApplied: !!flags['include-applied'] }); break;
      default: console.error(`FAILED:ui-drive unknown verb "${verb}"`); await d.close(); process.exit(1);
    }
    persist(flags, d, sess);
    console.log(JSON.stringify(result, null, 2));
    console.log(`SUCCESS:ui-drive:${verb}`);
  } catch (e) {
    console.error(`FAILED:ui-drive:${verb} ${String(e.message).split('\n')[0]}`);
    process.exitCode = 1;
  } finally {
    await d.close();
  }
}

// Run as CLI only when executed directly. Compare REALPATHS: this skill dir is reached
// through a junction (~/.claude/skills -> skills.daily), so Node realpaths import.meta.url
// but not process.argv[1]; a plain string compare would wrongly skip the CLI.
function __isMainModule() {
  try {
    const self = resolve(fileURLToPath(import.meta.url));
    const arg = process.argv[1];
    if (!arg) return false;
    if (resolve(arg) === self) return true;
    try { return resolve(realpathSync(arg)) === self; } catch { return false; }
  } catch { return false; }
}
if (__isMainModule()) {
  runCli(process.argv).catch(e => { console.error(`FAILED:ui-drive ${e.message}`); process.exit(1); });
}
