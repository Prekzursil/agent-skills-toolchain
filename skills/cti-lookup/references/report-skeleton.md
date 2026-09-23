# CTI report skeleton

Borrowed technique (report skeleton) — fill in from lookup results. Keep IOCs
**defanged** in prose (`scripts/ioc_defang.py defang`); ship the live,
machine-readable copy as the STIX 2.1 bundle. Every claim carries provenance;
absence of evidence is `unknown`, not `clean`.

```markdown
# CTI report: <subject>

- Report ID / date: <id> / <YYYY-MM-DD>
- Analyst: <name>
- Scope + authorization: <engagement id / owner-estate basis>
- Confidence: high | medium | low
- TLP: CLEAR | GREEN | AMBER | RED

## 1. Summary
<2-4 sentences: what the indicator/CVE is, verdict, and the recommended action.>

## 2. Indicators (defanged)
| IOC (defanged) | Type | Verdict | Sources | First/Last seen |
|----------------|------|---------|---------|-----------------|
| evil[.]com | domain | malicious | vt_domain, threatfoxSearch, otx_domain | ... |
| 8[.]8[.]8[.]8 | ipv4 | benign-scanner | greynoise_ip, abuseipdb_check | ... |
| <md5/sha256> | file | AgentTesla | bazaarHash, malware_overview, otx_hash | ... |

## 3. Reputation + enrichment
- VirusTotal (`vt_*`): <detections / categories / ASN>
- GreyNoise / AbuseIPDB / Pulsedive: <classification, abuse confidence, risk>
- abuse.ch (ThreatFox / URLhaus / MalwareBazaar): <IOC/family/tag hits>
- AlienVault OTX: <pulses referencing the indicator>

## 4. Exposure (breach / stealer logs) — owner-estate selectors only
- HIBP (`breachList`/`breachSearch`): <breaches, data classes>
- Hudson Rock (`stealer_domain`/`stealer_email`): <compromised machines, count>
- IntelligenceX (`intelx_search`): <paste/dark-web hits> (CTI lookup, not stealer-building)

## 5. Malware / campaign
- Family, MITRE ATT&CK techniques (from `malware_overview` / capa / `cve_to_attack`)
- Network IOCs (C2 domains/IPs) — defanged, added to section 2

## 6. Vulnerability context (if a CVE is in play)
- `nvd_get` metadata · `epss_score` · `kev_check` · affected CPEs (`cpe_match`)
- ATT&CK mapping via `cve_to_attack` (CWEs derived + verified)

## 7. ATT&CK mapping
| Tactic | Technique (ID) | Evidence |
|--------|----------------|----------|

## 8. Assessment
- Contradictions: <where sources disagree>
- Unknowns: <what was not resolvable>
- Source failures: <providers down / no key / rate-limited / Tor offline>

## 9. Recommended defensive actions
- Detections to write/validate (-> $detection-as-code)
- Blocklist/feed additions (defanged IOCs -> STIX bundle attached)
- Credential resets / hardening (if exposure found)

## 10. Provenance
- Providers + tool + version, corpus/schema hash, retrieved-at per finding
- STIX 2.1 bundle: <path> (indicator + vulnerability SDOs, uuid5 ids)
```

## STIX 2.1 bundle

Generate the machine-readable companion with `scripts/stix_export.py` (reuses
`ioc_defang.extract_iocs`, so it accepts raw or defanged report text):

```bash
python3 scripts/stix_export.py "$(cat report_body.txt)" > iocs.stix.json
# or pin a timestamp for reproducible bundles:
python3 scripts/stix_export.py "$(cat report_body.txt)" --created 2026-09-02T00:00:00.000Z
```

The bundle contains an `indicator` SDO per network/file IOC (STIX patterns like
`[domain-name:value = 'evil.com']`, `[file:hashes.'SHA-256' = '...']`) and a
`vulnerability` SDO per CVE. Object ids are `uuid5(type:value)` so re-running over
updated text produces stable, diffable ids. It is a **skeleton** — enrich with
relationships, `kill_chain_phases`, `labels`, or a producing `identity` before
publishing to a TIP.
