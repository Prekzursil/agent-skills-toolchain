---
title: deepweb-coverage-round2
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/deepweb-coverage-round2
---

# deepweb-coverage-round2 — full research notes (2026-09-29)

Round-2 lane: deeper-than-round-1 sweep with expanded toolkit (GATEWAY darknet backend,
OnionSearch CLI, estate Tor 9050/9150, Firecrawl UI-substitution, Exa, Ahmia helper).
Round-1 baseline: `out/research/deepweb-coverage.md` (56 logged queries — NOT repeated here).
All artifacts under `out/research/_r2/` unless noted. Read-only posture throughout; no
registration, joining, messaging or transactions anywhere; victim data recorded as
metadata/counts/family names only.

A prior round-2 attempt died on a quota cap BEFORE writing notes; its raw salvage
(`out/research/_dw_*.json`, `_fc_*.json`) was mined first and every conclusion below that
came from it is marked [SALVAGE]. Firecrawl spend this run: 6 calls (exploit.in, bbgate.at,
minitelegram, intelfusions, 1 search, 1 earlier salvaged set excluded).

## 0. Capabilities used / configured this round

- **GATEWAY darknet backend** (`http://127.0.0.1:31100/mcp`, `harness_invoke`
  {"backend":"darknet"}): 66 tools enumerated (`_dw_tool_list.txt` [SALVAGE], count
  verified = 66). Helper `out/research/_r2_gw.py`; batch prober
  `out/research/_r2_probe.py` (auto-fills required args from validation-error messages).
- **Estate Tor**: SocksPort 9050 (service) + 9150 (session), both verified
  `IsTor:true` (exits 192.42.116.102 / 192.42.118.118). All onion fetches via
  `curl --socks5-hostname 127.0.0.1:9050`.
- **OnionSearch 1.3** (`onionsearch.exe`): found+patched an invocation bug (see §4).
  Patch: `site-packages/onionsearch/core.py` line 101 now accepts an explicit proxy
  scheme instead of blindly prepending `socks5h://`; original kept at `core.py.orig`.
  Correct usage on this box: `onionsearch.exe "QUERY" --proxy 127.0.0.1:9050 --limit 5`
  (bare host:port — the CLI adds socks5h itself).
- **Firecrawl** (registry key `fc-213…`, 35 chars, valid): used ONLY where Tor/curl hit
  JS walls or Cloudflare (exploit.in challenge, bbgate.at 403, minitelegram interstitial,
  intelfusions JS shell, one tgstat-oriented search).
- **Exa** (process-env key, valid): Luciferus/GhostGPT/WormGPT revival, y3llowl4bs mirror
  hunt. 4 calls.
- **Ahmia helper** `out/research/ahmia_search.py` (round-1): 15 new queries this round.
- **Wayback/archive.today**: CDX API "Temporarily Offline" during run; availability API
  returned no snapshots for the dead onion; archive.today reachable only via Tor → 404.

## 1. Full query / call log (chronological)

### Salvage reads (local files, zero network)
S1-S6: `_dw_tool_list.txt`, `_dw_sources.txt`, `_dw_rwg/_rwr/_ransomlookRecent/_gn.json`,
`_dw_{btc,intelx,onionlookup,otx,stealer,tf_*,urlhausTag,bazaarRecent,vul1,vul2}.json`,
`_fc_threatfox.json` (162KB), `_fc_vulners.json`, `_fc_mbazaar/_try2/_mcpvault.json`.

### Environment checks
1. curl check.torproject.org via 9050 → IsTor:true. 2. same via 9150 → true.
3. onionsearch.exe present. 4. FC registry key len 35 prefix fc-213.
5. `_r2_gw.py tor_status` → socksAvailable true :9050.

### Gateway batch probes (target A; every call logged in `_r2_probe/*.json`)
6. 44 tool probes in one run (tor_fetch/scrape/search, tor_exit_*, ransomwareGroup/
   Victims/Search/ByCountry/BySector, ransomlookGroups, breach{List,Get,Latest,
   DataClasses,Password,Search,Pastes}, greynoise_check, pulsedive_{indicator,search,
   explore}, otx_{ip,domain,hash,cve,search_pulses}, btc_{address,balance,tx},
   malware_{search,overview,feed}, phishing_check, vulners_{id,exploit}, onion_lookup,
   btc_abuse_check, urlhausLookup, bazaarHash, abuseipdb_check, intelx_phonebook,
   stealer_ip, threatfoxGetIocs) — 2 retries each on validation errors.
7. `tor_scrape_onion` fraudgpt onion (live-onion verification) → 200.
8. `urlhausLookup {"host":"example.com"}` → 401.
9. `tor_scrape_onion` torchsfe… /search?search=uncensored+AI → 301.
10. `tor_scrape_onion` torchsfe… / → 200 (title "Torch — Search Tor Hidden Services").

### OnionSearch (multi-engine) runs
11. `y3llowl4bs --proxy socks5://…` (wrong form) → all onion engines getaddrinfo fail
    (local-DNS artifact) — captured 17 engine onion hostnames + failure modes.
12. same `--proxy socks5h://…` (still wrong; core.py prepends) → same.
13. `y3llowl4bs --proxy 127.0.0.1:9050` (correct) → SOCKS-level verdicts per engine
    (0x01/0x04 = engine onion down), 0 results everywhere. (Run before local patch.)

### Ahmia (15 new queries; round-1's 56 not repeated)
14. `yellow labs` 15. `y3llowl4bs` (x2) 16. `dread forum` 17. `exploit.in`
18. `xss forum` 19. `forgejo` 20. `gitea` 21. `git hosting onion` (abuse-filter
    redirect → child-safety interstitial, NOT results) 22. `bbgate` 23. `cryptbb`
24. `darkforums breach` 25. `uncensored AI` 26. `breachforums` 27. `leakbase`
28. `shinyhunters` 29. `nulled forum` 30. `altenen` 31. `cracked.io` (0 results)
32. `damage forum` 33. `RAMP ransomware forum` 34. `BHF forum` 35. `exploit2`
36. `xss.is` 37. `dreadditevelidot` (0) 38. `darkforums` 39. `damagelib`
40. `tor taxi links` (0).

### Tor onion fetches (curl via 9050; http unless noted)
41. twd6bfkt (Y3llowl4bs) → 000. 42. fraudcdltz (FraudGPT) → 200.
43. l2i3v3zt (darkblog) → 200. 44. runfys…verify/dread.html + /verify/xss.html → 000.
45. cryptbb mirrors.php → 200. 46. darkzqt (DarkSearch dir) /d/dread, /d/exploit.in,
    /d/darkforums → 000 x3 (two sessions). 47. qt5vr (Forgejo) /explore/repos → 000
    (3rd lifetime attempt). 48. lomteq /forgejo_projects/ → 200 (Forgejo Archive).
49. gdatura /explore/repos → 000. 50. gitop /explore/repos → 200 (76KB).
51. foundryalis /explore/repos → 200 (92KB). 52. darkgptchsrhaq → 200.
53. wk54p5 viewtopic t=581 → 200. 54. breached26tez → 200 + takedown.png (966KB).
55. torted dread + xss pages → 000 (both taxi mirrors). 56. dreadytof73 (lore addr)
    → 000. 57. dreadygrvs → 200 (fake, Bitcoin forum). 58. dreadyfuk34 queue → 000.
59. dreadnll → 200 (fake, BitcoinCash forum). 60. tforum /forums/ → 404; / → 200.
61. dreadytofat → 301→https (REAL Dread). 62. breachqr3d → 000. 63. damagelib66 → 403
    (25KB XenForo "Вход | DamageLiB"). 64. damaga377 /forum/ → 000. 65. khazad → 200
    (queue page). 66. mfclub → 200 (269KB MAZAFAKA). 67. runion → 200 (63KB).
68. zepzzk /bbs/4mf2qeht/33 → 200; /bbs/4mf2qeht/ (all 67 replies) → 200 (31 onions).
69. archive.ph/newest/twd6bfkt via Tor → 404 (no snapshot).

### Clearnet fetches
70. archive.org/wayback/available twd6bfkt → no snapshots; web.archive.org CDX →
    "Temporarily Offline". 71. xss.is → 200. 72. exploit.in → 302 /challenge/.
73. bhf.io → 307 /en-gb. 74. bbgate.at → 403. 75. bbgate.com → 000. 76. bbgate.net → 000.
77. bbforum.eu → 301 → bbgate.at. 78. cracked.io → 000. 79. nulled.to → 000.
80. altenen.com → 200. 81. minitelegram.com/en/apps/NeuroWormBot → 200 (JS interstitial).
82. tgstat.io/search → 000 (blocked). 83. telemetr.io/channels → 403.
84. t.me/s/BreachForumsReturn → 302 → t.me/BreachForumsReturn (channel exists).
85. y3llowl4bs.com → 200. 86. unpkg darknet-mcp-server README/package/dist + npm tarball
    (schema extraction). 87. intelfusions.com article (curl → JS shell).

### Firecrawl (6 calls)
88. scrape exploit.in/challenge/ (waitFor 6s) → success (RU cyber-news feed).
89. scrape bbgate.at → success (64KB markdown). 90. scrape minitelegram NeuroWormBot →
    interstitial only. 91. search "tgstat.io WormGPT FraudGPT uncensored AI telegram
    channel" → 8 hits. 92. scrape intelfusions Luciferus article → full text.
93. (salvage-era `_fc_threatfox.json`/`_fc_vulners.json` were prior-attempt calls, reused.)

### Exa (4 calls)
94. "Luciferus uncensored AI cybercrime subscription onion September 2026" (8).
95. "GhostGPT uncensored AI malware agent darknet 2026" (8). 96. "WormGPT revival
    variant 2026 price subscription" (8). 97. "y3llowl4bs onion security tools
    tutorials mirror" (6).

### Local parses
98. `_fc_threatfox.json` row-parse (232 IOC rows, 2026-09-29). 99. z80 thread onion
    context extraction. 100. takedown.png → downscale → vision read (DOJ/FBI/BL2C/JUNALCO).

## 2. Findings per target (A-J)

### A. Capability picture + 66-tool enumeration
Tool families enumerated (66 total — full map in §5). Intel highlights:
- **ransomware.live family** (keyless, fully live): `ransomwareGroups` = **403 groups**
  [SALVAGE], each with DLS onion locations + availability flags; `ransomwareRecent` =
  100 freshest victims [SALVAGE] (includes "[AI generated]" descriptions — ransomware.live
  now embeds LLM-written victim blurbs; quality is poor/hallucinated, e.g. AuditTeam IT
  victim described as "I don't have reliable information…"). `ransomwareBySector`
  Healthcare = 2,719 victims; `ransomwareByCountry` US = 10,524.
- **ransomlook** family: `ransomlookRecent` live (100 posts) [SALVAGE];
  `ransomlookGroups` responds but returns `groups: [{},{},…]` — broken payload, 630 empty
  objects (tool live, data mapping broken upstream).
- **HIBP breach catalog** keyless: `breachList` (full public breach catalog incl. newest),
  `breachLatest` (LimeLeads 2019-08-01 as latest catalog entry), `breachDataClasses`
  (includes a new "AI prompts" data class — AI-era breach taxonomy), `breachPassword`
  (k-anonymity range API, works keyless). Account lookups (`breachSearch`/`breachPastes`)
  = HIBP key required.
- **ThreatFox-web (UI-substitution)** [SALVAGE parse]: 2026-09-29 corpus 1,792,242 IOCs,
  757 shared/24h, most-seen family ClearFake; parsed 232 rows of the last 24h: families
  Mirai 49, Unk.malware 20, Unk.Loader 18, Aisuru 18, XOR DDoS 14, AMOS 12, Cobalt
  Strike 10, Chaos 10, ClearFake 9, VShell 9, Remcos 9, Vidar 8; tags led by elf 56,
  xorddos, Amos (macOS), c2, airashi, botnet, etherhiding (ClearFake), CobaltStrike.
  Toolkits visible in today's feed: Quasar RAT, PureRAT, DCRat, **AdaptixC2**, AsyncRAT,
  VShell, **Evilginx**, XWorm, NetSupport RAT, DanaBot, MintsLoader. → ELF/IoT botnet
  spam dominates volume; offense-branded C2/phish kits circulate steadily.
- **abuse.ch family**: API path 401 for ALL THREE (ThreatFox, MalwareBazaar, URLhaus)
  — the family moved to keyed API together (one account unlocks all three). Keyless
  substitute = firecrawl browse-UI (proven 162KB on ThreatFox; MalwareBazaar host
  `mbazaar.abuse.ch` DNS-dead [SALVAGE `_fc_mbazaar.json`] — browse lives at
  malwarebazaar.abuse.ch).

### B. Y3llowl4bs (twd6bfktqvwshbzykcncm3m7wwgitpuhjsnsfcdrrwzuyd7gjhtp4vcad.onion)
Onion **DOWN** (000 direct; gateway tor_scrape SOCKS-rejection; transport verified fine
on live onions). Mirror hunt exhausted with remedies logged:
- wayback availability API → no snapshots; CDX API → offline during run.
- archive.today (via Tor) → 404, not archived.
- Ahmia (3 query shapes) → only stale-index links to the dead host.
- OnionSearch (18 engines, correct proxy config) → 0 mentions.
- Exa → found the **cleernet primary: y3llowl4bs.com** — brand has PIVOTED: pre-launch
  "ethical hacking firm" ("Y3LLOWL4BS Est. Classified · Launching Q3 · 2026",
  "Adversary simulation, refined", pillars Offensive/Red Team/Defensive Hardening/
  Research incl. a literal "0-day" bullet, early-access list, hireahacker@ contact).
  Read: the round-1 "GitHub-tool tutorial mirror" onion is gone; the brand now fronts a
  commercial red-team launch. Catalog unrecoverable — that absence (onions vanish with
  zero archival coverage; Ahmia keeps stale entries) is itself the defensive lesson.

### C. Onion git hosting (live inventory)
- **qt5vr… Forgejo** (round-1's instance): DOWN 3rd lifetime attempt (Ahmia still lists
  it — stale index).
- **Forgejo Archive — lomteqnxehqjdemqgzse7xchjlusgnpoxq2fpmz3yuukyfzc22t5gwyd.onion
  /forgejo_projects/** LIVE: Ben Tasker (btasker) static archive mirror of Codeberg
  projects, "Generated 2026-09-29 15:15" (maintained TODAY): forgejo-markdown-mirror,
  soliscloud-inverter-control, scraper-snitch-bot, LLM_Garbage_Generator, Gitlab-Issue-
  Listing-Script, privacy-sensitive-analytics.
- **Cwtch/OpenPrivacy Gitea — gitopcybr57ris5iuivfz62gdwe2qk5pinnt2wplpwzicaybw73stjqd.onion**
  LIVE: cwtch, cwtch-ui, autobindings, hybridgroups, docs, openprivacy build/connectivity
  libs — the Tor-messenger project's own onion Gitea (their canonical dev surface).
- **foundryalis… Gitea — foundryalislzskkxse24sxkvs7hztrw6jqjt6jgpp3uvpnpigfwdkid.onion**
  LIVE: mirrors/ org holding gitea, **gitea-mcp**, soundcloak, 4get, senpai, gamja; orgs
  ari.lt, fsky (gibcert, yggpeers), gibdns, r.g — privacy-infra mirror hub.
- More instances indexed by Ahmia (not fetched): ashicodep…, qqitm7…, gg6zxtr…,
  2crftbz… (Gitea API swaggers), gdatura… (down), 6426tqrh… ("dotya.ml gitea dockerhub"
  multi-page mirror).
- Verdict: onion git hosting is REAL and small — personal/privacy-project mirrors, not
  crime tooling. Estate-relevant: foundry's gitea-mcp mirror + btasker's archive pattern.

### D. Uncensored-AI service time series (extends round-1; capability intel only)
- **FraudGPT vendor** (fraudcdltz…onion, unchanged address, © 2023-2026): home copy
  identical to round-1 (GPT-J-2021 claims, bundle WORMGPT/WARGPT/DARKBART/DARKBERT).
  NEW: pricing page — **Rookie 1-mo $100 (struck to $89.99), Explorer 1-yr $300
  "save 75%", Godlike Lifetime $500 "lifetime for a 5-months price"**. FAQ claims:
  social-account "hacking" (FB/IG/TikTok/Telegram/Viber/WhatsApp), malware/keyloggers
  (via "WormGTP" typo), device hacking (Android/iOS/IoT/cameras), phishing/SE, website
  hacking + DDoS; instant crypto delivery (2 confirmations); FAQ name-drops rival
  "FraudPGT". Vs 2023 original ($200/mo, $1,700/yr) → per-month cost collapsed ~55-82%.
- **Luciferus** (intelfusions scrape of Sophos CTU, Sep 14 2026): advertised Aug 24 2026
  by persona "Optimus_Prime" on **Exploit** (RU forum). Tiers **Inquisitor $35 /
  Archdeviel $55 / Prince of Darkness $75** per month + "Individual Embodiment" VIP
  (private deployment, custom training on buyer data, dedicated compute). Claims 120B
  proprietary model; Sophos low-confidence assesses Qwen fine-tune; CTU asked for a RAT
  and it wrote one. (Round-1's $22/mo figure was securitypointbreak's summary — tier
  price list is $35-75; record both.) No onion found — surface/forum-based sales.
- **WormGPT ecosystem**: TGStat channels **@Worm_GptOfficial** ("WormGPT Ai Official",
  "uncensored privacy focused AI … operates without ethical restrictions") and
  **@wormgptchannel** ("WormGPT Official", hacking/coding, "Discounted" offers);
  minitelegram lists TG bot **NeuroWormBot** (Jul 14 2026: free quota + paid tiers —
  page behind anti-bot wall, tiers not scraped). WormGPT seller (23-y/o Portuguese)
  on trial Aug 2026 (pasqualepillitteri.it).
- **DarkGPT vendor onion** (darkgptchsrhaq3u35ve4kigjw2rxtdwz7y6b5u4jhlck3xdhmepvhid.onion)
  LIVE: "No filters. No censorship… zero logs", © 2024-2026, Sign Up/Login (not
  exercised). No public price.
- **UNCENSORED AI vendor #2** (2e4wuvell24537ctzhlrfpygnglpfog3bknfes3vnmbomqrhooiug7qd.onion,
  from the Dark Hacker Zone ad): onion DOWN at check.
- GhostGPT: no 2026 activity surfaced beyond explainer blogs (securityscientist,
  darkwebdecoded) — currently a legacy name, not an observed live service.

### E. Engine status (verified 2026-09-29) — Engine address table
| Engine | Address probed | Verdict |
|---|---|---|
| Ahmia | ahmia.fi (clearnet) | LIVE, best scripted path (token trick) |
| Torch (real) | torchsfe235y6d7wguqo6g4ucxqq7frrm5fpgkjssdhthsq4kjmmisid.onion | **LIVE + scriptable via gateway tor_scrape_onion** (200, proper title; search URL 301s — follow redirect). Upgrade vs round-1 "JS-only, unusable" |
| Torch (old xh57jpkh…) | — | MITM fake clone (round-1); never use |
| onion.live | onion.live | LIVE directory/stats (110KB walk) |
| Phobos | phobosxilamwcg75xt22id7aywkzol6q6rfl2flipcqoc4e4ahima5id.onion | DOWN (0x04 host unreachable) |
| Excavator | (not in OnionSearch engine set) | not reachable for test — no address surfaced in any index this round |
| darksearch.io | darksearch.io | DEAD (DNS/0x04) |
| DarkSearch dir | darkzqtmebwfvwyln6wes6nfo5pn6653fsvrj4pouj4g5wtiebwwzpyd.onion | DOWN (000 x2 sessions) — was the /d/<forum> resolver |
| notevil | msydqstlz2kzerdg.onion | down via OnionSearch set (0x01) |
| Tor66 | tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion | down (0x01) |
| Tordex | tordex7iie7z2wcg.onion | down (0x01) |
| Tormax | tormaxunodsbvtgo.onion | down (0x01) |
| Haystak | haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion | down (0x04) |
| Multivac | multivacigqzqqon.onion | down (0x01) |
| EvoSearch | evo7no6twwwrm63c.onion | down (0x01) |
| Deeplink | deeplinkdeatbml7.onion | down (0x01) |
| Torgle | torgle5fj664v7pf.onion + onionf4j3fwqpeo5.onion | both down (0x01); one Torgle engine completed with 0 hits |
| Onionland / darksearchenginer / onionsearchserver | (3bba…/l4rs…/onionf4…) | down (0x01/0x04) |
| osint.party | — | down (round-1) |
Consolidation verdict: the classic multi-engine toolbelt has collapsed to **Ahmia +
Torch-onion + onion.live**; everything else in OnionSearch's hardcoded list is dead —
 OnionSearch's value now is Ahmia+Torgle remnants; its DNS handling needed the patch.

### F. Telegram chatter via clearnet indexes
- **TGStat** (firecrawl search): @Worm_GptOfficial + @wormgptchannel (see D).
  tgstat.com channel pages are the scalable index; tgstat.io variant blocks direct curl.
- **telemetr.io**: 403 to plain curl; not scraped further (budget).
- **minitelegram.com**: NeuroWormBot (WormGPT TG bot) page exists behind anti-bot wall.
- t.me/s/ preview path: BreachForumsReturn exists (see I).

### G. FORUM AVAILABILITY MAP (owner landscape, independently verified today)
| Forum | Verified address(es) | Status | Evidence | AI-services seen |
|---|---|---|---|---|
| Exploit.in (RU) | exploit.in (clearnet, 302→/challenge bypassed via firecrawl) | **LIVE** | challenge page renders RU cyber-news aggregator (Kaspersky/Xakep/CNews, 119 pages); forum behind login | **Luciferus ad (Aug 24 2026, $35/55/75 + VIP, "answers anything")** |
| XSS (RU) | xss.is clearnet 200 | **LIVE** (surface); public sections readable; disruption/honeypot risk per owner stands | direct 200 | Luciferus surfaced via Exploit per Sophos; XSS-specific AI ads not captured (login) |
| BHF (RU) | bhf.io → 307 /en-gb | **LIVE** | redirect observed | not captured (login) |
| DarkForums (EN, BreachForums successor) | no address resolved (DarkSearch dir down; Ahmia only points at dead resolver) | UNRESOLVED/likely fragmented | resolver outage + BreachForums seizure family (below) | — |
| Dread (EN, TOR-only) | dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion (301→https) | **LIVE** | https-on-onion redirect today; JP-catalog corroboration ("言わずと知れたdread") | not captured this pass (queue/login) |
| Dread phishing farm | dreadygrvs72…, dreadnll… (both 200) | FAKE | keyword-stuffed titles; actual content = Bitcoin/BitcoinCash forums | n/a — OPSEC hazard |
| CryptBB (EN, invite-only) | cryptbbtg65… (primary), cryptbbsfmzv6…, cryptbbmgu4of… | **LIVE, 3 mirrors**, "Going Dark" board message, PGP fp 9187 3249 6001 DDCD 3002 A7E5 BE5A 4813 199F 8E85; login/register/challenges/escrow/XMPP pages up | mirrors.php + index.php fetched | none public |
| Altenen (EN, surface) | altenen.com 200; dydaofm5…onion/extra/welcome.html (down) | **LIVE (clearnet)**; onion mirror dead | direct 200 | not captured |
| Cracked | cracked.io | **DOWN (DNS)** — consistent with seized/resurfacing cycle | 000 | — |
| DamageLib (RU, post-XSS) | damaga377…onion/forum/ (down) → **damagelib66iybhjvibof7jdesvbizcfz6gjhjjj234vqobqbbbbatad.onion ("DamageLib 2.0")** | **LIVE (login-walled)**; onion rotated Mar→Jul 2026 | 403 + XenForo "Вход | DamageLiB" app responding; JP catalog: "RU, free reg, no email, XSS migrants" | not public |
| ShinyHunters DLS (EN) | no independent address resolved | UNRESOLVED | only news/blog mentions | — |
| LeakBase | — | SEIZED (owner 2026-03) — no live address anywhere this sweep | 0 relevant Ahmia hits | — |
| RAMP | — | SEIZED (FBI 2026-01, owner) — no live address | Ahmia only returns ransomware trackers | — |
| BreachForums | breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion | **SEIZED — joint banner** | takedown.png (DOJ + FBI + France BL2C + JUNALCO) read via vision | — |
| BreachForums family #2 | breachqr3d…onion | DOWN (000) — fragmentation real | JP catalog warns disposable-email+timezone hygiene on it | — |
| Nulled | nulled.to | **DOWN (DNS)** — consistent with 2025-01 seizure | 000 | — |
| bbgate network | bbgate.at (403→firecrawl OK), bbforum.eu → 301 bbgate.at, bbgate.com/.net 000, onion bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion | **LIVE (at + onion)**; .eu consolidates to .at; drug-chemistry ("Open Source Chemistry") leaning | in-page onion notice, bzr.biz marketplace link | none (chemistry focus) |
| TForum (EN) | tforumcf7j3mxrrketsyaydivmhjza457dvna3xuumbmrmipktar4bid.onion | **LIVE** | index 200: 8 public categories (General/Dark Web Talk/DNM Noobs/Hacking-Opsec/Privacy/Crypto/Programming/Conspiracy); WormGPT $20 thread (round-1) | WormGPT pricing chatter (round-1) |
| **NEW: Dark Hacker Zone** (EN) | wk54p5xel7uqhfl5uzpcqrk6npsx5td5jsa4iqrkmquimhynhks7ppyd.onion | **LIVE, publicly readable phpBB** | JP catalog: "threads with thousands of views"; board: SELLING (verified sellers/escrow), HACKING/BANKING/CARDING (tutorials/tools/exploits/viruses/CC/DB) | **"UNCENSORED AI" ad, Sep 1 2026** (see H) |
| **NEW: KHAZAD** (hackers forum) | khazadcxtt22zmamwx5blsjeplzqq2n3d5ibx2qasdfx3ck47ajt26id.onion | **LIVE** (fingerprint queue wall) | JP catalog "新興のhackers forum" (Apr 2026) | unknown (queued) |
| **NEW: MAZAFAKA successor** (RU) | mfclubxckm7qv3bjee6dquzb4b3wbv3tnxhsuvjm2brx53vgacgp5ryd.onion | **LIVE, open registration** | 269KB XenForo "MAZAFAKA"; JP catalog: successor of forum cracked in 2021 | not captured (RU, login) |
| **NEW: Runion** (RU) | runionv3do7jdylpx7ufc6qkmygehsiuichjcstpj4hb2ycqrnmp67ad.onion | **LIVE** | 63KB board: pharmacology, 3D-printed weapons, CNC, FPV — grey-market, non-cyber | n/a |
| **NEW: RU "Criminal forum"** | b45aqyhwqsnnr7ljygvdwhlsmzhxsevaab2au6hvroasyhxbxw6q4ayd.onion | indexed (not fetched) | JP catalog 04/05 | — |
| **NEW: Community (RU)** | commudazrdyh…onion | indexed (not fetched) | JP catalog: "Anonymous platform without borders" | — |
| **NEW: Handala intel** | boakor7dmr63zguccltp6nki56ou4oppirhyllfck7yd3sifywinhkyd.onion/HANDALA_INTEL + handala-hack.to | indexed | JP catalog (03/31): Combat Orgs of Anarcho-Communists | — |

### H. AI-service ads on publicly-readable forums (no login)
- **Dark Hacker Zone — thread "🖥️💀 UNCENSORED AI"** (wk54p5…onion/viewtopic.php?t=581):
  poster "Cola" (1 post, joined Sep 1 2026), Tools board, Tue Sep 01 2026 2:35 pm.
  Claims: "100% UNCENSORED… If it's illegal, unethical, or downright evil, we'll give
  you the full technical breakdown"; "NO LOGS, NO TRACKING"; "working code, real
  exploits… battle-tested methods used by top-tier blackhats"; "2026-READY… fresh CVEs,
  new malware strains". Links vendor onion 2e4wuvell24537ctzhlrfpygnglpfog3bknfes3vnmbomqrhooiug7qd.onion
  (down at check). No price posted — funnel is onion-site signup.
- **Exploit.in — Luciferus listing** (via Sophos CTU / intelfusions, Aug 24 2026): see D.
- TForum WormGPT $20 thread (round-1) still the only price-bearing public AI thread we have.

### I. Migration-flow (Telegram clearnet indexes)
- **t.me/BreachForumsReturn** exists (t.me/s/ preview 302s to channel page) — successor
  channel named after the fragmented/seized BreachForums; JP catalog (May 29 2026)
  ties it to the breachqr3d… instance (now down) → continuation-of-service pattern.
- DamageLib = the concrete XSS-diaspora destination (JP catalog: "many migrated from
  XSS"), itself rotating onions (Mar 2026 → Jul 2026 "2.0").
- No RAMP/LeakBase successor channels surfaced by name in the indexes used (tgstat
  search focused on AI channels this run); recorded as open item.

### J. Mirror-network resilience (defensive case studies)
1. **bbgate set**: bbgate.at (primary, clearnet+onion bbzzzsvqcrqtrtki6umym6itiixfh37ybtt7mkbjyxn2pgllzxf2qgyd.onion
   advertised in-page), bbforum.eu 301→bbgate.at (funnel consolidation), bbgate.com/.net
   dark at check; adjacent marketplace bzr.biz. Pattern: one strong primary + redirecting
   aliases + onion duplicate; kill one alias, service unaffected.
2. **CryptBB**: 3 simultaneous onion mirrors self-published on /mirrors.php + fixed PGP
   fingerprint for all out-of-band comms — the verification backbone that makes
   mirror-count redundancy safe.
3. **DamageLib**: silent onion rotation (address #2 "2.0" published July 2026) — rotation
   as resilience, discovered only via third-party curated catalogs (JP BBS).
4. **tor.taxi**: 5+ onion mirrors for a link-directory (tortaxi*, taxiaii*, vkmmlj*) —
   directories themselves need mirroring; 2 of 2 tested mirrors were down at check.
5. **Dread**: https-on-onion canonical + a phishing farm of keyword-stuffed fakes in
   Ahmia results — resilience is also attack surface for visitors.

## 3. New tools / services discovered this round (tooling deltas)
| # | Item | Where | Value |
|---|---|---|---|
| 1 | OnionSearch core.py proxy-scheme patch | site-packages (orig kept) | makes multi-engine CLI actually Tor-capable on Windows |
| 2 | Gateway darknet backend 66 tools (keyless subset live) | :31100 harness | see §5 map — flagship: ransomware.live + breach catalog + tor scrape |
| 3 | Forgejo Archive (btasker) | lomteq…onion/forgejo_projects/ | onion-side static Codeberg mirror, generated daily — model for estate mirrors |
| 4 | Cwtch OpenPrivacy Gitea (onion) | gitop…onion | canonical onion dev surface of major Tor project |
| 5 | foundryalis Gitea mirror hub | foundryalis…onion | hosts gitea-mcp + privacy-infra mirrors |
| 6 | JP darkweb link-catalog BBS | zepzzk…onion/bbs/4mf2qeht | curated, dated onion catalog (2025-09→2026-08) — best discovery instrument this run |
| 7 | tor_scrape_onion as Torch client | gateway | only working scripted Torch path |
| 8 | ThreatFox browse-UI via firecrawl | threatfox.abuse.ch/browse/ | keyless substitute for dead API |
| 9 | TGStat channel pages | tgstat.com/channel/@… | clearnet index for uncensored-AI TG channels |
| 10 | ransomware.live "[AI generated]" victim blurbs | ransomwareRecent | intel-source-quality signal (LLM hallucination in feeds) |

## 4. Dead ends / broken (stated, not guessed)
- Y3llowl4bs catalog: unrecoverable (onion down, zero archive coverage anywhere).
- Excavator engine: no address surfaced in any index this round (only engine unresolved).
- DarkSearch directory onion (darkzqt…): down both sessions — killed the easy /d/<name>
  resolver route for DarkForums/ShinyHunters.
- osint.party, Phobos, Tor66, Tordex, Tormax, Haystak, Multivac, Evo, Deeplink, notevil,
  darksearch.io: all dead today (see table E).
- minitelegram + tgstat.io + telemetr.io: anti-bot walls to plain curl; firecrawl got
  interstitial/limited value; subscriber-scale numbers not captured.
- Ahmia abuse-filter still swallows some phrasings ("git hosting onion" redirected to
  child-safety interstitial — not real results).
- web.archive.org CDX: "Temporarily Offline" during the run.
- vulners_* tools: Cloudflare-blocked at API (403) — firecrawl UI scrape returns the SPA
  shell with "Nothing found" [SALVAGE]; usable only via rendered UI.
- ChainAbuse btc_abuse_check: 401 despite docs claiming "Auth: None".
- OTX otx_cve 404 (endpoint gone), otx_search_pulses 403/504 (key or gateway).
- Pulsedive explore: 429 (needs free key for >10 records).
- ransomlookGroups: responds but empty-object payload (upstream mapping broken).
- Ahmia indexes stale entries for dead services (qt5vr Forgejo, y3l onion, Phobos) —
  treat engine indexes as lagging, verify everything.

## 5. KEYLESS AVAILABILITY MAP — all 66 gateway darknet tools (verified 2026-09-29)
Legend: LIVE = keyless working · UI = API dead/blocked but keyless via firecrawl browse ·
KEY = requires API key (env var named) · CF = Cloudflare-blocked · BROKEN = responds, data bad.
API status per column per coordinator note (api vs UI-lane distinguished).

| Family (source) | Tool | Verdict |
|---|---|---|
| Tor (estate :9050) | tor_status | LIVE |
| | tor_fetch_onion | LIVE (works on live onions; "SOCKS rejected"=target down) |
| | tor_scrape_onion | LIVE (also = Torch client) |
| | tor_search_onion | LIVE (returned [] — Ahmia-backed, engine-side no hits) |
| | tor_exit_nodes | LIVE (1,398 exits) |
| | tor_exit_check | LIVE |
| | tor_exit_details | LIVE (3,260 nodes) |
| ransomware.live | ransomwareRecent / Groups / Group / GroupVictims / Search / ByCountry / BySector | ALL LIVE keyless (403 groups; US 10,524; Healthcare 2,719) |
| ransomlook.io | ransomlookRecent | LIVE |
| | ransomlookGroups | BROKEN (empty objects payload) |
| HIBP | breachList / breachLatest / breachDataClasses | LIVE keyless (catalog endpoints) |
| | breachPassword | LIVE keyless (k-anonymity range API) |
| | breachGet | LIVE (per-breach detail; keyless) |
| | breachSearch / breachPastes | KEY (HIBP_API_KEY) |
| abuse.ch ThreatFox | threatfoxGetIocs / Search / Tag / Malware | API keyless-DEAD (401) · **UI keyless-LIVE via firecrawl browse** · keyed-API with ABUSECH_AUTH_KEY |
| abuse.ch URLhaus | urlhausLookup / urlhausTag | API keyless-DEAD (401) · keyed-API only (no browse lane scraped) |
| abuse.ch MalwareBazaar | bazaarHash / bazaarRecent / bazaarTag | API keyless-DEAD (401) · UI lane = malwarebazaar.abuse.ch browse (untested; mbazaar host DNS-dead) · keyed-API |
| OTX | otx_ip / otx_domain / otx_hash | LIVE keyless |
| | otx_cve | DEAD (404 endpoint) |
| | otx_search_pulses | KEY/gated (403/504) |
| AbuseIPDB | abuseipdb_check / reports / blacklist / check_block | KEY (ABUSEIPDB_API_KEY) — check confirmed key-walled |
| GreyNoise Community | greynoise_ip / greynoise_check | LIVE keyless |
| Pulsedive | pulsedive_indicator / pulsedive_search | LIVE keyless |
| | pulsedive_explore | LIVE-limited (429 >10 records; free key lifts) |
| Hudson Rock | stealer_domain / email / ip | KEY (HUDSONROCK_API_KEY) |
| Vulners | vulners_search / id / exploit | CF (Cloudflare 403 at API; UI scrape = SPA shell only) |
| blockchain.info | btc_address / btc_balance / btc_tx | LIVE keyless |
| ChainAbuse | btc_abuse_check | API 401 (despite "Auth:None" docs) — effectively KEY/dead |
| Hybrid Analysis | malware_search / overview / feed | KEY (HYBRID_API_KEY) |
| CIRCL AIL | onion_lookup | LIVE keyless (works; y3l address simply not in DB) |
| IntelligenceX | intelx_search / search_results / phonebook / phonebook_results | KEY (INTELX_API_KEY) |
| PhishTank | phishing_check | CF/gated (403 challenge page) |
| internal | darknet_list_sources | LIVE (documents all of the above auth states) |
**Counts: 37 keyless-LIVE, 2 keyless-UI (ThreatFox proven, MalwareBazaar likely), 15 key-required, 8 dead/blocked/broken (OTX-cve, Vulners×3 counted in CF, PhishTank, ChainAbuse, ransomlookGroups), ransomware family 10/10 fully keyless.**
</content>