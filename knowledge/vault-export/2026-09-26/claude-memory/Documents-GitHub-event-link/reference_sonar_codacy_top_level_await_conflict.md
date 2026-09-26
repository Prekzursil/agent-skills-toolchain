---
permalink: main/claude-memory/documents-git-hub-event-link/reference-sonar-codacy-top-level-await-conflict
---

---
name: Sonar S7785 vs Codacy ESLint no-unused-expressions on top-level await
description: Direct rule conflict — Sonar's javascript:S7785 requires top-level await; Codacy's ESLint no-unused-expressions rejects bare await as expression statement. Resolution: follow Sonar's preferred form, silence Codacy's rule per-line with `// eslint-disable-line no-unused-expressions`.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
---
The QZP `provider_admin_bootstrap.mjs` bootstrap pattern hit a direct
linter conflict (PR #214 series, took 4 attempts to resolve):

- **Sonar `javascript:S7785`**: "Prefer top-level await over using a
  promise chain." → fires on `.then()` chain forms.
- **Codacy ESLint `no-unused-expressions`**: rejects bare top-level
  `await fn();` as an unused expression statement.

Resolution: follow Sonar's preferred form (top-level await is the
modern Node ES module idiom) and silence Codacy with the **rule-less**
inline directive:

```js
// eslint-disable-next-line
await someAsyncFn();
```

**Important:** Specifying the rule name explicitly does NOT work on
Codacy's ESLint engine. The rule-less form (no rule listed after
`disable-next-line`) is what reliably overrides the rule:

- ❌ `await fn(); // eslint-disable-line no-unused-expressions` (didn't suppress on PR #214 attempt 4)
- ❌ `// eslint-disable-next-line no-unused-expressions\nawait fn();` (didn't suppress on PR #214 attempt 1)
- ✅ `// eslint-disable-next-line\nawait fn();` (suppressed on PR #214 attempt 5)

The bare disable form bypasses Codacy's rule-name matching, which
is broader than ideal — but the line below is a single statement so
collateral suppression is bounded.

**Second-order conflict (PR #214 attempt 5+):** Sonar's
``javascript:S7724`` ("Specify the rules you want to disable") fires
on bare ``// eslint-disable-next-line``, demanding rule names. So
specifying rule names → Codacy's expr fires; leaving them off →
Sonar's S7724 fires. **Exactly one finding remains regardless.**

**Third-order resolution (PR #215):** A multi-rule list works on
PR scope but not main scope:
``// eslint-disable-next-line no-unused-expressions, no-void, no-floating-promises``

- Sonar S7724: satisfied (rules listed)
- Codacy expr (PR scope): satisfied (Codacy honors at least one rule name in the list, presumably ``no-unused-expressions``)
- Codacy expr (main scope): **still fires** — Codacy's main-scope analyzer does NOT honor the inline disable comment the same way as PR-scope analyzer

Verified on commit ``02b21ff`` (PR #215 squash on main): Codacy main
shows 1 expr finding even though PR #215 reported isUpToStandards=True
with 0 newIssues. ``defaultBranch.lastCommit`` was up-to-date.

This is a Codacy product-side asymmetry, not fixable code-side.
The fleet's strict-zero floor for this single line is **1 Codacy
finding on main**, regardless of comment form. Document and move on.

**Final resolution (PRs #216-#218): async IIFE + bare NOSONAR.**

Step 1 (PR #216): Async IIFE pattern. Sidesteps the
entire inline-disable-comment dependency by changing the code shape:

```js
(async () => {
  await runCliIfEntrypoint(import.meta.url);
})();
```

Why this works:
- The outer ``(...)()`` is a function call — ESLint's
  ``no-unused-expressions`` accepts function calls as valid
  expression statements (Codacy expr clean)
- Inside the IIFE, the await is in an async function body — Sonar's
  ``javascript:S7785`` ("prefer top-level await") only fires on
  ``.then()`` chains at the top scope, not awaits nested in async
  function bodies (Sonar S7785 clean)
- No inline disable comments needed → no Sonar S7724 trigger, no
  Codacy PR-vs-main asymmetry

**Verified on PR #216 + QZP main (commit 79639ac):** Codacy
isUpToStandards=True with 0 newIssues; Sonar PR scope 0 issues;
QZP main reanalysis confirmed Codacy=0 and Sonar=0/0/0/0.

The IIFE is the canonical pattern for top-level async work in JS
ES modules without triggering linter no-unused-expressions or
prefer-top-level-await rules. Use this any time a bootstrap
entrypoint needs to await async work.

**Step 2 (PR #218): Bare `// NOSONAR` for IIFE.** Sonar's S7785
has 3 firing conditions (discovered empirically, not in rule docs):
1. Bare top-level await (also fires Codacy expr)
2. `.then()` chain at top scope (documented S7785 message)
3. **Async IIFE at top scope** (NOT documented)

The IIFE form trips S7785 too. Resolution: bare `// NOSONAR` (no
rule suffix or description) on the IIFE opening line:

```js
(async () => { // NOSONAR
  await someAsyncFn();
})();
```

**Important:** Like Codacy's eslint-disable, Sonar's NOSONAR is
**only honored in the bare form**. Suffixed forms like
`// NOSONAR javascript:S7785 — explanation` are treated as
plain comments, not directives. Verified on QZP main commit
post-#218 (Sonar issue-search returned total=0).

Place reason text in a multi-line block comment ABOVE the
suppressed line so Sonar's parser sees only the bare directive.

Why other approaches failed:

- `const _x = await fn();` → triggers `no-unused-vars`. Underscore
  prefix isn't enough on Codacy's ESLint config.
- `if (ranAsCli) { process.exitCode ??= 0; }` → satisfies both
  linter rules but introduces a new branch with no test coverage,
  breaking the Coverage 100 Gate.
- `fn().then(() => {})` → satisfies Codacy but trips Sonar S7785.
- `void await fn();` → forbidden by `typescript:S3735`
  (per CLAUDE.md: void-prefix on async-call is unnecessary).

The eslint-disable-line directive is the canonical per-line escape
for ESLint rules in JS source. Codacy's ESLint engine honors it.