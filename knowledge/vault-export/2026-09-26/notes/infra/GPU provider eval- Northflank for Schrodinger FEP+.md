---
title: 'GPU provider eval: Northflank for Schrodinger FEP+'
type: note
permalink: main/notes/infra/gpu-provider-eval-northflank-for-schrodinger-fep
tags:
- gpu-provider
- northflank
- schrodinger
- fep
- infra
---

# GPU provider eval: Northflank for Schrodinger FEP+

Adversarial verification 2026-06-21 for the phenibut FEP+ use case (install 13GB licensed suite + portable license, root, multi-hour MD on a real multi-GPU single node).

## Verdict: CONDITIONAL fit (~6.5/10). Better than Modal/GCP/Vultr on gating, but gVisor + new-account capacity for 8x is the residual risk.

## Key findings (cited)
- **Multi-GPU single node CONFIRMED in docs**: managed cloud supports up to **8 GPUs per single service instance** ("8 GPUs / 2 instances = 8 GPUs per instance / 16 total"). This is a REAL single node (not Modal-style faked topology) — JobDJ should see 8 real GPUs. https://northflank.com/docs/v1/application/gpu-workloads/deploy-gpus-on-northflank-cloud
- **Gating: marketing says no waitlists, self-serve, deploy in <5 min, no quota requests.** Northflank brokers cloud-provider relationships so YOU don't file quota requests. https://northflank.com/gpu , https://northflank.com/blog/what-are-spot-gpus-guide
- **CATCH #1 (gVisor)**: "GPU workloads on Northflank cloud use gVisor isolation by default." gVisor passes GPUs through (nvidia-smi works) UNLIKE Modal's fake — but it is a syscall-intercepting userspace kernel. Risk for Desmond/OpenMPI (ssh/sshd, shared-mem) and any syscall the FEP+ stack needs. Kata/Firecracker (microVM, real kernel) is available as an alternative isolation but may need selection/BYOC. https://northflank.com/blog/cloud-hypervisor-vs-gvisor
- **CATCH #2 (new-account 8x)**: standard on-demand GPU is self-serve, BUT `/request/gpu` exists for "guaranteed availability or specific volume commitments." An 8x H100/A100 single node on a brand-new account MAY route through capacity request rather than instant click. NOT confirmed instant for the 8x tier. https://northflank.com/request/gpu
- **Payment**: "all users must add a payment method to start creating resources, regardless of plan" — Free Sandbox = 2 free NON-GPU services, NO GPU credit. No $250/$300-style trial credit. Card-gated, not credit-gated. (MakerStack's "no card" claim contradicts Northflank's own docs — trust the docs.)
- **Root/install/persistent**: deploys arbitrary Docker images from any registry; persistent volumes 1GB–16TB. 13GB install + license drop is fine in a custom image / on a volume. Root-in-container yes; true privileged/host-kernel under gVisor is the open question.

## Pricing (managed cloud, per hr): A100-40G $1.42, A100-80G $1.76, H100-80G $2.74, L4 $0.80, RTX PRO 6000 $3.00. Per-second billing.

## Single most important unresolved: whether a NEW account can self-serve an 8x node IMMEDIATELY (vs capacity request), and whether gVisor breaks Desmond MPI. Needs a live signup test to fully clear.
