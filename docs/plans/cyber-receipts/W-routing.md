# W-routing receipt

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: routing-doc, harness-router, classifier, tests, dual-write, ruff, git — all UNKNOWN

## Wave

W-routing — route the dark tools (TIER-0). Add the VirusTotal `vt_*` IOC row + unrouted
`cve-mcp` tools to `security-mcp-routing.md`; add `ioc` / `attack` capabilities to the
deep-research router mirroring `vuln`. Path-scoped, dual-write, no registry edits.

## Files owned (ONLY these)

- `.agents/skills/hacktricks/references/security-mcp-routing.md`
- `skills/hacktricks/references/security-mcp-routing.md`
- `agent-self/skills/hacktricks/references/security-mcp-routing.md`
- `.agents/skills/deep-research/references/research_harness/routing.py`
- `.agents/skills/deep-research/references/tests/test_routing.py`
- `.agents/skills/deep-research/SKILL.md`
- `skills/deep-research/references/research_harness/routing.py`
- `skills/deep-research/references/tests/test_routing.py`
- `skills/deep-research/SKILL.md`
- `docs/plans/cyber-receipts/W-routing.md`

## Claims (rewrite at each milestone)

- Routing doc `vt_*` IOC row added (PASSIVE, no scope expansion): UNKNOWN - not yet measured
- Routing doc unrouted cve tools (`osv_batch`, `cve_report`, `ghsa_search`/`ghsa_get`): UNKNOWN - not yet measured
- Routing doc note `m365_*` / `dns_email_security` are osint-mcp-server (not cve-mcp): UNKNOWN - not yet measured
- Envelope preserved (no Nuclei/Metasploit execution): UNKNOWN - not yet measured
- Harness `ioc` capability wired (osint `vt_*`): UNKNOWN - not yet measured
- Harness `attack` capability wired (mitre-attack-mcp, degrade-to-web): UNKNOWN - not yet measured
- Classifier keywords hash/ioc/virustotal -> ioc: UNKNOWN - not yet measured
- Classifier keywords mitre/att&ck/technique T1xxx -> attack: UNKNOWN - not yet measured
- Classifier false-positive guards: UNKNOWN - not yet measured
- test_routing.py extended + passing (both trees): UNKNOWN - not yet measured
- test_skill_consistency passing (both trees): UNKNOWN - not yet measured
- Dual-write trees identical: UNKNOWN - not yet measured
- ruff check + format clean: UNKNOWN - not yet measured
- Capability names actually wired: UNKNOWN - not yet measured
- Commit SHA: UNKNOWN - not yet measured

## PARENT MERGE

UNKNOWN - not yet measured
