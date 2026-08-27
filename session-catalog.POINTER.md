# session-catalog.md — pointer (the catalog itself is NOT in git)

The live session catalog is `C:\Users\Prekzursil\.agents\session-catalog.md` (~378 KB,
machine-generated, regenerated constantly). It is deliberately excluded from version
control twice: by the `session-catalog.md` entry in `$ExcludeFilePatterns` of
`scripts/sync-from-live.ps1` and by a `.agents/session-catalog.md` line in the toolchain
repo's `.gitignore`. Staging it crashed a git daemon on 27.08.2026; a churning 378 KB
generated blob has no place in history.

This pointer exists so the capture gap is documented rather than silent. Do not "fix"
the absence by committing the catalog — regenerate it on the live machine instead.
