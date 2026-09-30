# provision-docker-remote-host.ps1 — SAFE Docker path for this estate (2026-09-29)
#
# WHY THIS EXISTS: GCP Compute docs (updated 2026-09-28) state the only
# hypervisor supported inside a GCP L1 VM is Linux KVM — "Microsoft Hyper-V
# isn't supported." Our L1 is Windows Server, so the nested-virtualization
# flag + Hyper-V/WSL2/Docker Desktop path is DOCUMENTED-UNSUPPORTED and is the
# known cause of boot-loop "corruption" on GCP Windows VMs. The previously
# staged enable-nested-virt-and-docker.ps1 is DEAD — do not run it. The
# VirtualMachinePlatform/WSL features were rolled back to Disabled and
# hypervisorlaunchtype set Off on 2026-09-29 (verified) — reboot is safe.
#
# SAFE PATH: a small Linux VM in the same project runs the Docker engine;
# this Windows box drives it over SSH (docker -H ssh://...). No docker API
# port is exposed to any network — the engine stays reachable only via SSH
# keys. All staged compose stacks (pentagi, decepticon-upstream,
# firecrawl-selfhost) run there unchanged via DOCKER_HOST.
#
# Requires: gcloud authenticated (it is), project 750220148127, zone europe-central2-a.
# Cost note: e2-standard-2 (2 vCPU/4GB) ≈ on-demand pricing; use --preemptible
# or a spot policy for lab-only use. Stop the VM when idle.
$ErrorActionPreference = "Stop"
$Project = "750220148127"
$Zone    = "europe-central2-a"
$Name    = "offload-docker"

# 1. Create the Linux docker host (Debian 12, docker installed via startup script)
$StartupScript = @'
#!/bin/bash
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git curl
systemctl enable --now docker
useradd -m -s /bin/bash dockerops || true
usermod -aG docker dockerops
mkdir -p /home/dockerops/.ssh
'@
$Tmp = New-TemporaryFile
Set-Content -Path $Tmp -Value $StartupScript
gcloud compute instances create $Name `
    --project=$Project --zone=$Zone `
    --machine-type=e2-standard-2 `
    --image-family=debian-12 --image-project=debian-cloud `
    --boot-disk-size=100GB `
    --metadata=startup-script=$(Get-Content $Tmp -Raw) `
    --quiet

# 2. Push THIS box's public key (uses the estate key at ~/.ssh)
$PubKey = (Get-ChildItem "$env:USERPROFILE\.ssh\*.pub" | Select-Object -First 1).FullName
gcloud compute os-login ssh-keys add --key-file=$PubKey --project=$Project 2>$null
gcloud compute project-info add-metadata --project=$Project `
    --metadata="ssh-keys=dockerops:$(Get-Content $PubKey -Raw)" --quiet

# 3. Wait for SSH, then verify
Write-Host "waiting for SSH..."
Start-Sleep -Seconds 45
gcloud compute ssh $Name --project=$Project --zone=$Zone --command="docker version" --quiet

Write-Host ""
Write-Host "Docker host ready. From THIS box:"
Write-Host '  $env:DOCKER_HOST = "ssh://dockerops@<EXTERNAL_OR_INTERNAL_IP>"'
Write-Host "  (internal IP is free + private if both VMs share the VPC)"
Write-Host "  docker ps   # drives the remote engine"
Write-Host "  D:\opt\pentagi\bring-up.ps1  # works unchanged with DOCKER_HOST set"
Write-Host ""
Write-Host "Get the IP:  gcloud compute instances list --filter=name:$Name"
