---
name: two-tier-verify
description: Use when repeated code edits are triggering a full test-suite rerun each iteration and burning tokens/time, or before any commit. Splits verification into a cheap INNER loop per edit (only the affected/related tests plus type-check and lint on touched files) and a single OUTER loop at the commit boundary (full suite plus coverage plus held-out E2E/golden-journey plus a scoped mutation check). Gives concrete jest/vitest/playwright and pytest command recipes and the decision rule for which tier to run. NOT a replacement for the golden-journey done-signal (see seed-golden-journey); NOT for one-off single-file scripts where a full run is already trivial.
---

# two-tier-verify

The default agentic edit loop is `edit → rerun the WHOLE suite → read all output → edit again`.
That is the single biggest token/time sink in long repair sessions — ProjDevBench measured
**~4.81M tokens per problem**, dominated by re-running and re-reading tests that the last edit
could not possibly have affected. Test-impact selection (Ekstazi / Microsoft TIA / CloudBees)
cuts test time **32–70%** by running only the tests reachable from the change.

The fix is to **split verification into two tiers** and never confuse them:

- **INNER loop** — runs after *every* edit. Fast, narrow, cheap. Only the tests related to the
  files you touched, plus a type-check and a lint on those files. This is your iteration signal.
- **OUTER loop** — runs *once*, at the commit boundary (and before a PR). Slow, total, external.
  Full suite + coverage threshold + the held-out E2E/golden-journey + a scoped mutation check.
  This is your merge signal.

**Law:** the INNER loop is for *iterating*; it is never a done-signal. Only a green OUTER loop
authorizes a commit. Related-test selection is fast precisely because it is blind to seams it
can't reach — so it can go green while an integration path is broken. That gap is exactly what
the OUTER loop's full suite + golden-journey exist to close.

## The two tiers

| | INNER (per edit) | OUTER (per commit) |
|---|---|---|
| Frequency | every edit / iteration | once, at the commit/PR boundary |
| Target | tests **related to changed files** only | **full** suite |
| Also runs | type-check + lint on touched files | coverage threshold + held-out E2E/golden-journey + scoped mutation check |
| Budget | seconds (aim < 30s) | minutes — pay it once |
| Role | iteration feedback | **merge gate / done-signal** |
| On failure | fix, re-run INNER | map failure back to the change, drop to INNER |

## Decision rule — which tier, when

1. **After each edit → INNER.** Run related-tests + type + lint on the touched files. Loop here
   until green. Do NOT run the full suite between edits.
2. **At the commit boundary → OUTER, exactly once.** Full suite + coverage + golden-journey +
   mutation micro-check. Only a green OUTER run authorizes the commit.
3. **Escalate INNER → OUTER early** (run the full suite now, not at the boundary) when the change
   can fan out past what related-test selection can see:
   - a **shared/core/base module**, a widely-imported util, or a public interface changed;
   - **config / build / dependency / CI / test-infra** edits (`package.json`, `pyproject.toml`,
     `tsconfig`, `jest.config`, `conftest.py`, lockfiles) — impact selection can't model these;
   - the related-test set came back **empty or suspiciously small** for a real code change
     (selection missed it — trust the full suite instead).
4. **Never cite the INNER result as "done."** "Related tests pass" ≠ "the app works." The
   done-signal lives in the OUTER loop (full suite + golden-journey), per seed-golden-journey.

> **Neighbour — `smallest-check-ladder`** states this same split as four rungs: L0 lint/typecheck
> the edited file, L1 impacted tests, L2 full suite, L3 e2e against the built artifact. INNER here
> is its L0+L1; OUTER is its L2+L3. Go there for the rung-by-rung selector commands and the "name
> the rung you actually reached" honesty rails; stay here for the decision rule and the
> per-framework recipes below.

## Command recipes — JS / TS (jest, vitest, playwright)

**INNER (per edit):**
```bash
# jest — run only tests that import the changed file(s):
npx jest --findRelatedTests src/foo.ts src/bar.ts --coverage=false --bail
#   or, git-driven, all tests related to files changed vs HEAD:
npx jest -o --coverage=false            # --onlyChanged

# vitest — run only tests related to the changed files:
npx vitest related src/foo.ts --run     # --run = single pass, not watch
#   or git-driven since HEAD:
npx vitest run --changed

# type-check + lint on what you touched (the "AST" gate):
npx tsc --noEmit --incremental           # fast type gate (whole project, cached)
npx eslint src/foo.ts src/bar.ts --max-warnings=0

# Electron/web E2E in the INNER loop: run ONE spec, never the whole E2E suite:
npx playwright test e2e/that-one.spec.ts --project=chromium
```

**OUTER (per commit):**
```bash
npx jest --coverage                      # full suite + coverage
# (or vitest: npx vitest run --coverage)
# enforce the project's threshold — .coverage-thresholds.json is the SSOT if present:
#   jest reads coverageThreshold from config; fail the commit if it drops.
npx playwright test                      # full E2E incl. the held-out golden-journey
npx stryker run --mutate src/foo.ts,src/bar.ts   # mutation MICRO-check, scoped to the change
```

## Command recipes — Python (pytest)

**INNER (per edit):**
```bash
# affected module only:
pytest tests/test_foo.py -q -x
# test-impact selection across the repo (tracks which tests hit which lines):
pip install pytest-testmon && pytest --testmon -q     # reruns only impacted tests
# or fail-fast on last failures while iterating:
pytest --lf -q          # last-failed;  --ff = failed-first

# type + lint on the touched files (the "AST" gate):
mypy src/foo.py         # or: pyright src/foo.py
ruff check src/foo.py
```

**OUTER (per commit):**
```bash
pytest --cov=src --cov-report=term-missing        # full suite + coverage
# enforce threshold (SSOT = .coverage-thresholds.json if present):
pytest --cov=src --cov-fail-under=<threshold>
# held-out acceptance (kept out of the default select, e.g. an e2e marker):
pytest -m e2e                                     # the golden-journey / acceptance run
# mutation MICRO-check, scoped to the changed module:
mutmut run --paths-to-mutate src/foo.py           # or cosmic-ray for a targeted config
```

## Mapping an OUTER failure back to the change

The OUTER loop runs on an accumulation of edits, so a failure isn't self-locating. Recover the
seam without re-running everything:
```bash
git diff --name-only <last-green-outer>..HEAD     # the files in play
# re-run just the failing test against the suspect files:
npx jest --findRelatedTests <suspect-file> -t "<failing test name>"
pytest tests/test_x.py::test_y -q
# still ambiguous over many commits? bisect the failing test only:
git bisect start HEAD <last-green-outer>
git bisect run npx jest -t "<failing test name>"
```
Then drop back to the INNER loop on the located file until it's green, and re-run OUTER once.

## Caveats

- **Selection ≠ safety.** `--findRelatedTests` / `vitest related` / `--testmon` follow static or
  recorded import graphs; they miss runtime seams (subprocess spawns, IPC, file/DB side effects,
  mocked boundaries). That blind spot is *why* the OUTER loop keeps the held-out golden-journey —
  it exercises the real A→B→C path the selection can't model.
- **Type-check is project-wide by nature.** TS types cross files, so `tsc --noEmit` can't be a
  single-file op — use `--incremental` so it's still cheap in the INNER loop.
- **Coverage is an OUTER-only metric.** Never gate an inner edit on coverage %; it's a
  commit-boundary threshold, and it is necessary-but-not-sufficient (see seed-golden-journey).
- **Mutation is a micro-check, not a suite.** Scope it to the changed files (`--mutate <file>`);
  a full-tree mutation run belongs in CI, not the commit loop.
- **Config/dep/test-infra edits void selection** — always OUTER (rule 3).

## Three ways a green OUTER loop still lies (each measured, not hypothesised)

The OUTER loop is the merge signal, but it is measured against *your* working tree, on *your*
box, by *your* tests. Each of those three is a place a green has been wrong here.

### 1. WORKING-TREE green ≠ CLONE green

Measured: a suite reported **3,910 passed** in the working tree and **31 collection errors** from
a fresh clone of the *same commit*. The gap is everything the tree has that the commit does not —
untracked files, stale `__pycache__`, an editable install, a local `conftest.py`, a path that only
resolves because of where you happen to be standing. CI checks out a clone, so the clone is the
one that counts.

```bash
git clone --no-hardlinks "C:/Users/you/source/<repo>" /tmp/clonecheck   # Windows-style path:
cd /tmp/clonecheck && git checkout <sha> && <install> && <full suite>   #   MSYS mangles /c/...
```

Do this before any "ready to merge" claim on a repo whose suite you have never run cold. Note the
path form: use `C:/Users/...`, not `/c/Users/...` — and do **not** set `MSYS_NO_PATHCONV=1`
globally to work around it, because that suppresses the conversion the clone path itself needs
and the clone then silently does not happen.

### 2. LOCAL formatter green ≠ CI formatter green (CRLF vs LF)

Your working tree is CRLF; git stores LF; CI checks out LF. Formatters make different decisions
on the two forms — measured: `ruff format --check` said *"1 file already formatted"* locally while
CI said *"Would reformat"* for the same commit. Verify against the **stored blob**:

```bash
git show <rev>:<path>          # LF, exactly what CI checks out
git cat-file -p "$(git rev-parse <rev>:<path>)"
```

**Never `git archive` for this.** Re-measured on two files in this repo, with a control proving
all routes are byte-identical after LF-normalisation (so the delta is purely EOL, not content):
`git show` and `git cat-file -p` → 7,487 B / **0 CRLF**; `git archive` + `tar -x` and the working
tree → 7,627 B / **140 CRLF**. `git archive` applies export-time EOL conversion and hands back
exactly the bytes you were trying to look past. Pin the tool version too (`uvx ruff@<pinned>`) —
a local 0.15.22 and a CI 0.15.17 format differently.

### 3. A green SUITE is not a green DETECTOR

A gate that has never gone red is indistinguishable from a no-op. Two in-repo instruments exist
for this and are worth naming because they are otherwise unreachable — neither is referenced by
any skill, hook, or (for the first) any CI job:

- **`tools/detector-self-test/`** — the both-states harness: run a probe against the KNOWN-BROKEN
  state and require it to FIRE there before its silence counts as "fixed".
- **`tools/measure-guard/`** — `suitefloor` (a run below its declared minimum test count FAILS
  regardless of exit code — it is the §1 clone-vs-tree gap turned into a gate), `refcheck`,
  `wudeps`, `jsonparse` and `vendordrift` are executed by `.github/workflows/quality.yml`
  (`:114`, `:439-443`). **`blobread` is NOT** — grep it and you get exactly one hit,
  `quality.yml:416`, which is a *comment*. It is the §2 wrong-bytes reader and it is available
  as a library today, not as a gate. Naming a tool in a CI comment is not running it; count the
  step, not the mention.

The mutation micro-check in the OUTER loop is the same idea applied to the tests: revert a real
bug and require the suite to go red. One of six mutations surviving is a genuine hole, not noise.
