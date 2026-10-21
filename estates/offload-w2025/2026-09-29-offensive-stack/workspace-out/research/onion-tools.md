# Onion lane: offensive-security tooling on onion services

Run: 2026-09-29, VM C:\Users\prekzursil\.zcode\workspace\default, Tor expert bundle D:\opt\tor (v0.4.9.13) already running.
All onion fetches via `curl --socks5-hostname 127.0.0.1:9050` (read-only GET/POST search queries only; no registration, no downloads, no transactions). Liveness probe = GET / with UA Mozilla/5.0, record HTTP code + `<title>`. HTTP 000 = unreachable after >=2 attempts this session (may be slow/online later).

## Tor verification (this session)
- 9050: `curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip` -> `{"IsTor":true,"IP":"45.84.107.200"}`
- 9150: same -> `{"IsTor":true,"IP":"109.70.100.6"}`

## Helper scripts written (this session)
- `out/research/ahmia.sh` — ahmia.fi search; scrapes the anti-bot hidden token (e.g. `b178a1=9e72f9`) from homepage each run; without token, search silently redirects to homepage.
- `out/research/ahmia_full.py` — parses all `_ahmia_*.html` into `out/research/ahmia_candidates.json` (addr -> hits[{q,url,title,desc,last_seen}]).
- `out/research/torch.sh` — Torch search. NOTE: GET `/cgi-bin/omega/omega?P=...` returns curl exit 52 (empty reply); POST with `P,DEFAULTOP=and,DB,FMT=query,xDB,xFILTERS=.~~` works.
- `out/research/liveness.sh` — the liveness probe.
- Inline Python parsers for OnionLand (`<div class="link">` / `<div class="desc">`) and Tor66 result HTML.

## Queries issued (complete list)

### Ahmia (clearnet ahmia.fi; same index as its onion)
1 penetration testing toolkit | 2 ransomware builder | 3 metasploit | 4 hacking tools pack | 5 c2 framework | 6 cobalt strike | 7 red team toolkit | 8 exploit pack | 9 initial access | 10 botnet source | 11 pentest lab onion | 12 github mirror | 13 gitea onion | 14 gitlab onion | 15 source code leaked | 16 ransomware blog | 17 leak site | 18 ddos panel | 19 stealer | 20 kali linux mirror | 21 apt repository onion | 22 software mirror | 23 cracked software | 24 expoit database (sic) | 25 osint tools | 26 onion search engine | 27 exploit database | 28 cve mirror | 29 packet storm | 30 xss forum | 31 dread forum | 32 breach forums | 33 leaked database | 34 onion git hosting | 35 privatebin onion | 36 pastebin onion
- 2,676 unique .onion addresses parsed into `out/research/ahmia_candidates.json`.
- `/api/search/` = 404 (dead endpoint). Ahmia onion verified live: `juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion` (HTTP 200). Its anti-phishing CSS whitelists a second official onion pattern `msydqst.*2kzerdg.onion` (not resolved in tests).

### Torch (POST /cgi-bin/omega/omega)
1 pentest (POST probe) | 2 penetration testing tools | 3 red team toolkit | 4 c2 framework | 5 exploit pack | 6 hacking tools | 7 github mirror | 8 ransomware
- Live: `xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion` (HTTP 200; address corroborated by factually.co fact-check). Old v2 `xmh57jrzkzexv3s6.onion` dead (HTTP 000). ~10 results/query.

### OnionLand (GET /search?q=)
1 penetration testing tools | 2 github mirror | 3 gitea | 4 ransomware builder | 5 exploit db | 6 kali linux | 7 privatebin
- Live onion: `3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion` (address published on their own clearnet homepage onionland.cc; ~20 results/query; links are encrypted `/r?s=` redirects — parse `<div class="link">` for plaintext onion).

### Tor66 (GET /search?q=)
1 pentest | 2 hacking tools | 3 ransomware | 4 gitea
- Live: `tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion` (HTTP 200). Also runs Fresh Onions / Random Onions / TOP directories.

### Exa (api.exa.ai/search)
1 "Torch onion search engine current address 2026 xmh57j" | 2 "OnionLand search engine official onion address 2026" | 3 "Haystak onion search engine official address 2026" | 4 "Dread forum official onion address 2026 dark fail verified" | 5 "danwin1210 Daniel onion address danielas3rtn7uw3t6p2 free hosting"

### Firecrawl (api.firecrawl.dev/v1/search)
2 attempts -> HTTP 401 `{"error":"Unauthorized: Invalid token"}`. DEAD END — the env key was rejected this session.

### ransomware.live (clearnet API)
- GET `/v2/recentcyberattacks` -> HTTP 200, 100 entries (fields incl. claim_url, domain, infostealer_data).
- GET `/v2/groups` -> 403 groups listed, but free tier exposes only ransomware.live profile URLs, no leak-site .onion.

### GitHub (gh api search/repositories)
1 q=onion+search+dark+web | 2 q=onion+link+list+security | 3 q=darknet+osint+tool | 4 q=hidden+service+crawler+security | 5 q=darknet+monitor+ransomware+tor (no new results)
Plus repo metadata + README install sections: badchars/darknet-mcp-server, vichhka-git/OpenTor, rly0nheart/thedevilseye, evenblad3/onion-links.

### Other directories/APIs
- dark.fail/dread (clearnet) -> Dread onion extracted from HTML: `dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion`.
- onion.wiki/daniel-winzen -> Daniel's onion `danielas3rtn54uwmofdo3x2bsdifr47huasnmbgqzfrec5ubupvtpid.onion` (HTTP 200) — classic free-hosting/pastebin platform GONE; onion now fronts danwin.dev (E-Mail + GitHub IPv6 proxy only).
- torproject check API (above).

## FINDINGS

### A. Onion search engines / directories (verified HTTP 200 this session unless noted)
1. Ahmia — `juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion` — onion search index; clearnet ahmia.fi works; token-gated search.
2. Torch — `xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion` — oldest engine; POST-only CGI.
3. OnionLand — `3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion` — best result quality of the four; clearnet front onionland.cc.
4. Tor66 — `tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion` — engine + Fresh/Random/TOP directories; unique finds (Gitea cluster, RANION/ransomware cluster).
5. DANEX — `danexio627wiswvlpt6ejyhpxl5gla5nt2tgvgm2apj2ofrgm44vbeyd.onion` — "DarkNetEXplorer Search", live.
6. Toogle — `tooglenevuswtwz6ho66yxwukxqxdfkz3mgo4p2l336ycb7qzynwiuqd.onion` — live (HTTP 200).
7. BT4G — `bt4gcomcf45mceic277o3goxvizgh6yj6vazoj4o63wfqujzykzdavyd.onion` — torrent search on onion; surfaces tool/warez torrents (e.g. "Malwarebytes Anti-Exploit" listing seen).
8. Haystak — `haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion` — UNREACHABLE (2 attempts, HTTP 000) though address corroborated by 2 independent clearnet sources.
9. DNM Trust — `verifokewjcomhdf2rk3kloe4we2gkurqvax4tjnhepbx63dj7fyfoad.onion` — "Verified Mirror Registry & Anti-Phishing Hub for Anubis & Nexus"; live; useful for onion address verification discipline.

### B. Git hosting on onion (the "GitHub mirrors" of this lane) — verified live
1. **Darktea Gitea** — `it7otdanqu7ktntxzm427cba6i53w6wlanlh23v5i3siqmos47pzhvyd.onion` — "Gitea on the Dark Web"; 296 repos inventoried via `/api/v1/repos/search`. Headline security-relevant repos (descriptions quoted from API output):
   - Leaked source: Anonymous/Windows_XP_NT5 (XP SP1 source), Anonymous/Windows_Server_2000_Win2k3, Anonymous/MS-DOS-6, Anonymous/Windows_10 shared-source kit, Anonymous/OPNsense, Anonymous/Claude-Code-Source (v2.1.88 leak), mforce2/symphony (Opera Presto 12.15 leaked sources), unc0uth/AMI-BIOS-Jetway, Anonymous/AMD_Navi_GPU, Anonymous/TETRA_crypto (tetra:burst RE), estrogenic/Vanadium-2023-2025-Leak-Server, Anonymous/re3.
   - Exploit/vuln repos: Anonymous/BackLotus ("attempt at replicating BLACKLOTUS capabilities"), Anonymous/BlueHammer, Anonymous/GreenPlasma (Windows CTFMON arbitrary section creation EoP), Anonymous/MiniPlasma (CVE-2020-17103), Anonymous/RedSun, Anonymous/ZenBleed (CVE-2023-20593), Anonymous/PPPwn (PS4 PPPoE RCE), seekrit_stash/PrintNightmare (CVE-2021-1675), Anonymous/YellowKey (Bitlocker bypass), darkteauser/exploits, 0x00/shodan-cracker.
   - Malware/RAT: ksimz/BackLotus, MyEyesAreBleeding + ksimz/ransomrar ("ransomware application that masquerades as a RAR password cracker"), n0tr1v/rust-rat ("rat/cnc"), NoctisUmbra/LibreMalwareUtilities ("utilities for developing malware in rust"), Hiyouthereuk/Iosdroid-RAT (Android+iOS RAT), Anonymous/xmrig (0% donation), Lativia/profitmaker ("first Python Base Log Sorter for Stealers Log"), ures/Bitcoin_Private_Key_Scanner_from_Blockchain.info (+5 forks), Anonymous/payloads (Hak5 BashBunny/RubberDucky).
   - OpSec/guides: anonymousplanet(org)/thgtoa ("comprehensive guide for online anonymity and OpSec"), c0mmando/Hack-Liberty-Resources + forum.hackliberty.org archive, Netflix/PentestingDarkWebSites, Darktea/Guides (git-over-Tor how-to), Err0r/ANALizer ("run scripts against web sites through tor"), n0tr1v/bhcli (CLI for Black Hat Chat/Daniels Chat).
2. **Datura Gitea** — `gdatura24gtdy23lxd7ht3xzx6mi7mdlkabpvuefhrjn4t5jduviw5ad.onion` — OPSEC Bible (Nowhere/OPSEC + Hacking + blog-contributions), archive/EndGameV3 ("Local Copy of Dread's EndGameV3"), COWE ("Common OPSEC Weakness Enumeration" proposal), Darknet-Lantern (P2P onion-link aggregator), Datura-OS/DaturaOS-aptrepo, MetaDataRemover, and takedown-shield mirrors (archive/arti, archive/darkfi, archive/chutney, archive/debian-tor, archive/usbguard, archive/docker-obfs4-bridge, archive/docker-snowflake-proxy, nihilist/haveno, nihilist/MoneroSSO). Second address `gdatura24kxaw44...onion` dead.
3. **Ashigaru Gitea** — `ashicodepbnpvslzsl2bz7l2pwrjvajgumgac423pp3y2deprbnzz7id.onion` — "Explore - Gitea server" hosting Ashigaru/Ashigaru-Mobile (Samourai wallet fork).
4. **Open Privacy Gitea** — `gitopcybr57ris5iuivfz62gdwe2qk5pinnt2wplpwzicaybw73stjqd.onion` — official Open Privacy (Cwtch) Gitea.
5. **RIGHT TO PRIVACY Gitea** — `gg6zxtreajiijztyy5g6bt5o6l3qu32nrg7eulyemlhxwwl6enk6ghad.onion` — hosts themusicgod1/graphite2 ("graphite evacuated from nsa/microsoft") and RightToPrivacy/proxy-lists (collection of frontends). Alt instance `gg6zxtreuk4fwncctpau54vbl6qclj477j4evmopiqqxlj6f6pr7x4ad.onion` indexed, untested.
6. **git.dotya.ml mirror** — `2crftbzxbcoqolvzreaaeyrod5qwycayef55gxgzgfcpqlaxrnh3kkqd.onion` — Gitea mirror of clearnet git.dotya.ml (live, title verified).
7. **Arav's dwelling Git** — `qqitm7qlsbbubwmjos4cqzmvkqidg34rfnbyhuydhalep33fbvh22xyd.onion` — Gitea (live, "Explore - Arav's dwelling / Git").
8. **CodeCoffin** — `codecfn6joqlr6fiwxdreztojh563y33zpymvdn6zkxk2gtnggh6g5id.onion` — git host, live.
9. **Gitfield Forgejo** — `foundryalislzskkxse24sxkvs7hztrw6jqjt6jgpp3uvpnpigfwdkid.onion` — live.
10. **MMGen Forgejo** — `mmgen55rtcahqfp2hn3v7syqv2wqanks5oeezqg3ykwfkebmouzjxlad.onion` — mmgen-wallet + mmgen-geek-tools (live).
11. TransAtlantic Drama Club git — `fbbpkxllx6q6thq7nvgy6htx4yhcqzvlsqowuuk6tnz5lgcsoqd4zhid.onion` + `n4celbknwkn4twryohqzdko3txv7p3s7kgalvdglapd74vg3yrzin6id.onion` — live.
12. bentasker projects — `lomteqnxehqjdemqgzse7xchjlusgnpoxq2fpmz3yuukyfzc22t5gwyd.onion` — projects.bentasker.co.uk on onion (no /api/v1; custom site; btasker/Forgejo-Markdown-Mirror indexed).
13. `63d5k6ffofpgzmu5xajmjuqbw5erponapyaukkrzbf4jijjutdsktqqd.onion` — "Gitea API" page, live.
Untested/indexed only: `wgnobgtoeuxgsziwypnya4csbqx7gh4kgbwogv6ju25fwhwvg6vxgkyd.onion` (tested: resolves to "SpammersFamily — Tools & Access" shop which also fronts a Gogs), `potatoynwcg34xyodol6p6hvi5e4xelxdeowsl5t2daxywepub32y7yd.onion` (Golang ipxeplease code-review host; unreachable).

### C. Package/software repositories on onion (verified live)
1. Tails Debian package repository — `umjqavufhoix3smyq6az2sx4istmuvsgmz4bq5u5x56rnayejoo6l2qd.onion` ("Index of /dists/").
2. F-Droid official — `fdroidorg6cooksyluodepej4erfctzk7rrjpjbbr6wx24jh3lqyfwyd.onion` (+ `fdroidorub4kafzycyzuxyc4pyr6hjs7nrxggyyupa36jiilez3vrfid.onion`).
3. Privoxy + SourceForge download mirror — `privoxy5wtwbtk4wwyrdbg6oxeghvhghghmokcx2iawydkqmaztfbbid.onion` (Index of /sf-download-mirror/).
4. Qubes OS onion — `qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion` (Torch-indexed; untested).

### D. Ransomware/leak-site intelligence on onion (read-only)
1. **RansomLook onion** — `ransomlookumjrc6erzqn467lkcu2t5h4enjzfigvsxrrktxicysi2yd.onion` (HTTP 200) — open ransomware intel (source: github.com/RansomLook/RansomLook). Home currently links groups: chaos, clop, imnotavillian, interlock, kairos, killsec3, metaencryptor, the gentlemen, ulose, wallstreet. `/browse` page (1.0 MB) yields leak-site .onion addresses:
   - Blackbyte: `53d5skw4ypzku4bfq2tk2mr3xh5yqrzss25sooiubmjz67lb3gdivcad.onion`
   - Cicada3301: `cicadabv7vicyvgz5khl7v2x5yygcgow7ryy6yppwmxii4eoobdaztqd.onion`
   - Embargo: `embargobe3n5okxyzqphpmk3moinoap2snz5k6765mvtkk7hhi544jid.onion`
   - Malas: `malas2urovbyyavjzaezkt5ohljvyd5lt7vv7mnsgbf2y4bwlh72doqd.onion`
   - Red R…: `33zo6hifw4usofzdnz74fm2zmhd3zsknog5jboqdgblcbwrmpcqzzbid.onion`
   - Unattributed in page context: `2c7nd54guzi6xhjyqrj5kdkrq2ngm2u3e6oy4nfhn3wm3r54ul2utiqd.onion`, `dataleakypypu7uwblm5kttv726l3iripago6p336xjnbstkjwrlnlid.onion`, `dgnsojdh5d3wd72ubardzpot4f474ack6y4bk6upldm2kjucskcou2ad.onion`
   Alt RansomLook addresses: `ckz3vogaxctdaseysedq3tpg4r7n6ixe23dn6iv75av5p6b526mjbtid.onion` (dead at test time), `ckz3voga72xjwbm7gdjpmy763twukj2z5ocz5sxhz7sc534vav7cyvqd.onion` (Tor66-indexed, untested).
2. Tor66 "ransomware" hits (untested liveness): `ransomwr3tsydeii4q43vazm7wofla5ujdajquitomtd47cxjtfgwyyd.onion`, `ranionvkxg26pwtjgfjamj4my7t2pqv7mgriczr6kf2y6aixms32ipyd.onion` (RANION), `rdcfwq7i2ik6i3y35dmfkvflzqd4f2qktmx7wj4gfaim4e7fvajmdsqd.onion`, `zprxx7sfc26rufggreanowmme5qqouqegr2efnko6erycquwvpq5egid.onion`, `ssg3qvvu62kjmmltvlt574vdmv5jnklya3kqgefbvk7bpgjxyfe7vbqd.onion`, `6asxhsjql6jjnznrfjqqqe7kvjrmn45buzlqf3p3nqkrtkdlbkewuyad.onion`.

### E. Forums / markets / services with tooling activity (read-only intel; liveness as marked)
1. Dread — `dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion` (HTTP 301 = alive; dark.fail-verified; content login-walled).
2. HeLL Forum — `hellccam72ck3wajux74nordnnx6aoj5odun2bqnt6vggfz5nca4noyd.onion` + `helllbtvpp2jcwuqwwiymybimd2e2uo7dyb4dgejsudmhaiiyzmalxad.onion` (HTTP 200).
3. DarkNetArmy Forums — `darknet4zvovn77zgkppdrgzuf7i3kvn5aepmjp6g6djyyzxwyjyfcyd.onion` (HTTP 200; posts: "OPEN SOURCE INTELLIGENCE TOOLS FOR WEB ATTACKS AND RECONNAISSANCE", "Dorks Pack of the Best Tools" — mirrors `darknet73y7q47uzlvah7r3cdsg63zdczaa7a2bha2atnut3kqxdyyyd.onion`, `dna777qherukjwo6tux6tpy45x4wqg3jyg7kjkhwiqo7ho6fojpppsid.onion`).
4. PANDORUM — `pandorumwzudcql6f3ourlqw2voyh332a4tke64x7k46ds564adoeeyd.onion` (HTTP 200; has "C2 Frameworks" category).
5. Riddler's Stash — `rstashbrj3mxpy244j5wetlfq3k7h4dz2it3glx6e3ry437djbloweid.onion` (HTTP 200; "Crime Marketplace - Buy & Sell Credit Cards - Software - Backdoors - Ran…"; alt `rstashbrabv5ezel76m2vdzet4szdzncwvgd2q5y3kbsdw3q6spcglid.onion`).
6. DarkWay / "LONELY ROAD" — `darkn5g756epq6t6fkqdo3mvkxlvwjtgabsbh3x47yhqg3uguiy5z5yd.onion` (HTTP 200; /market/91 "(Hacking Tools)").
7. UnderMarket 2.5 — `undermarb6amvty6byuqyuutu7rqsdevqik2kz32zeulrnabxb3tluqd.onion` (HTTP 200; Ahmia-indexed "lucky strike" listing tagged cobalt strike); mirror `puyr3jb7wuztfdva6ghrpyxisdua335vduvrv6u6j6nhkgz6kypzteqd.onion` unreachable.
8. BoomMarket — `boom223dn5ryzidnl7ln2k7aq4z3ni32n4m7sfsd2dqeil6zo56vuuid.onion` (Ahmia-indexed; listings "DIAMONDFOX GORYNYCH BOTNET PANEL + BUILDER", "CERBERUS v10"); `silksjieoz36qxflcg54mz6xsj7a2vz2p3npcwxjl3erixua6jlkaeid.onion` ("Cythosia Botnet v3 [Webpanel + Builder]"). Capability intel: botnet panels/builders actively sold on markets 2024-2026.
9. Leaked-source sellers on Ahmia (indexed, untested): `ru3cyqujepvyvca7gwbqg5pl76y7mqfmaftgi734uzhbpagzcxiwdxyd.onion` ("PEGASUS RAT FULL VERSION SOURCE - 1000$ RAT FULL SOURCE CODE LEAKED!"), `darkpb3wllkvobilurc7m57qvlvjaawsnpqphxdxpvqvlibwkigtpaqd.onion` ("THANOS ANDROID BOTNET – SOURCE CODE"), `kw4zlnfhxje7top26u57iosg55i7dzuljjcyswo2clgc3mdliviswwyd.onion` ("Anubis Android Banking Botnet v.2.5"), trusthkimrfokhmvnrgljfed63h5vz23rlgf7e3zsapbdel37rl5mzqd.onion ("SPOOFING OTP BOT SOURCE CODE").
10. PoC chatter: `jaat7efxnopgxe7ypxzqpb46qmbaca36r7shexsowofexbfqp6p7xaad.onion` — "[PoC] CVE-2026-42945 - NGINX Rift Memory Corruption Flaw" (Best Carding World shop/blog — unverified, scam-adjacent).
11. Hire-hacker/service sellers (scam-heavy, low value): `torzcd47rw4qh36g4yqxvv2tmifgmu6jjalkyqz4e4lzzwtfdfc7qaqd.onion` (also surfaced "GitHub code-signing certificates stolen" news post), KalTeam `a6pdp5vmmw4zm5tifrc3qo2pyz7mvnk4zzimpesnckvzinubzmioddad.onion` (indexed; "Network Penetration"), HAK TEAM `hxlr57ifipooabc45y2unmoshykfqaafpju6rrjot2vpci3ijg3snoyd.onion`, Lumos `seunigvykiozpflbfj3deqozbbyrsouhhpdrugdbj5sshiedrr52bpid.onion`, DNA forum `vijosxvbf23h2yai2bauzjw4b5bawnbum24q2x2unp5onjdkn2l4zzid.onion`, `zkwda3wbc6jy5hbhhe7vj2r6ydblayhth3fhmgbtjxq6xysupswzh5ad.onion` (KalTeam "Server Breach"/"Malware Delivery" posts).
12. FraudGPT-adjacent: `fraudgptqdzh5wnn4qspamvfuktt2bdbok5axsijwlu27cnvpxgy2kyd.onion` ("FraudGPT & Related AI Tools" articles).

### F. Archives / libraries / intel blogs (verified live unless noted)
1. Imperial Library of Trantor — `kx5thpx2olielkihfyo4jgjqfb7zx7wxr3sd4xzt26ochei4m6f7tayd.onion` (HTTP 200; pentest books: "Hands-On Penetration Testing With Python", "Web Penetration Testing With Kali Linux").
2. DEF CON archives — `g7ejphhubv5idbbu3hb3wawrs5adw7tkx7yjabnf65xtzztgg4hcsqqd.onion` — Torch-indexed DEF CON 27/28/32 talks, workshops, demo labs; UNREACHABLE in 3 attempts (large/slow service; retry later).
3. InfoCon conference archives — `w27irt6ldaydjoacyovepuzlethuoypazhhbot6tljuywy52emetn7qd.onion` — Torch-indexed (DEF CON, BotConf, BSides); UNREACHABLE in 3 attempts.
4. tweedge's blog — `tweedge32j4ib2hrj57l676twj2rwedkkkbr57xcz5z73vpkolws6vid.onion` (HTTP 200) — hosts "A mirror of the Belsen Group FortiGate configs leak" (capability intel: leaked firewall configs mirror). Alt `tweedg66kb6wsqp2stwj4ot2bluauafurdxgh5udpr2lsl552mtfa3id.onion` dead.
5. 0ut3r Space — `reycdxyc24gf7jrnwutzdn3smmweizedy7uojsa7ols6sflwu25ijoyd.onion` (HTTP 200; darknet/security blog).
6. Ming Di Leom blog — `xw226dvxac7jzcpsf4xb64r4epr6o5hgn46dxlqk7gnjptakik6xnzqd.onion` (HTTP 301 alive; security blog, "Tag: gitlab").
7. Dark Web Link — `dwltorbltw3tdjskxn23j2mwz2f4q25j4ninl5bdvttiy4xb6cqzikid.onion` — Torch-indexed (GitHub/RaaS archives); unreachable at test time.
8. HACKERSTARS — `hsssfzzzxboe66mtswcrhxpzlmiejv246pun3ttasg3x4y6xayjag5id.onion` (Ahmia-indexed; "ShadowV2 Botnet — DDoS-for-Hire Service Targets Misconfigured Cloud Containers").

### G. Paste mirrors on onion
1. PrivateBin instance — `5b6kg6vyo4uk2w7y6eibyuhvpoxnkyaxkjqo72pomcbgbqfmenas3eqd.onion` (OnionLand-indexed; untested).
2. paste service — `d7n5aedn2ejfyvlwt5vzpm3gmnqqtfvlwbvx526e3ppjn44wuy3wumyd.onion` ("Redirect to /paste"; untested).
3. dpaste mirror — archived as repo on Datura Gitea ("dpaste mirror before mozilla takes it down").
4. Daniel's hosting pastebin/free hosting — DEAD (platform discontinued; onion now fronts danwin.dev mail + GitHub IPv6 proxy). GitHub IPv6 proxy (danwin.dev/github-ipv6-proxy/) still a useful access shim.

### H. Clearnet GitHub tooling FOR onion work (from gh sweep)
1. badchars/darknet-mcp-server — 464★, pushed 2026-09-22 — MCP server: dark-web intel (breach data, ransomware tracking, Tor .onion access, malware analysis, blockchain intel, exploit search, stealer logs). Install (from README): `npx darknet-mcp-server` or `claude mcp add darknet-mcp-server -- npx darknet-mcp-server`. Node -> likely Windows-native; not execution-verified.
2. vichhka-git/OpenTor — 85★, pushed 2026-05-01 — Tor/dark-web skill for AI agents (OpenCode & Claude Code); search 12 dark-web engines, spider .onion sites, extract IOCs. Install (from README): `npx skills add vichhka-git/OpenTor` or `git clone` into `~/.claude/skills/open-tor`; deps via `pip install -r requirements.txt`.
3. rly0nheart/thedevilseye — 267★ — OSINT CLI over Ahmia.fi (README fetch returned no install line; pip install per project docs — unverified).
4. evenblad3/onion-links — 20★, pushed 2026-09-16 — curated onion list for security researchers.
5. vlall/Darksearch 542★, itsmehacker/DarkScrape 512★, NexvisionLab/Darkweb-search-engine 151★ — crawler/scrape engines.

## Dead ends / limitations
- Firecrawl API key invalid (401 Unauthorized) — cross-check done via Exa + gh + direct fetches instead.
- Haystak onion unreachable (2x). DEF CON mirror + InfoCon unreachable (3x each) — likely slow, retry later.
- Daniel's classic hosting/pastebin discontinued. Tor v2 addresses (xmh57jrzkzexv3s6.onion) dead. Ahmia `/api/search/` endpoint 404. Ahmia second onion (`msydqst*2kzerdg.onion`) not resolved.
- bentasker onion has no Gitea API. ransomware.live free tier does not expose leak-site onions.
- Many Ahmia results are spam shops ("2222*.onion" cluster) — filtered by title keywords; raw data retained in `out/research/ahmia_candidates.json`.
- No downloads, no registrations, no interactions beyond read-only GET/POST search per lane rules.
