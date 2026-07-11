# Skills Manifest

> Auto-generated skill inventory for the agent-skills-toolchain repository.
> Last updated: 2026-07-04

| Skill Name | Origin | Description |
|---|---|---|
| 010-editor | custom | Use when applying binary templates (.bt), running 010 Editor scripts (.1sc), or performing hex editing with SweetScape 010 Editor |
| agentic-humanizer | vendored | Humanize AI text via a 5-pass rewrite with optional stylometric voice matching; optional Slop or Not Pro scoring (macOS). Vendored from numen-tech/slopornot |
| angr | built-in | Use when symbolic execution, path exploration, constraint solving, or programmatic reasoning about binary behavior is needed |
| apply-callee-type-ex | custom | Use when IDA Pro decompiler output suffers from missing or bad indirect-call types and you need ApplyCalleeTypeEx |
| aspnet-core | built-in | Build, review, refactor, or architect ASP.NET Core web applications using current official guidance |
| autofix-bot-api | custom | Scan code for security vulnerabilities, leaked secrets, and dependency issues via DeepSource autofix bot API |
| battlecats-event-unlock | custom | Use when working on Battle Cats special/event/tower stage visibility or on-demand unlock RE — the proven dual-dependency model (tree-admission + valid schedule row), decisive offsets, the Event Summoner tool, and approaches proven DEAD |
| bc-drive | custom | Deterministic on-demand driver for a LIVE Battle Cats (jp.co.ponos.battlecatsen, EN 15.4.1) instance on rooted BlueStacks. Reads engine state (scene/metrics) via crash-safe one-shot Frida NativeFunction calls (NO per-frame Interceptor) and actuates via OS-level adb shell input tap in device px. BC is a CUSTOM PONOS C++/GLES engine (not cocos2d-x). Use to script/inspect BC menu navigation, resolve its device-to-drawable coordinate space, or read scene state. Requires adb + frida-server up |
| bcsfe-save-roundtrip | custom | Pull/edit/push a Battle Cats (EN, rooted BlueStacks) SAVE_DATA — byte-exact PowerShell+HOME-flush pull, headless BCSFE library edit, in-place cat-redirect push preserving uid 10065 + SELinux context; incl. the MSYS path-mangling wipe gotcha and the Ototo cannon-unlock fields |
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
| chatgpt5-web | custom | Direct browser-automation ChatGPT 5 web lane — one skill, three modes via a `mode:` arg (query / discuss / curate): a single direct question/task, a back-and-forth discussion or sparring session, or compare-candidates and pick/recommend the best. Not for the legacy agent-lanes-chatgpt-web-* routes or Codex-side lanes (use codex-consult) |
| cheat-engine-workflow | custom | Use when performing Cheat Engine-driven runtime analysis, including value scanning, pointer sanity checks, AOB validation |
| cheat-engine-x64dbg-ida-handoff | custom | Use when moving runtime findings between Cheat Engine, x64dbg, and IDA Pro |
| cheminformatics-rdkit | custom | Use when you need license-free cheminformatics via the rdkit MCP server - molecular descriptors, fingerprints, Tanimoto similarity, scaffolds, and structure-format conversion |
| ci-silent-pass-lint | custom | Use before any PR creation or "gates green / ready to merge" claim — detects CI/gate workflows that report GREEN while masking findings (11 silent-pass shapes: continue-on-error, \|\| true, audit mode, no-token uploads, set+e swallows, stale-SHA gates, soft thresholds, and more) via deterministic workflow linting + MCP cross-check of actual finding-counts at HEAD |
| citation-mapping | custom | Use when you need to build a citation or reference map for a paper, tracing backward references and forward cited-by works from metadata APIs like Semantic Scholar and OpenAlex |
| claude-science-local | custom | Use to bring up, diagnose, or recover Anthropic's Claude Science local compchem workbench (a WSL2 daemon on 127.0.0.1:8000) via the cs verbs (open/ensure/status/fix/doctor/backup/restore) — 401 means alive, cs fix recovers the host-RAM/SQLite wedge, cs ensure before any :8000 call; LOCAL only |
| cloudflare-deploy | built-in | Deploy applications and infrastructure to Cloudflare using Workers, Pages, and related platform services |
| code-security | built-in | Security guidelines for writing secure code |
| codex-consult | custom | Use when the user wants a Codex-side orchestration pass — consult, curate, or review — via codex_local_* / codex_orchestrator_* tools instead of direct ChatGPT web automation; one skill, three modes (replaces the codex-local-* and agent-lanes-codex-* lanes) |
| codex-orchestrate | custom | Route a task to the right codex-as-MCP orchestration tool by intent — one skill, all modes: brainstorm (codex_brainstorm), discuss (codex_discuss), coordinate/fix (codex_coordinate), review/audit (codex_review), curate/governance (codex_curate), triage (codex_consult). Replaces the per-mode wrappers codex-audit/brainstorm/coordinate/curate/discuss/fix/governance/review/triage |
| codex-runtime-recovery | custom | Use when Codex state is split across Windows, WSL, or VS Code, sessions disappear, or state_5.sqlite files churn |
| codex-session-reunion | custom | Use when Codex sessions or rollout JSONL files are spread across Windows, WSL, backups, or VS Code mirrors |
| codex-vscode-host-routing | custom | Use when VS Code launches Codex from the wrong host or WSL becomes the default unexpectedly |
| comp-pharm-cascade | custom | Route a congeneric small-molecule series against a protein target through a cost-escalating cascade (experimental-anchor data → Boltz-2 ML breadth+pose → Schrödinger FEP/MM-GBSA physics → EXESS QM mechanism → figures) with consensus checks at the pose and published-number gates; verify the experimental anchor before spending compute |
| competitive-programming-solver | custom | Use when solving online judge, olympiad, or contest problems in C, C++, or Python |
| consensus-tooluniverse-research | custom | Use when downloading or harvesting research from Consensus.app — extract searches browser-free from the page payload, resolve papers to DOIs and open-access PDFs via ToolUniverse, organize by topic with a bibliography, and capture the Consensus Meter graphs |
| critique-panel | custom | Use to run the G3 CRITIQUE gate of the TCR design-review loop — a four named-persona panel (user-advocate / systems-consistency / a11y / brand-aesthetic) that each reason over ui-audit's Track-A numbers plus the screenshot, run the NN/g I-Like / I-Wish / What-If ritual, score the nine DESIGN-EVAL v1 dimensions 0-4 with critical-error overrides, then synthesize one deduped, severity-ranked findings list with a weighted composite and enumerated directions (the human decides at G4). A TRIAGE accelerator, not an oracle. Pairs with ui-audit and design-review-loop |
| ddi-admet-research | custom | Use as the front-end for biomedical research via the ToolUniverse MCP - drug-drug interactions, ADMET/CYP, target research, FDA labels, repurposing, pharmacovigilance |
| deepsource | built-in | Retrieve code review results from DeepSource - issues, vulnerabilities, and quality metrics |
| design-review-loop | custom | Use to run the full named TCR design-review workflow as 8 sequenced gates (G0 PRIME, G1 AUDIT, G2 TRANSPOSE, G3 CRITIQUE, G4 DIRECT, G5 ITERATE, G6 RECONCILE, G7 VERIFY, then loop back to G1) over a running app. The orchestrator of the transpose-then-discuss-then-revert motion — invokes ui-audit at G1, transpose-to-figma at G2, critique-panel at G3, and figma-implement-design plus the revert-gate at G6, holding the per-gate question banks and the rule that every apply-back is a reversible commit reverted if it regresses any tracked axis |
| design-tokens-pipeline | custom | Use for the W3C DTCG design-token round-trip the TCR design-review loop relies on at G5/G6 — extract tokens out of code (CSS custom properties + Tailwind theme dumps) into a DTCG JSON tree, validate the five DTCG v1.0 rules that break the Tokens-Studio to Style-Dictionary round-trip (missing-type, bad-alias, alias-cycle, raw-hex-in-code, reserved-misuse), and diff two token trees to emit BOTH the forward change set AND the inverse revert patch. Transforms via Style Dictionary + sd-transforms. Pairs with design-review-loop and figma |
| develop-web-game | built-in | Use when Codex is building or iterating on a web game (HTML/JS) and needs a reliable development + testing loop |
| devtu | custom | ToolUniverse (mims-harvard/ToolUniverse) development toolkit — one skill, eight sub-command modes: create a new scientific/API tool, fix an erroring tool, optimize tool JSON descriptions, optimize research skills, auto-discover life-science APIs and generate integration PRs, run the full self-improve/debug-test loop, apply tool-code quality patterns, or safely push and fix CI on GitHub. Mode picked from intent; each mode playbook lives under modes/ |
| dispatching-parallel-agents | marketplace:superpowers | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| doc | built-in | Use when the task involves reading, creating, or editing .docx documents |
| drug-discovery-literature-bridge | custom | Use when extracting molecules, targets, assays, and clinical context from a paper (via the Scholarly Access MCP paper_* tools) to seed the drug-discovery stack — ToolUniverse DDI/ADMET/target tools and the RDKit MCP — keeping DOI provenance on every extracted entity |
| dump-to-signature-workflow | custom | Use when converting dump or debugger evidence into durable signatures, AOB patterns, or diffable artifacts |
| executing-plans | marketplace:superpowers | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
| figma | built-in | Use the Figma MCP server to fetch design context, screenshots, variables, and assets from Figma |
| figma-implement-design | built-in | Translate Figma nodes into production-ready code with 1:1 visual fidelity using the Figma MCP workflow |
| finishing-a-development-branch | marketplace:superpowers | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work |
| firecrawl | custom | Web scraping, crawling, structured extraction, site mapping, and change monitoring via the Firecrawl MCP. Use to turn known or discovered URLs into clean markdown or schema-structured JSON, screenshot pages or extract brand identity (colors, fonts, spacing, components), crawl or map entire sites, harvest docs and cookbooks, run competitive or design research, parse local PDFs and Office files, search the web with operators and domain filters, monitor pages for meaningful changes, or drive an autonomous browse agent. Pairs with exa-search — Exa finds by meaning, Firecrawl fetches, extracts, crawls, and monitors |
| format-codex-sessions | custom | Use when Codex rollout JSONL files need to be turned into readable Markdown conversations or transcripts |
| frida | custom | Use when runtime hooking, device instrumentation, API tracing, or patch-on-the-fly behavior matters |
| frida-mcp | custom | Use when installing or configuring frida-mcp as an MCP server for live Frida instrumentation |
| gem-hunt | custom | Use when the user wants to DISCOVER high-value improvements to their OWN agentic workspace/toolkit — new hooks, behaviors, gems, skills, MCPs, cross-domain techniques, or frontier-harness patterns — via a wide multi-lens agent fan-out, then a consolidated adopt/prune decision. The named agentic-perfection sweep / extensive gem search. NOT for interrogating ONE existing plan (use grill-me-extensive), NOT for ordinary topic research (use deep-research) |
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
| jina-reader | custom | Zero-RAM, server-less fetch of a single web page as clean LLM-ready markdown via a one-line HTTP GET to Jina Reader (r.jina.ai plus the target URL) — no MCP, no resident process. Cheapest first hop for a simple or mostly-static page; escalate to the Firecrawl MCP for JS-heavy/dynamic/crawl/extract, or exa web_fetch for batch URL reads |
| jupyter-notebook | built-in | Use when the user asks to create, scaffold, or edit Jupyter notebooks (.ipynb) |
| linear | built-in | Manage issues, projects and team workflows in Linear |
| llm-security | built-in | Security guidelines for LLM applications based on OWASP Top 10 for LLM 2025 |
| lolbin-lookup | custom | Structured GTFOBins (Unix) + LOLBAS (Windows) living-off-the-land lookup over D:\knowledge — binary name to abuse technique/category to ready command |
| long-copy-orchestrator | custom | Use when moving large trees between Windows, WSL, VMs, or mounted disks |
| mcp-code-orchestrate | custom | Use when one task needs the SAME tool-call shape across MANY items (xref-walk over many functions, descriptor sweep over many SMILES, batch-resolve/screen a list of papers, multi-source aggregation) — write ONE script that calls provider CLIs/libs/MCP-stdio, filters+aggregates in-code, returns only the distilled result. Anthropic's code-execution-with-MCP 98.7% fan-out token-cut; decision rule >~5 same-shape calls |
| mcp-fleet-curation | custom | Use when plugins/skills/MCP servers keep REAPPEARING after you disable them, or when de-bloating the Claude Code catalogue — the permanent cure (claude plugin disable name@mkt --scope user, not the UI toggle) + mcp_doctor audit + the reversible .mcp.json park/restore flow + the catalogue-tax model |
| mcp-graphql | custom | Use when installing or configuring blurrah/mcp-graphql for Codex, Claude Code, or Gemini CLI |
| mechanistic-ddi-pipeline | custom | Use to produce a mechanistic drug-drug-interaction verdict by combining ToolUniverse CYP/DDI knowledge with Schrodinger structure and docking evidence |
| mise | custom | Use when managing dev tool or language runtime versions with mise (mise-en-place) — global vs per-project pins, per-directory env vars, the task runner, non-language CLI installs, or Windows PowerShell setup |
| multi-agent-quickstart | custom | Use when learning how to choose between the Codex multi-agent orchestration tools |
| multi-ai-mingle | custom | Use when the user wants seamless LOCAL collaboration between Claude Code and OpenAI Codex on one machine — fan out parallel Codex threads from Claude via the official codex mcp-server, plus a live symmetric chat + file-lease channel via mcp_agent_mail (replaces AgentBridge). Covers mount, the shared agent-mail http channel, verify-then-commit, and the real API sequence (ensure_project + codenames + tokens + contacts) |
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
| re-ensure | custom | Bring up the reverse-engineering MCP backends (IDA / Ghidra) on demand so mcp__ida-pro-mcp / mcp__ghidra-mcp / mcp__binary-ninja-mcp calls just work without manually opening or navigating the GUI apps. Cold-starts ONLY the requested backend (RAM-conscious), prefers an already-running GUI IDA on :13337 (never duplicates), and reports honestly that Binary Ninja (Personal license) cannot run headless. Companion to the automatic PreToolUse re-autolaunch hook |
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
| sec-corpora-update | custom | Refresh the local security corpora under D:\knowledge (PayloadsAllTheThings, GTFOBins, LOLBAS, OWASP WSTG/CheatSheets, Atomic Red Team) with a shallow, fail-open git pull each |
| secsearch | custom | Unified offline ripgrep search across all local security corpora under D:\knowledge with per-source provenance tags; use first for cross-source security/pentest/red-team lookups |
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
| transpose-to-figma | custom | Use when lifting a running or built UI back onto the Figma canvas (the G2 TRANSPOSE / Code-to-Canvas edge of the design-review loop) and you must pick the right code-to-Figma path — story.to.design for the component-system loop, the Figma MCP generate_figma_design for live or localhost screens, or html.to.design for an audit-only DOM record. Also covers what survives the lossy round-trip (DTCG tokens + Code-Connected components) versus what is lost (state, routing, data, logic). Do NOT use for Figma-to-code (use figma-implement-design); covers Reframe, momentstudio, WebCoder, bilbo |
| ui-audit | custom | Drive a running web or Electron app and emit a deterministic UI/UX + functional audit — accessibility, contrast, spacing, tap targets, dead buttons, affordance/focus-visible, motion duration, visual regression (Track-A) — then a structured design-quality VERDICT (Track-B) where Claude reasons over the pre-computed numbers plus the screenshot on the DESIGN-EVAL v1 rubric (nine dimensions scored 0-4, a critical-error override that forces a zero and caps the verdict, a weighted composite with color-contrast highest, and a one-dimension-per-call reliability protocol) against Refactoring-UI / Material / HIG / Nielsen / WCAG. READ-ONLY (drives and inspects, never edits app source). Emits terminal-state typed findings plus a typed critique schema with a computed weighted composite |
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
