# W-dfir receipt — `dfir-triage` skill

**Wave:** W-dfir (DFIR beyond memory + disk)
**Branch:** `cursor/cyber-suite-full-program`
**Owner files (ONLY these):** `.agents/skills/dfir-triage/**`, `skills/dfir-triage/**`, `docs/plans/cyber-receipts/W-dfir.md`

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

## Status

- Skeleton written: `UNKNOWN - not yet measured`
- Skill authored: `UNKNOWN - not yet measured`
- Dual-write mirror byte-identical: `UNKNOWN - not yet measured`
- Script tests pass: `UNKNOWN - not yet measured`
- ruff check / format clean: `UNKNOWN - not yet measured`
- Committed + pushed: `UNKNOWN - not yet measured`

## Scope delivered

Skill `dfir-triage` covers the gap beyond `volatility-3` (memory) and
`offline-linux-disk-surgery` (disk):

- EVTX / Sigma: Chainsaw, Hayabusa — `UNKNOWN - not yet measured`
- Artifact parse: dissect (one pip) — `UNKNOWN - not yet measured`
- Windows: EZ Tools / KAPE — `UNKNOWN - not yet measured`
- Timeline: Plaso — `UNKNOWN - not yet measured`
- Live response: Velociraptor offline collector only — `UNKNOWN - not yet measured`
- Network: tshark / Zeek / Suricata (0 daemon) — `UNKNOWN - not yet measured`
- Cloud/host: varc, container-explorer, Invictus/cloudgrep — `UNKNOWN - not yet measured`
- Email/phishing triage — `UNKNOWN - not yet measured`

## Non-duplication

- Memory forensics stays in `volatility-3` (LINK, do not duplicate) — `UNKNOWN - not yet measured`
- Disk surgery stays in `offline-linux-disk-surgery` (LINK, do not duplicate) — `UNKNOWN - not yet measured`

## Stop rules encoded

- Owner-authorized evidence only; no C2; preserve hashes/offsets; hand binaries to RE skills — `UNKNOWN - not yet measured`

## Verification commands

- `UNKNOWN - not yet measured`

## Artifacts

- Skill paths: `UNKNOWN - not yet measured`
- Commit SHA: `UNKNOWN - not yet measured`

## PARENT MERGE

None. This wave introduces a Markdown-first skill plus one tested, offline,
read-only helper script. No shared-file edits and no `.agents/agents.json`
registration are required for `dfir-triage` (all wrapped tools are host-gated
CLIs invoked ad hoc, not MCP servers).
