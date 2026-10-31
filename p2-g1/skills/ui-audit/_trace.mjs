import { chromium } from 'playwright';
import { resolveMock } from './_mock-data.mjs';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const log = [];
await ctx.route('**/api/**', r => {
  const u = new URL(r.request().url());
  const p = u.pathname.replace(/^.*\/api\/v1/, '') || '/';
  const body = resolveMock(r.request().method(), p);
  log.push(`${r.request().method()} ${p} -> ${Array.isArray(body) ? 'ARRAY' : typeof body}`);
  r.fulfill({ status: 200, contentType: 'application/json', body: body === null ? 'null' : JSON.stringify(body) });
});
const pg = await ctx.newPage();
pg.on('pageerror', e => console.log('PAGEERR:', (e.stack||e.message).slice(0, 600)));
await pg.goto('http://127.0.0.1:4200/admin/orders/ORD-101', { waitUntil: 'domcontentloaded', timeout: 30000 });
await pg.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
await new Promise(r => setTimeout(r, 1500));
console.log(log.join('\n'));
await b.close();
