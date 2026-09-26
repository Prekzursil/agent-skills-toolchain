---
title: Cross-rail byte-parity porting + Lean coverage calibration
type: note
permalink: main/techniques/cross-rail-byte-parity-porting-lean-coverage-calibration
tags:
- porting
- coverage
- verification
- typescript
- python
- self-reflect
---

# Cross-rail byte-parity porting + Lean coverage calibration

Two reusable techniques hardened while porting `ai-sessions-render` from Python to TypeScript (npm rail) on 2026-07-19. Both generalize to any "second implementation of the same spec" (language port, reimplementation, cross-vendor rebuild).

## Technique 1 — GENERATED cross-language parity fixtures gate a port

Don't just re-run ported unit tests; prove the two rails produce **byte-identical output**. Have the reference rail (Python) emit a fixture = `{input, output}` for an adversarial battery, then the port asserts `port(input) === output` byte-for-byte.

- **Three fixture layers** worked: (a) the pure security/sanitizer function over an adversarial battery (lone surrogates, variation-selector smuggling, multi-ZWJ emoji, markup contexts); (b) the renderers over every block type + an injection battery; (c) the ADAPTERS fed each reference adapter's exact input + asserting identical IR — this one embedded SAMPLED REAL data (44 real conversations), so it was gitignored and never packaged.
- **The generated-fixture caught a real library divergence** the port's own tests never would: markdown-it (JS) preserves a non-breaking space after a soft line break where markdown-it-py collapses it. 1/212 files, a few chars, no words lost. Documented as a known edge case rather than papered over.
- **A shared data table beats reimplementing a subtle predicate.** The JS hidden-unicode flag predicate is a table GENERATED from CPython's own `unicodedata` (a ~60-line generator that imports the REAL `_is_flagged`), so it cannot drift from Python by construction. Native JS `\p{Cf}` etc. was rejected: V8's Unicode version is unpinnable and disagreed with CPython UCD 16.0.0 on 4,803 codepoints. A sha256 self-test on the generated table catches corruption.
- **The end-to-end proof:** the installed npm CLI reproduced the Python CLI's numbers on the real corpus (212 rendered, gate 207/212), and a file-level diff was byte-identical on all 212 Markdown + 211/212 HTML.

## Technique 2 — Lean 100% coverage calibration (don't chase branch theater)

Enforce 100% where it's meaningful and achievable; refuse the theater tail.

- **Python (or any lang without pervasive null-coalescing):** 100% on ALL FOUR (statements/lines/functions/BRANCHES) is achievable and worth it. `pytest --cov-fail-under=100` + `[tool.coverage.run] branch=true`. The last ~18 branch-partials were all cheap falsy-path/empty-collection cases; a handful of targeted inputs closed them. Genuinely-unreachable defensive guards get a NARROW `# pragma: no cover` WITH justification (never function-level).
- **TypeScript:** 100% statements/lines/functions is achievable and meaningful; **100% BRANCH is coverage theater** because the `x ?? d` / `a || b` / `get()`/`s()` null-safety idiom emits a falsy-side branch for every defensive guard, many TYPE-PROVEN unreachable. Set a branch FLOOR (e.g. 88%) with a documented rationale, not 100%.
- **BUT first, delete the DEAD guards.** Many `?? []` / `?? {}` sat on NON-OPTIONAL typed fields (`conv.turns`, `t.blocks`, `b.data`) where TS already proves non-null — the fallback is dead code AND a permanently-uncovered branch. Removing them matched the reference rail (Python assumed well-formed IR too) AND cut the branch-coverage noise. Byte-parity tests confirmed output was unchanged.

## Cross-platform / CI gotchas that Windows-local coverage hid
- A gitignored REAL-DATA parity fixture SKIPS on CI, so any source path only that fixture exercised shows uncovered on CI (100% local, <100% CI). Fix: add SYNTHETIC coverage for it; verify locally by MOVING THE FIXTURE ASIDE to reproduce the CI condition.
- `fs.globSync` only stabilised in Node 22 → crashed the Node-20 CI leg though local Node 24 hid it. Use `readdirSync(src,{recursive:true})` (stable 18.17+), which also removed a Windows-path-`.replace(/\\/g,"/")` branch that differed Linux-vs-Windows.
- vitest transpiles with esbuild and does NOT type-check — a `readonly []` type error passed vitest but failed CI's separate `tsc --noEmit`. Always run `tsc` in CI, not just the test runner.

Relations: [[Verified-green read the summary not coverage]], project ai-sessions-render (auto-memory), toolchain windows-shell §10 (apostrophe/heredoc footgun).
