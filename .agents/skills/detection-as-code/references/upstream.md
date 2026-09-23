# Upstream notes — detection-as-code

Wrap, don't vendor. Every tool below is installed and invoked, never copied into this repo
(several are GPL/AGPL). Licenses are noted so a promotion decision is informed. All backtesting
is against lab / synthetic / owner-authorized logs only.

## Authoring, lint, convert

- **rsigma** — single Rust binary for Sigma write/lint/convert and `rsigma mcp serve` (the MCP
  the parent registers, host-gated). MIT. `https://github.com/wagga40/rsigma` (see the wave
  receipt for the exact `agents.json` block).
- **sigma-cli + pySigma** — reference CLI and validator/converter framework. LGPL-3.0.
  `pipx install sigma-cli` (or `pip install sigma-cli`); add backends with
  `sigma plugin install <backend>` (splunk, elasticsearch, microsoft365defender, ...).
  Validate: `sigma check <rules/>`. Convert: `sigma convert -t <backend> <rules/>`.
- **Sigma rule spec + rule repo** — `https://github.com/SigmaHQ/sigma` (rules: DRL 1.1;
  spec: `https://github.com/SigmaHQ/sigma-specification`). Use the spec's field names and
  `logsource` taxonomy so backend conversion resolves fields correctly.

## Test oracles (host-gated CLIs)

- **Zircolite** — standalone Sigma-on-EVTX/JSON/Auditd/Sysmon-for-Linux detector; writes a
  JSON array of matched-rule objects (`title`, `id`, `tags`, `count`, `matches`). AGPL-3.0.
  `https://github.com/wagga40/Zircolite`. Example:
  `python3 zircolite.py --evtx <sample.evtx> --ruleset <rules.json> --outfile out/sample.json`.
  Normalize with `detection_backtest.py normalize --oracle zircolite`.
- **Hayabusa** — fast Windows event-log Sigma engine (Rust). GPL-3.0.
  `https://github.com/Yamato-Security/hayabusa`. Example:
  `hayabusa json-timeline -d <evtx-dir> -J -o out/host.json` (`-J` = JSON array; each record
  carries `RuleTitle`, `Level`, `MitreTags`). Normalize with `--oracle hayabusa`.

Both are on-demand analyzers, not daemons. Pick one per environment; the normalizer output is
oracle-agnostic so a manifest is portable across them.

## Labelled log corpora (for backtest samples)

- **Cisco Talos EvidenceForge** — generates synthetic, labelled event logs for detection
  testing. `https://github.com/Cisco-Talos/EvidenceForge`. Best for deterministic CI fixtures.
- **EVTX-ATTACK-SAMPLES** — real attack EVTX grouped by ATT&CK technique (Sabajete Elezaj /
  @SBousseaden). `https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES`. Map each file to its
  technique in the manifest's `attack` list.
- **Security-Datasets / attack_data** — OTRF Security-Datasets and Splunk `attack_data` are
  larger labelled corpora for regression backtests.
  `https://github.com/OTRF/Security-Datasets`, `https://github.com/splunk/attack_data`.
- **sysmon-modular** — Olaf Hartong's modular Sysmon config, so lab telemetry matches the
  fields rules expect. `https://github.com/olafhartong/sysmon-modular`.

## Coverage ledger

- **ATT&CK Navigator** — renders the layer JSON `detection_backtest.py` emits.
  `https://mitre-attack.github.io/attack-navigator/`. Layer format version 4.5.
- **DeTT&CT** — scores detection/data-source coverage and diffs against a target technique set
  for the "still uncovered" list. GPL-3.0. `https://github.com/rabobank-cdc/DeTTECT`.
- **mitre-attack-mcp** (parent-registered, if enabled) — STIX-backed ATT&CK graph + Navigator
  layers offline against the attack-stix-data corpus.

## Expected-hit manifest schema

JSON object (YAML accepted when PyYAML is installed):

```
name:     string, optional — report/layer name.
samples:  list of objects, each:
  name:            string  — the sample log identifier (matches the results ledger `sample`).
  expect_fire:     [string] — rule titles/ids that MUST fire on this sample (true positives).
  expect_no_fire:  [string] — rule titles/ids that must NOT fire (false-positive guard).
  attack:          [string] — ATT&CK technique IDs this sample exercises (T1003.001, ...).
```

Results ledger (produced by `normalize`, consumed by `reconcile`):

```
results: list of { sample: string, fired: [string], attack: [string] }
```

Rule matching is case-insensitive on the identifier string. A technique is credited as covered
only when its sample passes, so the Navigator layer never overstates coverage.
