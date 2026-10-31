---
title: onion-research
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/onion-research
---

# onion-research — round-3 onion lane notes (2026-09-29)

Lane: "Deep-web research relevant to agentic offensive security: private red-team playbooks,
0day research teasers, C2 framework forks, cracked security-tool distributions."
Named engines: ahmia, onionland, torch, darksearch. READ-ONLY throughout: every fetch was a
plain GET of a public page; no registration, login, posting, transaction, or download of any
binary. Prior rounds: `deepweb-coverage.md` (round 1), `deepweb-coverage-round2.md` (round 2)
— not repeated, extended.

## 0. Environment state used this round

- Tor: already provisioned at `D:\opt\tor` (v0.4.9.13), SocksPort 9050 primary / 9150 fallback,
  scheduled task `TorProxy`. See `tor-setup.md` (updated 19:05 today).
- Verification run at start of this ask:
  `curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip` →
  `{"IsTor":true,"IP":"45.84.107.200"}`, exit 0. Tor CONFIRMED live.
- Gateway darknet backend still up: `out/research/_r2_gw.py tor_status {}` →
  `socksAvailable true 127.0.0.1:9050`.
- Ahmia helper `out/research/ahmia_search.py` (round-1 token trick) reused as-is.
- New helper this round: `out/research/_r3_batch.py` (3-engine batch; requests+PySocks —
  urllib cannot do socks5h) and `_r3_onionland.py` (onionland-only battery).
- Raw artifacts under `out/research/_r3/` (HTML/JSON per fetch) and
  `out/research/ahmia3_*.html`, `probe_*.html`, `onionlive_*.html`.

## 1. ENGINE STATUS 2026-09-29 — all four named engines exercised

| Engine | Address probed | Verdict (evidence) |
|---|---|---|
| Ahmia | ahmia.fi clearnet (token trick) | LIVE, best scripted engine. 25 queries this round. |
| **Onionland** | `http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion` | **LIVE + scriptable (server-rendered, form GET /search)**. Root 200 / 287,587 B, title "OnionLand Search Engine - Deep Web and Tor .onion Search". REVERSAL of round 2 ("down 0x01" at this same address). Address corroborated by `onion.live/site/onionland-search`. Results are FUZZY-match (lots of noise, ads) but it indexes surfaces Ahmia misses (found Dead Drop + cracked IDA dir). |
| DarkSearch (directory) | `http://darkzqtmbdeauwq5mzcmgeeuhet42fhfjj4p5wbak3ofx2yqgecoeqyd.onion` | **LIVE (rotated address!)** — 200 / 10,136 B, "DarkSearch - Your gateway to the dark web!". Round 2 had the older `darkzqtmebwf…` DOWN; this is a NEW address (rotation). GET `/search?q=…`; also `/d/<name>` resolver, `/fresh`, `/top-onions`, login.php. Footer: Dread /d/DarkSearch, Pitch (@darksearch → pitchprash4aqilfr7sbmuwve3pnkpylqwxjbj2q5o4szcfeea6d27yd.onion), TorWatch (xq5hcm32…), DNN (dnn5egjcgwx7kcysjffhmm7ciy4bchxhpo443azrcn23xbyq666uqxyd.onion). |
| DarkSearch (engine, separate service) | `http://engin5cbd7izh2dlmugwrvvegtltxefgiefs6fo7esurguckwblpjsad.onion` | **LIVE with keyless JSON API**: `GET /api/search?q=<q>&category=<cat>` → `{"success":true,"results":[],"total":0}` (schema verified live; corpus tiny — 0 results for all 6 security queries). Also `/api/categories`, `/api/recent`. "DarkSearch Engine — Anonymous .onion Search". |
| Torch (real) | `http://torchsfe235y6d7wguqo6g4ucxqq7frrm5fpgkjssdhthsq4kjmmisid.onion` | LIVE but search still NOT scriptable: `/search?search=cobalt%20strike` → 301 → `/search/?search=…` → 200 but only 5,222 B SPA shell (`resultsFiltersMenuWrapper`), no server-rendered results. Dead end confirmed for round 3 (matches round 1-2). Old `xh57jpkh…` remains a flagged MITM fake (round 1). |

Engine-address discovery path: Ahmia queries "onionland" (139 results) and "darksearch"
(33) + `curl https://onion.live/site/onionland-search` and `/site/darksearch` (both HTTP 200,
onion addresses in page). onion.live itself remains LIVE.

## 2. EVERY QUERY ISSUED THIS ROUND (chronological)

### Engine discovery
1. ahmia `onionland` → 139 results (found hidden-wiki clone farm, DARK WEB TOOLS dir
   uwhunapg…, Torgol engine torgol6s65…, Liberty Wiki v3al42du…, torwikij… mirrors,
   Piranha Market (drug market — noted, out of scope), Let's Decentralize rollcall hikariu7…,
   runfys… PGP-verify site)
2. ahmia `darksearch` → 33 results (found NEW dir address darkzqtmb…, engine engin5cbd…,
   runfys…/verify/darksearch mirrors)
3. curl `https://onion.live/site/onionland-search` → 45,378 B, address 3bbad7f…
4. curl `https://onion.live/site/darksearch` → 51,143 B, address darkzqtmb…
5. Tor probes (curl via 9050): darkzqtmb… 200/10,136 B; engin5cbd… 200/14,324 B;
   3bbad7f… 200/287,587 B.

### DarkSearch dir `/search?q=` (all → "No results found" — tiny curated corpus)
6. `cobalt strike` 7. `dread` (calibration — returned 1 verified hit proving parser)
8. `red team playbook` 9. `0day` 10. `c2 framework` 11. `cracked burp`

### DarkSearch engine `/api/search?q=` (all → `{"success":true,"results":[],"total":0}`)
12. same 6 terms as above.

### Onionland `/search?q=` (17 queries, all 200, 8-24 fuzzy results each)
13. `cobalt strike` 14. `red team playbook` 15. `0day` 16. `c2 framework` 17. `cracked burp`
18. `brute ratel` 19. `havoc c2` 20. `mythic c2` 21. `sliver c2` 22. `cracked cobalt strike`
23. `cracked ida` 24. `exploit broker` 25. `zero day` 26. `red team tools` 27. `metasploit`
28. `nuclei` 29. `dread`

### Ahmia (25 queries this round; token trick; raw in ahmia3_*.html / ahmia_q_onionland.html)
30. `onionland` (139) 31. `darksearch` (33) 32. `red team playbook` (63) 33. `red team wiki` (201)
34. `pentest playbook` (76) 35. `0day` (88) 36. `0day exploit` (214) 37. `exploit broker` (529)
38. `cobalt strike` (28) 39. `brute ratel` (97) 40. `havoc c2` (25) 41. `mythic c2` (101)
42. `sliver c2` (24) 43. `cracked cobalt` (26) 44. `cracked ida` (22) 45. `cracked burp` (22)
46. `red team tools` (7) 47. `offensive toolkit` (19) 48. `红队` (111) 49. `免杀` (125)
50. `cobaltstrike 破解` (74 — noise: drug-market fuzzy matches) 51. `initial access broker` (1343)
52. `malware source code` (23) 53. `redteam wiki` (1125 — SEO wiki-farm spam; NO genuine
    red-team wiki found = absence finding) 54. `0day today` (1536 — no 0day.today onion
    surfaced; spam farm dominance)

### Onion page GETs (read-only, via 9050 unless noted)
55. Dead Drop root + `thread/6`, `thread/8`, `thread/24` (below)
56. rtdxrpt3… root + `/pdf/` (content-farm scraper; "the-hacker-playbook-series-1.html" among
    scraped SEO pages)
57. torport… `/news/505/metabase-sqli-zero-day…` (200 after 301)
58. fckilf… `/9.0/` + `/9.0/cracked/` (open directory listing, below)
59. pandorumwzud… C2 Frameworks category `d4500000-d5b6-11f0-b8e5-81cd813b1a30` (200/225 KB)
    + Cracked Software category `e7055660-ec6a-11f0-b2f7-0b1d46d7f0f7` (200/225 KB)
60. jaat7efx… (Best Carding World) `viewforum.php?f=46` Tools board (200/66 KB, 476 topics)
61. hellccam72… (HeLL Forum) `cat_software.html` (200/39 KB)
62. publicag… (HiddenWWW) root (200/17,578 B)
63. C2 Marketplace Escrow 3mt575pd… `/`, `/blog`, `/faq` via 9050 (000), 9150 (000),
    gateway tor_scrape_onion (HostUnreachable); mirror 3mt575pds2… → HTTP 500 — DOWN at check
64. OPSEC Bible opbible7… `/hacking/` via 9050/9150/https → 000 all — DOWN at check
65. Dark Hacker Zone wk54p5… `search.php?keywords=red+team&sr=topics` and `keywords=0day`
    → 200 but "Search found 0 matches" (guest search yields nothing; board index
    SELLING/Tools/Exploits/Viruses visible)
66. Torch `/search?search=cobalt%20strike` (301 → SPA shell, above)
67. RansomLook onion mirror ckz3vog… `/browse` → 000 at check (Ahmia-indexed; NOT verified live)

### GitHub sweep (gh api search/repositories, per_page=6, sort=updated)
68. `topic:onion+topic:search+created:>2026-06-01` → 0 hits (no new onion tooling since June)
69. `onionland+search` → shaugrin/dark_web_crawler (0★, 2024, kw-crawl via ahmia+onionland)
70. `darksearch` → uzaif-lab/darksearch (2★, Streamlit darkweb TI scraper), 5 name-only repos
71. `brute+ratel` → Xpatr0nX/Brute-Ratel-BOFs (1★ 2026-09-25, BOFs ported to BR),
    he1sel/MSSQL-BOF-BRC4 (0★ 2026-08-05, MSSQL BOFs patched-fork), cognis-digital/c2detect
72. `cobalt+strike+cracked` → P4x1s/CobaltStrike-4.8-Cracked (73★ 2023), k8gege/Aggressor
    (1071★, Ladon for CS + cracked CS download, CN), Loki-whoami/CobaltStrike4.1_Cracked,
    RASSec/Cobalt-Strike-Cracked, ParkSideSupp/CobaltStrike4.3_Cracked — the clearnet
    distribution spine of the same cracked-CS pattern seen on onion
73. `lumina+idapro` → **RenardDev/IDATeamsDocker (49★ 2026-07-22)** — Docker for HexLicSrv +
    HexVault + Lumina(+MySQL) + `license_patch.py`, supports IDA 9.4
74. `c2+framework+mcp` → schwarztim/sec-sliver-c2-mcp (6★ 2026-09-09),
    jiushill/godzilla-mcp (3★, Godzilla webshell MCP), ByebyDoggy/AdaptixC2-Workspace (1★),
    schwarztim/sec-powershell-empire-mcp (1★), swfk2154/Stopen (OODA pentest agent with
    AntSword/Behinder/Godzilla 3-protocol WebShell), liuxinye23/CyberStrikeAI
Repo details: `gh api repos/…` for c2detect (34★, Python, PyPI cognis-c2detect),
IDATeamsDocker (49★), AdaptixC2-Workspace (1★; README unreadable/binary — not analyzed).

### Exa / Firecrawl cross-checks
75. Firecrawl search `"Pandorum darknet market \"C2 Frameworks\" OR \"Cracked Software\" forum"`
    → NO clearnet CTI coverage of Pandorum at all (only TG-channel tangents). Finding: Pandorum
    is darknet-native, unreported.
76. Exa search `"onion C2 marketplace escrow selling command and control frameworks cracked
    Cobalt Strike Brute Ratel 2026"` → 8 hits (Brinztech CS 4.12 advisory, FalkonC2 writeups,
    BleepingComputer CS→BR migration, securityscientist BR-C4-crack Q&A, CTI wiki,
    redteamguide alternatives page)
77. Firecrawl search `brinztech … cracked site:brinztech.com` → correct advisory URL
78. curl Brinztech advisory
    `…/…of-a-cracked-cobalt-strike-4-12-variant/` → 200/43,268 B, body extracted (below)

## 3. FINDINGS BY TOPIC SLIVER

### A. Cracked security-tool distributions (strongest haul)
- **Cracked IDA Pro 9.0 open directory** (onion fckilfkscwusoopguhi7i6yg3l6tknaz7lrumvlhg5mvtxzxbbxlimid.onion):
  `/9.0/` holds full installers `ida-pro_90_x64win.exe`, `ida-pro_90_x64linux.run`,
  `ida-pro_90_x64mac.app.zip`, `ida-pro_90_armmac.app.zip`; `/9.0/cracked/` holds the license
  crack: `hexvault_client_90_cracked.zip` (2.8M), `hexvault_client_90_cracked_MacOS_ARM64.zip`
  (5.6M), `hexvault_server_90_cracked.zip` (4.4M), `ida_keygen_v2.7z` (5.6M),
  `lumina90_cracked.zip` (5.1M), all dated 2025-Jan-12/14. Capability pattern: Hex-Rays piracy
  = keygen + self-hosted Lumina + self-hosted HexVault/HexLicSrv. Filenames/sizes recorded;
  NOTHING downloaded (no transacting rule).
- **Brinztech advisory (validated 2026-06-15)**: "Restructured Extensibility, Bypass Logic, and
  the Darknet Commercialization of a Cracked Cobalt Strike 4.12 Variant" — cracked CS 4.12
  (Fortra core update Nov 2025) with modified extensibility + license-check bypass, sold via
  escrow listings on **rehubcom.io/threads/3033/** and **Exploit Forum (exploit.in)** at
  **$2,500 initial fixed**. Pattern: cracks are now modified/forked, not raw copies.
- **Dead Drop forum** (kzmcudnrse3nbz5dtnqavv4v3lkps5sadh3tl2wvf7ot2fhgj37enrqd.onion): index
  public — Marketplace 142 threads/891 posts, Tools & Exploits 87/634, Access Trading; 5,707
  members, ~341 posts today, est. 2023, currently recruiting with invite codes. Public thread
  titles: "Cobalt Strike 4.9 — cracked — working beacon" (67 replies/2,341 views),
  "Sliver C2 setup guide — OPSEC hardened" (18/445), "Which C2 in 2026 — Sliver vs CS vs
  Havoc" (89/3,421). Thread BODIES login-walled — recorded titles/counts only.
- **Pandorum market** (pandorumwzudcql6f3ourlqw2voyh332a4tke64x7k46ds564adoeeyd.onion): modern
  marketplace with dedicated **C2 Frameworks**, **Cracked Software**, **Brute accounts**
  categories; visible taxonomy: SERVICES (bulletproof hosting, DDOS, VPN/Proxy, cashout),
  FRAUD (cards/CVV, dumps, carding tools, real documents), DATABASES & LOGS (stealer logs,
  combo lists), CRYPTO TOOLS (seed grabbers, drainers, withdrawal bots), TRAFFIC (spam,
  installs), SOFTWARE (marketplace scripts, keygens & activators, anti-detect, fingerprint
  spoofers). Zero clearnet CTI coverage (Firecrawl empty). Thread lists login-walled.
- **Dark Matter market** still lists "INVICTI EXPLOIT KIT – HACK/PENTEST WEBSITES — $14"
  (darkmaq7vctf…onion; round-1 sighting re-confirmed in Ahmia index).
- **HeLL Forum** (hellccam72… + mirror helllbtvpp…) `cat_software.html`: a whole cracked/
  malware catalog — "Fra 0 Crypter", keyloggers, "10x Monero Silent Miner", ANTIDETECT 7.3 +
  FRAUDFOX VM bundles, cracked Photoshop/Ableton, "A Trading Bot for Binance with Source Code".
- **Best Carding World "Tools" board** (jaat7efx…, viewforum f=46): 476 topics — recent:
  Bulk SMTP Checker (Sep 18 2026), "The Ultimate Google Dorking Engine [SHADOHDORKS]"
  (Sep 14 2026), Facad1ng URL-masking for phishing (open-source tool re-posted), "GTX 700 RAT
  (SERVER+PANEL+SRC)" (12 replies) — pattern: OSS/cracked tool packages posted as attachments.
- Clearnet spine (gh): P4x1s/CobaltStrike-4.8-Cracked 73★, k8gege/Aggressor 1071★ (CN cracked-CS
  hub) — the same distribution pattern on GitHub.

### B. C2 framework forks / ecosystem
- On-onion demand-side proof: Dead Drop's CS-vs-Sliver-vs-Havoc debate thread; Pandorum's
  C2 Frameworks category; a dedicated **"C2 Marketplace Escrow"** service existed
  (3mt575pd… + mirror 3mt575pds2…; Ahmia-indexed blog/faq/privacy pages) — DOWN at check
  (000/000/HostUnreachable/HTTP 500 mirror). C2 commerce has its own escrow layer now.
- Supply-side (clearnet/gh): cracked CS 4.12 modified-variant advisory (Brinztech); CS→Brute
  Ratel migration (BleepingComputer); Brute-Ratel BOF ports (Brute-Ratel-BOFs,
  MSSQL-BOF-BRC4); **c2detect** fingerprints 16+ C2 families (CS, Sliver, Mythic, Havoc,
  Brute Ratel +11) — defensive complement; new-family coverage: **FalkonC2** (Flare +
  Brinztech write-ups, memory-only execution).
- MCP-ification of C2s (agentic angle): sec-sliver-c2-mcp, godzilla-mcp,
  sec-powershell-empire-mcp, AdaptixC2-Workspace, Stopen (OODA agent + 3 WebShell protocols) —
  C2s are becoming agent-callable tool surfaces on BOTH sides.

### C. 0day research teasers
- **TorPortal** (torportbymf56ref5lqztbbsz7vunmkrkxsn47l67yaayvghmjqz2xid.onion): onion
  directory + "dark web news" mirror of BleepingComputer with Zero-day tag — verified live:
  Metabase unauthenticated SQLi zero-day (v1.58+, exploited from Aug 3 2026 vs
  Framework/Tally/LexisNexis instances; /api/session/reset_password; plaintext creds grabbed),
  plus related zero-day headlines (PaperCut, Cisco SEG, Oracle/Nissan). Onion-side 0day news
  mirror = cheap monitoring surface.
- No live 0day-broker marketplace surfaced (0day.today onion not found in any engine; "0day"
  queries dominated by "Blackhat Pakistan" BTC-generator spam farm — btcx6jx7… ×3 mirror
  domains — scam noise; "Enough about Hacker Factor's 0days" tor blog (tv54samlti…) noise).
- Exploit trade is login-walled everywhere (Dead Drop, Pandorum, DamageLib per round 2);
  HeLL/DHZ have Exploits boards but guest search returns nothing.

### D. Private red-team playbooks
- **The OPSEC Bible** (opbible7ojqidm4jek5mfbfi5tsbnyf7wdy5elt4zafqrurpcghlekad.onion/hacking/):
  "Offensive Security Writeups" collection — Ahmia-indexed with two URLs, but DOWN at check
  (000 ×3 paths). Recorded as indexed-but-dead.
- **Best Carding World**: "DLL Sideloading for Initial Access – Red Team Operator's Guide"
  (viewtopic f=43&p=50024) — tradecraft writeup hosted on a carding forum; publicly indexed.
- **"HIRE RED TEAM | ADVERSARY SIMULATION"** service pages (wsdwonpew…/d3ka2mnk… onions,
  ?service=red_team) and "Hire a Hacker Agency" (r5f44tyh…): the "red team" brand is fully
  commoditized on onion as a for-hire service.
- "#1 Mobile Hacker For Hire" blog (torzcd47rw4…): reposts of tool pages incl. "C# tools with
  modifications to improve their evasion for red team exercises" (evasion-variant posts) and
  "Python Windows Incident Response Toolkit" — content-farm mirror of clearnet repos.
- No genuine "red-team wiki"/"playbook" vault found on onion (redteam wiki = 1,125 SEO-spam
  wiki-farm hits, zero real). Playbook material lives in login-walled forums and clearnet
  mirrors; absence is the finding.
- Content-farm noise documented: rtdxrpt3… (PDF/SEO scraper farm — "the-hacker-playbook" as
  scraped keyword page, not a real book).
- CN side: 自由国度 (jnptn2lbn4anv7ut345j5xdumf4o7illlb5wezcnxcyygoxo3iaffpad.onion) — Chinese
  marketplace with a "虚拟/源码/漏洞" (virtual/source code/vulnerabilities) category; 联合中文
  担保交易集市 (mmawlww2ns2…, Chinese escrow market). 免杀 (AV-evasion) queries surface these
  but no dedicated CN red-team playbook on onion.

### E. New tools/services found this round (not in rounds 1-2)
| Item | Type | Where | Status |
|---|---|---|---|
| Onionland Search Engine | onion search engine (scriptable) | 3bbad7f…onion | LIVE (verified) |
| DarkSearch directory (rotated address) | onion directory/search | darkzqtmb…onion | LIVE (verified) |
| DarkSearch Engine + JSON API | onion engine, keyless API | engin5cbd…onion | LIVE (verified, tiny corpus) |
| Dead Drop forum | invite-only tooling/market forum | kzmcudn…onion | LIVE (index public, bodies walled) |
| Pandorum market | market w/ C2+Cracked categories | pandorumwzud…onion | LIVE (taxonomy public) |
| Cracked IDA 9.0 open dir | pirated RE-tool distribution | fckilf…onion | LIVE (listing read; no downloads) |
| TorPortal | news mirror (BleepingComputer zero-day feed) + market dir | torport…onion | LIVE (verified) |
| HiddenWWW | PublicWWW clone (source-code search, 936,596,896 pages) | publicag…onion | LIVE (verified) |
| TORHACKS service listings | hacking-service catalog | zqmlrtv3pqd…onion | indexed (not fetched) |
| KalTeam | tool portal (password cracking page) | zkwda3wbc…onion | indexed (not fetched) |
| RansomLook onion mirror | leak-site aggregator mirror | ckz3vog…onion | DOWN at check |
| C2 Marketplace Escrow | C2 escrow market (2 addresses) | 3mt575pd… / 3mt575pds2… | DOWN at check (500) |
| The OPSEC Bible | offensive writeup collection | opbible7…onion | DOWN at check |
| 自由国度 | CN marketplace w/ vuln/source category | jnptn2lbn4…onion | indexed (not fetched) |
| c2detect | C2 fingerprinter (defensive) | github.com/cognis-digital/c2detect | verified via gh (34★, PyPI) |
| IDATeamsDocker | open blueprint of the IDA license-infra crack | github.com/RenardDev/IDATeamsDocker | verified via gh (49★) |
| C2-MCP integrations | agent-callable C2 surfaces | see §2 queries 74 | verified via gh |

## 4. DEAD ENDS / NOT REACHABLE (stated, not guessed)

- **Torch scripted search**: JS-only SPA (5,222 B shell; resultsFiltersMenuWrapper; zero
  server-rendered results). Third round confirming this. Torch home remains live.
- **DarkSearch dir + engine**: live but corpus returns nothing for security terms — engines in
  name, directories in fact.
- **Onionland result quality**: fuzzy keyword matching + heavy ad interlayers; usable as
  discovery, not as relevance-ranked search.
- **C2 Marketplace Escrow** (both addresses), **The OPSEC Bible**, **RansomLook onion mirror**:
  down at check (000 / HTTP 500 / HostUnreachable via curl 9050+9150 and gateway
  tor_scrape_onion). Ahmia/onion indexes still list them — stale-index lag is systematic.
- **Dark Hacker Zone guest search**: phpBB search.php returns "Search found 0 matches" for
  "red team" and "0day" to guests (content guest-gated); round-2's direct viewtopic fetch
  worked, so per-topic fetch remains possible but search does not.
- **Dead Drop / Pandorum / DamageLib bodies**: login/invite-walled. Per lane rules I did NOT
  register, request invites, or bypass — intel limited to public index/titles/taxonomy.
- **No 0day.today onion**, no live 0day-broker market found via any of the 4 engines.
- **No genuine red-team wiki/playbook vault on onion** — only SEO wiki farms + login-walled
  forums. (Absence = finding.)
- **Brinztech advisory URL**: Exa's truncated URL 404'd; correct URL found via Firecrawl and
  fetched (site body heavy with chrome; advisory body extracted via keyword search).
- **AdaptixC2-Workspace README**: fetch returned binary garbage — not analyzed.
- **Pandorum**: no clearnet reporting found (Firecrawl search empty of CTI coverage).

## 5. OPSEC / safety posture (recorded, no actions to take)

- All fetches were anonymous GETs through estate Tor; no POSTs, no account creation, no
  purchases, no file downloads from any onion host (cracked-IDU listing read as HTML only).
- Fresh onion addresses in this file were resolved live through Tor this session; treat
  address lists in third-party indexes as stale until re-verified (proven repeatedly).
- The "Cracked Wallet" market cluster (AceMarket etc.) and drug markets appearing in results
  were noted and deliberately not pursued — outside lane scope.