# Open loops register

Live register of unfinished work. **Nothing here may be closed silently** — an item is
closed only by writing the evidence that closed it into the Evidence column.
This file is the anti-abandonment mechanism from
`deep-thoughts/2026-09-23-harness-ossification-and-insight-decay.md` (DT-1, R2/R4).

Owner column: **O** = owner-only (I cannot do it), **C** = Claude can do it, **B** = both.
Review-by exists so a decision expires into "re-examine" rather than becoming permanent truth.

Last updated 2026-09-24 (plaintext policy; L-11 + L-12 closed; L-14 fix written).

## Blocking — something cannot ship until these resolve

| ID | Item | Why it blocks | Owner | Review by | Status | Evidence when closed |
|---|---|---|---|---|---|---|
| L-01 | **Dinu Plast engagement facts** — the two 2023 CVs contradict each other: end date Jul 2022 vs Jun 2023, title Web Developer vs Freelancer Informatica, location Ramnicu Valcea vs Bucuresti (company registry says Ramnicu Valcea, CUI 16367462) | The Experience section cannot be written. A document beats a recollection: pull the REGES-Online extract | O | 2026-10-15 | OPEN | |
| L-02 | **Undocumented employment history** beyond Dinu Plast and momentstudio | Owner stated salaried/internship work exists; none of it is written down anywhere. Intake interview is the only source | O | 2026-10-15 | OPEN | |
| L-03 | **English CEFR level** — advanced, but C1 vs C2 unconfirmed | Languages section on every document | O | 2026-10-15 | OPEN | |

## Reputational — must land before supervisor contact (doctorate is committed)

| ID | Item | Why | Owner | Review by | Status | Evidence when closed |
|---|---|---|---|---|---|---|
| L-04 | **Personal-Finance-Management rename** — rename package and classes off `com.preethi.thrifty`, update manifest/gradle/imports, remove the "all rights reserved" line, README states it began from an uncredited template and diverged (~90% original) | Owner's account is that he used an unnamed uncredited template, not a knowing fork. The current package name implies another author, which is false. Renaming makes the repo more honest, not less. Does not erase git history — the defensible position is "diverged and renamed", never "no association existed" | C | 2026-10-10 | OPEN | |
| L-05 | **ORCID corrections** — education entry currently credits the BSc to University of Bucharest; truth is Titu Maiorescu BSc + UB master's. Also normalise name to `Andrei-Mihai Visalon` and attach the ChemRxiv preprint and Zenodo deposit | Public record contradicts the CV. A supervisor cross-checking finds the mismatch. ~30 min of work | O | 2026-10-10 | OPEN | |
| L-06 | **Three GitHub credentials exposed in a session transcript** (one fine-grained + one classic on 2026-09-23; a third fine-grained pasted 2026-09-24) | Rotate once current work completes. A transcript is not the vault: the private-estate plaintext policy permits credentials in the private repo, which is not the same as a credential sitting in a conversation log. Owner handles credential lifecycle; Claude will never rotate | O | 2026-10-01 | OPEN | |

## Gated — work exists but cannot be linked yet

| ID | Item | Why | Owner | Review by | Status | Evidence when closed |
|---|---|---|---|---|---|---|
| L-07 | **momentstudio.ro repo** — 63,363 remote branches (63,116 `cursor/*`), 89 `rescue/*` tags | Branches tab reads as unattended agent runs and undoes the credit the entry earns. Prune before any link | B | 2026-11-01 | OPEN | |
| L-08 | **agent-skills-toolchain repo** — 403 MB, committed browser-profile binaries, red CI badge, no LICENSE | Most recently pushed repo, so first thing a reviewer meets. Described in prose until purged and green. "open-source" may not be used without a LICENSE | B | 2026-11-01 | OPEN | |
| L-09 | **Airline-Reservations-System** language badge says Python on a C++ project | Reviewer-visible inconsistency. Fix with a `.gitattributes` linguist-vendored rule | C | 2026-11-01 | OPEN | |

## Harness — found broken this session, not yet fixed

| ID | Item | Why | Owner | Review by | Status | Evidence when closed |
|---|---|---|---|---|---|---|
| L-10 | **MCP project-key case collision** — cwd `C:\Users\prekzursil` (lowercase p) does not match the project key `C:/Users/Prekzursil` holding the 120-entry disable list, so at the real cwd nothing is disabled and all 88 servers launch | Root cause of both the ~30 server failures and the startup context cost. Fix is ADDITIVE (copy the list onto the lowercase key), never destructive. Must be done with the session closed; editing `.claude.json` while Claude runs clobbers it | C | 2026-10-01 | OPEN | |
| L-11 | **estate-deny-guard use-vs-mention defect** — every rule matched the literal command text, so writing a file whose *content* documented a forbidden command tripped the rule. Present in `estate-deny-guard.py` AND `no-force-push/tripwire.py` | Blocked five legitimate writes 2026-09-23/24, including the guard's own test file | C | 2026-10-15 | **CLOSED 2026-09-24** | Fixed in both guards: heredocs bound for a file sink are stripped, heredocs piped to an interpreter are still scanned, `-m` bodies stripped. `scripts/test_estate_deny_guard.py` ALL-PASS (11 cases) incl. `executed-heredoc-still-scanned` and `fix_did_not_blind_the_rule_to_real_paths` controls |
| L-12 | **estate-sync skill** and **push-guard** | The durable, reproducible skill the owner asked for; push-guard is the mechanical fix for the recurring abandoned-work problem | C | 2026-10-31 | **CLOSED 2026-09-24** | `skills/estate-sync/SKILL.md` (audit / link / bootstrap / reconcile, carries the plaintext policy) + `scripts/push-guard.ps1`. push-guard proven by 4 controls: clean→silent, seeded unpushed commit→detected, `-FailOnFindings`→exit 1, pushed→clears. Run live on this box it found 87 modified + 77 untracked + 4 stale branches |
| L-13 | **Self-hosted Actions runner** on offload-w2025 | Repo is now private, so Actions minutes are metered. A self-hosted runner on the idle VM costs zero minutes and has no cap | C | 2026-10-31 | OPEN | |
| L-14 | **home link down — TWO LAYERS, both real.** (a) *rclone serve persistence*: `HOME-SETUP.md` step 4 told home to run `rclone serve sftp` in a FOREGROUND shell, so it died with the shell/session/machine. (b) *tailnet reachability*: home shows `offline, last seen 2h` from the VM while rclone IS listening locally on the desktop — a listening port is useless off the tailnet. Most likely cause: the desktop sleeps. **Correction to my own earlier claim:** I said the cause "isn't intermittent tailnet as the register claimed" — too strong. The register was describing layer (a)'s symptom via layer (b); both defects exist | B | 2026-10-31 | **(a) FIXED on home, (b) OPEN — blocking** | (a) home session installed task `home-link-serve` (logon-only) + Startup copy; my `platform/vm-link/install-home-service.ps1` now ADOPTS it rather than registering a rival on the same ports, and adds a boot trigger + auto-restart + port self-verification. Handoff at `platform/vm-link/HANDOFF-to-home-2026-09-24.md`. (b) needs `powercfg /change standby-timeout-ac 0` on home — owner's call, cannot be done remotely while home is off |
| L-15 | **basic-memory vault has no versioned backup** | Permission question is SETTLED — see `knowledge/policy/2026-09-24-private-estate-plaintext.md`: plaintext credentials may go in the private vault, so no review or redaction is needed first. The remaining blocker is **correctness, not permission**: the VM vault holds 717 notes, home holds 1,126, so the backup must be taken **from home**. Committing the VM's copy would plant a 409-note-poorer snapshot that a later restore would treat as authoritative | B | 2026-10-05 | OPEN (unblocked, must run on home) | 4 VM-only notes already committed at `knowledge/vault-export/2026-09-24/` |

## Academic calendar — dated, non-recoverable

| ID | Item | Date | Owner | Status |
|---|---|---|---|---|
| L-16 | Two candidate supervisors contacted (not one — a supervisor with no vacant 2027 position cannot admit him) | by Dec 2026 | O | OPEN |
| L-17 | Working relationship with one supervisor | by Feb 2027 | O | OPEN |
| L-18 | Confirm ECTS sum reaches 300 (read both diploma supplements) — if short, July 2027 is impossible and the whole track is moot | Oct 2026 | O | OPEN |
| L-19 | Ask FMI secretariat whether the 2027 dissertation defence precedes the SDI registration window (~1–12 July). If not, everything slips to July 2028 | Oct 2026 | O | OPEN |

## Decisions with expiry — re-examine, do not treat as settled

| ID | Decision | Taken | Re-examine by | Why it expires |
|---|---|---|---|---|
| D-01 | `skillListingBudgetFraction` kept at 0.04 for parity with home rather than the 0.01 a research lane recommended | 2026-09-23 | 2026-10-31 | The 0.01 recommendation is itself an unverified dismissal. Settle by measurement: run sessions at 0.01 with the router live and check skill discovery still works, then set the same value on BOTH machines |
| D-02 | SemEval-2027 skipped | 2026-09-24 | 2027-01-31 | Correct today because the publication list is optional and only a tie-break. Re-examine only if a supervisor wants it as joint work |
| D-04 | **Private-estate plaintext policy** — credentials may live uncensored in the private vault and be read/printed in local sessions; the boundary is egress, not existence. SSOT: `knowledge/policy/2026-09-24-private-estate-plaintext.md` | 2026-09-24 | **no expiry** | Revisit ONLY if the repo's visibility changes or the estate stops being single-owner — either event invalidates the premise. The repo-public lock in `estate-deny-guard` is what makes this safe and must never be weakened |
| D-03 | pbinfo placed in Honors rather than near the headline | 2026-09-24 | on first drafting | Costs the structural neutralisation of AI-authorship suspicion. If the disclosure approach proves weak in practice, revisit |
