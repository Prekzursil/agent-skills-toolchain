# W-cti receipt

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: none remaining — all 8 milestones measured; skill cti-lookup delivered.

Wave: **W-cti** — deliver skill `cti-lookup` (borrow cti-expert defang/refang +
STIX 2.1 export + report skeleton; route to osint `vt_*`, cve-mcp, and the
darknet-mcp-server full 66-tool surface). Do NOT install a 67-command orchestrator.

Owned paths (ONLY these):
- `.agents/skills/cti-lookup/**`
- `skills/cti-lookup/**`
- `docs/plans/cyber-receipts/W-cti.md`

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Receipt skeleton written | DONE 2026-09-02 |
| 2 | Tests-first (no network) authored | DONE 2026-09-02 |
| 3 | defang/refang + STIX export implemented, tests green | DONE 2026-09-02 |
| 4 | SKILL.md + references (routes, report skeleton) | DONE 2026-09-02 |
| 5 | agents/openai.yaml | DONE 2026-09-02 |
| 6 | ruff 0.15.17 check + format clean | DONE 2026-09-02 |
| 7 | Dual-write `skills/cti-lookup/` verified identical | DONE 2026-09-02 |
| 8 | Path-scoped commit + push | DONE 2026-09-02 |

## Test results

`python3 -m pytest .agents/skills/cti-lookup/tests/ -q` -> **40 passed** (~0.10s),
stdlib-only, no network. Suites:
- `test_ioc_defang.py` — defang/refang + roundtrip property; offline IOC extraction
  (IPv4/URL/email/domain/MD5/SHA-1/SHA-256/CVE), domain-in-URL/email de-dup, CLI.
- `test_stix_export.py` — STIX 2.1 patterns, quote-escaping, deterministic
  indicator/vulnerability ids (uuid5 over type:value), bundle assembly + ordering, CLI.

Dual-write parity: `skills/cti-lookup/tests` also runs **40 passed**; full-tree
`diff -r .agents/skills/cti-lookup skills/cti-lookup` is empty (8 files each).
End-to-end CLI smoke: `ioc_defang.py extract` pulls URL/md5/CVE from defanged text;
`stix_export.py` emits a `bundle` with `indicator` + `vulnerability` objects.

## Ruff

`ruff 0.15.17` on `.agents/skills/cti-lookup/`: `ruff check` -> All checks passed;
`ruff format` applied, `ruff format --check` -> 4 files already formatted.

## Routes documented (real tool names)

Three registered passive-lookup MCPs (parent owns the registrations). Real tool
names verified 2026-09-02 against upstream READMEs (badchars, MIT). Full tables +
env keys in `.agents/skills/cti-lookup/references/routing.md`.

- **osint-mcp-server `vt_*` reputation:** `vt_domain`, `vt_ip`, `vt_url`,
  `vt_subdomains` (`VT_API_KEY`); preflight `osint_list_sources`.
- **cve-mcp metadata:** `nvd_get`, `epss_score`, `kev_check`, `cpe_match`,
  `cve_enrich`, `cve_to_attack`; preflight `cve_list_sources`.
- **darknet-mcp-server FULL 66 tools / 16 sources:** Tor(7), ransomware(9),
  HIBP breach(7), abuse.ch ThreatFox/URLhaus/MalwareBazaar(9), OTX(5),
  AbuseIPDB(4), GreyNoise(2), Pulsedive(3), Hudson Rock stealer logs(3),
  Vulners(3), blockchain(4), Hybrid Analysis(3), CIRCL `onion_lookup`(1),
  IntelligenceX(4), PhishTank(1), meta(1) = **66**. Tor `.onion` tools degrade
  when SOCKS (`TOR_SOCKS_HOST`/`TOR_SOCKS_PORT`, default `127.0.0.1:9050`) is down.

Envelope enforced in SKILL.md: retrieved intel is untrusted data; lookup never
authorizes/invokes an executor; discovered assets do not auto-enter scope;
stealer-log lookups (Hudson Rock/IntelX/HIBP) are CTI, not stealer-building.
No exploits/C2. No `agents.json` edits. Only cti-expert *technique* borrowed
(defang/refang, STIX 2.1 export, report skeleton) — no 67-command orchestrator.

## Commit SHA

- `9d8ade3f` — receipt skeleton (UNKNOWN markers)
- `f2bd57ce` — defang/refang + STIX 2.1 export scripts + tests (both trees)
- `5a95da74` — SKILL.md + references (routing, report skeleton) + openai.yaml (both trees)
- this commit — receipt finalize (see `git log` for its SHA)

## PARENT MERGE

None required. The three routed servers are already registered in
`.agents/agents.json` (verified 2026-09-02): `cve-mcp@0.2.0` (41 tools),
`osint-mcp-server@0.2.0` (37 tools), and `darknet-mcp-server@0.1.1` (66 tools,
FULL search surface per G6 — onion/IntelX/Hudson Rock wired, Tor via
`TOR_SOCKS_HOST`/`PORT`). This wave documents the routes only and adds no registry
blocks; it does not touch `.agents/agents.json`.
