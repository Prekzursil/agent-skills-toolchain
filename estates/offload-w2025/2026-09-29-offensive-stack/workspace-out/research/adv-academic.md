---
title: adv-academic
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/adv-academic
---

# Adversarial completeness review — academic / preprint angle
**Domain:** paper-artifact and university/industry-lab security-research tools absent from the known-tools list.
**Date of work:** 2026-09-29. **All GitHub facts below verified live in this session** via authenticated `gh api repos/<owner>/<repo>` (stars + `pushed_at` reported per repo) and `gh search repos`; paper/venue facts from arXiv/venue web searches run this session. Nothing below was assumed from memory without a live check; items I could not verify are listed under "Not found / not verifiable".

---

## Verified haul (34 tools, none in the known-tools list)

### Tier 1 — high value (closes real capability gaps)

| # | Tool | Repo (verified) | Origin paper / venue | Evidence |
|---|------|-----------------|----------------------|----------|
| 1 | **CyberGym** | github.com/sunblaze-ucb/cybergym (917★, pushed 2026-08-28) | "CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities", arXiv 2506.02548, UC Berkeley (Dawn Song's sunblaze lab) | WebSearch + gh api |
| 2 | **CyberGym-E2E** | github.com/sunblaze-ucb/cybergym-e2e (78★, pushed 2026-09-29) | "CyberGym-E2E", arXiv 2606.04460 — full lifecycle: discovery → PoC → patch | gh search + WebSearch |
| 3 | **Cybench** | github.com/andyzorigin/cybench (334★, pushed 2026-09-24) | arXiv 2408.08926, Stanford/NYU; 40 professional CTF tasks + agent framework | WebSearch + gh api |
| 4 | **NYU CTF Bench** | github.com/NYU-LLM-CTF/NYU_CTF_Bench (176★) | arXiv 2406.05590; 200 CSAW challenges, offensive-security agent eval | gh search repos "nyu ctf" |
| 5 | **BountyBench** | github.com/bountybench/bountybench (106★, pushed 2026-09-26) | arXiv 2505.15216, NeurIPS 2025; dollar-scored attacker/defender eval on 25 real bug-bounty programs | WebSearch + gh search |
| 6 | **garak** | github.com/NVIDIA/garak (9386★, pushed 2026-09-16) | NVIDIA research; "the LLM vulnerability scanner" — hundreds of probes for jailbreak/injection/hallucination failure modes | gh api |
| 7 | **PyRIT** | github.com/Azure/PyRIT (pushed 2026-03-25) | Microsoft AI Red Team; Python Risk Identification Toolkit for generative-AI red teaming | gh api |
| 8 | **AgentDojo** | github.com/ethz-spylab/agentdojo (877★, pushed 2026-06-02) | NeurIPS 2024 D&B, ETH Zurich SPY Lab; dynamic indirect-prompt-injection benchmark with swappable attack/defense suites | WebSearch + gh api |
| 9 | **hackingBuddyGPT** | github.com/ipa-lab/hackingBuddyGPT (1248★, pushed 2026-09-13) | arXiv 2409.09493 "Hacking, The Lazy Way: LLM Augmented Pentesting", ipa-lab (Frankfurt UAS); LLM-augmented pentest agent (Linux priv-esc, web API pentest) | WebSearch + gh api |
| 10 | **AutoPenBench** | github.com/lucagioacchini/auto-pen-bench (102★, pushed 2026-09-21) | arXiv Oct-2024, EMNLP Industry 2025 (Politecnico di Torino); containerized pentest benchmark, 33 tasks, milestone scoring, vulnerable-container builder | WebSearch + gh search |
| 11 | **MaliciousAgentSkillsBench** | github.com/protectskills/MaliciousAgentSkillsBench | arXiv 2602.06547 "Do Not Mention This to the User: Detecting and Understanding Malicious Agent Skills in the Wild" (2026); 157 behaviorally-verified malicious agent skills from 69 repos + 98,380-skill ecosystem snapshot | WebSearch |
| 12 | **FirmAgent** | github.com/vul337/FirmAgent (90★, pushed 2026-09-29) | NDSS 2026: "FirmAgent: Leveraging Fuzzing to Assist LLM Agents with IoT Firmware Vulnerability Discovery" — official repo | gh search + WebSearch |
| 13 | **angr** | github.com/angr/angr (9118★, pushed 2026-09-29) | UCSB Shellphish research platform (S&P 2016 demo paper lineage); binary analysis + symbolic execution. Conspicuously absent from the known list | gh api |
| 14 | **AFL++** | github.com/AFLplusplus/AFLplusplus (6777★, pushed 2026-09-28) | USENIX Security 2020 paper "AFL++: Combining Incremental Steps of Fuzzing Research"; the list has only LLM-fuzzing papers, no coverage-guided fuzzer | gh api |
| 15 | **LLM4Decompile** | github.com/albertan017/LLM4Decompile (7060★, pushed 2026-02-12) | arXiv 2403.05286; decompile stripped binaries with LLM models (HF-hosted) | gh api |
| 16 | **ReSym** | github.com/lt-asset/resym (138★, pushed 2026-08-15) | ACM CCS 2024 **Distinguished Paper Award**; recover variables/structs from stripped binaries via LLMs | gh search repos ReSym |

### Tier 2 — medium value

| # | Tool | Repo (verified) | Origin / venue | Evidence |
|---|------|-----------------|----------------|----------|
| 17 | **PurpleLlama / CyberSecEval** | github.com/meta-llama/PurpleLlama (4409★, pushed 2026-08-18) | Meta; CyberSecEval 1–4 cyber capability + safety evals, CodeShield, PromptGuard | gh api |
| 18 | **Adversarial Robustness Toolbox** | github.com/Trusted-AI/adversarial-robustness-toolbox (6248★) | IBM Research; ML evasion/poisoning/extraction attacks & defenses | gh api |
| 19 | **Fuzz4All** | github.com/fuzz4all/fuzz4all (338★) | ICSE 2024, UIUC; universal LLM-powered fuzzer for any target language | gh api |
| 20 | **KernelGPT** | github.com/ise-uiuc/KernelGPT (179★, pushed 2026-08-24) | ASPLOS 2025, arXiv 2401.00563, UIUC; LLM-synthesized syscall specs to boost syzkaller kernel fuzzing | WebSearch + gh search |
| 21 | **VulnBot** | github.com/KHenryAegis/VulnBot (197★) | arXiv 2501.13411; multi-agent collaborative pentest framework, RAG-augmented, task-graph phases | WebSearch + gh api |
| 22 | **D-CIPHER / nyuctf_agents** | github.com/NYU-LLM-CTF/nyuctf_agents (165★, pushed 2026-07-17) | NYU CTF baseline agents incl. D-CIPHER collaborative agent | gh search |
| 23 | **ToolFuzz** | github.com/eth-sri/ToolFuzz (43★, pushed 2026-09-08) | ETH Software Reliability Lab; fuzzing framework for testing LLM-agent tools | gh search |
| 24 | **InjecAgent** | github.com/uiuc-kang-lab/InjecAgent (171★) | UIUC; benchmark of indirect prompt injection against tool-integrated agents | gh api |
| 25 | **HoF-Bench** | github.com/weareaisle/HoF-Bench (8★, pushed 2026-09-19; HF: aisleinc/HoF-Bench) | AISLE lab (arXiv Jul 2026); rediscover 95 real CVEs in openssl/curl/gnutls/etc. from pre-fix source alone | gh search + repo README read |
| 26 | **Psyzkaller** | github.com/TCA-OSS/psyzkaller | DSN '26 paper artifact: "Psyzkaller: Learning from Historical and On-the-Fly Execution Data for Smarter OS Kernel Fuzzing" | gh search |
| 27 | **syzkaller** | github.com/google/syzkaller (6332★, pushed 2026-09-29) | Google; the kernel fuzzer every kernel-fuzzing paper builds on; absent from list | gh api |
| 28 | **Fuzzilli** | github.com/googleprojectzero/fuzzilli (2347★, pushed 2026-09-28) | Google Project Zero; S&P 2019 paper "Fuzzilli: JavaScript Engine Fuzzing". NOTE: repo moved from `google/` to `googleprojectzero/` — the old path 404s | gh api (404 on old path, found new) |
| 29 | **CHAP** | github.com/marvang/chap (5★, pushed 2026-04-05) | 2026 research artifact: "Context Handoff for Autonomous Penetration testing" — long-horizon autonomous offensive security, ships an improved AutoPenBench | gh search |
| 30 | **Inspect AI** ⚠️ | github.com/UKGovernmentBEIS/inspect_ai (2883★, pushed 2026-09-29) | UK AI Security Institute eval framework; the harness behind the known "aisi open-weight cyber evaluation" item — listed because the framework itself (plus inspect_evals ports of cybench/cybergym) is a distinct, broader artifact | gh api + WebSearch (cybergym→inspect_evals issue #586) |

### Tier 3 — low value (real paper artifacts, narrow utility)

| # | Tool | Repo (verified) | Origin / venue |
|---|------|-----------------|----------------|
| 31 | **EnIGMA (CTF agent)** | github.com/enigma-agent/benchmarks + /trajectories | arXiv 2409.16165 (Princeton NLP + NYU); SWE-agent-based CTF solver; code lives in the org's `benchmarks` repo (the often-cited `ethz-spylab/ctf-agent` path 404s) |
| 32 | **PentestEval** | github.com/Richael-y/PentestEval (17★, pushed 2026-09-14) | stage-level pentest evaluation demo |
| 33 | **RedAgent** | github.com/QuirkShark/RedAgent (6★) | "RedAgent: Red Teaming LLM Applications with Context-aware Autonomous Language Agent" — code+data artifact |
| 34 | **ObliInjection** | github.com/ReachalWang/ObliInjection (15★, pushed 2026-09-24) | NDSS 2026: order-oblivious prompt injection against LLM agents with multi-source data |

---

## Install methods (as verified / canonical)

- **PyPI-native:** `pip install garak` · `pip install pyrit` · `pip install agentdojo` · `pip install adversarial-robustness-toolbox` · `pip install angr` · `pip install inspect-ai` · `pip install hackingbuddyGPT` (docs.hackingbuddy.ai quickstart)
- **Docker-first:** AFL++ `docker pull aflplusplus/aflplusplus`; cybench, NYU_CTF_Bench, nyuctf_agents, auto-pen-bench, CHAP, VulnBot, bountybench, cybergym, cybergym-e2e, FirmAgent, ReSym (CCS24 artifact), Psyzkaller — `git clone <repo>` then the repo's docker-compose/run scripts
- **WSL/Linux-only:** syzkaller, Fuzzilli (swift build), KernelGPT, PurpleLlama CyberSecEval harness
- **git clone + python env:** ToolFuzz, InjecAgent, Fuzz4All (`pip install -e .`), LLM4Decompile (HF models), PentestEval, RedAgent, ObliInjection, EnIGMA benchmarks
- **Dataset-only:** MaliciousAgentSkillsBench (HF + GitHub), HoF-Bench (HF: aisleinc/HoF-Bench), NYU CTF dataset inside NYU_CTF_Bench

Windows runnability per tool is given in the submitted result (`windows` field: native/docker/wsl).

---

## Leads not found / not verifiable (state of the search)

- **HouYi** (Kunlun Lab LLM prompt-injection framework, arXiv 2412.xxxx family): `gh search repos "HouYi prompt injection"` → no results. No public artifact found.
- **EnIGMA code**: only org site + `benchmarks`/`trajectories` repos; no standalone agent repo.
- **PentestAgent** (paper "PentestAgent: Incorporating LLM Agents to Automated Penetration Testing"): only unrelated community repos (GH05TCREW/pentestagent, 3130★ — community tool, not the paper artifact, out of my lane). No paper artifact located.
- **BreachSeek** (arXiv 2408): no public artifact.
- **Cyber-Zero / CRAKEN**: cited in 2026 CTF-agent papers; no artifact repos found.
- **Kintsugi** (USENIX Sec 2026, LLM-generated eBPF containment policies) and **PANGOLIN** (USENIX Sec 2026, LLM-driven multilingual IoT firmware fuzzing): seen on the USENIX 2026 program page; no repos found via gh search.
- **ProtocolGuard** (NDSS 2026): songxpu/ProtocolGuard exists (15★) but I did not confirm it is the NDSS artifact — left out of the haul.
- **ATOBench** (daxtar2/ATOBench, 2★): exists, referenced in agentic-pentest literature, but too little verified detail to rank.
- **HackingBuddyGone**: the `ipa-lab/hackingBuddyGone` path 404s; the active successor is hackingBuddyGPT (listed).

## Borderline duplicates vs. known list (included with caveats)

- **inspect_ai** vs known item "aisi open-weight cyber evaluation" — same org, framework vs. one eval suite; kept with caveat.
- **InterCode-CTF** — folded into Cybench; not listed separately (princeton-nlp/intercode is stale per 2026 competitive-landscape writeup).
- **PentestGPT** — covered by known "aeg-hit/pwngpt"; not re-listed.
- **CyberMetric** (cybermetric/CyberMetric, 125★) — MCQ knowledge benchmark; skipped as low-utility for this estate.

## Queries tried (for dedup across hunters)

WebSearch (10): cybench…Stanford; "NYU CTF Bench"…; "AutoPenBench"…; "hackingBuddyGone"…; "VulnBot"…; "AgentDojo" ethz-spylab…; "BountyBench"…; "EnIGMA" CTF agent…; PrimeVul…; CyberGym…; KernelGPT…; USENIX Security 2026 accepted papers LLM agents…; NDSS 2026 accepted papers LLM agent security MCP…; "Malicious Agent Skills in the Wild"….
WebFetch (2): ndss-symposium.org/ndss2026/accepted-papers/ (relevant titles extracted; no artifact URLs on page); usenix.org/conference/usenixsecurity26/technical-sessions (truncated mid-page; one artifact link visible: Xxxxsir/Lethe).
gh api repos/<r> (~35 lookups): andyzorigin/cybench, zhilizhang/cybench(404), NYU-APP-SEC/CTFBench(404), luca-gioacchini/AutoPenBench(404→renamed), ipa-lab/hackingBuddyGPT, ipa-lab/hackingBuddyGone(404), KHenryAegis/VulnBot, ethz-spylab/agentdojo, ethz-spylab/bountybench(404→moved), ethz-spylab/ctf-agent(404), ethz-spylab/toolfuzz(404→eth-sri), uiuc-kang-lab/InjecAgent, Azure/PyRIT, NVIDIA/garak, fuzz4all/fuzz4all, albertan017/LLM4Decompile, WhitzardAI/RedAgent(404→QuirkShark), Trusted-AI/adversarial-robustness-toolbox, meta-llama/PurpleLlama, angr/angr, AFLplusplus/AFLplusplus, google/fuzzilli(404→googleprojectzero), google/syzkaller, UKGovernmentBEIS/inspect_ai, google/fuzzilli, DAMO-NLP-SG/PrimeVul(404→DLVulDet), sunblaze-ucb/cybergym, QuirkShark/RedAgent, NYU-LLM-CTF/NYU_CTF_Bench, NYU-LLM-CTF/nyuctf_agents, marvang/chap, enigma-agent/{enigma-agent(404),benchmarks,trajectories}, weareaisle/HoF-Bench README.
gh search repos (~20 queries): AutoPenBench; "CTF bench NYU"; "nyu ctf"; BountyBench; enigma ctf agent; ToolFuzz; RedAgent red teaming; fuzzilli; KernelGPT; enigma-agent; PrimeVul; ReSym; PentestAgent; BreachSeek; psyzkaller; hof-bench; AICrypto benchmark; ObliInjection; FirmAgent; ProtocolGuard; ATOBench; "HouYi prompt injection"; CyberGym-E2E; "cyber-zero CTF"; "dependency steering attacks skills"; "Kintsugi eBPF LLM"; "PANGOLIN firmware fuzzing LLM"; PentestEval; CyberMetric.

## Coverage statement

Reached: arXiv/venue pages via web search, the NDSS 2026 accepted-papers listing, the USENIX Security 2026 technical-sessions page (partial — truncated mid-page before later sessions), and authenticated GitHub REST search/API for every candidate artifact (existence, description, stars, last push). Not reachable: full USENIX 2026 program tail, NDSS paper-page artifact links (listing page shows none), IEEE S&P 2026 program (not fetched — time/round budget; USENIX+NDSS scans already surfaced the 2026 artifacts above). Searches stopped returning new names after the final batch (EnIGMA org, Kintsugi/PANGOLIN, PentestEval, CyberMetric all terminal).