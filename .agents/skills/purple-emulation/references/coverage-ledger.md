# Coverage ledger — ATT&CK Navigator + DeTT&CT

The per-atomic verdicts roll up into a **coverage ledger**: which ATT&CK techniques your
detections actually catch, measured by emulation rather than asserted on a slide. Two
consumers, one source of truth (the expected-hit manifest + the results file).

## ATT&CK Navigator layer

`detection_coverage.py --navigator layer.json` emits an ATT&CK Navigator v4.5 layer. Import it
at the offline Navigator (or the `mitre-attack-mcp` layer surface) to see coverage as a heatmap.

Score / colour mapping:

| verdict | score | colour | reading |
|---|---|---|---|
| `DETECTED` | 100 | green `#4caf50` | technique exercised and caught |
| `PARTIAL` | 50 | amber `#ffb300` | partial visibility — tune the rule |
| `MISSED` | 1 | red `#e53935` | exercised, not caught — a gap |
| `UNVERIFIED` | 0 | grey `#bdbdbd` | no expected detection declared |

The layer carries a `gradient` and `legendItems` so the colours render without hand-config.
Only techniques present in the manifest are scored; the map is honest about what was actually
emulated, not the full ATT&CK matrix painted green.

## DeTT&CT

DeTT&CT (rabobank-cdc) scores **detection coverage and data-source quality** over time. This
skill's manifest is compatible input:

- `technique` + `expected_detections` map to DeTT&CT's technique-to-detection scoring.
- `data_sources` map to DeTT&CT's data-source administration (what telemetry *should* exist).
- Feed the manifest/results into a DeTT&CT techniques-administration YAML to track a detection's
  maturity (from "no coverage" → "good") across repeated emulation rounds.

The Navigator layer is the *snapshot*; DeTT&CT is the *trend*. Use the checker for the snapshot
and gap backlog; graduate to a DeTT&CT admin file when you need coverage-over-time.

## The gap backlog

The point of the ledger is the **MISSED/PARTIAL** list — the detection-engineering backlog.
The checker prints it (and exits `1` when it is non-empty) so a CI job can gate on "no new
coverage regressions". Each gap is a ticket for `detection-as-code`:

1. author or fix the Sigma/EDR rule,
2. re-emulate the same atomic,
3. confirm the verdict flips to `DETECTED`.

## claim-verify-gate ledger

`--ledger ledger.json` emits a `claim-verify-gate` ledger where each atomic is a claim
("detection fired for `Txxxx`"), with `source_probe` = the emulation and `verify_probe` = the
SIEM/EDR query (mechanically different). `DETECTED` → `CONFIRMED`, `MISSED` → `REFUTED` (with a
rewritten sentence naming the gap), `UNVERIFIED` → `UNVERIFIED` (with a settling experiment).
It is built to pass `claim_gate.py` so the coverage claims survive the same honesty gate as any
other load-bearing finding.
