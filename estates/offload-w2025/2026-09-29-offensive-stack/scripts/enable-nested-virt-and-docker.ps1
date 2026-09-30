# !! DO NOT RUN - RETIRED 2026-09-29 !!
# GCP docs (updated 2026-09-28): the ONLY hypervisor supported inside a GCP L1 VM
# is Linux KVM. "Microsoft Hyper-V is not supported." This VM is a Windows Server
# L1, so the nested-virt flag does NOT make Hyper-V/WSL2/Docker Desktop supported;
# enabling those features is the boot-loop corruption class on GCP Windows VMs.
# VirtualMachinePlatform + WSL features were rolled back to Disabled and
# hypervisorlaunchtype set Off on 2026-09-29 (verified).
# SAFE PATH: D:\opt\scripts\provision-docker-remote-host.ps1 (remote Linux engine via SSH)
throw "retired: use provision-docker-remote-host.ps1"
