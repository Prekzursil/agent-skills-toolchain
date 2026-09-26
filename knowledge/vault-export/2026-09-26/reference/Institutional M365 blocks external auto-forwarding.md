---
title: Institutional M365 blocks external auto-forwarding
type: guide
permalink: main/reference/institutional-m365-blocks-external-auto-forwarding
tags:
- microsoft365
- outlook
- email
- forwarding
- gotcha
- unibuc
---

University/institutional Microsoft 365 tenants commonly BLOCK external auto-forwarding. Verified 2026-07-18 on `daria-smaranda.grama@s.unibuc.ro` (University of Bucharest).

## The trap
- [gotcha] The OWA forwarding rule SAVES, Outlook shows "Email is being forwarded to X", and incoming mail ARRIVES at the M365 inbox — but nothing is delivered to the external destination, and NO non-delivery report (NDR) is generated. Silent transport-level drop by the tenant outbound anti-spam policy. #silent-block
- [gotcha] There is NO client-side fix — it's an admin policy. The forwarding banner in OWA is NOT proof of delivery. #no-client-fix

## Diagnostic (distinguish "blocked" from "slow M365 latency")
- [check] (1) confirm the test mail arrived at the M365 inbox; (2) confirm ZERO delivery to the external destination after several minutes (`in:anywhere` search on the destination — covers spam/trash); (3) confirm no NDR in the M365 account. That combination ⟹ tenant block. Legit M365 forwarding usually delivers within a few minutes. #diagnostic

## Workarounds
- [pattern] PULL instead of PUSH: Gmail "Add a mail account" (POP3 fetch) is a DIFFERENT mechanism the outbound-forward policy may not cover — but POP is often ALSO disabled on the tenant, needs the account password (+ app-password if MFA on). Or ask the institution's IT to permit forwarding. #pop-pull-workaround

Evidence: mail reached the Outlook inbox, forwarding enabled + "is being forwarded" banner, but 0 forwarded copies delivered to the Gmail destination after 15+ min, no NDR. Confidence the cause is a tenant block ≈ 85% (couldn't inspect admin policy directly).

## Relations
- relates_to [[Gmail forwarding to per-source folders — automation playbook + gotchas]]
