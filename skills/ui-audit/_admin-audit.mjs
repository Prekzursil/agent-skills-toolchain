#!/usr/bin/env node
// Mock-aware admin auditor: drives the running Angular admin with the API mocked,
// emits capture.mjs-compatible bundles (desktop + 390px mobile) + runs axe-core.
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { resolveMock } from './_mock-data.mjs';

const BASE = 'http://127.0.0.1:4200';
const OUT = process.argv[2] || './admin-audit-out';
mkdirSync(OUT, { recursive: true });

const STYLE_PROPS = [
  'marginTop','marginBottom','marginLeft','marginRight','paddingTop','paddingBottom','paddingLeft','paddingRight',
  'gap','rowGap','columnGap','fontSize','fontWeight','lineHeight','color','backgroundColor','width','height',
  'display','position','transitionDuration','transitionProperty','animationDuration','animationName',
  'outlineStyle','outlineWidth','cursor',
];
const MAX_ELEMENTS = 250;

const AREAS = [
  ['dashboard', '/admin/dashboard'],
  ['products', '/admin/products'],
  ['orders', '/admin/orders'],
  ['order-detail', '/admin/orders/ORD-101'],
  ['users', '/admin/users'],
  ['coupons', '/admin/coupons'],
  ['content-home', '/admin/content/home'],
  ['content-pages', '/admin/content/pages'],
  ['content-blog', '/admin/content/blog'],
  ['content-media', '/admin/content/media'],
  ['returns', '/admin/returns'],
  ['inventory', '/admin/inventory'],
  ['support', '/admin/support'],
  ['ops', '/admin/ops'],
];

const API_RE = /\/api\/v1(\/.*)?$/;

async function installMock(context) {
  await context.route('**/api/**', async (route) => {
    const req = route.request();
    const u = new URL(req.url());
    const m = API_RE.exec(u.pathname);
    const pathname = m ? (m[1] || '/') : u.pathname.replace(/^.*\/api\/v1/, '');
    const body = resolveMock(req.method(), pathname);
    if (body === null) return route.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

async function getComputedStyles(page) {
  return page.evaluate(({ props, maxEls }) => {
    const INTERACTIVE = new Set(['A','BUTTON','INPUT','SELECT','TEXTAREA']);
    const els = Array.from(document.querySelectorAll('*')).slice(0, maxEls);
    return els.map((el) => {
      const cs = getComputedStyle(el); const rect = el.getBoundingClientRect();
      const styles = {}; for (const p of props) styles[p] = cs[p] || null;
      styles._rect = { width: rect.width, height: rect.height, x: rect.x, y: rect.y };
      let sel = el.tagName.toLowerCase();
      if (el.id) sel = '#' + el.id;
      else if (el.className && typeof el.className === 'string' && el.className.trim())
        sel = el.tagName.toLowerCase() + '.' + el.className.trim().split(/\s+/).join('.');
      return { selector: sel, tagName: el.tagName, textContent: (el.textContent||'').slice(0,100).trim(),
        isInteractive: INTERACTIVE.has(el.tagName) || el.getAttribute('role')==='button' ||
          (el.getAttribute('tabindex')!=null && el.getAttribute('tabindex')!=='-1'),
        inlineStyle: el.getAttribute('style')||'', styles };
    });
  }, { props: STYLE_PROPS, maxEls: MAX_ELEMENTS });
}

async function getPageSignals(page) {
  try {
    return await page.evaluate(() => {
      let rm=false, fv=false, bad=0;
      const scan=(rules)=>{ for(const r of rules){ const t=r.cssText||'';
        if(r.media && /prefers-reduced-motion/i.test(r.conditionText||r.media.mediaText||'')) rm=true;
        if(/prefers-reduced-motion/i.test(t)) rm=true;
        if(/:focus-visible/i.test(r.selectorText||t)) fv=true;
        if(r.cssRules){ try{scan(r.cssRules);}catch{} } } };
      for(const s of Array.from(document.styleSheets)){ try{scan(s.cssRules);}catch{bad++;} }
      return { hasReducedMotionRule:rm, hasFocusVisibleRule:fv, inaccessibleSheets:bad };
    });
  } catch { return { hasReducedMotionRule:false, hasFocusVisibleRule:false, inaccessibleSheets:0 }; }
}

async function snap(page, name, viewport, rec) {
  const shot = join(OUT, `${name}.png`);
  try { await page.screenshot({ path: shot, fullPage: true }); } catch {}
  let a11y=null; try { a11y = await page.accessibility.snapshot(); } catch {}
  const elements = await getComputedStyles(page);
  const pageSignals = await getPageSignals(page);
  // visible text length to detect empty/blank renders
  let textLen = 0; try { textLen = await page.evaluate(() => (document.body?.innerText||'').trim().length); } catch {}
  const heading = await page.evaluate(() => {
    const h = document.querySelector('h1,h2,[role=heading]'); return h ? h.textContent.trim().slice(0,80) : null;
  }).catch(()=>null);
  const bundle = { screen: name, url: page.url(), viewport, timestamp: new Date().toISOString(),
    screenshotPath: shot, a11ySnapshot: a11y, elements, pageSignals,
    consoleMsgs: rec.consoleMsgs, networkRequests: rec.networkRequests, pageErrors: rec.pageErrors,
    textLen, heading };
  writeFileSync(join(OUT, `${name}.bundle.json`), JSON.stringify(bundle, null, 2));
  return bundle;
}

async function runAxe(page) {
  try {
    const r = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
      tags: v.tags, sample: (v.nodes[0]?.target||[]).join(' ') }));
  } catch (e) { return [{ id:'axe-error', impact:'n/a', help:String(e.message).slice(0,120), nodes:0 }]; }
}

(async () => {
  const browser = await chromium.launch();
  const results = [];
  for (const [name, path] of AREAS) {
    for (const [vpName, vp] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      const context = await browser.newContext({ viewport: vp });
      await installMock(context);
      const page = await context.newPage();
      const rec = { consoleMsgs: [], networkRequests: [], pageErrors: [] };
      page.on('console', m => rec.consoleMsgs.push({ type: m.type(), text: m.text().slice(0,300) }));
      page.on('pageerror', e => rec.pageErrors.push({ name: e.name||'Error', message: (e.message||String(e)).slice(0,300) }));
      page.on('response', r => { const s=r.status(); if (s>=400) rec.networkRequests.push({ url:r.url(), status:s, flagged:true }); });
      try { await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 30000 }); } catch (e) { rec.pageErrors.push({ name:'NavigationError', message:String(e.message).split('\n')[0] }); }
      try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch {}
      await new Promise(r => setTimeout(r, 1200));
      const fullName = `${name}.${vpName}`;
      const bundle = await snap(page, fullName, vpName, rec);
      const axe = vpName === 'desktop' ? await runAxe(page) : null;
      results.push({ area: name, viewport: vpName, url: page.url(), heading: bundle.heading, textLen: bundle.textLen,
        pageErrors: rec.pageErrors.length, errSample: rec.pageErrors[0]?.message || null,
        consoleErrors: rec.consoleMsgs.filter(c=>c.type==='error').length,
        axeViolations: axe ? axe.length : null, axe });
      console.log(`[audit] ${fullName} url=${page.url().replace(BASE,'')} h=${JSON.stringify(bundle.heading)} text=${bundle.textLen} pgErr=${rec.pageErrors.length} axe=${axe?axe.length:'-'}`);
      await context.close();
    }
  }
  writeFileSync(join(OUT, 'results.json'), JSON.stringify(results, null, 2));
  await browser.close();
  console.log('SUCCESS:admin-audit');
})().catch(e => { console.error('FAILED:admin-audit', e.message); process.exit(1); });
