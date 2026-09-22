# AUD-0033 detector control fixture

Fenced path that MUST be extracted:

```
command-center/WORK-UNIT-CATALOG.json
```

Also a source-relative path that exists next to this fixture:

`local-rel-target.txt`

Dot-directory path that must resolve as EXISTS:

`.agents/skills`

Known-good repo paths:

- `docs/agentic-perfection/CHANGELOG.md` may or may not exist; extractor still emits it
- `scripts/claude-science/cs-doctor.ps1` may or may not exist; extractor still emits it

Planted typo that must be MISSING / NEVER-EXISTED:

`command-center/does-not-exist-AUD0033-typo.json`

Prose with slashes that must NOT become path tokens: the input/output ratio and this/that distinction are ordinary English, not filesystem paths.
