# GCP Windows + Docker: definitive research (firecrawl, 2026-09-29)

Lane: gcp-windows-docker (owner-side, firecrawl search + GCP docs scrape)
Status: EXHAUSTED — authoritative answer found, acted on.

## Verdict
**Nested virtualization + Hyper-V/WSL2/Docker Desktop on this VM is
DOCUMENTED-UNSUPPORTED and is the exact "corrupts the server" class.**

Evidence: GCP Compute docs "About nested virtualization" (updated 2026-09-28,
scraped via firecrawl): *"The only hypervisor supported in an L1 VM is Linux
KVM; Microsoft Hyper-V isn't supported."* Restrictions also exclude E2/ARM/
memory-optimized/AMD(except N4D). Our VM: n2-custom-12-98304, Intel Cascade
Lake, not shielded, not preemptible, VBS off — the flag WOULD apply, but the
flag only legitimizes KVM-in-Linux; Windows L1 + Hyper-V remains unsupported.
Boot-loop search results (WSL issue #4784, MS Answers automatic-repair threads,
Unraid VMP boot-loop) are this failure class on VT-x-less VMs.

## Incident contained (2026-09-29)
Earlier in this session VirtualMachinePlatform + Microsoft-Windows-Subsystem-Linux
had been enabled via DISM with a reboot PENDING — on a VT-x-less VM that reboot
was a brick risk. Rolled back same day: both features verified `State: Disabled`,
`bcdedit hypervisorlaunchtype Off`. Reboot is now safe.

## The working solution for our exact context (ranked)
1. **Remote Linux Docker engine over SSH (RECOMMENDED)** — small Debian VM in
   the same project/VPC runs docker; this box sets `DOCKER_HOST=ssh://…`.
   No docker API port exposed anywhere (SSH-key-only), zero risk to the
   Windows server, all staged compose stacks run unchanged.
   Provisioned by: `D:\opt\scripts\provision-docker-remote-host.ps1`
   (e2-standard-2, 100GB, docker+compose via startup script, estate SSH key).
2. Same-VPC internal IP (free, private) or Tailscale IP if the operator
   prefers the existing tailnet (TAILSCALE_OAUTH_CLIENT_SECRET is on-box).
3. Windows Server process-isolation containers (native, no Hyper-V) — real but
   **Linux-image stacks cannot run**, so it does not serve pentagi/decepticon/
   firecrawl; noted for completeness.

## Retired
`enable-nested-virt-and-docker.ps1` overwritten with DO-NOT-RUN retirement
notice + throw. Docker Desktop stays installed but inert (harmless without
Hyper-V; can be uninstalled any time).

## Sources (queries + scrapes logged)
- firecrawl search ×4 (nested virt gcloud; WSL2 boot loop; docker without
  nested virt; remote docker engine tailscale)
- firecrawl scrape: docs.cloud.google.com enabling + overview pages (2026-09-28
  revision)
- corroboration: microsoft/WSL#4784, MS Answers Hyper-V boot failures,
  docker.com vm-vdi + containers-on-GCE docs, tailscale docker guide
