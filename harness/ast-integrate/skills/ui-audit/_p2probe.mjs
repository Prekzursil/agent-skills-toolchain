import { chromium } from 'playwright';
const t0 = Date.now();
const log = (m) => console.log(`[${((Date.now()-t0)/1000).toFixed(1)}s] ${m}`);
log('launching');
const b = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
log('launched');
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const pg = await ctx.newPage();
const errs = []; pg.on('pageerror', e => errs.push(e.message.slice(0,120)));
await pg.goto('http://localhost:4202/shop', { waitUntil: 'domcontentloaded', timeout: 45000 });
log('domcontentloaded title=' + JSON.stringify(await pg.title()));
const idle = await pg.waitForLoadState('networkidle',{timeout:10000}).then(()=>'OK').catch(()=>'TIMEOUT');
log('networkidle=' + idle);
const info = await pg.evaluate(() => ({
  textLen: document.body.innerText.trim().length,
  h1: (document.querySelector('h1,h2')||{}).textContent?.trim().slice(0,60) || null,
  imgs: document.images.length,
  links: document.querySelectorAll('a[href]').length,
  buttons: document.querySelectorAll('button').length
}));
log('info=' + JSON.stringify(info));
log('pageErrors=' + errs.length + ' ' + (errs[0]||''));
await b.close(); log('closed');
