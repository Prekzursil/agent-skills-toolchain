# Lane: onion-forums — dark forum/marketplace chatter about AI red-teaming & LLM hacking services

Date: 2026-09-29. VM: Windows Server, Git Bash, curl via Tor SOCKS proxy `socks5h://127.0.0.1:9050` (v0.4.9.13 at D:\opt\tor, see out/research/tor-setup.md).
Rules kept: **read-only GET of public pages only** — no registration, no login, no transactions, no vendor contact, anywhere.

## 1. Proxy verification (run this session)

- `curl -s -m 30 --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip` → `{"IsTor":true,"IP":"45.84.107.200"}` — Tor live (same as the ask's pre-check).
- All `.onion` fetches below went through `curl --socks5-hostname 127.0.0.1:9050`. Clearnet mirrors/intel sites fetched directly.

## 2. Search engines: addresses found, endpoints, and quirks

### Ahmia
- Remembered address `juhanurmihxlp77ikkq76a7y7r3xjkknsq7vwkmu4u2js3vl77p2c4yad.onion` → **wrong** (curl exit 97, http=000). Dead end by memory; do not reuse.
- Real address discovered from `https://ahmia.fi/` footer (200): `juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion`.
- **Onion search endpoint is broken for non-browser clients**: `/search/?q=FraudGPT` → 302 → `/` even with fresh homepage token (`name="b178a1" value="9e72f9"`, rotates) + cookie jar; `https -k` on onion → 000 (they serve HTTP only on onion).
- **Workaround (used for all Ahmia queries)**: clearnet mirror `https://ahmia.fi/search/?q=<q>&b178a1=<fresh token>` with `-c/-b` cookie jar from the homepage fetch → 200. Fresh token per query. Parser: out/tmp/parse_ahmia.py.
- Ahmia AND-matches all terms: queries like `AI hacking`, `hacking AI`, `PromptLock` returned the empty-results page (~5.0–5.7 KB) — no indexed pages contain all tokens. That is a real negative, not a failure.

### Torch
- Mirrors found via Ahmia query `torch search engine`: live `torchac4pcsccozhpiskcckhyida2jjimt5gwlbetdub2ge5u6gkityd.onion` (200, form action `search.htm`, param `P`, DEFAULTOP and/or; claims **3,524,919 documents**), live classic `xmh57jr7ldr5s6xxbhvlizj2yqoo7bi4kzmjuvaj3ccadfq4lw54lmid.onion` (200, meta-refresh → `/cgi-bin/omega/omega`), `torchs7vpa4w6ddmgj56yseropeo5y47ixktki57a45l7zmwxrffnnqd.onion` (200). Dead: `torchrc2xp3jiktpw3rsdaagpaxwqjgvimw63uxp3jybejxxjbkejsqd.onion` (000).
- `search.htm?P=...` on the new mirror ignored the param (returned "46,750 matches" = all docs). **Working endpoint**: classic mirror `http://xmh57jr7ldr5s6xxbhvlizj2yqoo7bi4kzmjuvaj3ccadfq4lw54lmid.onion/cgi-bin/omega/omega?P=<q>&DEFAULTOP=and` with Referer header.
- Result quality for this lane is poor: see §3.

### OnionLand
- `onionlandsearchengine.com` → DNS failure (dead domain, both direct and via proxy).
- Live mirrors discovered via Exa: `onionlandsearchengine.net` (200), `onionland.live` (200); `onionlandsearch.ink` (000). Onion address published on homepage: `n3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion`.
- **Onion search endpoint down**: `http://n3bbad7...onion/search?q=FraudGPT` → 000 twice via proxy. **Fallback used**: clearnet mirror `https://onionlandsearchengine.net/search?q=<q>` (200). Results are redirect-wrapped (`/r?s=base64`), real URL in `<div class="link">`; parser out/tmp/parse_ol.py.

### Other status/churn sources
- `dark.fail` (via proxy, 200; **updated Tue, 29 Sep 2026 19:29:42 UTC**): alert banner "**Archetyp Market was seized by German law enforcement**"; Dread online `dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion`; Drug Hub online `drughub666py6fgnml5kmxa7fva5noppkf6wkai4fwwvzwt4rz645aqd.onion`; Recon **offline** `recon222tttn4ob7ujdhbn3s4gjre7netvzybuvbq2bcqwltkiqinhad.onion`; Exploit.in Forum **offline** `exploitivzcm5dawzhe6c32bbylyggbjvh5dyvsvb5lkuz5ptmunkmqd.onion`. dark.fail's own onion: `darkfailenbsdla5mal2mxn2uz66od5vtzd5qozslagrfzachha3f3id.onion`.
- `darknetlive.com/markets/` → now serves Australian online-casino SEO spam (site dead/parked — itself churn evidence).
- Dread search: `/search/?q=FraudGPT` → 301 → https; `curl -sL -k` on `https://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion/search?q=FraudGPT` → 000 twice. **Unreachable this session despite dark.fail listing it online.**

## 3. Every query issued

### Ahmia (clearnet mirror + fresh token, 20 queries; byte sizes show result volume)
| Query | Bytes | Note |
|---|---|---|
| FraudGPT | 66,905 | multiple live storefronts (see §4) |
| WormGPT | 65,734 | live storefronts + support/payment pages |
| EvilGPT | 30,800 | DarkNetArmy forum threads |
| DarkGPT | 44,586 | two distinct DarkGPT onions |
| AI hacking | 5,674 | **empty** (AND-match, no results) |
| ChatGPT jailbreak | 349,568 | heavy spam + DarkNetArmy threads |
| jailbreak prompt | 1,107,158 | largest set; mostly spam clones |
| PromptLock | 5,010 | **empty** on onion indexes (tool known only from clearnet intel) |
| AI phishing | 189,015 | |
| AI pentest | 145,514 | |
| deepfake KYC | 160,535 | |
| AI botnet | 828,171 | Blueroom botnet-creation pages surfaced |
| red team AI | 13,540 | |
| ransomware AI | 183,511 | security-blog mirrors mostly |
| dark AI | 625,412 | |
| unethical AI | 324,735 | |
| hacking AI | 5,674 | **empty** |
| torch search engine | 1,044,763 | found Torch mirrors + SEO-spam clones |
| onionland | 117,353 | SEO clones only |
| onionland search | 914,061 | SEO clones only |

### Torch (Omega CGI on xmh57 classic mirror, 5 queries)
- `FraudGPT` → **1 match** (TorLinks link-list). `WormGPT` → **0 matches**.
- `jailbreak` → 342 matches, all Kindle-jailbreak/ebook noise (Imperial Library forum).
- `uncensored AI hacking` (AND) → 3 matches. `pentest AI` (AND) → ~50 matches: Portuguese Q&A forum "Respostas Ocultas" `xh6liiypqffzwnu5734ucwps37tn2g6npthvugz3gdoqpikujju525yd.onion` (course chatter, not tool ads).
- Conclusion: Torch's index is shallow/stale for AI-crime names. Recorded honestly.

### OnionLand (clearnet mirror, 5 queries)
- `FraudGPT` → richest set: new storefront `fraudgptnpqx4vbujyhmvaga2z6d4sqgnrk63wsfg7u4ilxws5t3hayd.onion` (example prompts incl. "generate a modular HTTP loader", "compare my HTTP loader output with WD runtime"); directory listings (CoreDir, Tor verified links, Uncensored Search directory AI category, "Forbidden Dark Links", Hebrew portal); scam-list hit "FRAUDGPT (SCAM) fraudgpt3zuz5snkuznqysbaawg3jodnz4e64umkbybhk22ca2spurid.onion" on Deepweb Q&A `g7ohpg6uygzy7f2ecsvadzgrszo5e47hc64o34yjjq7a4rymbfsskaqd.onion` (updated 02/15/2025).
- `WormGPT` → storefronts `wormgpt3y4c7jcb574sov7ypmwbr6pggawpzhfsfohbp4od3obioiuad.onion` ("WormGPT3 - AI Powered Hacking Tool"), `wormgptxgsn3fbljnwiero3cv5agfee26kkhe7xs7awjiqzu6zaetqqd.onion`; Deepweb Answers forum demand thread "Does anyone know how to get darkgpt/wormgpt/bert gpt/dark bert" `muexe2o3hzug5ycmmhiagvmf63x6sqdrirrzouif5mbis5djjceclgad.onion/641/...`.
- `jailbreak prompt AI` → WalletWatch blog post (10 June 2026) "The Inevitability of AI Vulnerabilities: Mastering Prompt Injection Exploits" `wdo4k4wrpnqcxft7xvkysjv5z3gykw2pppuq6zwgohr6hjqdhfpu4lqd.onion/...` + market ad spam.
- `AI hacking` → **KalTeam** `zkwda3wbc6jy5hbhhe7vj2r6ydblayhth3fhmgbtjxq6xysupswzh5ad.onion/ai-database.php`: "AI Database Hacking — Breach AI and machine learning databases. Training data extraction, model weights retrieval, proprietary algorithm access."
- `DIG AI` → TorLi directory verified listing `3q6ytxkudm5zeaje3xg7sg6ogzqy6bugchpshwgvj6ckao4m3u2dsgyd.onion/service/dig-ai` (BTC $109,760 ticker shown).

### Exa (clearnet intel cross-check, 5 queries, all 200)
1. `onionland search engine onion address current` → found live mirrors.
2. `FraudGPT WormGPT dark web AI tool 2026 still active` → stateofsurveillance.org ecosystem piece; mallory.ai "Dark Web Market for Malicious AI Tools Expands Beyond WormGPT and FraudGPT"; factually.co compare (2026-03-15); everykey.com "AI Dark Web 2026" (2026-07-04).
3. `PromptLock first AI powered ransomware gpt-oss` → ESET newsroom + welivesecurity (first known AI-powered ransomware, uses OpenAI **gpt-oss:20b** locally), The Hacker News 2025-08-27, DarkReading, Splunk analysis.
4. `Qilin ransomware AI negotiation chatbot analysts` → Qilin affiliate "on-call lawyers" reporting (RedPacket 2025-06-24), Qualys/ARETE/BlackPoint spotlights (no dedicated AI-negotiation-bot confirmation found in this pass — treat as unverified).
5. `dark web AI agents MCP cybercrime 2026` → SecuritySenses "Threat Actor Dark Factory (Future of AI Hacking?)"; GitHub `badchars/darknet-mcp-server`; arXiv 2609.26761 (MCP agent hijacking); Cisco MCP-insecurity report (2026-02-19); Flare AI-agents cybercrime intel (2026-04-30).

### WebFetch (2 deep reads)
- stateofsurveillance.org "FraudGPT to Huione: Inside the AI Scam Tool Ecosystem" — full tool list captured (§4).
- mallory.ai story — 2026 tool list captured (§4).

## 4. Capability intelligence: what attackers advertise (primary sources read through the proxy)

### Live .onion storefronts fetched this session (GET only; all 200)

**FraudGPT** — `fraudgptqdzh5wnn4qspamvfuktt2bdbok5axsijwlu27cnvpxgy2kyd.onion`
- "Ultimate AI Hack Tool", "most advanced uncensored AI for hacking, fraud, and social engineering". Advertised capabilities: phishing emails/fake pages/social-engineering campaigns; "generate custom malware, trojans, ransomware, and exploit code instantly"; exploit/vulnerability DB; "bypass security systems, firewalls, and detection mechanisms"; carding tools, BIN databases, non-VBV bins, cardable sites; "Scan websites across massive CVE database (PRO)".
- Pricing seen on site: Plus **$32/mo** (promo), **$149→$119/mo**; Pro (monthly/yearly/lifetime); "SOLD OUT: Promotional Starter Kit (€89.99)". No username/password — captcha generates a 32-char User ID. Referral system (`register.php?ref=...`, "Earn!"). Self-hosted blog with comparisons vs HackGPT/DarkBART/WarGPT ("Why FraudGPT Dominates HackGPT").
- **Churn**: ~10 sibling/mirror storefronts indexed (fraudgptcri76…, fraudgptilr7…, fraudgptwbfis…, fraudfeolryx…, fraudcdl2…, fraudcdlt…, fraudp7kc…, gptfkuovk…, fraudgpkklckue… — the last with multi-language SEO pages), one scam-flagged address (fraudgpt3zuz…), plus name-riding casino spam. French/Italian/Czech/Swahili/Thai/Hebrew/Arabic localized pages = SEO farm behavior.

**WormGPT** — `hl2mjycmmejhtf52ealhygt246kkuuzwfth5z2irqwuk3r4lsfuoyxqd.onion`
- "AI generator without moral principles", "GPT Alternative for BlackWork", "PRIVACY FOCUSED • CRYPTO PAYMENTS • NO LIMITS". Features: unlimited characters, coding-focused training, multiple expert models, free Stable Diffusion image gen (beta).
- Pricing page (`/pricing.html`): **V1 $189/mo**, **V2 $249/mo** (API access, code-file work), **V3 Stable Diffusion free** while beta. Disclaimers insist "security researchers" framing.
- Cross-check: original was GPT-J-based, announced on HackForums 2023-06-28, shut down 2023-08-09; variants now on Grok/Mixtral backends ~€60 (stateofsurveillance); **~19,000 WormGPT user accounts leaked 2026-07-15** (mallory.ai).

**DarkGPT** — `darkgptvje5yohv2huc3wofljva2kibojeusveqwiqhffvocgcwbprad.onion`
- "Anonymous AI. No logs. No traces. No limits." Pure-HTML Tor-only chat, configured "to always answer, without refusals or censorship". Donation-funded ($6/$20,000 community goal, XMRPay), purchasable "skip tokens" for queue, currently **temporarily down** ("can't pay the electricity bill"). Second DarkGPT storefront: `darkgptchsrhaq3u35ve4kigjw2rxtdwz7y6b5u4jhlck3xdhmepvhid.onion` (Login/Register). Distinct from the open-source DarkGPT OSINT tool on GitHub.

**PikaSim (Agentic SMS verification)** — `77mlhb4yz4kcg24ewnpevy3balbkb5jwknnriq6ximdpn4r4pzai3qad.onion/agentic-sms`
- Purpose-built **MCP server for autonomous AI agents** to order phone-verification numbers: "Connect any AI agent to PikaSim and let it order SMS verification numbers on its own… 190+ countries… No account. No KYC. Settled in crypto from a prepaid wallet."
- Keyless endpoint `https://pikasim.com/mcp`; tools `create_wallet` (returns wallet code + `ak_live_` API key + spend-only welcome credit), `order_sms_verification` (most quick numbers **under $1**), `create_deposit` (Lightning/USDT/Monero/Bitcoin destinations the agent funds itself). "Mostly real non-VoIP mobile numbers that pass checks blocking virtual numbers."
- Site's own demo: "A real Claude session ordering a Discord verification number through the PikaSim MCP server. It compared 19 countries by price, delivery success rate, and line type."
- Why it matters: this is commodity infrastructure for LLM-agent-driven bulk account creation/verification bypass — the clearest 2026-era "AI-agent crime stack" item found on the onion.

**Dark Web Tools shop** — `uwhunapgupna4lwdocdphly3k7o6rgysvczwcjj6epqq2bv7ax4xkeid.onion` (200 on retry)
- WooCommerce-style shop selling "AI Forex Robot MT5", "AI trading bot Forex MT5", USDT-flashing style items, plus SEO blog ("Top 10 Dark Web Search Engines in 2026" — body had no usable links). Assessed scam-flavored, low intel value beyond presence.

### Advertised but not fetched directly (found via index snippets/forums)

**Blueroom** — `h4mbh55t6lizfg6sgl6he3x7xwxdp62tgymjdwphjlq3cotbzkg6poid.onion`
- Attack-service shop: "Botnet Creation — Build custom botnet from scratch. Malware development, C2 infrastructure, infection vector, command panel"; "**AI Chatbot Service** — Compromise AI chatbot deployments. Customer service bots, support AI. Training data, conversation logs"; "Call Flooding — thousands of calls per minute". "Private Blueroom handling, fast delivery, discreet support."

**KalTeam** — `zkwda3wbc6jy5hbhhe7vj2r6ydblayhth3fhmgbtjxq6xysupswzh5ad.onion/ai-database.php`
- "**AI Database Hacking** — Breach AI and machine learning databases. Training data extraction, model weights retrieval, proprietary algorithm access." First-person AI/ML-specific attack service seen on the onion this session.

**ML HACKER / HIRE ML HACKER / AI SECURITY** — `d3ka2mnkpqd6g7o3lot4uqnihzlhfmd2x2zfjvhi3cjolxly6st2kaad.onion` + mirror `wsdwonpewkwtshchi7g24576nbcp37qv3kj2d3xscixizziplqjhjqid.onion`
- "Advanced security testing for AI-driven applications and autonomous systems" — for-hire landing pages (unverified capability; scam-risk high).

**Debay** — `deba7hcel5t4nodxhyik2oamkf3bl3gyvae7kq3xtxs3fnw2jvl3doyd.onion`
- Marketplace listing item p=68 "**Claude API / AWS Bedrock / AI APIs**" — resale of AI API access (stolen-account/hijacked-key pattern per intel reporting); also sells "Buy Malware | Rats | Keylogger" (item p=61).

**DarkNetArmy Forums** — `darknet2icddbyt7othtadtgxne7tdxumutxnuzju2hcooll6eswgnqd.onion` (+5 mirror addresses indexed: darknet4esmeg…, darknet4zvovn…, darknet73y7q4…, darknet7ecwhl…, dna777qher…, dna777z3eui…, dna777z3jje…)
- Thread titles indexed (full posts behind login — not entered): "(2026) HOW TO JAILBREAK AI: GPT, CLAUDE, GEMINI, GROK & OTHERS ✅", "ADVANCED JAILBREAK TOOL", "BLACKHAT CHATGPT … JAILBREAK CHATGPT (WORKING)", "CHATGPT TO EVILGPT [LATEST ChatGPT JAILBREAK] [ASK ANYTHING]", "ChatGPT Uncensored [Jailbreak]", "ChatGPT Plus 6 Months Method", "HOW TO USE CLAUDE AI FOR FREE", "[UPDATED] OPENAI GPT-4 FREE | UNLIMITED PREMIUM", "💀 CHATGPT PROMPTS 💀", "🤑 Uncensored AI For Coding 🤑", "THE BEST Uncensored AI (No-Login, Pictures, Coding) - High Mode", "HOW TO MAKE MONEY with AI METHOD - NEW".
- **Churn signal**: the same threads served from 5+ rotating onion addresses = cheap mirror-farm, likely scam/lead-gen as much as real forum.

**Dark Hacker Zone forum** — `wk54p5xel7uqhfl5uzpcqrk6npsx5td5jsa4iqrkmquimhynhks7ppyd.onion`
- Threads: "Dark AI for Hackers 💣 - Page 6", "7. AI Jailbreak - Sensitive Information Disclosure", "🖥️💀 UNCENSORED AI".

**TALMAR** — `talmar6s34dyof777yffwowrs3tmyesoyrxneixvxqionds7cm6hpeqd.onion` + mirror `talmar6sv3ivpjyb4v64xtfflhhaqce4gv2cgo4kc5j5te36b2azbfyd.onion`
- "JAILBREAK COORDINATION" — dedicated jailbreak coordination site.

**JailBreak AI** — `n6vbpq45rw3zgwg6hgkrq5nqfpzu3e46irzbrknoowe2bxo4dbgk62yd.onion`
- "Uncensored AI Chat – Free, No Filters | JailBreak AI".

**DIG AI** — `digdig2nugjpszzmqe5ep2bk7lqfpdlyrkojsx2j6kzalnrqtwedr3id.onion` (Japanese Hidden Wiki by ときえのき, `enokidtzvhaflcixtk6xbo7djdkekbsmjek6y2xt37za6il7tqyy3bid.onion`: "アカウント無しで無検閲AIが使える" = account-less uncensored AI); TorLi verified listing; TForum thread "Is Dig Ai Down?" — churn (instability).

**Hebrew darknet portal** — `darkbw7rlwnxydjrkc6tdzzztzufevh7l7sdtgjsyihpyz64fr3c4kyd.onion` — AI section: "DIG AI :: DarkGPT :: FraudGPT :: WormGPT" (non-English ecosystem confirmation).

**Japanese BBS Z80H** — `zepzzkoz3cb3cm3hi5roh5zagwgkvotnqwwa2b7az7qw33osfxjgljyd.onion` — thread "【脱獄】ChatGPTなどのLLMを日本語で脱獄する方法【AI】" (Japanese-language LLM jailbreak methods).

**Worm GPT local / Revive** — `revivewah4hxtbc5c3vfymd65siz3cwksqh4yabc4c7mjjpsxopjj4qd.onion` — "Worm GPT, darkest GPT for your local machine" — self-hosted uncensored-model distribution.

**Undress AI** — `undress3bkljozfp6ne5cnttcdd7vmh4dvkwol3776yvubumweoaqiqd.onion` — nudify/deepfake service with deposit flow (AI-abuse service; adjacent to the lane's scope).

**Sherubit "Bitcoin Fake Transaction AI 2025"** on Unimarket — `unimktsvz42li7s27bsn7lorf6byfdxowvvt7m6jpmfuy2ec7yvuqnqd.onion/product/sherubit-bitcoin-sender-pro-...` — "Send up to 500 BTC Per day" fake-tx scamware with AI branding.

**Best Carding World** — `jaat7efxnopgxe7ypxzqpb46qmbaca36r7shexsowofexbfqp6p7xaad.onion` — "Utilise AI to Amplify your Cyber Attacks"; "HOW AI IS DOMINATING CARDING WITH EASE IN 2024: 1 pieces 1.9 USD" listing.

### Intel-vendor cross-check (clearnet; corroborates + extends the onion haul)

- **ESET (2025-08-26/27)**: **PromptLock** — first AI-powered ransomware found in the wild (POC stage); embeds **gpt-oss:20b** via local Ollama API to generate cross-platform lock scripts at runtime. Not advertised on onion indexes (Ahmia/Torch negative results above support that).
- **Mallory.ai (2026-06/08)**: **GhostGPT** (branded criminal AI-as-a-service, "no logs, instant responses"); **KawaiiGPT** (free dark LLM, Unit 42; vuln scanning + malicious code gen); **"AI Pentest Checker"** sold by Russian-speaking actor **"Trim"** (2026-08-21): jailbroken **Claude Opus 4.8 + GLM-5** wired to **Nuclei, ffuf, katana, gitleaks** for automated web vulnerability scanning; **MessiahGPT** (BreachForums/Telegram; uncensored platform advertising ransomware/phishing kits/stealers/crypters/rootkits; free trial queries, low-cost crypto subscriptions, no KYC); many such tools are "wrappers around legitimate models, stolen accounts, or hijacked API keys". **WormGPT ~19,000-account leak (2026-07-15)**.
- **State of Surveillance (2026)**: FraudGPT sold by "CanadianKingpin" since 2023-07-22 at **$200/mo or $1,700/yr** (today's onion charges less — price collapse signal); WormGPT variants ~€60; **DarkBard, WolfGPT, DarkGPT, Evil-GPT, XXXGPT (sextortion), GhostGPT**; **Huione Guarantee** (Telegram scam supermarket; ~$70B flow; sells **AI face-changing software for live video calls $200 lifetime**, **WormGPT licenses $200 lifetime**; US Treasury designation 2025-05, FinCEN action 2025-10; AI-vendor revenue +1,900% YoY 2024) and **Xinbi Guarantee** (~$8B; Telegram purged thousands of channels late 2025); abused voice-clone APIs (**ElevenLabs $5/clone**, Speechify, PlayHT, Lovo); deepfake video (DeepFaceLive/DeepFaceLab, Magicam, Amigo AI, Avatarify for fake job interviews); AI phishing kits with ChatGPT integration + AiTM MFA bypass (Intel 471/Proofpoint); **BlackMamba** LLM-keylogger PoC (HYAS).
- **Qilin**: affiliates offered on-call lawyers for negotiations (2025-06 reporting). Claims of an AI negotiation chatbot were **not confirmed** by anything I read this session — left unverified.

## 5. Market churn notes (2026-09-29 state)

- **Archetyp Market**: seized by German LE (dark.fail alert banner, current).
- **Recon**: offline (dark.fail). **Exploit.in**: offline at listed address (dark.fail). **Drug Hub**: online. **Dread**: listed online but **unreachable this session** (2 attempts, 000).
- **darknetlive.com**: parked → casino spam (a long-time churn/status source is gone).
- **OnionLand**: clearnet .com dead; moved to .net/.live/.cc/.io mirrors; onion search endpoint down today.
- **Ahmia onion**: search endpoint redirects home for non-browser clients; clearnet mirror required (token+cookie anti-bot flow added recently).
- **Torch**: alive on 3+ mirrors, index shallow; new-mirror search.htm ignores GET params from curl.
- **AI-tool market churn pattern**: FraudGPT/WormGPT brand splintered into 10+ SEO storefront clones with multi-language pages and at least one scam-flagged address; original-era prices ($200/mo) collapsed to $32–$249 promos; revenue shifted to (a) no-KYC agentic infrastructure (PikaSim), (b) stolen/hijacked AI API resale (Debay "Claude API / AWS Bedrock / AI APIs"), (c) Telegram ecosystems (Huione/Xinbi, purged late 2025), (d) BreachForums-branded relaunches (MessiahGPT).
- **Scam-vendor Q&A** (`g7ohpg6uygzy7f2ecsvadzgrszo5e47hc64o34yjjq7a4rymbfsskaqd.onion`, Scam Vendors category, last updates Jul 2025 / Feb 2025): "FRAUDGPT (SCAM)", "PATHFINDER RAT (SCAM)", "WOLF BANK HACKER" — most AI-hacking "vendors" on the onion are themselves scams; treat storefronts as advertising claims, not verified capability.

## 6. Dead ends / blocked paths

- Ahmia **onion** search endpoint unusable from curl (302→home; https→000) — clearnet mirror used instead (documented fallback).
- Torch new mirror `search.htm` ignores curl GET params; only the classic `/cgi-bin/omega/omega` worked.
- OnionLand `.com` DNS-dead; onion search endpoint 000 via proxy — clearnet mirror used.
- **Dread**: unreachable this session despite being listed online (2 attempts). Its search would likely be the best forum-text source; not obtained.
- **darknetlive.com/markets/**: parked/casino spam; no market list.
- Forum interiors (DarkNetArmy thread bodies, Dark Hacker Zone posts, Deepweb Answers, TForum, Respostas Ocultas): indexed snippets only; full threads require accounts — **not created** (rules).
- **Firecrawl**: both `FIRECRAWL_API_KEY` and `FIRECRAWL_API_KEY_2` → 401 "Unauthorized: Invalid token" (stale keys — flag for other lanes).
- **Exploit.in / Nulled / Cracked / RAMP**: no live public entry point found this session (Exploit.in listed offline by dark.fail).
- Ahmia AND-matching: `AI hacking`, `hacking AI`, `PromptLock` genuinely empty on onion index.
- Qilin "AI negotiation bot": no confirmable source found — not claimed.

## 7. Raw artifact index (this workspace)

- Ahmia result pages: out/tmp/a_*.html (20 queries); parsed: out/tmp/ahmia_all.txt (4,710 results).
- Torch pages: out/tmp/torch_*.html, out/tmp/t2–t4.html.
- OnionLand pages: out/tmp/ol_*.html.
- Storefronts: out/tmp/p_fraudgpt.html, p_fg_reg.html, p_wormgpt.html, p_wg_price2.html, p_darkgpt.html, p_pikasim.html, p_fg_price.html (404).
- Status: out/tmp/darkfail.html, out/tmp/dnl_markets.html.
- Scripts: out/tmp/ahmia2.sh (token+cookie search), out/tmp/parse_ahmia.py, out/tmp/parse_ol.py, out/tmp/strip.py, out/tmp/exa.sh.
