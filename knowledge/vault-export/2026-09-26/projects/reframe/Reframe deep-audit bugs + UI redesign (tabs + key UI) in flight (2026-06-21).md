---
title: Reframe deep-audit bugs + UI redesign (tabs + key UI) in flight (2026-06-21)
type: note
permalink: main/projects/reframe/reframe-deep-audit-bugs-ui-redesign-tabs-key-ui-in-flight-2026-06-21
tags:
- reframe
- audit
- ui-redesign
- bugs
- ui-ux-pro-max
---

# Reframe deep-audit + UI redesign (2026-06-21)

User feedback after installing: Models&System confusing; "add key but no where + no available keys shown"; "some boxes don't work"; selection state unclear; needs-download confusing. Directive: deep bug audit + fix ALL + add tabs + redesign + use ui-ux skills.

## SKILLS made available + applied (copied to ~/.claude/skills, live this session):
ui-ux-pro-max (design DB: dark/OLED, Fira, WCAG-AAA + pro-UI checklist), make-interfaces-feel-better, frontend-design-direction (=> daily tool: dense/quiet/scannable, NOT landing), frontend-a11y, design-system. Bug-fix toolkit = superpowers:systematic-debugging, tdd-workflow, verification-loop, reviewers.

## DEEP AUDIT (wf_4e1e9211, 12 agents adversarially-verified) — CONFIRMED bugs:
- [CRIT] DirectorPanel op-row buttons (Disable/Enable, Move ↑/↓) DirectorPanel.tsx:493,496-513 — no onClick + no delegation + row <li> tabIndex=0 has no onKeyDown => fully INERT ("boxes don't work").
- [HIGH] Readiness "Add a provider key"/"Grant consent" buttons render + sidecar emits (handlers.py:3257-3268) but NO key/consent UI mounted => dead-ends ("add key, no where"). ReadinessBadge.tsx:48-56 + ModelsSystemPanel:412 early-return.
- [HIGH] OFFLINE not enforced on cloud AI egress: _run_ai_job (handlers.py:2478-2540) + phase8.select/director.plan/thumbnail.select/index.build/search build live cloud providers gated only by consent/routing/weights, never offline => offline=True still egresses. (assets/diarize DO guard_network; AI paths don't.)
- [HIGH] Sidecar RESTART RACE: sidecar.ts onExit :455-460 + onSpawnError :448-453 don't check the firing child===this.child; restart() kills child1+spawns child2; child1 exit (later tick) rejects child2 reqs + nulls this.child + spawns child3 => TWO live python + response misrouting. Reachable via "Restart sidecar" UI. Fix: `if(this.child===child)` guard both listeners.
- [HIGH] silenceTrim CAPTION-CUE DESYNC (refine/trim_clip): interior-keep concat doesn't remap cue timestamps => captions drift.
- [MED] PathsPanel ORPHANED (data-root change/open-folder QoL) — mounted nowhere. BatchConsentCard ORPHANED (per-batch budget-ack, informational).
- [SEED] AddKeyRow/ProviderKeyRow/ConsentToggle ORPHANED = the key UI itself.
- REFUTED (NOT bugs): deferred Director ops regenScroll/ocrExtractList (intentional DEFERRED_KINDS), refine.py save_project dead-dep (nit).

## REDESIGN PLAN (wf_4a8fc444 / branch feat/ui-redesign, in flight): backend fixes (offline+cue + restart-race) ∥ then sequential renderer: WU-TABS (top-level tabs Library/Create/Director/Repurpose/Settings, active-state+keyboard) -> WU-PROVIDERS (wire AddKeyRow/ProviderKeyRow/ConsentToggle into "Providers & API Keys" Settings panel: catalog picker + get-free-key links + testKey + upsert + setConsent + usage + status badges; Readiness buttons navigate here; add providers.upsert/testKey/remove/setConsent to typed client) -> WU-DIRECTOR-CONTROLS (wire inert buttons + keyboard) -> WU-MODELS-REDESIGN (selection badges, model-state clarity Installed/Download-MB/Downloading/Needs-key, disabled clarity, empty-state, no hard Analyze gate, wire PathsPanel). Each TDD 100% + design-skills + formatters-before-commit. Then verify + GUI-verify (Playwright-Electron) + peer-review + rebuild installer.

## NEXT after build: GUI-verify the new tabs/key-UI actually work in the launched app; merge; rebuild installer to Documents\Reframe-Installer; show user. momentstudio fleet finalize (wf_6185284c) still running separately.