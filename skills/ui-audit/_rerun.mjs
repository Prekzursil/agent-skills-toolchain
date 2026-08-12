import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import { resolveMock } from './_mock-data.mjs';
const BASE = 'http://127.0.0.1:4200';
const AREAS = [['order-detail', '/admin/orders/ORD-101'], ['content-pages', '/admin/content/pages']];
const b = await chromium.launch();
for (const [name, path] of AREAS) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.route('**/api/**', r => {
    const u = new URL(r.request().url());
    const p = u.pathname.replace(/^.*\/api\/v1/, '') || '/';
    const body = resolveMock(r.request().method(), p);
    r.fulfill({ status: 200, contentType: 'application/json', body: body === null ? 'null' : JSON.stringify(body) });
  });
  const pg = await ctx.newPage();
  const errs = []; let cerr = 0;
  pg.on('pageerror', e => errs.push(e.message.slice(0, 160)));
  pg.on('console', m => { if (m.type() === 'error') cerr++; });
  await pg.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await pg.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  await new Promise(r => setTimeout(r, 1200));
  let axe = [];
  try { const ar = await new AxeBuilder({ page: pg }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze(); axe = ar.violations.map(v => v.impact + ':' + v.id + 'x' + v.nodes.length); } catch {}
  const h = await pg.evaluate(() => { const x = document.querySelector('h1,h2'); return x ? x.textContent.trim().slice(0, 50) : null; });
  console.log(name, '| h=' + JSON.stringify(h), '| pgErr=' + errs.length, errs[0] || '', '| cErr=' + cerr, '| axe=[' + axe.join(',') + ']');
  await ctx.close();
}
await b.close();
