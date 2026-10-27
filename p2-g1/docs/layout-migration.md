# Layout migration

This document records the estate layout migration for TST-0256.

- Source of truth: repository paths under `command-center/` and `tools/`.
- Conversion is LF-normalized and path-separator independent.
- Probe control: a missing file is a detector, not a skip.

Converted POSIX path: `/docs/layout-migration.md`

| old path | new path | notes |
| --- | --- | --- |
| `src/` | `tools/` | production libraries |
| `cc/` | `command-center/` | catalogs and receipts |
| `handbook/` | `docs/` | operator documentation |

```
python tools/layout_migrate.py --apply
```
