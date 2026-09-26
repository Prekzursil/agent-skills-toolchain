---
name: Codacy Bandit ignores
description: Codacy's Bandit invocation does not honor inline `# nosec B603,B607`
  (ID-tagged) annotations — bare `# nosec` (no IDs) is honored. Use the bare form
  in QZP.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-codacy-nosec-id-tagged-ignored
---

Codacy's Bandit invocation strips/ignores `# nosec` annotations that
specify IDs in comma-separated form like `# nosec B603,B607`. The
issue persists even with current commits — verified on QZP commit
`16d97e3` where two `apply_deterministic_patches.py` subprocess.run
sites carrying `# noqa: S603,S607  # nosec B603,B607` continued to be
flagged by Bandit_B603 in Codacy's PR analysis.

The fix that works: switch to the **bare `# nosec`** form (no IDs).
Codacy honors that. Standalone Bandit CLI honors both forms.

This applies to:
- `scripts/quality/rollup_v2/apply_deterministic_patches.py:71,86`
- `scripts/quality/run_codex_exec.py:129`
- `scripts/quality/run_qlty_zero.py:194,212`
- Any future subprocess.run site in QZP

PR #206 documents this in code comments and was the first batch where
the pattern was reliably verified across 4 sites.