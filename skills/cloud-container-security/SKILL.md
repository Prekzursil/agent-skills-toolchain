---
name: cloud-container-security
description: "Use when auditing OWNER cloud accounts, container images, Kubernetes clusters, IaC, or SBOM/secret posture (AWS/Azure/GCP/K8s/M365). Read-only CSPM + non-destructive attack-path + SBOM/verified-secret scanning with Prowler, Trivy, kubescape, Steampipe/Powerpipe, cloudfox, trufflehog, and Syft."
license: "Wraps upstream tools by CLI/MCP (never vendored): Trivy/Prowler/kubescape/Syft Apache-2.0, cloudfox MIT, trufflehog/Steampipe/Powerpipe AGPL-3.0."
---

# cloud-container-security — CSPM, container / K8s / IaC, SBOM & secrets (owner cloud)

## Overview

Seven best-in-class OSS scanners that answer "is my cloud estate configured
safely, and what is shipping inside my images?" — **read-only posture and
non-destructive enumeration only**, on accounts and clusters you own.

| Tool | Answers | License | Channel |
|------|---------|---------|---------|
| **Prowler** | Cloud posture / CSPM (AWS/Azure/GCP/K8s/M365) + keyless Hub check catalog | Apache-2.0 | CLI + MCP |
| **Trivy** | Image / filesystem / repo / IaC-misconfig / K8s / SBOM / secret scan | Apache-2.0 | CLI + `trivy mcp` plugin |
| **kubescape** | Kubernetes posture vs NSA / CIS / MITRE ATT&CK | Apache-2.0 | CLI |
| **Steampipe / Powerpipe** | SQL-queryable cloud posture + compliance benchmarks | AGPL-3.0 (wrap) | CLI (ephemeral) |
| **cloudfox** | Non-destructive cloud **attack-path** enumeration | MIT | CLI |
| **trufflehog** | **Verified** leaked secrets (git / fs / images / buckets) | AGPL-3.0 (wrap) | CLI |
| **Syft** | SBOM generation (CycloneDX / SPDX) feeding vuln scanners | Apache-2.0 | CLI |

Everything here is defensive: find the misconfiguration / exposed secret /
vulnerable package, then **fix it or write a detection** — never exploit it.

## STOP rules (read before running anything)

1. **Owner cloud / accounts / clusters only (H1).** Point these at AWS/Azure/GCP
   accounts, kubeconfig contexts, registries, and repos you own or are explicitly
   authorized to assess. Never scan third-party tenants. `cloudfox` and Prowler
   read live cloud APIs with your ambient credentials — confirm the identity
   first (`aws sts get-caller-identity`, `az account show`, `gcloud config list`,
   `kubectl config current-context`).
2. **No always-on daemon.** This skill is on-demand CLI/MCP invocation. Do **not**
   stand up Falco, a persistent Steampipe/`powerpipe` service, a Prowler
   dashboard server, or any resident agent. If a run needs Steampipe's service,
   start it for the run and `steampipe service stop` after.
3. **No exploitation, no attack detonation.** `cloudfox` enumerates paths
   (Get/List/Describe) but does not act on them. **stratus-red-team** (which
   *detonates* attack techniques in cloud) is deliberately **not** in this skill —
   it lives in `$purple-emulation`. Link to it; do not duplicate it here.
4. **AGPL is wrapped, never vendored (G17).** trufflehog, Steampipe, and Powerpipe
   are AGPL-3.0. Invoke their released binaries as external processes; do not copy
   their source into this repo.
5. **Secrets by env NAME only.** Reference `${AWS_PROFILE}`, `${PROWLER_API_KEY}`,
   etc. Never write a live key into a command, file, or the receipt.

## When to use / when NOT

**Use** for: a cloud security baseline, CIS/NSA compliance evidence, image/IaC
scanning in CI or ad hoc, finding an over-privileged role or public bucket,
generating an SBOM, or hunting verified secret leaks in your own code/artifacts.

**Do NOT use** for: live exploitation (out of scope), attack emulation
(`$purple-emulation`), memory/disk forensics (`$volatility-3`,
`$offline-linux-disk-surgery`), SAST of app source (`$semgrep`, `$code-security`),
or general CVE lookup (`$cve-mcp`). This skill *feeds* those, it does not replace
them.

## Host-gate (preflight)

These tools are host-gated — none are assumed present. Check what is installed
first (read-only, no network, no subprocess, always exits 0):

```bash
python3 scripts/preflight.py            # report all seven lanes
python3 scripts/preflight.py --tools trivy syft   # check a subset
```

Absent tools are reported, never enforced. Install only the lane you need
(per-tool notes below); prefer the standalone release binary inside an isolated
assessment host.

## The seven tools

### 1. Prowler — cloud posture / CSPM (Apache-2.0)

Ambient-credential, read-only CSPM across providers. The **Prowler Hub**
(`hub.prowler.com`) is a keyless online catalog of checks + threat intel; the CLI
runs those checks against your accounts.

```bash
uvx prowler aws                                  # scan current AWS identity (read-only)
uvx prowler aws --compliance cis_3.0_aws         # a named compliance framework
uvx prowler kubernetes                           # in-cluster / kubeconfig posture
uvx prowler aws --severity critical high -M csv json-ocsf html
uvx prowler azure ; uvx prowler gcp ; uvx prowler m365
```

Prowler only calls Get/List/Describe-class APIs. Scope with `--service`,
`--check`, `--region`, or an explicit `${AWS_PROFILE}`. See `references/tool-matrix.md`
for output modes and MCP wiring.

### 2. Trivy — image / IaC / K8s / SBOM / secret (Apache-2.0)

The workhorse. One binary scans containers, filesystems, git repos, IaC, live
clusters, SBOMs, and secrets.

```bash
trivy image --severity HIGH,CRITICAL <image>
trivy fs --scanners vuln,secret,misconfig .
trivy config .                                   # Terraform/K8s/Dockerfile misconfig
trivy k8s --report summary                       # OWNER cluster (current context)
trivy image --format cyclonedx -o sbom.json <image>   # emit an SBOM
```

**MCP:** `trivy plugin install mcp` then `trivy mcp` (stdio; also HTTP/SSE). Host-gated;
already registered DEFAULT-OFF in the parent `.agents/agents.json` (`command: trivy`,
`args: ["mcp"]`, `enabled: false`) — the parent flips it on once the binary + plugin
are present. See PARENT MERGE in the receipt.

### 3. kubescape — Kubernetes posture (Apache-2.0)

Scores a cluster or manifests against NSA, CIS, and MITRE ATT&CK for Kubernetes.

```bash
kubescape scan                                   # current kubecontext (OWNER cluster)
kubescape scan framework nsa,cis,mitre --format json
kubescape scan *.yaml                            # pre-deploy manifest scan
kubescape scan image <image>
```

Install via krew (`kubectl krew install kubescape`), the official installer, or a
release binary — **not** on npm/PyPI. No packaged MCP exists (see below).

### 4. Steampipe / Powerpipe — SQL posture & benchmarks (AGPL-3.0, wrap)

Query cloud config as SQL, then run compliance benchmarks over it. The engines are
AGPL (wrapped as external binaries); the compliance **mods** are Apache-2.0.

```bash
steampipe plugin install aws azure gcp kubernetes
steampipe query "select title, arn from aws_iam_role where name like 'admin%'"
# Benchmarks need the service briefly; start -> run -> STOP (no always-on daemon):
steampipe service start
powerpipe benchmark run aws_compliance.benchmark.cis_v300
steampipe service stop
```

### 5. cloudfox — non-destructive attack-path enumeration (MIT)

Maps who-can-reach-what in **your** cloud: over-permissioned roles, secrets in
launch data, public resources, pivot paths. Read-only (Get/List/Describe); it
surfaces paths, it never walks them.

```bash
cloudfox aws --profile ${AWS_PROFILE} all-checks   # OWNER profile only
cloudfox azure ; cloudfox gcp
```

Feed its findings into remediation or into `$purple-emulation` for authorized,
lab/owned validation — not into live exploitation.

### 6. trufflehog — verified secret scanning (AGPL-3.0, wrap)

Finds leaked credentials and, with `--only-verified`, confirms which are still
live by validating them against **their own** provider.

```bash
trufflehog git file://. --only-verified          # your repo history
trufflehog filesystem <path> --only-verified
trufflehog docker --image <image> --only-verified
```

`--only-verified` makes a validation call to the secret's provider — keep it to
**owner** secrets. Use `--no-verification` for a fully offline pass.

### 7. Syft — SBOM generation (Apache-2.0)

Produces a complete bill-of-materials to hand to a vulnerability scanner.

```bash
syft <image> -o cyclonedx-json=sbom.json
syft dir:. -o spdx-json
```

Pair with Trivy (`trivy sbom sbom.json`), grype/osv-scanner, or route packages to
`$cve-mcp` (`osv_batch`) for vulnerability status.

## Workflow (owner cloud)

1. **Confirm identity + scope.** `aws sts get-caller-identity` /
   `kubectl config current-context`; verify it is an owner account.
2. **Preflight.** `python3 scripts/preflight.py` — see which lanes are installed.
3. **Posture.** Prowler (accounts) + kubescape (clusters) + `trivy config` (IaC).
4. **Supply chain.** Syft → SBOM; Trivy image/fs vuln+secret scan.
5. **Secrets.** trufflehog `--only-verified` over owner repos/images.
6. **Attack paths.** cloudfox `all-checks` (read-only) for over-privilege / exposure.
7. **Route findings:** CVEs → `$cve-mcp`; detections → `$detection-as-code`;
   authorized validation of a path → `$purple-emulation`. Fix or detect — never exploit.

## Routing / hand-offs

- **SBOM / image CVEs →** `$cve-mcp` (`osv_batch`, `cve_report`) and the routing
  envelope in hacktricks `references/security-mcp-routing.md`.
- **Turn findings into detections →** `$detection-as-code` (Sigma), `$dfir-triage`.
- **Attack detonation / stratus-red-team →** `$purple-emulation` (lab/owned only).
- **Authorized active testing →** `$hexstrike-ai-authorized-engagement` (after the
  W-rails target-scope + evidence hooks are green).
- **Complementary cloud MCP:** `cloud-audit` (AWS/Azure/GCP read audit) is
  registered DEFAULT-OFF in the parent registry; owner accounts only (H1).

## MCP wiring (parent-owned — see the receipt PARENT MERGE section)

- **trivy** — already registered DEFAULT-OFF in `.agents/agents.json`
  (`command: trivy`, `args: ["mcp"]`, `enabled: false`). No child action needed.
- **prowler-mcp** — verified to exist (`prowler-mcp` on PyPI v0.5.0; hosted
  `https://mcp.prowler.com/mcp`; Docker `prowlercloud/prowler-mcp`). Exact
  DEFAULT-OFF block proposed for the parent in the receipt.
- **kubescape** — **no packaged MCP exists** (absent from npm and PyPI; only
  from-source community repos `slashben/kubescape-mcp-server` (Go) and
  `mohdhaji87/Kubescape-MCP` (Python)). Building a from-source Go daemon violates
  the anti-overfit anchor, so this skill **wraps the kubescape CLI only** and
  proposes no agents.json block.

## References

- `references/tool-matrix.md` — fuller per-tool command reference, output modes,
  install channels, licenses, and host-gate notes.
- `scripts/preflight.py` — read-only host-gate check (tested; no network).
