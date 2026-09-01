# Subagent Profiles -- On-Demand MCP Attachment Reference

This file defines 5 specialized subagent profiles for heavy tool groups. Instead of
loading all MCP servers into the main session (which adds ~200K tokens of overhead),
the orchestrator spawns a scoped subagent that attaches only the servers it needs.

**Dispatch pattern**: Use the Agent tool (or Task() in metaswarm) with the system
prompt and MCP server configs listed below. The subagent inherits the working
directory and file access from the parent session but only loads the listed servers.

**Source of truth**: Server configs are extracted from
`C:\Users\Prekzursil\.agents\agents.json`. Plugin-provided servers (marked `[plugin]`)
are managed by the Claude Code plugin system and do not need manual config -- they
attach automatically when their plugin is enabled and the subagent invokes the
relevant tool prefix.

---

## 1. Reverse Engineering (`re-analyst`)

**Purpose**: Binary analysis, decompilation, memory scanning, runtime instrumentation.

**System prompt**:
```
You are a reverse engineering specialist with access to IDA Pro, Ghidra, Binary Ninja,
CheatEngine, Frida, and HexStrike. Focus on binary analysis, decompilation, memory
scanning, and runtime instrumentation. Use the appropriate tool for each task: IDA Pro
for deep static analysis and type recovery, Ghidra for scriptable batch analysis,
Binary Ninja for IL-level reasoning, Frida for runtime hooking, CheatEngine for memory
scanning, and HexStrike for AI-assisted binary pattern analysis.
```

**Trigger contexts**: `.idb` files, `.bndb` files, `.i64` files, PE/ELF/Mach-O
binaries, memory dumps, decompilation requests, "reverse engineer", "disassemble",
"decompile", "hook function", "scan memory".

**Skills**: `reverse-engineering-toolkit`, `ida-decompiler-cleanup`, `binary-ninja`,
`ghidra-automation-recipes`, `frida`, `cheat-engine-workflow`

### MCP servers to attach

#### binary-ninja-mcp
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "binary-ninja-mcp", "--host", "localhost", "--port", "9009"]
}
```

#### cheatengine
```json
{
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\opt\\cheatengine-mcp-bridge\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\.local\\opt\\cheatengine-mcp-bridge\\MCP_Server\\mcp_cheatengine.py"]
}
```

#### frida-mcp
```json
{
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\opt\\frida-mcp\\.venv\\Scripts\\frida-mcp.exe",
  "args": []
}
```

#### ghidra-mcp
```json
{
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\opt\\ghidra-mcp\\.venv\\Scripts\\python.exe",
  "args": [
    "C:\\Users\\Prekzursil\\.local\\opt\\ghidra-mcp\\GhidraMCP-release-1-4\\bridge_mcp_ghidra.py",
    "--ghidra-server", "http://127.0.0.1:8089/"
  ]
}
```

#### hexstrike-ai
```json
{
  "transport": "stdio",
  "command": "py",
  "args": ["-3", "C:\\Users\\Prekzursil\\.local\\opt\\hexstrike-ai\\hexstrike_mcp_launcher.py"],
  "startup_timeout_sec": 90
}
```

#### ida-pro-mcp
```json
{
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\opt\\ida-pro-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\.local\\opt\\ida-pro-mcp\\.venv\\Lib\\site-packages\\ida_pro_mcp\\server.py"]
}
```

**Required env**: None (all local servers).

---

## 2. Browser Testing (`browser-tester`)

**Purpose**: End-to-end browser automation, visual regression, cross-browser testing,
Chrome DevTools debugging.

**System prompt**:
```
You are a browser automation and testing specialist. Use Playwright for E2E test
authoring and execution, Chrome DevTools MCP for live debugging, performance tracing,
and accessibility auditing, and BrowserStack for cross-browser and cross-device testing.
Prefer Playwright for repeatable test scripts and Chrome DevTools for interactive
debugging sessions.
```

**Trigger contexts**: E2E tests, `*.spec.ts` / `*.test.ts` with browser imports,
browser debugging, cross-browser testing, UI testing, "playwright", "e2e", "browser
test", "screenshot test", "lighthouse", "accessibility audit".

**Skills**: `playwright`, `playwright-interactive`, `webapp-testing`,
`chrome-devtools-mcp:chrome-devtools`, `chrome-devtools-mcp:a11y-debugging`,
`chrome-devtools-mcp:debug-optimize-lcp`

### MCP servers to attach

#### playwright [plugin]
Plugin-managed (`playwright@claude-plugins-official`). Tools are prefixed
`mcp__plugin_playwright_playwright__*`. Enable the plugin in settings.json or
attach via:
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"],
  "startup_timeout_sec": 60
}
```

#### chrome-devtools [plugin]
Plugin-managed (`chrome-devtools-mcp@claude-plugins-official`). Tools are prefixed
`mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`. Enable the plugin in
settings.json or attach via:
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "chrome-devtools-mcp@latest"],
  "startup_timeout_sec": 60
}
```

#### browserstack
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@browserstack/mcp-server@1.2.11"],
  "env": {
    "BROWSERSTACK_USERNAME": "${BROWSERSTACK_USERNAME}",
    "BROWSERSTACK_ACCESS_KEY": "${BROWSERSTACK_ACCESS_KEY}"
  },
  "startup_timeout_sec": 60
}
```

**Required env**: `BROWSERSTACK_USERNAME`, `BROWSERSTACK_ACCESS_KEY` (for BrowserStack
only; Playwright and Chrome DevTools work locally).

---

## 3. Cloud Infrastructure (`cloud-deployer`)

**Purpose**: Deploy and manage cloud resources across AWS, Firebase, DigitalOcean, and
edge/PaaS platforms.

**System prompt**:
```
You are a cloud infrastructure specialist. Deploy and manage cloud resources across
AWS (serverless, SAM, CDK), Firebase, DigitalOcean, and edge platforms (Cloudflare,
Netlify, Vercel, Render, Railway). Use the appropriate service for the workload: AWS
for serverless and enterprise, Firebase for mobile/web backends, DigitalOcean for
simple app hosting, and edge platforms for static sites and JAMstack.
```

**Trigger contexts**: Deployment, cloud infrastructure, serverless, hosting, "deploy",
"aws", "firebase", "digitalocean", "cloudflare", "netlify", "vercel", "render",
"railway", IaC files (`template.yaml`, `serverless.yml`, `firebase.json`,
`render.yaml`).

**Skills**: `cloudflare-deploy`, `netlify-deploy`, `vercel-deploy`, `render-deploy`,
`railway:use-railway`, `aws-serverless:aws-lambda`,
`aws-serverless:aws-serverless-deployment`, `deploy-on-aws:deploy`

### MCP servers to attach

#### aws-serverless [plugin]
Plugin-managed (`aws-serverless@claude-plugins-official`). Tools are prefixed
`mcp__plugin_aws-serverless_aws-serverless-mcp__*`. Enable the plugin in
settings.json to activate. Provides SAM init/build/deploy/invoke/logs and ESM
guidance tools.

#### deploy-on-aws [plugin]
Plugin-managed (`deploy-on-aws@claude-plugins-official`). Tools are prefixed
`mcp__plugin_deploy-on-aws_*`. Provides documentation search, pricing, and cost
analysis tools.

#### firebase [plugin]
Plugin-managed (`firebase@claude-plugins-official`). Tools are prefixed
`mcp__plugin_firebase_firebase__*`. Provides project management, app creation,
SDK config, security rules, and environment management.

#### digitalocean
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@digitalocean/mcp", "--services", "apps", "--transport", "stdio"],
  "env": {
    "DIGITALOCEAN_API_TOKEN": "${DIGITALOCEAN_TOKEN}"
  },
  "startup_timeout_sec": 60
}
```

**Required env**: `DIGITALOCEAN_TOKEN` (for DigitalOcean). AWS and Firebase use their
own auth flows via plugin. Edge platform CLIs use their respective tokens.

---

## 4. Design (`design-implementer`)

**Purpose**: Translate Figma designs into production code with 1:1 visual fidelity.

**System prompt**:
```
You are a design-to-code specialist. Translate Figma designs into production-ready
code with 1:1 visual fidelity. Use the Figma MCP to fetch design context, screenshots,
variables, tokens, and component metadata. Adapt output to the target project's stack,
component library, and design tokens. Follow Code Connect mappings when available.
Always invoke the figma-use skill before calling use_figma.
```

**Trigger contexts**: Figma URLs (`figma.com/design/...`, `figma.com/board/...`,
`figma.com/make/...`), design implementation requests, "implement this design",
"design to code", "figma", UI component creation from mockups.

**Skills**: `figma:figma-use`, `figma:figma-implement-design`,
`figma:figma-generate-design`, `figma:figma-code-connect`,
`figma:figma-create-design-system-rules`, `frontend-design:frontend-design`

### MCP servers to attach

#### figma [plugin]
Plugin-managed (`figma@claude-plugins-official`). Tools are prefixed
`mcp__plugin_figma_figma__*`. Enable the plugin in settings.json to activate.

The canonical server config (if manual attachment is needed):
```json
{
  "transport": "http",
  "url": "https://mcp.figma.com/mcp"
}
```

**Required env**: None (Figma plugin uses OAuth via the plugin system).

---

## 5. Code Quality (`code-quality-auditor`)

**Purpose**: Cross-reference code quality and security findings across multiple
analysis platforms.

**System prompt**:
```
You are a code quality and security auditor. Cross-reference findings across Codacy,
SonarQube, DeepSource, and Semgrep. Prioritize issues by severity, identify patterns
across tools, and produce actionable remediation plans. Use Codacy for overall code
quality metrics, SonarQube for deep static analysis and IDE integration, DeepSource
for automated fixes, and Semgrep for custom rule scanning and supply-chain analysis.
```

**Trigger contexts**: Code quality audits, security reviews, metric analysis, "code
quality", "security audit", "static analysis", "lint", "sonar", "codacy", "deepsource",
"semgrep", pre-PR quality gates.

**Skills**: `semgrep`, `code-security`, `security-best-practices`,
`autofix-bot-api`, `deepsource`, `semgrep-plugin:semgrep-scan`

### MCP servers to attach

#### codacy
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@codacy/codacy-mcp@latest"],
  "env": {
    "CODACY_ACCOUNT_TOKEN": "${CODACY_ACCOUNT_TOKEN}",
    "CODACY_API_TOKEN": "${CODACY_API_TOKEN}"
  },
  "startup_timeout_sec": 60
}
```

#### sonarqube
```json
{
  "transport": "stdio",
  "command": "docker",
  "args": [
    "run", "-i", "--rm",
    "-e", "SONARQUBE_TOKEN",
    "-e", "SONARQUBE_ORG",
    "-e", "SONARQUBE_URL",
    "-e", "SONARQUBE_IDE_PORT",
    "docker.io/mcp/sonarqube:latest"
  ],
  "env": {
    "SONARQUBE_TOKEN": "${SONARQUBE_TOKEN}",
    "SONARQUBE_ORG": "${SONARQUBE_ORG}",
    "SONARQUBE_URL": "${SONARQUBE_URL}",
    "SONARQUBE_IDE_PORT": "${SONARQUBE_IDE_PORT}"
  },
  "startup_timeout_sec": 60
}
```

#### deepsource
```json
{
  "transport": "stdio",
  "command": "C:\\Program Files\\nodejs\\node.exe",
  "args": ["C:\\Users\\Prekzursil\\.local\\opt\\deepsource-mcp-server\\deepsource-mcp-wrapper.mjs"],
  "env": {
    "DEEPSOURCE_API_KEY": "${DEEPSOURCE_API_KEY}"
  }
}
```

#### semgrep [plugin]
Plugin-managed (`semgrep@claude-plugins-official`). Tools are prefixed
`mcp__plugin_semgrep-plugin_semgrep__*`. Enable the plugin in settings.json to
activate. Standalone CLI config (if manual attachment is needed):
```json
{
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\bin\\uvx.exe",
  "args": ["semgrep-mcp", "--semgrep-path", "C:\\Users\\Prekzursil\\.local\\bin\\semgrep.exe"],
  "startup_timeout_sec": 60
}
```

**Required env**: `CODACY_ACCOUNT_TOKEN`, `CODACY_API_TOKEN` (Codacy);
`SONARQUBE_TOKEN`, `SONARQUBE_ORG`, `SONARQUBE_URL`, `SONARQUBE_IDE_PORT` (SonarQube);
`DEEPSOURCE_API_KEY` (DeepSource). Semgrep plugin handles its own auth.

---

## Dispatch Quick Reference

| Profile | ID | Server count | Plugin servers | Standalone servers |
|---|---|---|---|---|
| Reverse Engineering | `re-analyst` | 6 | 0 | 6 |
| Browser Testing | `browser-tester` | 3 | 2 | 1 |
| Cloud Infrastructure | `cloud-deployer` | 4 | 3 | 1 |
| Design | `design-implementer` | 1 | 1 | 0 |
| Code Quality | `code-quality-auditor` | 4 | 1 | 3 |

## Usage Example

When the orchestrator detects a trigger context, it dispatches like this:

```
Spawn a subagent with:
  - System prompt: [profile system prompt above]
  - MCP servers: [attach the listed server configs]
  - Skills to prime: [listed skills]
  - Task: [the specific user request]
```

For plugin-managed servers, the subagent just needs the plugin enabled in
settings.json -- no manual config attachment is needed. For standalone servers,
pass the JSON config blocks above when spawning the agent.

## Maintenance

- When `agents.json` changes, re-verify the configs in this file match.
- Run `agents mcp test --runtime` to validate server health before dispatch.
- Plugin versions update automatically; standalone server versions are pinned
  in agents.json.
