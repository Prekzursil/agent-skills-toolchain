// ==UserScript==
// @name         GitHub PAT Quick Fill
// @namespace    github-pat-quick-fill
// @version      8.1
// @description  One-click MAX all fine-grained PAT permissions. DOM-driven (no hardcoded permission list) so it survives GitHub adding/removing permissions. Handles the current "Add permissions" picker UI + the older checkbox/dropdown UI.
// @match        https://github.com/settings/personal-access-tokens/new*
// @match        https://github.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const esc = () => document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));

  // ════════════════════════════════════════════════════════════════════
  //  ACCESS-LEVEL SCORING  (lower = more access; 0 = admin = the max)
  //  Handles "Access: Read-only", "Read and write", "Admin", "No access".
  //  Purely text-based, so new levels GitHub introduces still rank sanely.
  // ════════════════════════════════════════════════════════════════════
  function accessScore(text) {
    const t = norm(text).replace(/^access:\s*/, '');
    if (/^admin/.test(t)) return 0;
    if (/read and write|read & write|read\/write/.test(t)) return 1;
    if (/^write/.test(t)) return 2;
    if (/read-only|read only|^read\b/.test(t)) return 3;
    if (/no access/.test(t)) return 9;
    return 50; // not an access control
  }
  const isAccessText = (t) => accessScore(t) < 50;

  // ════════════════════════════════════════════════════════════════════
  //  STEP 1 — Repository access: pick "All repositories" (radio group)
  // ════════════════════════════════════════════════════════════════════
  function selectAllRepos() {
    for (const r of document.querySelectorAll('input[type="radio"]')) {
      const lbl = r.closest('label') || (r.id && document.querySelector(`label[for="${CSS.escape(r.id)}"]`));
      if (lbl && /all repositor/i.test(lbl.textContent) && !r.checked) { r.click(); return true; }
    }
    return false;
  }

  // ════════════════════════════════════════════════════════════════════
  //  STEP 2 — Add EVERY available permission.
  //  Current GitHub UI: an "Add permissions" button opens a searchable
  //  listbox of [role=option] items. Clicking an option toggles
  //  aria-selected and immediately adds a permission row (the dialog stays
  //  open). Repository and Account each have their own "Add permissions".
  //
  //  Robustness: the form re-renders on every add, invalidating node refs,
  //  so we RE-QUERY the first unselected option each loop instead of
  //  iterating a captured list. The permission NAMES are read from the
  //  live picker — nothing is hardcoded.
  // ════════════════════════════════════════════════════════════════════
  // Match an "Add permissions" trigger by BOTH visible text and aria-label —
  // GitHub renders one per category (Repository / Account / any future one) and
  // some are icon-only buttons with no text. Category-agnostic by design.
  const findAddTriggers = () =>
    [...document.querySelectorAll('button, summary, [role="button"], [role="combobox"]')]
      .filter((b) => visible(b) && (/add permissions/i.test(norm(b.textContent)) || /add permissions/i.test(b.getAttribute('aria-label') || '')));

  const openDialog = () =>
    [...document.querySelectorAll('[role="dialog"], [role="listbox"], [role="menu"]')]
      .filter(visible).pop();

  // Scroll the whole page so lazily-mounted permission sections (the Account
  // section mounts only when scrolled into view) are in the DOM before we scan
  // for their "Add permissions" trigger. THIS is the fix for the missed Account
  // category — from the top of the page only the Repository trigger exists yet.
  async function mountLazySections() {
    const h = document.body.scrollHeight;
    for (let y = 0; y <= h; y += 400) { window.scrollTo(0, y); await sleep(90); }
    window.scrollTo(0, 0);
    await sleep(200);
  }

  // Select every option in the currently-open picker. Re-queries each loop
  // (rows re-render on every add, invalidating node refs) and scrolls the list
  // to surface any virtualized options.
  async function addAllInOpenPicker() {
    let added = 0;
    for (let guard = 0; guard < 400; guard++) {
      const dlg = openDialog();
      if (!dlg) break;
      const pick = () => [...dlg.querySelectorAll('[role="option"]')]
        .find((o) => o.getAttribute('aria-selected') !== 'true' && visible(o));
      let next = pick();
      if (!next) {                                   // maybe more options below the fold
        const list = dlg.querySelector('[role="listbox"]') || dlg;
        list.scrollTop = list.scrollHeight;
        await sleep(160);
        next = pick();
        if (!next) break;                            // genuinely all selected
      }
      next.scrollIntoView({ block: 'nearest' });
      next.click();
      added++;
      await sleep(120);                              // let React add the row + re-render
    }
    return added;
  }

  // Process EVERY category's "Add permissions" trigger. Re-mounts lazy sections
  // and re-scans between passes, so repo + account (+ a hypothetical 3rd) are
  // all covered regardless of order or lazy rendering.
  async function addAllPermissions() {
    let added = 0;
    const processed = new WeakSet();
    for (let pass = 0; pass < 8; pass++) {
      await mountLazySections();
      const btns = findAddTriggers().filter((b) => !processed.has(b));
      if (!btns.length) break;
      for (const btn of btns) {
        processed.add(btn);
        btn.scrollIntoView({ block: 'center' });
        await sleep(150);
        btn.click();
        await sleep(750);                            // wait for the picker to open
        added += await addAllInOpenPicker();
        esc();                                       // close the picker
        await sleep(450);
      }
    }
    return added;
  }

  // ════════════════════════════════════════════════════════════════════
  //  STEP 3 — Upgrade every permission's access to its maximum.
  //  Each added permission shows an aria-haspopup "Access: …" button
  //  (defaults to Read-only). Open it, pick the highest-access option
  //  the menu offers (Admin > Read and write > Read-only). Some perms are
  //  read-only-max; those are left as-is. Also upgrades the older-UI
  //  access dropdowns whose button text is a bare access level.
  //  RE-QUERY each loop (rows re-render as levels change).
  // ════════════════════════════════════════════════════════════════════
  async function maxAllAccess() {
    let changed = 0;
    const seen = new Set();
    for (let guard = 0; guard < 200; guard++) {
      const btn = [...document.querySelectorAll('button[aria-haspopup]')]
        .find((b) => isAccessText(b.textContent) && visible(b) && accessScore(b.textContent) > 1 && !seen.has(b));
      if (!btn) break;
      seen.add(btn);
      const cur = accessScore(btn.textContent);
      btn.scrollIntoView({ block: 'nearest' });
      btn.click();
      await sleep(350);
      const menu = [...document.querySelectorAll('[role="menu"], [role="listbox"]')].filter(visible).pop();
      if (menu) {
        const opts = [...menu.querySelectorAll('[role="menuitemradio"], [role="option"], [role="menuitem"]')].filter(visible);
        let best = null, bestScore = 99;
        for (const o of opts) { const s = accessScore(o.textContent); if (s < bestScore) { bestScore = s; best = o; } }
        if (best && bestScore < cur) { best.click(); changed++; await sleep(160); }
        else esc();
      } else { esc(); }
      await sleep(120);
    }
    return changed;
  }

  // Safety net for the OLD UI (plain checkboxes) — harmless on the new UI.
  async function checkStrayBoxes() {
    let checked = 0;
    for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
      if (cb.checked || cb.closest('#gh-pat-open, #gh-pat-max') || !visible(cb)) continue;
      cb.click();
      checked++;
      await sleep(40);
      if (!cb.checked) {
        try {
          const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked')?.set;
          if (set) { set.call(cb, true); cb.dispatchEvent(new Event('input', { bubbles: true })); cb.dispatchEvent(new Event('change', { bubbles: true })); }
        } catch {}
      }
    }
    return checked;
  }

  // ════════════════════════════════════════════════════════════════════
  //  ORCHESTRATOR
  // ════════════════════════════════════════════════════════════════════
  async function maxEverything() {
    const r = {};
    selectAllRepos();
    await sleep(400);
    console.log('[PAT] Adding all permissions…');
    r.added = await addAllPermissions();
    await sleep(600);
    console.log(`[PAT] Added ${r.added}. Maxing access levels…`);
    r.maxed = await maxAllAccess();
    r.boxes = await checkStrayBoxes();

    const accessBtns = [...document.querySelectorAll('button[aria-haspopup]')].filter((b) => isAccessText(b.textContent) && visible(b));
    r.permRows = accessBtns.length;
    r.notAtMax = accessBtns.filter((b) => accessScore(b.textContent) > 1).length; // >1 means below "read and write"
    r.addBtnsLeft = findAddTriggers().length;
    console.log('[PAT] Result:', r);
    return r;
  }

  // ════════════════════════════════════════════════════════════════════
  //  URL BUILDER — only the fields GitHub still accepts as URL params
  //  (name / owner / description / expiration). Permissions are NOT
  //  hardcoded here anymore — they are added live by the Max button.
  // ════════════════════════════════════════════════════════════════════
  function buildPatUrl() {
    const owner = prompt('GitHub resource owner (username or org slug):', '');
    if (!owner) return null;
    const tokenName = prompt('Token name:', 'Full access PAT') || 'Full access PAT';
    const expiration = prompt("Expiration days or 'none':", 'none') || 'none';
    const params = new URLSearchParams({
      name: tokenName,
      description: 'Broad access PAT',
      target_name: owner,
      expires_in: expiration,
    });
    return 'https://github.com/settings/personal-access-tokens/new?' + params.toString();
  }

  // ════════════════════════════════════════════════════════════════════
  //  UI
  // ════════════════════════════════════════════════════════════════════
  const isPatPage = () => location.pathname.includes('/settings/personal-access-tokens/new');

  function makeBtn(id, text, bottom, bg) {
    if (document.getElementById(id)) return null;
    const btn = document.createElement('button');
    btn.id = id; btn.type = 'button'; btn.textContent = text;
    Object.assign(btn.style, {
      position: 'fixed', right: '16px', bottom, zIndex: '99999', padding: '10px 14px',
      borderRadius: '10px', border: '1px solid rgba(255,255,255,0.15)', background: bg,
      color: '#fff', fontSize: '14px', fontWeight: '600', cursor: 'pointer',
      boxShadow: '0 6px 24px rgba(0,0,0,0.25)', transition: 'all 0.15s',
      fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
    });
    btn.onmouseenter = () => (btn.style.opacity = '0.85');
    btn.onmouseleave = () => (btn.style.opacity = '1');
    document.body.appendChild(btn);
    return btn;
  }

  function initUI() {
    if (!document.getElementById('gh-pat-open')) {
      const openBtn = makeBtn('gh-pat-open', '🔑 PAT Quick Fill', '16px', '#0969da');
      if (openBtn) openBtn.onclick = () => { const u = buildPatUrl(); if (u) location.href = u; };
    }
    if (isPatPage() && !document.getElementById('gh-pat-max')) {
      const maxBtn = makeBtn('gh-pat-max', '⚡ Max ALL Permissions', '64px', '#8250df');
      if (maxBtn) {
        maxBtn.onclick = async () => {
          const label = maxBtn.textContent;
          maxBtn.textContent = '⏳ Working… (may take ~30–60s)';
          maxBtn.style.pointerEvents = 'none';
          try {
            const r = await maxEverything();
            const lines = ['✅ Done!', '', `Permissions added: ${r.added}`, `Access levels maxed: ${r.maxed}`, `Permission rows now: ${r.permRows}`];
            if (r.notAtMax > 0 || r.addBtnsLeft > 0) {
              lines.push('', `⚠️ ${r.notAtMax} row(s) below Read-and-write (may be read-only-max perms), ${r.addBtnsLeft} "Add permissions" still present.`, 'Click again to catch stragglers, or check console (F12).');
            } else {
              lines.push('', '🎉 Every permission added and maxed.');
            }
            lines.push('', 'Review, then click "Generate token".');
            alert(lines.join('\n'));
          } catch (err) {
            console.error('[PAT]', err);
            alert('⚠️ Error: ' + err.message + '\nCheck console (F12).');
          } finally {
            maxBtn.textContent = label;
            maxBtn.style.pointerEvents = '';
          }
        };
      }
    }
    if (!isPatPage()) document.getElementById('gh-pat-max')?.remove();
  }

  // ════════════════════════════════════════════════════════════════════
  //  BOOT
  // ════════════════════════════════════════════════════════════════════
  if (document.body) initUI(); else document.addEventListener('DOMContentLoaded', initUI);

  let lastHref = location.href;
  new MutationObserver(() => {
    if (location.href !== lastHref) {
      lastHref = location.href;
      document.getElementById('gh-pat-open')?.remove();
      document.getElementById('gh-pat-max')?.remove();
      setTimeout(initUI, 500);
    } else if (isPatPage() && !document.getElementById('gh-pat-max')) {
      setTimeout(initUI, 300);
    }
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
