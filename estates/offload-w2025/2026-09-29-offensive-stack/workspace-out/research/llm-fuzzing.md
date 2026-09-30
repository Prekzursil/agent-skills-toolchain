# Research: llm-fuzzing — LLM-guided fuzzers (input generation quality, harness generation)

Date: 2026-09-29. Researcher lane: "llm-fuzzing". Estate context (from ask): Windows Server VM, **no Docker engine** (GCP no VT-x), CyberStrike 1.1.16, MCP gateway 127.0.0.1:31100 (43 backends), Ollama qwen3:4b local, Python C:\Python314\python.exe.

Estate checks actually run this session (Git Bash):
- `clang --version` → `command not found`; `where clang` → "Could not find files" → **LLVM/Clang NOT installed** (needed by RALFuzz/PromptFuzz/PromeFuzz).
- `ollama list` → `command not found` in this bash PATH (ask states Ollama qwen3:4b exists on estate — likely installed elsewhere/service-only; not verifiable from this shell).

---

## Named tools from the ask

### 1. RALFuzz — LLM-assisted C fuzz-harness generation (FOUND, Windows-native)
- Repo: https://github.com/Go-ther/RALFuzz (0★, pushed 2026-07-05, Python). Found via `gh api 'search/repositories?q=RALFuzz'` — sole hit.
- README (read via `gh api repos/Go-ther/RALFuzz/readme`): "execution- and risk-aware workflow for generating and mutating fuzz harnesses for native C library APIs". Two stages: (1) seed harness gen from API signatures + execution context + cleanup/risk hints, validated by real compiler; (2) evolutionary mutation where LLM fills/rewrites changed regions. Heavily modified derivative of TitanFuzz artifact (Zenodo 7978832), retargeted from Python DL APIs to C11 harnesses. Zenodo DOI 10.5281/zenodo.20116397.
- **Windows evidence (README, verbatim)**: "On Windows, installing LLVM to the default path `C:\Program Files\LLVM\bin` is supported. If Clang is installed elsewhere, put its `bin` directory on PATH or pass `--compiler /path/to/clang`." Sanitizer runtime dir auto-added to PATH on Windows.
- Install: `git clone https://github.com/Go-ther/RALFuzz && pip install -r requirements.txt` (Python 3.10–3.12 recommended), plus clang + llvm-cov. LLM: any OpenAI-compatible API via `SEED_API_KEY` / `MUTATION_API_KEY` env vars (frozen snapshot used deepseek-v4-flash + qwen3-coder-next). **No OpenAI-lock; could point at local gateway.**
- Estate fit: HIGH — explicit Windows path support, pure Python + clang. Blocker today: clang absent on VM (checked above).

### 2. RESTing-LLAMA — LLM REST API fuzzing (paper ONLY — no public artifact found)
- Paper: "RESTing-LLAMA: Large Language Model based REST API Fuzzing", ACM DOI 10.1145/3779208.3785383 (scraped via Firecrawl `/v1/scrape`). Abstract: LLMs for security fuzzing of REST APIs, compared against RESTler; targets listed in paper: casdoor, kavita, chatwoot, audiobookshelf, gitea, komga, microcks, grocy, Astra, jellyfin, outline, ever-traduora, commafeed, request-baskets, appwrite, VoAPI2, apache/answer (all Go-heavy REST services).
- **No own GitHub repo linked on the ACM page** (only fuzz-target repos + microsoft/restler-fuzzer). Zenodo API search `q=RESTing-LLAMA` → no relevant hit. GitHub searches for RESTing/RESTLLM variants returned only unrelated llama REST servers.
- Closest usable artifacts in the same space: fuzzwise, p2s (below), RESTLess (sunsunk/RESTLess, cited by Exa), RestTSLLM (uffsoftwaretesting, C#/Python, 3★, LLM+TSL REST integration-test generation, venv-based → Windows-runnable).

### 3. SemFuzz — semantics-aware protocol fuzzing (FOUND)
- Paper: arXiv 2603.05989 (submitted 2026-03-06), **WWW 2026** (ACM DOI 10.1145/3774904.3792541). Scraped abstract via Firecrawl: LLM extracts structured semantic rules from RFCs, generates test cases that intentionally violate them, detects deep semantic bugs by response-vs-expected comparison. **16 potential vulns / 10 confirmed / 5 previously unknown / 4 CVEs** across 7 protocol implementations.
- Public code: https://github.com/yangting111/BSFuzz (4★, Python, pushed 2025-11-05) — repo README describes the Bluetooth specialization: "context-aware semantic fuzzing framework guided by the Bluetooth Core Specification … LLM agents for test generation and verification"; `srcs/Test_Seq_Generation/SemFuzz.py` is the main fuzzing loop; FAISS RAG over spec text; packet senders for BLE ADV/LL/L2CAP/ATT/SMP.
- Install: conda python 3.11.8 + `pip install -r requirements.txt`; README states **Ubuntu 22.04.4 LTS** requirement; BLE SUL interface (`Bluetooth_SUL.py`) implies Linux BlueZ-style stack. → **Windows: WSL only.** No releases.

---

## Harness generation (the other half of the ask)

### FuzzAnything/PromptFuzz — 346★, Rust
- "Prompt Fuzzing for Fuzz Driver Generation": mutates LLM prompts in a fuzz loop to generate C/C++ fuzz drivers; coverage-guided API-combination scheduling; libFuzzer + AFL++ (v1.0.0 2026-04-10); LLVM 18; any OpenAI-spec LLM (`OPENAI_ENDPOINT/OPENAI_MODEL_NAME/OPENAI_API_KEY`). README claims 40.12% branch coverage (1.61× OSS-Fuzz human targets) and **33 valid security bugs from 49 unique crashes**, with a tracked bug table (libaom, libvpx, libmagic, libtiff, sqlite3, c-ares, libjpeg-turbo, libpcap, cJSON, curl).
- Install: sanctioned path is Docker (USAGE.md `docker build -t promptfuzz .`); native path = Rust build + LLVM18 + target library build.sh scripts. Windows native: plausible (Rust + clang) but unsupported/untested → `windows: docker|wsl-leaning, unknown`. Value: HIGH capability, MEDIUM practicality on this estate.

### pvz122/PromeFuzz — 61★, CCS 2025 (artifact badges: available/functional/reproduced)
- "Knowledge-Driven Approach to Fuzzing Harness Generation with LLMs" — code metadata + docs + API usage patterns + API-correlation scheduling + built-in crash analyzer; claims to beat OSS-Fuzz-Gen, PromptFuzz, CKGFuzzer on branch coverage & vuln discovery.
- Install: Docker recommended; manual = `uv sync` + `sudo apt install bear build-essential cmake clang llvm libclang-dev clang-format libomp-dev` + `./setup.sh` → Linux-oriented. Windows: docker (pending on estate).

### google/oss-fuzz-gen — 1441★
- Google production harness generation for OSS-Fuzz (C/C++/Java/Python), 26 real vulns incl. CVE-2024-9143 (OpenSSL) per awesome-list; OSS-Fuzz blog 2026 posts "Introducing LLM-based harness synthesis for unfuzzed projects" and "agent-based build generation" show it's the active production baseline. Evaluation needs OSS-Fuzz Docker infra → Windows: docker. Value: MEDIUM (reference/benchmark; the AISF docs: google.github.io/oss-fuzz/research/llms/target_generation/).

### Adjacent harness-gen / kernel / DL:
- security-pride/CKGFuzzer — 147★, C++, CodeQL + code knowledge graph + LLM for fuzz drivers; docker_shared layout → Linux/Docker.
- ise-uiuc/KernelGPT — 179★, ASPLOS'25, LLM infers+repairs Syzkaller specs; 24 new kernel bugs, 11 CVEs; needs Linux kernel source + syzkaller + clang-14 → Windows: no.
- QGrain/SyzGPT — 64★, ISSTA'25, dependency-based RAG for low-frequency syscalls in kernel fuzzing.
- ise-uiuc/TitanFuzz — 94★, ISSTA'23 ancestor (PyTorch/TF), stale 2023 — RALFuzz is its modernized C-native descendant.
- NJU-iSE/FUEL — arXiv 2506.17642, feedback-driven DL framework fuzzing via generation+analysis LLMs, feedback-aware simulated annealing, program self-repair; 104 new bugs (93 confirmed). Requires Ubuntu ≥20.04 + CUDA GPU (up to 128GB GPU mem for 72B via vLLM) + DeepSeek API → not for this VM; technique reference for input-generation quality.
- ucsb-seclab/PDFuzzer — 5★, CCS 2026, "From Documentation to Zero-day Vulnerabilities: LLM-Driven Fuzzing of JavaScript Engines in PDF Readers".
- SoftSec-KAIST/SatFuzz — 3★, WISA'26, LLM-assisted command syntax extraction for flight software fuzzing.
- GitHubSecurityLab/seclab-taskflows-fuzzing — 19★, "LLM-driven OSS-Fuzz-style fuzzing pipeline … AFL++ for execution, clang+lcov coverage, LLM agent for harness writing, coverage-feedback decisions, triage, reporting"; runs on GitHub Security Lab Taskflow Agent; needs AFL++ → WSL/Linux; good architectural blueprint, backed by github.blog post.
- cirrus-uchicago/Locus — 13★, "agentic predicate synthesis for directed fuzzing" (U Chicago).
- OwenSanzas/oss-fuzz-gen fork — "Modified OSS-Fuzz-Gen for enhanced fuzzing harness generation" (1★, unpicked).

## Protocol fuzzing (ChatAFL lineage)

- ChatAFLndss/ChatAFL — 398★, NDSS'24, LLM-guided protocol fuzzing on AFLNet: LLM extracts protocol grammar, diversifies seed messages, breaks coverage plateaus. Artifact = Docker/ProfuzzBench → Windows: docker/WSL. Zenodo 10115151.
- PoeenCy/SigFuzz-MQTT — 0★, LLM-guided MQTT logic-bug fuzzing with zero-overhead SIGTRAP tracing.
- luongtrieudai2005/LIFA-Fuzz — 0★, async black-box custom-protocol fuzzing from LLM inference on real traffic.
- ShovalBenjer/LLM-BLE-Fuzzer — 1★, OpenAI-driven BLE payload mutation w/ web dashboard.
- StepStone (Oakland'26, ucR) — LLM-based GPU kernel driver fuzzing via user-space libraries; PDF found (cs.ucr.edu/~zhiyunq/pub/oakland26_gpu_fuzzing.pdf), **no public repo found** (`gh search StepStone GPU fuzzing` → 0 hits).
- monad-developers/ultrafuzz — 92★, end-to-end agentic smart-contract fuzzing/threat hunting.

## REST/API fuzzing (RESTing-LLAMA's space)

- thedarianwong/fuzzwise — 1★, CMPT 479 Spring 2026 project: **LLM-augmented stateful REST fuzzing** with OpenAPI 3.0 producer-consumer dependency inference; 4 configs isolating LLM payload quality vs LLM sequence exploration vs RESTler-style static dictionary; **local Qwen 2.5 via Ollama**; Python 3.11+; Docker Desktop only needed for local target APIs (fuzzing remote APIs = pure Python; README shows Windows venv activate). Directly relevant to "input generation quality" A/B evidence.
- alberttrann/p2s-fuzzing-framework — 0★ but v1.2.0 SDK: stateful REST API **security** testing (IDOR/lifecycle/business-flow); records real traces, compiles to OCLI primitives, LLM generates fault-seeking mutations, executed against resettable backend — "live system response, not another model, is the execution signal". Python 3.10+; `p2s doctor`; pip-style SDK. Windows: pure Python, likely native (not explicitly stated → unknown).
- cdbkk/vuln-monkey — 9★, TypeScript/npm: `npx vuln-monkey "curl ..."` — LLM analyzes endpoints, generates attack payloads, fires them, classifies responses, writes MD/JSON reports. Node ≥20 → **Windows native, trivial install**. v0.3.0 security-hardened.
- selab-gatech/restgpt — 14★, ICSE'24 NIER "Leveraging LLMs to Improve REST API Testing" (Zenodo 10467805): gpt-4o-mini converts human-readable OpenAPI description text into machine-readable constraints; `python3 restgpt.py` predefined mode (9 bundled specs) runs without Docker; ~$10 OpenAI cost. Java+Python.
- sunsunk/RESTLess — older LLM REST fuzzing baseline (cited by Exa search).
- Gilgamesh512/LLM-Assisted-API-Fuzzing — 1★, context-aware payload generation + repair + runtime feedback.
- engrAntor/ai-powered-api-testing-agent — 0★, Schemathesis v4 + LangChain + Gemini 2.0 Flash probes for IDOR/auth/logic.
- Yifan-Song793/RestGPT — 1404★ — **NOT a fuzzer** (WWW'24 LLM agent controlling apps via REST); recorded to disambiguate.

## Local-first / Windows-native finds (best estate fits)

### TaoYaTou/IndusFuzz — 工业协议模糊测试智能体 (0★ but very active)
- LLM-driven industrial-protocol fuzzing agent, **automatic fallback to local deterministic random mutation when LLM unavailable**. Local-first Ollama ("data never leave your machine"). Protocols: Modbus TCP, S7Comm, DNP3, IEC 60870-5-104, IEC 61850 MMS, EtherNet/IP, OPC UA.
- **Windows evidence (README tables, verbatim)**: "OS: Windows 10 / 11 (64-bit)"; "Official support: Windows 10/11 (64-bit) only"; compatibility matrix: main fuzzing flow ✅ Tested on Windows; API-key encryption via DPAPI (Windows-only feature); 147 pytest cases with **Windows runner**; roadmap v2.0.0 "Cross-platform (macOS/Linux)" — i.e., Windows is the primary platform. Ports 102/502 need admin.
- Install: `git clone https://github.com/TaoYaTou/IndusFuzz && python -m venv agentscope_env && .\agentscope_env\Scripts\activate && pip install -r requirements.txt`. Releases: v1.8.5 (2026-09-21, 2 assets) — actively shipping.
- Estate fit: HIGH — Windows-first, Ollama-local, protocol scope matches offensive estate; auth context required (ICS warning in README).

### zaydmulani09/phaedra — 15★, created 2026
- "Local-first, LLM-guided, coverage-driven fuzzer for network protocols and binary formats. Single Rust binary. Zero signup. Zero cloud." LLM seed bootstrap via **local Ollama**, TOML schema-aware field-level mutation, SanCov edge bitmaps via shared memory, crash triage/minimize in SQLite, `phaedra compat` drives existing libFuzzer harnesses. Install: `cargo install phaedra` (or build from source). CI badge (ci.yml). Coverage instrumentation targets Rust services; Windows native = likely (Rust), untested claim → unknown. Value: MEDIUM-HIGH.

### Invicti-Security/brainstorm — 401★
- Local LLM (Ollama) + ffuf loop for smart directory/file discovery: crawl → LLM suggests paths → ffuf → learn from hits → repeat. Python 3.6+, needs ffuf binary + Ollama. Invicti blog documents method. Windows: native (Python + ffuf.exe). Value: MEDIUM (web-tier complement to CyberStrike).

### user1342/AutoCorpus — 74★
- LLM (local Mistral-7B-Instruct-v0.2, CUDA) generates fuzzing **corpus/seed files** for natural-language formats (JSON/XML/config). README: "AutoCorpus has been tested on Windows 11; however, it should be compatible with Unix". Input-generation-quality lane; heavy (16GB RAM rec, GPU). Value: MEDIUM.

## MCP fuzzing (estate runs 43 MCP backends — direct relevance)

- manthanghasadiya/mcpsec — 26★, Python, **pip: `pip install mcpsec`** (PyPI v2.4.0). "AI-driven dynamic protocol fuzzer for the Model Context Protocol — state violations, transport crashes, application-layer logic flaws (SSRF, LFI) before your AI agents do." Value: HIGH for this estate.
- mcp-runtime/mcp-server-fuzzer — 46★, Python, generic MCP server fuzzer (json-rpc method/payload fuzzing). Value: MEDIUM-HIGH.
- kodivante/MCPwn — 1★, MCP auditor+fuzzer (schema audit, command injection, path traversal, tool-access scope).
- ShovalBenjer/mcp-guard — 1★, zero-dep Python adversarial MCP fuzzer (shell injection, SSRF, overflow, type confusion, prompt injection probes).
- buildwithabid/mcp-testkit — 1★, vitest/jest MCP testing framework w/ fuzz matchers.

## Fuzzing-the-LLM (adjacent domain, noted for completeness)
cyberark/FuzzyAI 1578★ (jailbreak fuzzing), mnns/LLMFuzzer 380★ (first LLM-app fuzzing framework, stale), prompt-security/ps-fuzz 703★, Amazon TurboFuzzLLM, RainJamesY/FuzzLLM. Cross-checked against scadastrangelove/awesome-ai-security-tools "Fuzzing the LLM" section — no gaps.

## Agentic vuln-research frameworks that include fuzzing
- fuzzingbrain/afc-crs-all-you-need-is-a-fuzzing-brain — 137★, DARPA AIxCC 4th place; LLM "suspicious-point" brain + OSS-Fuzz toolchain + verified PoV/patch. **Docker required, Linux recommended** → blocked on this estate until Docker. Companion: fuzzingbrain/FuzzingBrain-Bench (7★; 77 challenges / 43 projects C/C++/Java) — the bench is pure eval data, usable anywhere.
- branover/hexgraph — 20★, self-hosted agentic binary/firmware VR: decompile→fuzz→verify in disposable Docker (static-only default, network off), findings typed-graph + SQLite, **exposes MCP** (localhost UI + MCP ops; BYOK Anthropic/local Claude/mock). Docker only for target parsing → partial fit.
- vul337/FirmAgent — 90★ (mirror AxiaoJJ 6★), NDSS'26: fuzzing assists LLM agents for IoT firmware; needs IDA + Docker + QEMU → not for this estate.
- Stefan0x03/fissure — 1★, agentic CVE-triage + fuzzing reproduction via Lacuna (measures advisory-informed seed gen vs blind fuzzing).
- AIxCyberChallenge/sherpa — AIxCC-adjacent CRS (surfaced by Chinese-language Exa query).

## Practitioner signal (read, not run)
- gusarich.com/blog/billions-of-tokens-later/ — "Billions of Tokens Later: Scaling LLM Fuzzing in Practice" (HN 2025-07-18) — industrial-scale lessons on LLM fuzzing economics.
- blog.oss-fuzz.com posts (2026): "LLM-based harness synthesis for unfuzzed projects", "OSS-Fuzz integrations via agent-based build generation".
- github.blog — "AI-powered fuzzing with the GitHub Security Lab Taskflow Agent".
- nowarp.io compiler-testing series — coverage+grammar+LLM compiler fuzzing, 100 bugs.

---

# EVERY QUERY ISSUED (exhaustive log)

## GitHub API (`gh api search/repositories`), all with per_page 5–50:
1. `q=RESTLLM+OR+RESTing-LLAMA` (per_page=20)
2. `q=RALFuzz` (per_page=20)
3. `q=SemFuzz` (per_page=20)
4. `q=REST+API+fuzzing+LLM&sort=updated` (per_page=30)
5. `q=llm+fuzzing+in:name,description&sort=updated` (per_page=50)
6. `q=OSS-Fuzz-Gen` (per_page=5)
7. `q=ChatAFL` (per_page=5)
8. `q=KernelGPT` (per_page=5)
9. `q=Fuzz4All` (per_page=5)
10. `q=TitanFuzz` (per_page=5)
11. `q=Speedgun fuzzing` (per_page=5) → gh transport PROTOCOL_ERROR, retried via Exa instead
12. `q=RESTGPT` (per_page=10, sort=stars)
13. `q=FuzzGPT` (per_page=10, sort=stars)
14. `q=topic:llm+fuzzing` (per_page=10, sort=stars)
15. `q=LLM+protocol+fuzzing+created:>2026-01-01` (per_page=10)
16. `q=llm+fuzzer+created:>2026-04-01&sort=stars` (per_page=20)
17. `q=StepStone+GPU+fuzzing`
18. `q=agentic+fuzzing&sort=updated` (per_page=15)

## Repo detail calls: `gh api repos/{owner}/{repo}` and `repos/{owner}/{repo}/readme` (raw) for:
Go-ther/RALFuzz (readme full), yangting111/BSFuzz (readme), uffsoftwaretesting/RestTSLLM (readme), TaoYaTou/IndusFuzz (readme ×2 sections), google/oss-fuzz-gen, ChatAFLndss/ChatAFL, ise-uiuc/KernelGPT, fuzzingbrain/afc-crs-…, vul337/FirmAgent, thedarianwong/fuzzwise, alberttrann/p2s-fuzzing-framework, Yifan-Song793/RestGPT, pvz122/PromeFuzz (readme + sed range), zaydmulani09/phaedra, Invicti-Security/brainstorm, user1342/AutoCorpus, FuzzAnything/PromptFuzz (readme + USAGE.md contents API), security-pride/CKGFuzzer, selab-gatech/restgpt, branover/hexgraph, GitHubSecurityLab/seclab-taskflows-fuzzing, NJU-iSE/FUEL, cdbkk/vuln-monkey, manthanghasadiya/mcpsec, Agent-Hellboy/mcp-server-fuzzer (redirects to mcp-runtime/mcp-server-fuzzer), scadastrangelove/awesome-ai-security-tools (readme + section extract). Releases checked: TaoYaTou/IndusFuzz (v1.8.5 2026-09-21, 2 assets; v1.8.4; v1.8.3), Go-ther/RALFuzz (2 releases).

## Exa (`POST https://api.exa.ai/search`, key env EXA_API_KEY):
1. "RESTing-LLAMA REST API fuzzing large language models paper github"
2. "SemFuzz protocol fuzzing semantic LLM github repository"
3. "RESTGPT REST API fuzzing via large language models FSE 2024 artifact github Lyuheng Fang"
4. "LLM 驱动 模糊测试 工具 github 协议 fuzzing 智能体" (Chinese)
5. "Google Speedgun OSS-Fuzz-Gen LLM fuzzing fleet"
6. "MCP server fuzzing tool model context protocol security fuzzer 2026"
(First Exa call failed auth: `%EXA_API_KEY%` cmd-style expansion not honored in Git Bash → fixed with `$EXA_API_KEY`.)

## Firecrawl (`POST https://api.firecrawl.dev/v1/...`):
1. `/v1/scrape` arxiv.org/abs/2603.05989 (SemFuzz abstract) — first attempt 401 (env var was literal placeholder `${FIRECRAWL_API_KEY}`); real key read from Windows user env via PowerShell `[Environment]::GetEnvironmentVariable('FIRECRAWL_API_KEY','User')`.
2. `/v1/scrape` dl.acm.org/doi/10.1145/3779208.3785383 (RESTing-LLAMA page).
(/v1/search was not usable — the runtime env var is broken; scrape worked with the registry key. Tavily not tried: not in env.)

## Other:
- HN Algolia: `search?query=LLM%20fuzzing&tags=story&hitsPerPage=15`.
- Zenodo API: `records?q=RESTing-LLAMA&size=5` → no relevant artifact.
- VM checks: `clang --version`, `where clang`, `ollama list` (results above).

# DEAD ENDS / NOT FOUND
- RESTing-LLAMA: **no public code artifact** (ACM page links only target repos; Zenodo empty). Paper-only.
- StepStone (Oakland'26 GPU driver LLM fuzzing): paper PDF exists, no repo.
- Speedgun: Google internal OSS-Fuzz-Gen eval fleet — no standalone repo (confirmed via Exa → only google.github.io/oss-fuzz docs).
- SemFuzz full 7-protocol artifact: only the Bluetooth variant (BSFuzz) is public.
- Firecrawl search backend unusable via env (literal placeholder); scrape worked with registry key. Worked around, not abandoned.

# EXHAUSTION CLAIM
Consecutive final queries (`agentic+fuzzing` created:>2026 sweep, MCP fuzzing Exa, Speedgun/StepStone probes) returned only items already recorded or adjacent-domain (fuzzing-the-LLM, QA frameworks). All three mandated backends used: gh sweep (18 queries + ~30 repo reads), Exa (6), Firecrawl (2 scrapes). Exhausted=true for this lane.
