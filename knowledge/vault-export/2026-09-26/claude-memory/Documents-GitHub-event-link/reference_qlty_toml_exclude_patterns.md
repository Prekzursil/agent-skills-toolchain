---
name: qlty.toml exclude_patterns vs [[exclude]] block
description: Top-level exclude_patterns scopes qlty's NATIVE smells; [[exclude]] block
  is plugin-scoped only. Use top-level array for file_complexity/duplication/return_statements
  exclusions.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-qlty-toml-exclude-patterns
---

When qlty (the qlty.sh CLI) reports the deprecation warning "The [[ignore]] field in qlty.toml is deprecated. Please use [[exclude]] or exclude_patterns instead," picking the wrong replacement leaves native smells flagged.

**Two different exclusion mechanisms:**

1. **Top-level `exclude_patterns` array** — scopes qlty's NATIVE smells (file_complexity, function_complexity, return_statements, duplication, line-too-long, etc.) PLUS all plugin runs. This is what you almost always want for "exclude this directory from analysis entirely."

   ```toml
   config_version = "0"

   exclude_patterns = [
       "ent/**",
       "**/ent/**",
       "static/**",
       "**/static/**",
       "**/*.[0-9a-f]*.js",  # webpack hash-name bundles
   ]
   ```

2. **`[[exclude]]` block** — plugin-scoped only. Requires a `plugins` field. Native smells IGNORE this block.

   ```toml
   [[exclude]]
   plugins = ["eslint", "prettier"]  # or ["*"] for all plugins
   file_patterns = ["specific-tool-paths/**"]
   ```

**The trap:** Migrating `[[ignore]]` → `[[exclude]] plugins=["*"]` makes qlty stop emitting the deprecation warning, but qlty's native smell engine still scans everything because the `[[exclude]]` block doesn't influence smell scope. Result: you "fix" the warning and still get hundreds of smell findings on minified bundles, generated code, etc.

**How to apply:**
- For broad scope correction (skip generated/vendored/minified directories from ALL analysis), use top-level `exclude_patterns`.
- For plugin-specific exclusions (e.g. "don't run prettier on this Go file"), use the `[[exclude]]` block.
- When migrating from deprecated `[[ignore]]`, default to top-level `exclude_patterns` unless you specifically need per-plugin scoping.

**Discovered in:** devextreme PR #25 (2026-04-28). Initial migration from `[[ignore]]` to `[[exclude]] plugins=["*"]` left ~50 minified-bundle complexity findings until moved to top-level `exclude_patterns`.

**Reference:** https://docs.qlty.sh/qlty-toml