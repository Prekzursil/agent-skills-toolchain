---
name: Codacy engines.eslint.exclude_paths is silently ignored
description: Codacy's .codacy.yaml `engines.<name>.exclude_paths` works for the `metric`
  engine but is silently ignored by ESLint (and probably other plugin engines). Use
  top-level `exclude_paths` instead.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-codacy-per-engine-exclude-paths
---

When you want Codacy to skip specific files for a specific engine (e.g. "don't run ESLint on these vendored .ts files"), the intuitive config is:

```yaml
engines:
  eslint:
    enabled: true
    exclude_paths:
      - "scripts/beads-fetch-conversation-history.ts"
      - "scripts/beads-fetch-pr-comments.ts"
      - "scripts/beads-self-reflect.ts"
```

**This silently doesn't work for ESLint.** Codacy ignores the `exclude_paths` key under `engines.eslint`. The findings keep being emitted on the listed files.

The same key DOES work for the `metric` engine — verified on QZP's `engines.metric.exclude_paths` listing ~20 files that legitimately have high complexity but should be excluded from the +10 PR-delta cap. Those files don't get flagged.

So the bug is engine-specific. As of 2026-04-28 it's confirmed broken at least for ESLint.

**Reliable mechanism: top-level `exclude_paths` array.** This excludes the listed files from ALL engines (Codacy itself + all plugin engines).

```yaml
exclude_paths:
  - "scripts/beads-fetch-conversation-history.ts"
  - "scripts/beads-fetch-pr-comments.ts"
  - "scripts/beads-self-reflect.ts"
  # ... plus existing
  - "generated/**"
  - "tests/**"
  - "profiles/**"
```

**Tradeoff:** ALL engines skip the file (including DeepScan, Semgrep, etc., not just the noisy one). For files that are vendored/auto-generated/intentionally outside QA scope, this is usually what you want anyway.

**How to apply:**
- If you find yourself adding `exclude_paths` under `engines.<name>:` and Codacy keeps emitting findings on those files, move them to the top-level `exclude_paths` instead.
- The deprecated TSLint + JSHint engines respect `engines.<name>.enabled: false` (verified — they stop running entirely). Per-engine `exclude_paths` is the unreliable knob.

**Discovered in:** QZP PR #186 (added engines.eslint.exclude_paths) → didn't work → PR #188 moved to top-level. Confirmed live: Codacy main analysis at 2026-04-28T11:34:17 still emitted ~150 ESLint findings on the listed files even with the per-engine exclude in place.