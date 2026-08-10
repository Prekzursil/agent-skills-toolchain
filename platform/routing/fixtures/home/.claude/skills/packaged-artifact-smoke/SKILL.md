---
name: packaged-artifact-smoke
description: >-
  Use when you need to prove a BUILT deliverable actually works end-to-end, not
  just that its source tree is CI-green. Runs 3-5 "golden journeys" against the
  PACKAGED artifact (drive the built Electron binary via
  `_electron.launch({executablePath})`, or `pip install dist/*.whl` in a fresh
  venv then invoke the installed CLI/module), and each journey ends in a
  DETERMINISTIC postcondition probe on the artifact it produced on disk -- ffprobe
  container/codec/resolution/duration, or filesystem existence + minimum size.
  Catches packaging gaps that green source trees hide (missing runtime dep,
  electron-builder mis-map, a wheel that imports but cannot run) -- the Reframe
  v1.4 precedent. Reusable helper consumed by A2-golden-journey-oracle and any
  pain app. Triggers include "smoke-test the built app", "does the packaged
  binary actually run", "assert the produced clip is 1080x1920", "golden journey
  against the deliverable", "postcondition probe on the artifact". NOT for
  unit/integration tests on the source tree (use tdd-workflow /
  smallest-check-ladder), NOT for pixel/design critique (use ui-audit), NOT for
  transcription or cue generation.
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

### The reusable helper: `postcondition.mjs`
### Library API
### Journey / manifest schema
### CLI
### Shadow-mode discipline (council C5 — mandatory)
### When NOT to use
### Requirements
### Verification
