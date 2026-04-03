# Skills Manifest

> Auto-generated skill inventory for the agent-skills-toolchain repository.
> Last updated: 2026-04-04

| Skill Name | Origin | Description |
|---|---|---|
| agent-lanes-chatgpt-web-curate | custom | Use when the user explicitly wants final comparison or curation through the direct ChatGPT web lane |
| agent-lanes-chatgpt-web-discuss | custom | Use when the user explicitly wants discussion, ideation, or sparring through the direct ChatGPT web lane |
| agent-lanes-chatgpt-web-query | custom | Use when the user explicitly wants a direct ChatGPT web / Agentify lane rather than Codex orchestration |
| agent-lanes-codex-consult | custom | Use when the user explicitly wants a Codex-side consultation lane for structured analysis or tradeoff review |
| agent-lanes-codex-curate | custom | Use when the user explicitly wants Codex orchestration to compare options and choose the best one |
| agent-lanes-codex-review | custom | Use when the user explicitly wants a Codex-side review or critic lane |
| angr | built-in | Use when symbolic execution, path exploration, constraint solving, or programmatic reasoning about binary behavior is needed |
| apply-callee-type-ex | custom | Use when IDA Pro decompiler output suffers from missing or bad indirect-call types and you need ApplyCalleeTypeEx |
| aspnet-core | built-in | Build, review, refactor, or architect ASP.NET Core web applications using current official guidance |
| autofix-bot-api | custom | Scan code for security vulnerabilities, leaked secrets, and dependency issues via DeepSource autofix bot API |
| binary-ninja | custom | Use when Binary Ninja UI workflows, intermediate-language reasoning, or Binary Ninja Python API automation are needed |
| binary-ninja-diff-signatures | custom | Use when working in Binary Ninja to compare versions, analyze changed functions, or generate stable signatures |
| binary-ninja-mcp | custom | Use when installing or configuring Binary Ninja MCP, especially when a plugin or npm-based MCP bridge must be wired |
| bindiff | custom | Use when comparing two related binaries or database exports to identify changed functions or patch deltas |
| binexport | custom | Use when exporting IDA Pro, Binary Ninja, or Ghidra analysis into BinExport artifacts for BinDiff |
| binja-sigmaker | custom | Use when generating byte signatures or AOB patterns from Binary Ninja for runtime hooks or trainer work |
| brainstorming | marketplace:superpowers | You MUST use this before any creative work - creating features, building components, adding functionality |
| chatgpt5-web-curate | custom | Use when the user explicitly wants final curation or selection performed through the direct ChatGPT web lane |
| chatgpt5-web-discuss | custom | Use when the user explicitly wants a discussion or sparring-partner interaction through ChatGPT web |
| chatgpt5-web-query | custom | Use when the user explicitly wants a direct ChatGPT 5 web/Agentify interaction |
| chatgpt-apps | built-in | Build, scaffold, refactor, and troubleshoot ChatGPT Apps SDK applications that combine an MCP server and widget UI |
| cheat-engine-workflow | custom | Use when performing Cheat Engine-driven runtime analysis, including value scanning, pointer sanity checks, AOB validation |
| cheat-engine-x64dbg-ida-handoff | custom | Use when moving runtime findings between Cheat Engine, x64dbg, and IDA Pro |
| cloudflare-deploy | built-in | Deploy applications and infrastructure to Cloudflare using Workers, Pages, and related platform services |
| code-security | built-in | Security guidelines for writing secure code |
| codex-audit | custom | Use when you want an audit-style orchestration pass over risk, gaps, and verification needs |
| codex-brainstorm | custom | Use when you want two Codex peers to generate ideas before synthesis |
| codex-coordinate | custom | Use when you want Codex to split roles and consolidate the outcome |
| codex-curate | custom | Use when you want a final best-option selector, optionally with PromptBridge talk-only curation |
| codex-discuss | custom | Use when you want two Codex peers to debate tradeoffs before synthesis |
| codex-fix | custom | Use when you want Codex to coordinate a fix path across multiple reasoning roles |
| codex-governance | custom | Use when you need a final governance-oriented decision across options and risks |
| codex-local-consult | custom | Use when the user explicitly wants a structured Codex-side consultation pass |
| codex-local-curate | custom | Use when the user explicitly wants Codex orchestration to select or synthesize the best option |
| codex-local-review | custom | Use when the user explicitly wants a Codex-led review or critique pass |
| codex-review | custom | Use when you want one Codex critic to review a plan or change before implementation |
| codex-runtime-recovery | custom | Use when Codex state is split across Windows, WSL, or VS Code, sessions disappear, or state_5.sqlite files churn |
| codex-session-reunion | custom | Use when Codex sessions or rollout JSONL files are spread across Windows, WSL, backups, or VS Code mirrors |
| codex-triage | custom | Use when you need a fast classification of next steps before deeper work |
| codex-vscode-host-routing | custom | Use when VS Code launches Codex from the wrong host or WSL becomes the default unexpectedly |
| deepsource | built-in | Retrieve code review results from DeepSource - issues, vulnerabilities, and quality metrics |
| develop-web-game | built-in | Use when Codex is building or iterating on a web game (HTML/JS) and needs a reliable development + testing loop |
| dispatching-parallel-agents | marketplace:superpowers | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| doc | built-in | Use when the task involves reading, creating, or editing .docx documents |
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
| hexstrike-ai-authorized-engagement | custom | Use when an authorized security assessment, bug bounty, red-team, or CTF task should be routed through HexStrike AI |
| hexstrike-ai-mcp | custom | Use when installing, repairing, or registering HexStrike AI as an MCP server for Codex, Claude Code, or Gemini CLI |
| hexstrike-ai-setup | custom | Use when installing, wiring, validating, or troubleshooting a local HexStrike AI runtime |
| ida-decompiler-cleanup | custom | Use when Hex-Rays decompiler output in IDA Pro is noisy, poorly typed, or hard to reason about |
| ida-pro-mcp | custom | Use when installing or configuring mrexodia/ida-pro-mcp for IDA Pro |
| imagegen | built-in | Use when the user asks to generate or edit images via the OpenAI Image API |
| jupyter-notebook | built-in | Use when the user asks to create, scaffold, or edit Jupyter notebooks (.ipynb) |
| linear | built-in | Manage issues, projects and team workflows in Linear |
| llm-security | built-in | Security guidelines for LLM applications based on OWASP Top 10 for LLM 2025 |
| long-copy-orchestrator | custom | Use when moving large trees between Windows, WSL, VMs, or mounted disks |
| mcp-graphql | custom | Use when installing or configuring blurrah/mcp-graphql for Codex, Claude Code, or Gemini CLI |
| multi-agent-quickstart | custom | Use when learning how to choose between the Codex multi-agent orchestration tools |
| netlify-deploy | built-in | Deploy web projects to Netlify using the Netlify CLI |
| notion-knowledge-capture | built-in | Capture conversations and decisions into structured Notion pages |
| notion-meeting-intelligence | built-in | Prepare meeting materials with Notion context and Codex research |
| notion-research-documentation | built-in | Research across Notion and synthesize into structured documentation |
| notion-spec-to-implementation | built-in | Turn Notion specs into implementation plans, tasks, and progress tracking |
| offline-linux-disk-surgery | custom | Use when a Linux guest disk must be inspected, grown, or repaired offline with qemu-nbd, guestfish, GPT tools |
| openai-docs | built-in | Use when the user asks how to build with OpenAI products or APIs and needs up-to-date official documentation |
| pdf | built-in | Use when tasks involve reading, creating, or reviewing PDF files |
| peutils | custom | Use when inspecting or repairing PE-focused details in Binary Ninja |
| playwright | built-in | Use when the task requires automating a real browser from the terminal |
| playwright-interactive | built-in | Persistent browser and Electron interaction through js_repl for fast iterative UI debugging |
| promptbridge-codex-consult | custom | Use when installing, probing, or debugging PromptBridge-backed Codex consultation |
| quality-gate-automation-architect | custom | Use when designing, comparing, or reviewing autonomous repo-quality automation |
| radare2 | custom | Use when command-line disassembly, debugging, hex editing, or scriptable low-level binary triage is needed |
| reboot-safe-ops-continuation | custom | Use when a reboot is required in the middle of migration or repair work and you need exact pre-reboot state capture |
| receiving-code-review | marketplace:superpowers | Use when receiving code review feedback, before implementing suggestions |
| render-deploy | built-in | Deploy applications to Render by analyzing codebases, generating render.yaml Blueprints |
| repomix | built-in | Use when packing a repository into an AI-friendly bundle with Repomix |
| requesting-code-review | marketplace:superpowers | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| ret-sync | custom | Use when synchronizing a live debugger with IDA Pro, Binary Ninja, or compatible disassemblers |
| reverse-engineering-toolkit | custom | Use when selecting or sequencing reverse-engineering tools for Windows native analysis |
| screenshot | built-in | Use when the user explicitly asks for a desktop or system screenshot |
| security-best-practices | built-in | Perform language and framework specific security best-practice reviews |
| security-ownership-map | built-in | Analyze git repositories to build a security ownership topology |
| security-threat-model | built-in | Repository-grounded threat modeling that enumerates trust boundaries, assets, attacker capabilities |
| semgrep | built-in | Run Semgrep static analysis scans and create custom detection rules |
| sentry | built-in | Use when the user asks to inspect Sentry issues or events |
| slides | built-in | Create and edit presentation slide decks (.pptx) with PptxGenJS |
| sora | built-in | Use when the user asks to generate, remix, poll, list, download, or delete Sora videos via OpenAI video API |
| speech | built-in | Use when the user asks for text-to-speech narration or voiceover |
| spreadsheet | built-in | Use when tasks involve creating, editing, analyzing, or formatting spreadsheets |
| subagent-driven-development | marketplace:superpowers | Use when executing implementation plans with independent tasks in the current session |
| swfoc-modding | custom | Research-backed workflow for Star Wars: Empire at War / Forces of Corruption modding, SDK/tooling, debugging |
| swfoc-reverse-engineering | custom | Use when working on SWFOC editor runtime or native analysis |
| swfoc-runtime-address-hunting | custom | Use when hunting SWFOC-specific runtime addresses, function anchors, structures, or memory regions |
| systematic-debugging | marketplace:superpowers | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| test-driven-development | marketplace:superpowers | Use when implementing any feature or bugfix, before writing implementation code |
| transcribe | built-in | Transcribe audio files to text with optional diarization and known-speaker hints |
| ui-ux-pro-max | built-in | UI/UX design intelligence with searchable database |
| using-git-worktrees | marketplace:superpowers | Use when starting feature work that needs isolation from current workspace |
| using-superpowers | marketplace:superpowers | Use when starting any conversation - establishes how to find and use skills |
| vercel-deploy | built-in | Deploy applications and websites to Vercel |
| verification-before-completion | marketplace:superpowers | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs |
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
