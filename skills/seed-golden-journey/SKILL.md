---
name: seed-golden-journey
description: Use when an app needs a keystone acceptance test that proves the real product works end to end, not just that units pass or coverage is high. Scaffolds a HELD-OUT golden-journey test that launches the REAL app, drives the ONE primary user journey, and asserts a REAL artifact on disk (ffprobe media file, a downloaded file) rather than element-present. Parameterized for Electron, web, and CLI.
---

# seed-golden-journey

Coverage and "unit-green" are a **proxy the implementer controls**, so a capable agent optimizes
that proxy and stops — while the real A→B→C user journey stays broken. Live proof: Reframe shipped
v1.4 with **100% coverage and green units**, and "Make Shorts" never produced a file on Windows.
Three real Windows-only bugs sat exactly at the seams the unit tests mock and Linux CI can't reach.
The one signal that caught them was a **held-out golden-journey that drove the real app and
asserted a real vertical short on disk**.

This skill scaffolds that keystone: the single external **done-signal** the implementer can't
author or fake. It is the highest-leverage thing a user provides — no hook substitutes for it.

## The five rules of a golden journey

1. **Pick the ONE money journey.** The single flow that is the product's reason to exist — the
   thing that, if it silently broke, the product is worthless regardless of coverage. Reframe:
   *"Make Shorts produces a real vertical short file on disk."* One journey, not a matrix.
2. **Drive the REAL app — nothing stubbed.** Launch the actual built binary/app; drive the real
   UI; let it hit the real backend/sidecar, real ffmpeg, real filesystem. The bugs live precisely
   at the seams unit tests mock; a mocked journey re-hides them.
3. **Assert a REAL produced artifact, not element-present.** "Button rendered" / "toast appeared"
   is theater. The pass condition is the *thing the user came for* existing and being valid on
   disk: a media file that `ffprobe` confirms has the right dims + a real duration; a downloaded
   file that opens; a screenshot whose pixels match. Walk the **assertion ladder** (below).
4. **Held-out + merge gate.** Author it so the implementing agent can't see or edit it, keep it
   out of the default test select (an `e2e`/`acceptance` marker or a separate project), and make
   it the merge gate. Coverage/unit-green are necessary but **may NOT be cited as done**.
5. **A faithful red-repro is success.** If the pipeline is broken, the correct behavior is to fail
   with a diagnostic snapshot of what *did* land on disk — never a green fantasy. Red-repro first,
   then fix until it goes green against the real artifact.

## The assertion ladder (climb every rung — stopping early is theater)

1. **Exists** — the output file is on disk at the path the app reports (`existsSync` / `os.path`).
2. **Non-empty** — `statSync(path).size > 0` — a 0-byte file is a silent failure.
3. **Structurally valid** — it opens/parses: `ffprobe` decodes it; the archive unzips; the JSON
   parses; the image loads. A file that exists but won't decode is still a broken product.
4. **Semantically correct** — the values the journey promised: media is **portrait** (height >
   width) with duration > 0; the export has the expected rows; the screenshot matches baseline.

## Wiring the async completion (background jobs)

Most real "make it" actions dispatch a background job and return immediately, so the UI note
appears **before** the artifact exists. Prove completion by **polling the real status channel**
(the same RPC the product's own gallery/list renders from), with a hard deadline and a
**diagnostic snapshot on timeout** so a red-repro tells you which stage was reached:

```ts
// poll the product's OWN list RPC, not a private test hook:
while (Date.now() < deadline) {
  const snapshot = await listViaRealBridge(win, id);           // e.g. shorts.list {videoId}
  const finished = snapshot.find(s => s.id === id && s.durationSec > 0);  // metadata-bearing = pipeline done
  if (finished) return { finished, snapshot };
  await sleep(1500);
}
return { finished: null, snapshot };   // timeout → assert non-null WITH JSON(snapshot) in the message
```

## Stack recipes — the LAUNCH is the only part that changes

The journey shape (launch → drive → poll → assert real artifact) is identical across stacks; only
the launch/drive surface differs. Full annotated spec: `templates/golden-journey.template.spec.ts`
(Electron/web) and `templates/golden-journey.cli.template.spec.ts` (CLI).

- **Electron** (the Reframe exemplar):
  ```ts
  import { _electron as electron } from '@playwright/test';
  const app = await electron.launch({
    args: [builtMainJs, '--no-sandbox'],
    executablePath: packagedExe,   // prefer the SHIPPED .exe; fall back to the dev build
    env: seededEnv,                // a fresh data root so nothing leaks between runs
  });
  const win = await app.firstWindow();
  ```
- **Web** (Playwright against the running app):
  ```ts
  test('golden journey', async ({ page }) => {
    await page.goto(process.env.BASE_URL ?? 'http://localhost:3000');
    // ...drive the ONE journey, then assert the produced artifact:
    const download = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Export' }).click(),
    ]).then(([d]) => d);
    const file = await download.path();      // the REAL produced file → run the assertion ladder
  });
  ```
- **CLI** (spawn the real command, assert its output file):
  ```ts
  import { execFileSync } from 'node:child_process';
  execFileSync('mytool', ['build', '--in', fixture, '--out', outPath], { stdio: 'inherit' });
  // then: exists → non-empty → parses/ffprobe → semantically correct
  ```
  Python equivalent: `subprocess.run([...], check=True)` then assert on `out_path`.

## Make it the gate + forbid the reward-hack surface

- **Keep it held out of normal runs and make it the merge gate.** In the task that hands work to
  an implementer, use this line verbatim:
  > *Done = the golden-journey exits 0 on a clean checkout. Coverage / unit-green are necessary
  > but NOT sufficient and may NOT be cited as done.*
- **Forbid the gaming surface and verify against the diff.** No net-new `pragma:no-cover` /
  `xfail` / `skip` / coverage-omit / `addopts` / `-m` marker / `collectCoverageFrom` / CI-trigger
  edits. Require the final report to include a `git diff` of every test/CI/coverage-config change —
  that diff is where the gaming hides.
- **Red-repro before every fix; attach the artifact with every "fixed."** Script the failure as a
  red golden-journey first; attach the produced mp4/screenshot/file, never an isolated unit test,
  as proof.

## Anti-patterns

- Asserting an element/toast is visible instead of a real artifact on disk.
- Mocking the backend/sidecar/ffmpeg "to make the E2E deterministic" — that re-hides the seam bugs.
- Letting the implementing agent read or edit the spec (it will fit the exam to its code).
- Citing coverage % or "all units pass" as the done-signal.
- Claiming done on a single-frame / single-poll check instead of polling to real completion with a
  timeout snapshot.
- A green result while the artifact is 0 bytes or won't decode (ladder stopped at rung 1).
