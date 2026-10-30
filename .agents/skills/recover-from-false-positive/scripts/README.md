# scripts

Operational scripts for the recover-from-false-positive skill.

- `scrub_refusals.py` — JSON-aware .jsonl log surgeon (dry-run by default, `--apply` to
  write; tar.gz backup first; refuses any edit that would increase dangling parentUuids).
  Modes: plain (scrub-all), `--fix-active`, `--desaturate [--file]`, `--handoff`,
  `--backtest`, `--selfcheck`, `--latest`.

Vendored from https://github.com/88plug/recover-from-false-positive (FSL-1.1-ALv2).
