# W-dfir receipt — `dfir-triage` skill

**Wave:** W-dfir (DFIR beyond memory + disk)
**Branch:** `cursor/cyber-suite-full-program`
**Owner files (ONLY these):** `.agents/skills/dfir-triage/**`, `skills/dfir-triage/**`, `docs/plans/cyber-receipts/W-dfir.md`
**Status: DONE — measured 2026-09-02.**

## Status

- Skeleton written: DONE (commit `35c4c6ff`).
- Skill authored: DONE (commit `0df87a69`).
- Dual-write mirror byte-identical: DONE — `diff -r .agents/skills/dfir-triage skills/dfir-triage` → `IDENTICAL`.
- Script tests pass: DONE — 12 passed on each tree (`pytest -p no:cacheprovider`).
- ruff check / format clean: DONE — ruff 0.15.17, `All checks passed!` + `4 files already formatted`.
- Committed + pushed: DONE — pushed to `origin/cursor/cyber-suite-full-program`.

## Scope delivered

Skill `dfir-triage` covers the gap beyond `volatility-3` (memory) and
`offline-linux-disk-surgery` (disk). Markdown-first: `SKILL.md` is the workflow +
golden rules; each lane is a `references/*.md`; one tested stdlib helper ships in
`scripts/`.

- EVTX / Sigma: Chainsaw, Hayabusa — DONE (`references/evtx-sigma.md`).
- Artifact parse: dissect (one pip) + EZ Tools / KAPE — DONE (`references/artifact-parse.md`).
- Windows: EZ Tools / KAPE — DONE (`references/artifact-parse.md`).
- Timeline: Plaso (`log2timeline`/`psort`) — DONE (`references/timeline.md`).
- Live response: Velociraptor **offline collector only** — DONE (`references/live-response.md`); explicit hard boundary: no server/agent/callback/C2.
- Network: tshark / Zeek / Suricata, pcap **file mode**, 0 daemon — DONE (`references/network-forensics.md`).
- Cloud/host: varc, container-explorer, cloudgrep, Invictus log kit — DONE (`references/cloud-host-triage.md`).
- Email/phishing triage — DONE (`references/email-phishing.md`).

## Non-duplication (LINK, do not duplicate)

- Memory forensics stays in `volatility-3` — DONE: linked from `SKILL.md`, `references/stop-rules.md`, `references/upstream.md`, `references/live-response.md`; no memory-analysis content added here.
- Disk surgery stays in `offline-linux-disk-surgery` — DONE: linked from the same files; no disk-repair/resize content added here.

## Stop rules encoded

`references/stop-rules.md` + the `SKILL.md` "Golden rules" section encode:
- Owner-authorized evidence only; discovered assets do not auto-enter scope.
- Preserve hashes/offsets (mechanized by `scripts/evidence_manifest.py`); work on read-only copies.
- No C2; no live response beyond the offline collector; no daemons/sensors (pcap file mode only); no detonation.
- Hand binaries to the RE skills (`capa-triage` → `malware-analysis-triage` / `reverse-engineering-toolkit`); memory → `volatility-3`; disk → `offline-linux-disk-surgery`.

## Helper script (tests + fakes, no live network)

`scripts/evidence_manifest.py` — stdlib-only, offline, **read-only** chain-of-custody
hasher: per-file digest with optional `--offset`/`--length` byte range (so carved
regions keep provenance), `--json` or table output. It never writes, moves, or
executes evidence. Tests: `scripts/tests/test_evidence_manifest.py` — 12 pytest
cases over tmp-file fakes (full-file digest vs hashlib, offset/length slice, EOF
clamp, alt algo, invalid algo, missing file, directory, multi-file manifest, JSON
exit 0, table exit 0, missing-file exit 1, no-args usage exit 2).

## Verification commands (measured 2026-09-02)

```
export PATH="$HOME/.local/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
python3 -m pytest -p no:cacheprovider -q .agents/skills/dfir-triage/scripts/tests/   # 12 passed
python3 -m pytest -p no:cacheprovider -q skills/dfir-triage/scripts/tests/           # 12 passed
ruff check   .agents/skills/dfir-triage/scripts/ skills/dfir-triage/scripts/         # All checks passed!
ruff format --check .agents/skills/dfir-triage/scripts/ skills/dfir-triage/scripts/  # 4 files already formatted
diff -r .agents/skills/dfir-triage skills/dfir-triage                                # IDENTICAL
```

Honest scope note: the wrapped DFIR CLIs (Chainsaw, Hayabusa, dissect, Plaso,
Velociraptor, tshark/Zeek/Suricata, varc, container-explorer, cloudgrep, EZ
Tools/KAPE) are **host-gated and not installed in this cloud VM**, so they were
not executed here — the skill wraps and documents them (wrap-don't-vendor). Only
the shipped stdlib helper was run and tested.

## Artifacts

- Skill paths: `.agents/skills/dfir-triage/` (canonical) and `skills/dfir-triage/` (dual-write mirror).
- Files (13 per tree): `SKILL.md`, `agents/openai.yaml`, `references/{evtx-sigma,artifact-parse,timeline,live-response,network-forensics,cloud-host-triage,email-phishing,stop-rules,upstream}.md`, `scripts/evidence_manifest.py`, `scripts/tests/test_evidence_manifest.py`.
- Commit SHA (skill delivery): `0df87a69` — "W-dfir: add dfir-triage skill ...".
- Commit SHA (receipt skeleton): `35c4c6ff`.

## PARENT MERGE

None. This wave introduces a Markdown-first skill plus one tested, offline,
read-only helper script. No shared-file edits and no `.agents/agents.json`
registration are required for `dfir-triage`: every wrapped tool is a host-gated CLI
invoked ad hoc, not an MCP server. `agents/openai.yaml` follows the sibling
`volatility-3` shape (`interface:` with quoted `display_name`/`short_description`/`default_prompt`).
