# W-cloud receipt — cloud-container-security skill

**Wave:** W-cloud · **Branch:** `cursor/cyber-suite-full-program` · **Status:** DELIVERED — skill authored, dual-written, scripts tested, MCP existence verified.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

(The sentence above is the mandated skeleton marker. It is retained verbatim per the wave
contract; this receipt has since been rewritten at each milestone, so the line no longer
describes the unit's state — the measured claims below govern.)

## Claims

| Claim | Status |
|-------|--------|
| Receipt skeleton written first | DONE (created before authoring) |
| `.agents/skills/cloud-container-security/SKILL.md` authored | DONE |
| `agents/openai.yaml` authored (quoted `display_name`/`short_description`/`default_prompt`) | DONE |
| Dual-write `skills/cloud-container-security/**` byte-identical | DONE (`diff -r` empty) |
| Tools covered: Prowler, Trivy, kubescape, Steampipe/Powerpipe, cloudfox, trufflehog, Syft | DONE (7 lanes) |
| Stop rules present (owner-cloud H1; no always-on Falco/daemon; stratus→purple link; no exploit; AGPL wrap) | DONE |
| Scripts have tests with fakes, no live network | DONE (`preflight.py` + 6 passing tests) |
| ruff 0.15.17 check + format clean on touched Python | DONE (checks passed; 2 files already formatted) |
| MCP existence verified (trivy / prowler / kubescape) | DONE (trivy=plugin+already-registered; prowler=PyPI 0.5.0; kubescape=no package) |
| PARENT MERGE agents.json blocks recorded | DONE (see below) |
| Commit SHA | RECORDED BELOW |

## Tool coverage (all read-only / non-destructive; owner cloud only)

| Tool | Purpose | License (SPDX, verified via `gh api .license`) | Channel |
|------|---------|------------------------------------------------|---------|
| Prowler | CSPM AWS/Azure/GCP/K8s/M365 + keyless Hub | Apache-2.0 | CLI + MCP (`uvx prowler-mcp`) |
| Trivy | image/fs/repo/IaC/K8s/SBOM/secret | Apache-2.0 | CLI + `trivy mcp` plugin |
| kubescape | K8s posture NSA/CIS/MITRE | Apache-2.0 | CLI only |
| Steampipe/Powerpipe | SQL posture + compliance benchmarks | AGPL-3.0 (wrap, don't vendor) | CLI (ephemeral service) |
| cloudfox | non-destructive attack-path enum | MIT | CLI |
| trufflehog | verified secret scan (`--only-verified`) | AGPL-3.0 (wrap, don't vendor) | CLI |
| Syft | SBOM (CycloneDX/SPDX) | Apache-2.0 | CLI |

## Stop rules (encoded in SKILL.md)

1. Owner cloud / accounts / clusters only (H1); confirm identity before scanning.
2. No always-on daemon (no Falco, no resident Steampipe/Powerpipe service, no dashboard server); on-demand only.
3. No exploitation / no attack detonation. cloudfox enumerates paths but does not walk them; **stratus-red-team lives in `$purple-emulation`** (linked, not duplicated).
4. AGPL (trufflehog/Steampipe/Powerpipe) wrapped as external binaries, never vendored (G17).
5. Secrets by env NAME only.

## Skill paths

- Canonical: `.agents/skills/cloud-container-security/`
  - `SKILL.md`, `agents/openai.yaml`, `references/tool-matrix.md`,
    `scripts/preflight.py`, `scripts/test_preflight.py`
- Dual-write mirror: `skills/cloud-container-security/` (byte-identical)

## Verification commands run

```text
npm view trivy-mcp version            -> 0.0.1-security (placeholder, NOT the plugin)
npm view prowler-mcp / kubescape-mcp  -> E404 (not on npm)
curl pypi.org/pypi/prowler-mcp/json   -> v0.5.0 (2026-03-19) exists
curl pypi.org/pypi/kubescape-mcp/json -> {"message":"Not Found"}
gh api repos/aquasecurity/trivy-mcp   -> exists (plugin: `trivy plugin install mcp` + `trivy mcp`)
gh search repos kubescape mcp         -> only from-source community repos (slashben Go, mohdhaji87 Python)
gh api repos/<8 tools>/.license       -> Apache-2.0 x5, AGPL-3.0 x3 (trufflehog/steampipe/powerpipe), MIT (cloudfox)
ruff check  scripts/                  -> All checks passed
ruff format --check scripts/          -> 2 files already formatted
pytest scripts/test_preflight.py -q   -> 6 passed
python3 scripts/preflight.py          -> exit 0 (0/8 present on this cloud VM; fail-open, correct)
diff -r .agents/skills/... skills/... -> MIRRORS IDENTICAL
```

## PARENT MERGE — proposed `.agents/agents.json` blocks

Parent owns `.agents/agents.json`; this wave did NOT edit it. All entries follow the
existing host-gated DEFAULT-OFF schema (cf. `jadx-mcp`/`cloud-audit`/`rsigma`/`trivy`).

### 1. `trivy` — ALREADY REGISTERED (no parent action needed)

Verified present in `.agents/agents.json` today, exactly as the wave requested
(`command: "trivy"`, `args: ["mcp"]`, `enabled: false`). Recorded here for completeness:

```json
"trivy": {
  "label": "trivy",
  "description": "Trivy MCP plugin (`trivy mcp`, Aqua): container/IaC/K8s/SBOM/secret scan. Host-gated on the trivy binary + `trivy plugin install mcp`. Registered DEFAULT-OFF until the binary is present.",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "trivy",
  "args": ["mcp"],
  "credentialNames": [],
  "tags": ["approved", "claude-only", "local", "stdio", "security", "default-off"]
}
```

### 2. `prowler-mcp` — NEW, proposed DEFAULT-OFF (verified exists)

`prowler-mcp` is published on PyPI (v0.5.0, 2026-03-19) → runnable via `uvx prowler-mcp`
(stdio). The **Prowler Hub** surface is keyless; **Prowler App/Cloud** result tools need
`PROWLER_API_KEY` only if the owner uses Prowler Cloud SaaS — so `env` is omitted here
(matching the ambient-credential, no-env pattern of `cloud-audit`). Owner accounts only (H1).

```json
"prowler-mcp": {
  "label": "prowler-mcp",
  "description": "Prowler MCP (prowler-cloud/prowler mcp_server, Apache-2.0): keyless Prowler Hub check + threat-intel catalog, plus Prowler App/Cloud result tools (only if the owner uses Prowler Cloud SaaS -- add PROWLER_API_KEY by env NAME then). Local stdio via `uvx prowler-mcp` (PyPI 0.5.0). Host-gated on uv; DEFAULT-OFF until owner cloud identity is confirmed. Owner accounts only (H1). Read-only posture; not a network executor.",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "uvx",
  "args": ["prowler-mcp"],
  "credentialNames": [],
  "tags": ["approved", "claude-only", "local", "stdio", "security", "default-off"]
}
```

Alternative launches (if `uvx` is undesirable): Docker `docker run --rm -i prowlercloud/prowler-mcp`
(stdio), or the hosted server `npx -y mcp-remote https://mcp.prowler.com/mcp` (add
`--header "Authorization: Bearer ${PROWLER_API_KEY}"` for App/Cloud tools).

### 3. `kubescape` — NO MCP BLOCK PROPOSED (CLI-wrap only)

No packaged kubescape MCP exists: absent from npm (E404) and PyPI (`kubescape-mcp` Not Found;
the kubescape CLI itself is not a PyPI package). The only MCP servers are **from-source community
repos** — `slashben/kubescape-mcp-server` (Go; kubescape co-founder's personal repo; pushed
2025-05-19; not archived) and `mohdhaji87/Kubescape-MCP` (Python; 2025-07-05). Standing up a
from-source Go/Python daemon violates the anti-overfit anchor (ENABLE-native > BORROW > … > no new
daemon), so **this skill wraps the kubescape CLI directly and proposes no agents.json entry.**
If the owner later wants a kubescape MCP, build `slashben/kubescape-mcp-server` from source on the
RE host and register it host-gated DEFAULT-OFF — a separate, future decision, not this wave.

## Commit

- Skill (canonical + mirror): commit `533d5f33` — 10 files, 1006 insertions (`feat(skills): add cloud-container-security (W-cloud) …`).
- Receipt (this file): committed in the immediately following path-scoped commit on this branch.
- Branch: `cursor/cyber-suite-full-program`. Path-scoped commits only; no shared-file edits.
