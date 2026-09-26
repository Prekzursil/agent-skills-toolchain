---
title: GPU cloud providers - enterprise tier GPU gating for Schrodinger FEP+ (June
  2026)
type: note
permalink: main/research/infra/gpu-cloud-providers-enterprise-tier-gpu-gating-for-schrodinger-fep-june-2026
tags:
- gpu-cloud
- schrodinger-fep
- gpu-gating
- phenibut
---

# Enterprise GPU cloud gating research (June 2026)

Use case: install 13GB licensed Schrodinger suite + run multi-hour MD on real (multi-)GPU root VM. #1 killer = new/trial accounts get GPU access GATED. Modal faked multi-GPU; GCP free trial GPU quota 0; Vultr = support ticket on every GPU plan.

## Verdicts (5 enterprise providers)
- **Oracle OCI**: $300/30d trial. GPU service limit = HARD 0 for TRIAL accounts (official docs limits-by-service); even Pay-As-You-Go shows "Contact Us" -> service-limit increase ticket via My Oracle Support, approval takes days. NOT self-serve. BM.GPU.A100=8xA100-80G. ~$4/hr A100-80G, ~$3.50/hr L40S. Verdict: requires_approval (quota_request).
- **Azure**: $200/30d trial. GPU quota = ZERO on new subs, quota-increase request often DENIED for credit/trial subs (payment-history gated). requires_approval.
- **AWS**: Activate credits exist but new-account GPU vCPU quota = 0 (G/P families); must request increase w/ business justification, capacity-gated, P5 in high demand. requires_approval.
- **Alibaba**: up to $5000 credits / 12-mo ECS trial (CPU t5 only). gn7s GPU family needs ticket to apply; GPU quota gated. requires_approval.
- **IBM Cloud**: BEST candidate. $200 credit (after PAYG upgrade w/ card) + $1000 VPC credit (120d) + 50% off L40S/A100 via code GPU4YOU thru 30 Jun 2026. gx3 GPU profiles: gx3d-160x1792x8h100 = 8x H100-80G single node; also 2x/4x L40S, A100 PCIe. Standard GPU profiles provisionable by selecting profile - NO quota ticket documented (only B300 needs support case). BUT no positive forum/Reddit confirmation a brand-new account launches instantly without per-account GPU quota wall -> mark unknown leaning self-serve, NOT confirmed instant.

## Bottom line
All 5 hyperscalers gate GPU on new/trial accounts EXCEPT possibly IBM Cloud (standard profiles documented as no-ticket; needs empirical confirmation). For guaranteed instant self-serve multi-GPU, specialist providers (Lambda, RunPod, etc.) remain better than the big-5. IBM gx3d 8xH100 is the only big-5 multi-GPU node that looks self-serve on paper.
