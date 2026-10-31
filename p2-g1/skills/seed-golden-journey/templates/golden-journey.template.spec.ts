// golden-journey.template.spec.ts — the KEYSTONE held-out acceptance test.
//
// Fill in every << PLACEHOLDER >>. Delete the launch variant you don't use.
// Derived from Reframe app/e2e/golden-journey.spec.ts. This is the single external
// "done-signal": it drives the ONE money journey through the REAL app and asserts a
// REAL produced artifact on disk. Coverage + unit-green are necessary-but-not-sufficient.
//
// THE JOURNEY (everything against the live app — nothing stubbed):
//   launch the built app
//     → << the primary input is present / seeded / imported >>
//     → << navigate to the ONE money feature >>
//     → << perform the deterministic action that produces the artifact >>
//     → the UI acknowledges the dispatch
//     → poll the product's OWN status/list channel until the artifact is FINISHED
//     → assert the produced file EXISTS + is NON-EMPTY + is STRUCTURALLY VALID +
//       is SEMANTICALLY CORRECT (the assertion ladder — climb every rung).
//
// A faithful RED-REPRO is success: if the pipeline is broken, this fails with a
// diagnostic snapshot of what DID land on disk. A green fantasy is the failure mode.

import { test, expect, _electron as electron, type ElectronApplication, type Page } from '@playwright/test';
import { existsSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
// import { execFileSync } from 'node:child_process';   // ← uncomment for the ffprobe rung

let app: ElectronApplication;                 // ← remove if using the WEB variant
const consoleErrors: string[] = [];
const failedRequests: string[] = [];

/** The subset of your product's "list/status" record this test reads. Mirror the real shape. */
interface ProducedArtifact {
  path: string;
  id: string;
  durationSec: number;   // ← swap for whatever proves "the pipeline finished" (rows, bytes, …)
  width: number;
  height: number;
}

/**
 * Read the product's OWN list/status RPC through the LIVE bridge (the same call the
 * real gallery/list renders from), so we observe the exact backend the job ran against.
 * Return [] on any hiccup so the caller's poll retries instead of throwing mid-render.
 */
async function listViaBridge(win: Page, id: string): Promise<ProducedArtifact[]> {
  return win.evaluate(async (theId: string): Promise<ProducedArtifact[]> => {
    try {
      const api = (window as unknown as {
        api?: { rpc: (m: string, p?: unknown) => Promise<{ items?: ProducedArtifact[] }> };
      }).api;
      if (!api) return [];
      // << the real list RPC + params, e.g. 'shorts.list', { videoId: theId } >>
      const res = await api.rpc('<<LIST_RPC>>', { id: theId });
      return Array.isArray(res?.items) ? res.items! : [];
    } catch {
      return [];
    }
  }, id);
}

/**
 * Poll until a FINISHED artifact appears (metadata-bearing ⇒ the full pipeline completed)
 * or the deadline passes. Returns the final artifact + the last snapshot (the intermediates
 * on disk) so a red-repro is self-diagnosing about which stage was reached.
 */
async function pollForFinal(
  win: Page,
  id: string,
  deadlineMs: number,
): Promise<{ final: ProducedArtifact | null; snapshot: ProducedArtifact[] }> {
  let snapshot: ProducedArtifact[] = [];
  while (Date.now() < deadlineMs) {
    snapshot = await listViaBridge(win, id);
    const final = snapshot.find((s) => s.id === id && s.durationSec > 0); // ← "finished" predicate
    if (final) return { final, snapshot };
    await new Promise((r) => setTimeout(r, 1500));
  }
  return { final: null, snapshot };
}

test.beforeAll(async () => {
  // ── VARIANT A — ELECTRON (delete if web) ─────────────────────────────────────
  // Prefer the SHIPPED package (real .exe); fall back to the dev build. Seed a FRESH
  // data root so nothing leaks between runs. Provision any first-run assets the money
  // journey needs (mirror a real first-run — that's setup, not a code bug).
  const built = { main: '<<PATH_TO_BUILT_MAIN_JS>>', executablePath: '<<PACKAGED_EXE_OR_UNDEFINED>>' };
  // await provisionAssets(...);   // ← if the journey needs a downloaded model/asset first
  app = await electron.launch({
    args: [built.main, '--autoplay-policy=no-user-gesture-required', '--no-sandbox'],
    ...(built.executablePath ? { executablePath: built.executablePath } : {}),
    env: { /* << seeded app env: fresh DATA_ROOT, fixtures, etc. >> */ },
  });
  const win = await app.firstWindow();
  // ── end VARIANT A ────────────────────────────────────────────────────────────

  // Bind console/pageerror/response collectors from the FIRST frame so they cover the
  // whole session. Chromium's "Failed to load resource: 404" line omits the URL — capture
  // it here so a resource error is self-diagnosing instead of an anonymous console string.
  win.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  win.on('pageerror', (e) => consoleErrors.push(`PAGEERROR: ${e.message}`));
  win.on('response', (r) => { if (r.status() >= 400) failedRequests.push(`${r.status()} ${r.url()}`); });
  win.on('requestfailed', (req) =>
    failedRequests.push(`FAILED ${req.url()} (${req.failure()?.errorText ?? 'unknown'})`));
  await win.waitForLoadState('domcontentloaded');
});

test.afterAll(async () => {
  await app?.close();
});

test('<<PRODUCT>> produces a real <<ARTIFACT>> on disk (golden journey)', async () => {
  test.setTimeout(240_000);            // real ffmpeg/render/export needs generous headroom
  const win = await app.firstWindow();

  // A — the shell is up and the primary input is present.
  await expect(win.locator('<<APP_READY_LOCATOR>>')).toBeVisible();
  await expect(win.locator('<<INPUT_PRESENT_LOCATOR>>').first()).toBeVisible();

  // B — navigate to the ONE money feature.
  await win.locator('<<NAV_TO_FEATURE_LOCATOR>>').click();
  await expect(win.locator('<<FEATURE_READY_LOCATOR>>')).toBeVisible();

  // C — the DETERMINISTIC action that produces the artifact. Prefer the manual/explicit
  // path over an ML/heuristic one so a tiny fixture reliably yields output (Reframe: a
  // fixed 0:00→0:02 manual range beats AI moment-pick, which emits "no candidates").
  // << drive the inputs and trigger the produce action >>
  await win.locator('<<PRODUCE_BUTTON_LOCATOR>>').click();

  // Surface a DISPATCH error (bad params / dead backend) as the failure, not a silent timeout.
  await win.locator('<<NOTE_OR_ERROR_LOCATOR>>').first().waitFor({ state: 'visible', timeout: 30_000 });
  if (await win.locator('<<ERROR_LOCATOR>>').isVisible()) {
    throw new Error(`dispatch failed: ${(await win.locator('<<ERROR_LOCATOR>>').textContent())?.trim()}`);
  }
  await expect(win.locator('<<SUCCESS_NOTE_LOCATOR>>')).toContainText('<<DISPATCH_ACK_TEXT>>');

  // PRIMARY DONE-SIGNAL — wait for the FINISHED artifact, then walk the assertion ladder.
  const { final, snapshot } = await pollForFinal(win, '<<ARTIFACT_ID>>', Date.now() + 200_000);
  expect(
    final,
    `no finished <<ARTIFACT>> appeared within 200s — the job never completed ` +
      `(snapshot incl. intermediates: ${JSON.stringify(snapshot)})`,
  ).not.toBeNull();

  const produced = resolve(final!.path);
  // Rung 1 — exists.  Rung 2 — non-empty.
  expect(existsSync(produced), `artifact exists on disk: ${produced}`).toBe(true);
  expect(statSync(produced).size, `artifact is non-empty: ${produced}`).toBeGreaterThan(0);
  // Rung 3 — structurally valid (uncomment for media; adapt for zip/json/image):
  //   const dims = execFileSync('ffprobe', ['-v','error','-select_streams','v:0',
  //     '-show_entries','stream=width,height','-of','csv=p=0', produced]).toString().trim();
  //   expect(dims, `ffprobe could decode ${produced}`).toMatch(/^\d+,\d+$/);
  // Rung 4 — semantically correct (the promise of the journey):
  expect(final!.height, `portrait (h>w) — got ${final!.width}x${final!.height}`).toBeGreaterThan(final!.width);
  expect(final!.width, 'real dimensions').toBeGreaterThan(0);
  expect(final!.durationSec, 'real duration').toBeGreaterThan(0);
});

test('no console errors across the golden-journey session', async () => {
  // Kept SEPARATE from — and AFTER — the file-on-disk verdict so a renderer console error
  // never masks the primary "did a real artifact get produced?" signal.
  expect(
    consoleErrors,
    `console errors: ${JSON.stringify(consoleErrors)}\n` +
      `failed requests (URLs behind any "Failed to load resource" line): ${JSON.stringify(failedRequests)}`,
  ).toEqual([]);
});

/* ── VARIANT B — WEB (use INSTEAD of the Electron beforeAll/test above) ───────────
import { test, expect } from '@playwright/test';
import { existsSync, statSync } from 'node:fs';

test('<<PRODUCT>> produces a real <<ARTIFACT>> (golden journey)', async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto(process.env.BASE_URL ?? 'http://localhost:3000');
  await expect(page.locator('<<APP_READY_LOCATOR>>')).toBeVisible();
  // ...drive the ONE money journey...
  // Assert the REAL produced artifact — capture the download the app hands the user:
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '<<EXPORT_BUTTON>>' }).click(),
  ]);
  const file = await download.path();                       // the real produced file
  expect(file && existsSync(file)).toBe(true);              // rung 1
  expect(statSync(file!).size).toBeGreaterThan(0);          // rung 2
  // rungs 3–4: ffprobe/parse/open + assert the promised values (see main template).
});
──────────────────────────────────────────────────────────────────────────────── */
