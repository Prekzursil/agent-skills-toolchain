# Skills Manifest

> Auto-generated skill inventory for the agent-skills-toolchain repository.
> Last updated: 2026-06-09

| Skill Name | Origin | Description |
|---|---|---|
| 010-editor | custom | Use when applying binary templates (.bt), running 010 Editor scripts (.1sc), or performing hex editing with SweetScape 010 Editor |
| agent-lanes-chatgpt-web-curate | custom | Use when the user explicitly wants final comparison or curation through the direct ChatGPT web lane |
| agent-lanes-chatgpt-web-discuss | custom | Use when the user explicitly wants discussion, ideation, or sparring through the direct ChatGPT web lane |
| agent-lanes-chatgpt-web-query | custom | Use when the user explicitly wants a direct ChatGPT web / Agentify lane rather than Codex orchestration |
| agentic-humanizer | vendored | Humanize AI text via a 5-pass rewrite with optional stylometric voice matching; optional Slop or Not Pro scoring (macOS). Vendored from numen-tech/slopornot |
| angr | built-in | Use when symbolic execution, path exploration, constraint solving, or programmatic reasoning about binary behavior is needed |
| apply-callee-type-ex | custom | Use when IDA Pro decompiler output suffers from missing or bad indirect-call types and you need ApplyCalleeTypeEx |
| aspnet-core | built-in | Build, review, refactor, or architect ASP.NET Core web applications using current official guidance |
| autofix-bot-api | custom | Scan code for security vulnerabilities, leaked secrets, and dependency issues via DeepSource autofix bot API |
| battlecats-event-unlock | custom | Use when working on Battle Cats special/event/tower stage visibility or on-demand unlock RE — the proven dual-dependency model (tree-admission + valid schedule row), decisive offsets, the Event Summoner tool, and approaches proven DEAD |
| binary-ninja | custom | Use when Binary Ninja UI workflows, intermediate-language reasoning, or Binary Ninja Python API automation are needed |
| binary-ninja-diff-signatures | custom | Use when working in Binary Ninja to compare versions, analyze changed functions, or generate stable signatures |
| binary-ninja-mcp | custom | Use when installing or configuring Binary Ninja MCP, especially when a plugin or npm-based MCP bridge must be wired |
| bindiff | custom | Use when comparing two related binaries or database exports to identify changed functions or patch deltas |
| binexport | custom | Use when exporting IDA Pro, Binary Ninja, or Ghidra analysis into BinExport artifacts for BinDiff |
| binja-sigmaker | custom | Use when generating byte signatures or AOB patterns from Binary Ninja for runtime hooks or trainer work |
| biomedical-paper-triage | custom | Use when turning a raw list of biomedical papers (DOIs, PMIDs, arXiv ids, or titles) into a defensible, ranked, access-tagged shortlist via the Scholarly Access MCP paper_* tools, paired with the consensus-tooluniverse-research T1-T4 by human/animal/in-vitro evidence-grading scheme |
|
| brainstorming | marketplace:superpowers | You MUST use this before any creative work - creating features, building components, adding functionality |
| chatgpt-apps | built-in | Build, scaffold, refactor, and troubleshoot ChatGPT Apps SDK applications that combine an MCP server and widget UI |
| chatgpt5-web-curate | custom | Use when the user explicitly wants final curation or selection performed through the direct ChatGPT web lane |
| chatgpt5-web-discuss | custom | Use when the user explicitly wants a discussion or sparring-partner interaction through ChatGPT web |
| chatgpt5-web-query | custom | Use when the user explicitly wants a direct ChatGPT 5 web/Agentify interaction |
| cheat-engine-workflow | custom | Use when performing Cheat Engine-driven runtime analysis, including value scanning, pointer sanity checks, AOB validation |
| cheat-engine-x64dbg-ida-handoff | custom | Use when moving runtime findings between Cheat Engine, x64dbg, and IDA Pro |
| cheminformatics-rdkit | custom | Use when you need license-free cheminformatics via the rdkit MCP server - molecular descriptors, fingerprints, Tanimoto similarity, scaffolds, and structure-format conversion |
| ci-silent-pass-lint | custom | Use before any PR creation or "gates green / ready to merge" claim — detects CI/gate workflows that report GREEN while masking findings (11 silent-pass shapes: continue-on-error, \|\| true, audit mode, no-token uploads, set+e swallows, stale-SHA gates, soft thresholds, and more) via deterministic workflow linting + MCP cross-check of actual finding-counts at HEAD |
| citation-mapping | custom | Use when you need to build a citation or reference map for a paper, tracing backward references and forward cited-by works from metadata APIs like Semantic Scholar and OpenAlex |
| cloudflare-deploy | built-in | Deploy applications and infrastructure to Cloudflare using Workers, Pages, and related platform services |
| code-security | built-in | Security guidelines for writing secure code |
| codex-audit | custom | Use when you want an audit-style orchestration pass over risk, gaps, and verification needs |
| codex-brainstorm | custom | Use when you want two Codex peers to generate ideas before synthesis |
| codex-consult | custom | Use when the user wants a Codex-side orchestration pass — consult, curate, or review — via codex_local_* / codex_orchestrator_* tools instead of direct ChatGPT web automation; one skill, three modes (replaces the codex-local-* and agent-lanes-codex-* lanes) |
| codex-coordinate | custom | Use when you want Codex to split roles and consolidate the outcome |
| codex-curate | custom | Use when you want a final best-option selector, optionally with PromptBridge talk-only curation |
| codex-discuss | custom | Use when you want two Codex peers to debate tradeoffs before synthesis |
| codex-fix | custom | Use when you want Codex to coordinate a fix path across multiple reasoning roles |
| codex-governance | custom | Use when you need a final governance-oriented decision across options and risks |
| codex-review | custom | Use when you want one Codex critic to review a plan or change before implementation |
| codex-runtime-recovery | custom | Use when Codex state is split across Windows, WSL, or VS Code, sessions disappear, or state_5.sqlite files churn |
| codex-session-reunion | custom | Use when Codex sessions or rollout JSONL files are spread across Windows, WSL, backups, or VS Code mirrors |
| codex-triage | custom | Use when you need a fast classification of next steps before deeper work |
| codex-vscode-host-routing | custom | Use when VS Code launches Codex from the wrong host or WSL becomes the default unexpectedly |
| competitive-programming-solver | custom | Use when solving online judge, olympiad, or contest problems in C, C++, or Python |
| consensus-tooluniverse-research | custom | Use when downloading or harvesting research from Consensus.app — extract searches browser-free from the page payload, resolve papers to DOIs and open-access PDFs via ToolUniverse, organize by topic with a bibliography, and capture the Consensus Meter graphs |
| ddi-admet-research | custom | Use as the front-end for biomedical research via the ToolUniverse MCP - drug-drug interactions, ADMET/CYP, target research, FDA labels, repurposing, pharmacovigilance |
| deepsource | built-in | Retrieve code review results from DeepSource - issues, vulnerabilities, and quality metrics |
| develop-web-game | built-in | Use when Codex is building or iterating on a web game (HTML/JS) and needs a reliable development + testing loop |
| dispatching-parallel-agents | marketplace:superpowers | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| doc | built-in | Use when the task involves reading, creating, or editing .docx documents |
| drug-discovery-literature-bridge | custom | Use when extracting molecules, targets, assays, and clinical context from a paper (via the Scholarly Access MCP paper_* tools) to seed the drug-discovery stack — ToolUniverse DDI/ADMET/target tools and the RDKit MCP — keeping DOI provenance on every extracted entity |
| dump-to-signature-workflow | custom | Use when converting dump or debugger evidence into durable signatures, AOB patterns, or diffable artifacts |
| executing-plans | marketplace:superpowers | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
| figma | built-in | Use the Figma MCP server to fetch design context, screenshots, variables, and assets from Figma |
| figma-implement-design | built-in | Translate Figma nodes into production-ready code with 1:1 visual fidelity using the Figma MCP workflow |
| finishing-a-development-branch | marketplace:superpowers | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work |
| format-codex-sessions | custom | Use when Codex rollout JSONL files need to be turned into readable Markdown conversations or transcripts |
| frida | custom | Use when runtime hooking, device instrumentation, API tracing, or patch-on-the-fly behavior matters |
| frida-mcp | custom | Use when installing or configuring frida-mcp as an MCP server for live Frida instrumentation |
| gh-address-comments | built-in | Help address review/issue comments on the open GitHub PR for the current branch |
| gh-fix-ci | built-in | Use when a user asks to debug or fix failing GitHub PR checks that run in GitHub Actions |
| ghidra-automation-recipes | custom | Use when automating Ghidra analysis with Script Manager scripts, ghidra_bridge, or repeatable Python-driven recipes |
| ghidra-bridge | custom | Use when automating Ghidra from Python, driving analyses from an external REPL or script |
| ghidra-mcp | custom | Use when installing or configuring GhidraMCP for a local Ghidra workflow |
| grill-me-extensive | custom | Program-scale extensive grilling addon to the vendored grill-me skill: scout, brainstorm-fanout to surface directions beyond the ask, a categorized decision list walked one question at a time with a recommendation each, durable capture, then converge to a locked decision log; grill modes for expansion, modification, scope-change, modernization, better-ideas, red-team, simplification, prioritization |
| hexstrike-ai-authorized-engagement | custom | Use when an authorized security assessment, bug bounty, red-team, or CTF task should be routed through HexStrike AI |
| hexstrike-ai-mcp | custom | Use when installing, repairing, or registering HexStrike AI as an MCP server for Codex, Claude Code, or Gemini CLI |
| hexstrike-ai-setup | custom | Use when installing, wiring, validating, or troubleshooting a local HexStrike AI runtime |
| humanizer | vendored | Remove signs of AI writing using Wikipedia's 'Signs of AI writing' patterns; optional personal-voice match. Vendored from blader/humanizer |
| ida-decompiler-cleanup | custom | Use when Hex-Rays decompiler output in IDA Pro is noisy, poorly typed, or hard to reason about |
| ida-pro-mcp | custom | Use when installing or configuring mrexodia/ida-pro-mcp for IDA Pro |
| imagegen | built-in | Use when the user asks to generate or edit images via the OpenAI Image API |
| imhex | custom | Use when hex editing, binary analysis, pattern language parsing, file identification, hash computation, or hex dump generation is needed |
| jupyter-notebook | built-in | Use when the user asks to create, scaffold, or edit Jupyter notebooks (.ipynb) |
| linear | built-in | Manage issues, projects and team workflows in Linear |
| llm-security | built-in | Security guidelines for LLM applications based on OWASP Top 10 for LLM 2025 |
| long-copy-orchestrator | custom | Use when moving large trees between Windows, WSL, VMs, or mounted disks |
| mcp-graphql | custom | Use when installing or configuring blurrah/mcp-graphql for Codex, Claude Code, or Gemini CLI |
| mechanistic-ddi-pipeline | custom | Use to produce a mechanistic drug-drug-interaction verdict by combining ToolUniverse CYP/DDI knowledge with Schrodinger structure and docking evidence |
| mise | custom | Use when managing dev tool or language runtime versions with mise (mise-en-place) — global vs per-project pins, per-directory env vars, the task runner, non-language CLI installs, or Windows PowerShell setup |
| multi-agent-quickstart | custom | Use when learning how to choose between the Codex multi-agent orchestration tools |
| netlify-deploy | built-in | Deploy web projects to Netlify using the Netlify CLI |
| notion-knowledge-capture | built-in | Capture conversations and decisions into structured Notion pages |
| notion-meeting-intelligence | built-in | Prepare meeting materials with Notion context and Codex research |
| notion-research-documentation | built-in | Research across Notion and synthesize into structured documentation |
| notion-spec-to-implementation | built-in | Turn Notion specs into implementation plans, tasks, and progress tracking |
|
| oa-pdf-retrieval | custom | Use when downloading an open-access paper PDF with verifiable provenance (allowlisted host, license, sha256) and honest access classification — classify with paper_access_status first, only fetch oa_pdf items, and cite rather than download free-to-read or subscription items |
| offline-linux-disk-surgery | custom | Use when a Linux guest disk must be inspected, grown, or repaired offline with qemu-nbd, guestfish, GPT tools |
| openai-docs | built-in | Use when the user asks how to build with OpenAI products or APIs and needs up-to-date official documentation |
| pbinfo-python-jit | custom | Use when a pbinfo.ro Python solution is correct but still TLEs and needs carefully prepared native hot-path helpers |
| pdf | built-in | Use when tasks involve reading, creating, or reviewing PDF files |
| peutils | custom | Use when inspecting or repairing PE-focused details in Binary Ninja |
| playwright | built-in | Use when the task requires automating a real browser from the terminal |
| playwright-interactive | built-in | Persistent browser and Electron interaction through js_repl for fast iterative UI debugging |
| quality-gate-automation-architect | custom | Use when designing, comparing, or reviewing autonomous repo-quality automation |
| radare2 | custom | Use when command-line disassembly, debugging, hex editing, or scriptable low-level binary triage is needed |
| reboot-safe-ops-continuation | custom | Use when a reboot is required in the middle of migration or repair work and you need exact pre-reboot state capture |
| receiving-code-review | marketplace:superpowers | Use when receiving code review feedback, before implementing suggestions |
| render-deploy | built-in | Deploy applications to Render by analyzing codebases, generating render.yaml Blueprints |
| repomix | built-in | Use when packing a repository into an AI-friendly bundle with Repomix |
| requesting-code-review | marketplace:superpowers | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| ret-sync | custom | Use when synchronizing a live debugger with IDA Pro, Binary Ninja, or compatible disassemblers |
| reverse-engineering-toolkit | custom | Use when selecting or sequencing reverse-engineering tools for Windows native analysis |
| rtv-pdr | custom | Use when a hard coding work-unit has failed once, is contentious, or scores HIGH on the ESE gate — spawns N parallel Opus rollouts, runs a recursive tournament where fresh judge agents (never contestants) pick the winner, then optionally runs a PDR refine pass. Expensive; gate behind ESE.
| scholarly-literature-review | custom | Use when you have a DOI, PMID, arXiv id, or title (or a list) and want canonical metadata, a per-paper access-status table (oa_pdf vs free-to-read vs subscription vs unavailable), citation/reference expansion, or a metadata-and-abstract summary via the Scholarly Access MCP paper_* tools |
| schrodinger-maestro-driver | custom | Use when driving the local Schrodinger MCP for structure-based drug discovery - SMILES to 3D, LigPrep, Protein Prep Wizard, Glide grid generation, Glide docking, Prime MM-GBSA, QikProp ADMET, conversion, run_schrodinger_python escape hatch |
| screenshot | built-in | Use when the user explicitly asks for a desktop or system screenshot |
| security-best-practices | built-in | Perform language and framework specific security best-practice reviews |
| security-ownership-map | built-in | Analyze git repositories to build a security ownership topology |
| security-threat-model | built-in | Repository-grounded threat modeling that enumerates trust boundaries, assets, attacker capabilities |
| semgrep | built-in | Run Semgrep static analysis scans and create custom detection rules |
| sentry | built-in | Use when the user asks to inspect Sentry issues or events |
| slides | built-in | Create and edit presentation slide decks (.pptx) with PptxGenJS |
| slop-check | vendored | Detect AI-generated text/images, clean artifacts, and score readability via Slop or Not Pro (macOS-only — degraded on Windows). Vendored from numen-tech/slopornot |
| social-dm-search | custom | Use when the user wants to search or read direct messages and chats across Instagram DMs, Facebook Messenger groups/pages, or WhatsApp (proof-of-concept, off by default) |
| social-find-post | custom | Use when the user wants to find or recall a specific post, reel, or saved item across Instagram or Facebook |
| social-media-toolchain | custom | Reference for the user's personal social MCPs (Instagram live, Facebook Messenger groups/pages, WhatsApp proof-of-concept; TikTok public read-only) - servers, auth and setup, tool inventory, residential-proxy and account-state guidance, and hard limits (E2EE, version gotchas, ban risk) |
| sora | built-in | Use when the user asks to generate, remix, poll, list, download, or delete Sora videos via OpenAI video API |
| speech | built-in | Use when the user asks for text-to-speech narration or voiceover |
| spreadsheet | built-in | Use when tasks involve creating, editing, analyzing, or formatting spreadsheets |
| structure-based-screening | custom | Use when running a structure-based drug-discovery or molecular-docking campaign on the local schrodinger MCP - receptor PDB plus ligands to docked, MM-GBSA-rescored, ADMET-profiled poses. Covers the prepwizard to glide_grid to ligprep to glide_dock to prime_mmgbsa to qikprop chain, grid-box centering, license-token sequencing, and the path gotchas |
| subagent-driven-development | marketplace:superpowers | Use when executing implementation plans with independent tasks in the current session |
| swfoc-modding | custom | Research-backed workflow for Star Wars: Empire at War / Forces of Corruption modding, SDK/tooling, debugging |
| swfoc-reverse-engineering | custom | Use when working on SWFOC editor runtime or native analysis |
| swfoc-runtime-address-hunting | custom | Use when hunting SWFOC-specific runtime addresses, function anchors, structures, or memory regions |
| systematic-debugging | marketplace:superpowers | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| test-driven-development | marketplace:superpowers | Use when implementing any feature or bugfix, before writing implementation code |
| tiktok-public-research | custom | Use when the user wants to read public TikTok data - trending, a creator's public posts/likes, a hashtag feed, a video's metadata/comments/related, or user search - via the self-hosted tiktok MCP. Covers the read-only tool inventory, ms_token and residential-proxy reliability knobs, and hard limits (no own feed, no saved, no DMs, no posting; unofficial-API ban and IP-block risk) |
| transcribe | built-in | Transcribe audio files to text with optional diarization and known-speaker hints |
| ui-ux-pro-max | built-in | UI/UX design intelligence with searchable database |
| using-git-worktrees | marketplace:superpowers | Use when starting feature work that needs isolation from current workspace |
| use-image-clipboard | custom | Use when needing to read an image from the Windows clipboard and save it to a temporary PNG file on disk — required workaround for Antigravity CLI which lacks native Alt+V image paste |
| using-superpowers | marketplace:superpowers | Use when starting any conversation - establishes how to find and use skills |
| vercel-deploy | built-in | Deploy applications and websites to Vercel |
| verification-before-completion | marketplace:superpowers | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs |
| video-watermark-removal | custom | Use when removing a static logo, watermark, or TV bug from a video seamlessly — per-frame big-LAMA streaming inpaint over a tight logo-only mask with feathered composite and audio re-mux, plus the operational pitfalls (tight mask not generous box, retry transient WSL2 CUDA/cuFFT failures, detached WSL daemon to dodge the background hang-reaper) |
| voice-analyze | vendored | Reverse-engineer a voice profile from writing samples, including an AI-tells scan. Vendored from Prekzursil/ghostwriter |
| voice-apply | vendored | Apply a voice profile to transform content; enforces a mandatory AI-tells check on output. Vendored from Prekzursil/ghostwriter |
| voice-blend | vendored | Blend multiple voice profiles with weighted mixing into a hybrid voice. Vendored from Prekzursil/ghostwriter |
| voice-create | vendored | Generate a custom voice profile from a natural-language description. Vendored from Prekzursil/ghostwriter |
| volatility-3 | custom | Use when a memory image must be analyzed to recover processes, modules, or unpacked binaries |
| webapp-testing | built-in | Toolkit for interacting with and testing local web applications using Playwright |
| windbg-command-cookbook | custom | Use when you need concrete WinDbg Preview command sequences for crash dumps or exception context |
| windbg-preview | custom | Use when triaging Windows crash dumps, inspecting threads, exceptions, modules, memory, or debugger commands |
| windows-virtualization-conflict-triage | custom | Use when Hyper-V, VBS, VMware Workstation, Docker, or WSL conflict on a Windows host |
| winui-app | built-in | Bootstrap, develop, and design modern WinUI 3 desktop applications with C# and the Windows App SDK |
| writing-plans | marketplace:superpowers | Use when you have a spec or requirements for a multi-step task, before touching code |
| writing-skills | marketplace:superpowers | Use when creating new skills, editing existing skills, or verifying skills work before deployment |
| wsl-vmware-cutover | custom | Use when moving Linux workloads from WSL into VMware with D-first staging, cold backups, rollback checkpoints |
| x64dbg | custom | Use when live-debugging a Windows process, tracing code paths, setting breakpoints |
| yeet | custom | Use only when the user explicitly asks to stage, commit, push, and open a GitHub pull request in one flow |
