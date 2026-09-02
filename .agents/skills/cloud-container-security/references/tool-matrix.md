# cloud-container-security — tool matrix

Fuller reference for the seven scanners. All are **read-only / non-destructive**
and run against **owner** cloud, clusters, registries, and repos only (H1). None
run as an always-on daemon.

## Install channels & licenses (verified 2026-09-02)

| Tool | License (SPDX) | Install | Not available via |
|------|----------------|---------|-------------------|
| Trivy | Apache-2.0 | brew / apt / release binary; `trivy plugin install mcp` for the MCP | npm `trivy-mcp` is a `0.0.1-security` placeholder — NOT the plugin |
| Prowler | Apache-2.0 | `pip install prowler` / `uvx prowler`; MCP `uvx prowler-mcp` (PyPI 0.5.0) or Docker `prowlercloud/prowler-mcp` or hosted `mcp.prowler.com/mcp` | — |
| kubescape | Apache-2.0 | `kubectl krew install kubescape`, official installer, release binary | npm ✗, PyPI ✗, no packaged MCP |
| Steampipe | AGPL-3.0 | official installer / brew (wrap, don't vendor) | — |
| Powerpipe | AGPL-3.0 | official installer / brew (wrap, don't vendor) | needs a Steampipe/Postgres backend |
| cloudfox | MIT | release binary / `go install` | — |
| trufflehog | AGPL-3.0 | release binary / brew / Docker (wrap, don't vendor) | — |
| Syft | Apache-2.0 | official installer / brew / release binary | — |

## Prowler (CSPM)

```bash
uvx prowler aws                                   # current identity, all checks
uvx prowler aws --profile ${AWS_PROFILE} --region us-east-1
uvx prowler aws --compliance cis_3.0_aws          # named framework
uvx prowler aws --service s3 iam --severity critical high
uvx prowler aws -M csv json-ocsf html             # output formats -> ./output/
uvx prowler kubernetes ; uvx prowler azure ; uvx prowler gcp ; uvx prowler m365
```

- Ambient credentials (AWS profile/role, `az login`, gcloud ADC, kubeconfig).
- Read-only (Get/List/Describe). No resource is created or modified.
- **Prowler Hub** (`hub.prowler.com`) is the keyless catalog of checks + threat
  intel; the CLI executes those checks locally.
- MCP surface: Prowler Hub tools are keyless; Prowler App/Cloud result tools need
  `${PROWLER_API_KEY}` (only if you use Prowler Cloud SaaS).

## Trivy (all-surface scanner)

```bash
trivy image --severity HIGH,CRITICAL <image>
trivy image --scanners vuln,secret,misconfig,license <image>
trivy fs --scanners vuln,secret .
trivy repo <git-url>
trivy config .                                    # IaC: TF / K8s / Dockerfile / Helm
trivy k8s --report summary                        # OWNER cluster (current context)
trivy sbom sbom.json                              # scan an existing SBOM
trivy image --format cyclonedx -o sbom.json <image>
```

- MCP plugin: `trivy plugin install mcp` → `trivy mcp` (stdio default; `--transport`
  http|sse). Registered DEFAULT-OFF in the parent registry.

## kubescape (K8s posture)

```bash
kubescape scan                                    # current kubecontext
kubescape scan framework nsa,cis,mitre --format json --format-version v2
kubescape scan control C-0016                     # single control
kubescape scan *.yaml                             # pre-deploy manifests
kubescape scan image <image>
```

- CLI only. No packaged MCP (community from-source repos exist; not adopted).

## Steampipe / Powerpipe (SQL posture + benchmarks)

```bash
steampipe plugin install aws azure gcp kubernetes
steampipe query "select name, arn from aws_iam_user where mfa_enabled = false"
# Benchmarks need the DB backend briefly — start, run, STOP:
steampipe service start
powerpipe mod install github.com/turbot/steampipe-mod-aws-compliance
powerpipe benchmark run aws_compliance.benchmark.cis_v300
steampipe service stop
```

- Engines are AGPL-3.0 (wrapped). Compliance mods are Apache-2.0.
- Never leave `steampipe service` running as an always-on daemon.

## cloudfox (non-destructive attack-path)

```bash
cloudfox aws --profile ${AWS_PROFILE} all-checks  # OWNER profile only
cloudfox aws --profile ${AWS_PROFILE} permissions
cloudfox azure ; cloudfox gcp
```

- Read-only enumeration (Get/List/Describe). Surfaces over-privileged roles,
  secrets in launch data, public resources, and pivot paths. Output → `~/.cloudfox/`.
- It maps paths; it does **not** exploit them. Validation of a path belongs in
  `$purple-emulation` (lab/owned, authorized).

## trufflehog (verified secrets)

```bash
trufflehog git file://. --only-verified           # local repo history
trufflehog github --org=<owner-org> --only-verified
trufflehog filesystem <path> --only-verified
trufflehog docker --image <image> --only-verified
trufflehog s3 --bucket=<owner-bucket> --only-verified
trufflehog git file://. --no-verification         # fully offline pass
```

- `--only-verified` validates a candidate against its provider (a live call to the
  credential's own service). Keep strictly to **owner** secrets.

## Syft (SBOM)

```bash
syft <image> -o cyclonedx-json=sbom.json
syft dir:. -o spdx-json
syft <image> -o table                             # human summary
```

- Hand the SBOM to Trivy (`trivy sbom`), grype, osv-scanner, or route packages to
  `$cve-mcp` (`osv_batch`) for vulnerability status.

## Routing envelope

Findings feed remediation and detection, never exploitation. Route CVEs to
`$cve-mcp`, detections to `$detection-as-code`, authorized path validation to
`$purple-emulation`, and authorized active testing to
`$hexstrike-ai-authorized-engagement` (after the W-rails scope + evidence hooks
are green). The dangerous-tool envelope is hacktricks
`references/security-mcp-routing.md`.
