---
name: packaged-artifact-smoke
description: Use when you need to prove a BUILT deliverable actually works end-to-end, not just that its source tree is CI-green. Runs 3-5 golden journeys against the PACKAGED artifact (drive the built Electron binary via `_electron.launch({executablePath})`, or `pip install dist/*.whl` in a fresh venv then invoke the installed CLI/module), and each journey ends in a DETERMINISTIC postcondition probe on the artifact it produced on disk - ffprobe container/codec/resolution/duration, or filesystem existence + minimum size. Catches packaging gaps that green source trees hide (missing runtime dep, electron-builder mis-map, a wheel that imports but cannot run). Triggers include smoke-test the built app, does the packaged binary actually run, assert the produced clip is 1080x1920, golden journey against the deliverable. NOT for unit/integration tests on the source tree (use tdd-workflow), NOT for pixel/design critique (use ui-audit).
---
# Packaged-Artifact / Effect-Assertion Smoke Runner

Prove the **built deliverable** does its job — by driving it and then asserting a
**real artifact on disk**, deterministically. This is the one class of gap that a
green source tree cannot catch: the code compiles, unit tests pass, coverage is
100%, and the shipped `.exe` / `.whl` still fails to launch or produces a broken
file because of a packaging error (missing runtime dependency, electron-builder
resource mis-map, wheel metadata that imports but cannot execute).

**Local precedent (why this exists):** Reframe v1.4 was CI-green on every unit
test yet the packaged app surfaced a cascade of latent packaging gaps only when
run end-to-end on the real target — `--no-deps` installs missing hypothesis/httpx,
unpinned opencv, `electron-builder --publish-never`, `assets.ensure` silently
skipping. See gem-hunt **MASTER A-Tier2 packaged-artifact gate** (⊕3, REC
BUILD-lite) and **agentic-repair-1 #4/#5, agentic-repair-2 #4**.

## The shape of a golden journey

Each journey has two halves:

1. **RUN** — invoke the *packaged* deliverable (never the source tree):
   - **Electron:** Playwright's `_electron.launch({ executablePath: <builtBinary> })`,
     drive a minimal flow, trigger the export.
   - **Python wheel:** `pip install dist/*.whl` into a **fresh venv**, then run the
     installed console-script / `python -m pkg` on a fixture input.
   - **Any CLI:** exec the built binary on a fixture.
2. **POSTCONDITION PROBE** — assert the artifact it produced:
   - `media` → `ffprobe` reads container / video+audio codec / width×height /
     duration (e.g. Reframe must emit a **non-zero, 1080×1920** mp4).
   - `exists` → the file exists on disk and is ≥ N bytes (catches 0-byte / silent-skip).

Keep it to **3–5 journeys** — the highest-value user paths, not exhaustive coverage.
Coverage is the source tree's job; this gate answers "does the *thing we ship* work".

## The reusable helper: `postcondition.mjs`

Zero third-party deps — Node stdlib + system `ffprobe`/`ffmpeg`. Import it as a
library (this is the primary use; A2-golden-journey-oracle and any pain app consume
it) or drive it as a CLI.

### Library API

```js
import {
  probeMedia, assertMedia, assertExists,
  runJourney, runManifest, installWheelFreshVenv,
} from './postcondition.mjs';

// Probe -> normalized descriptor
const p = probeMedia('out/clip.mp4');
// { container, durationSec, sizeBytes, videoCodec, audioCodec, width, height, fps, nbStreams }

// Assert a produced media artifact (all expect fields optional)
const r = assertMedia('out/clip.mp4', {
  container: 'mp4',        // substring, case-insensitive (ffprobe returns a comma list)
  videoCodec: 'h264', audioCodec: 'aac', hasAudio: true,
  width: 1080, height: 1920,        // exact
  minWidth: 1080, minHeight: 1920,  // or lower-bounds
  minDurationSec: 0.5, maxDurationSec: 600,
  minBytes: 1000,
});
// -> { ok, checks:[{name,expected,actual,pass}], probe }

assertExists('out/report.json', { minBytes: 2 });  // -> { ok, checks, sizeBytes }

// Fresh-venv wheel install (proves the wheel installs from clean, not just imports)
const { python, venvDir } = installWheelFreshVenv('dist/app-1.0-py3-none-any.whl');
```

### Journey / manifest schema

```jsonc
{
  "app": "reframe",
  "journeys": [
    {
      "id": "reframe-emits-1080x1920",
      "run": {                          // omit for a probe-only journey
        "cmd": "C:/path/to/Reframe.exe", // or the fresh-venv python, or a Playwright driver script
        "args": ["--in", "fixtures/land.mp4", "--out", "out/vert.mp4"],
        "cwd": "C:/work", "timeoutMs": 180000, "env": {}, "shell": false
      },
      "postcondition": {
        "type": "media",
        "file": "out/vert.mp4",         // relative resolves against run.cwd
        "expect": { "width": 1080, "height": 1920, "minDurationSec": 1, "minBytes": 10000 }
      }
    }
  ]
}
```

`runJourney(journey)` returns a terminal-state receipt
`{ id, outcome:'PASS'|'FAIL', run, assertion }`. If the RUN step exits non-zero the
journey fails **without** probing (the build itself broke). `runManifest(manifest)`
runs all journeys, prints per-journey `SUCCESS:<id>` / `FAILED:<id> …` markers and a
summary, and returns `{ total, passed, failed, ok, receipts, enforce }`.

### CLI

```bash
node postcondition.mjs run <manifest.json>            # SHADOW (default): observe+log, ALWAYS exit 0
node postcondition.mjs run <manifest.json> --enforce  # blocking: exit 1 on any journey failure
node postcondition.mjs probe <file>                   # dump ffprobe descriptor as JSON
node postcondition.mjs assert <file> --width 1080 --height 1920 --videoCodec h264
node postcondition.mjs selftest                       # synthesize a fixture and self-verify (11 checks)
```

## Shadow-mode discipline (council C5 — mandatory)

This runner is **invoked only on demand** and defaults to **SHADOW**: it observes,
logs a structured report, and **exits 0 regardless of assertion outcome** — it can
never block a build or nag. A caller opts into blocking with `--enforce` (or
`enforce:true`). The council **fast-tracks this class** (deterministic,
near-zero-false-positive, tautological) to `ENFORCE` after a **1-session burn-in**
per repo — an ffprobe assertion cannot be miscalibrated, so a 4-stage ladder on it
is pure time-to-value tax. Still: only turn on `--enforce` for a specific pain app
once a **signed golden journey exists** for it and it has cleared its burn-in
(council C4/C5). Route high-frequency shadow logs to a bounded, rotating sink — never
the main `terminal.jsonl` ledger.

## When NOT to use

- Unit / integration tests on the **source** tree → `tdd-workflow`,
  `smallest-check-ladder`.
- Pixel / design-quality critique of a running UI → `ui-audit`.
- Transcription, caption cue generation, watermark removal → the media skills.
- As a generic "run any ffmpeg command" helper — it is scoped to the
  RUN-then-postcondition-probe contract above.

## Requirements

- Node ≥ 18 (uses `node:` builtins; ESM). Verified on Node 24 / Windows.
- `ffprobe` (and `ffmpeg` for `selftest`) on `PATH`, or set `FFPROBE` / `FFMPEG`.
- For wheel journeys: `python` on `PATH` (or set `PYTHON`).

## Verification

`node postcondition.mjs selftest` synthesizes a real 1080×1920 h264+aac mp4 with
ffmpeg and exercises probe / assertMedia (pass **and** fail paths) / assertExists /
runManifest — 11 checks, all green on Node 24 + WinGet ffmpeg.
