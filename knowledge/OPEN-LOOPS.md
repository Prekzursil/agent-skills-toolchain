# Open loops register

Live register of unfinished work. **Nothing here may be closed silently** — an item is
closed only by writing the evidence that closed it into the Evidence column.
This file is the anti-abandonment mechanism from
`deep-thoughts/2026-09-23-harness-ossification-and-insight-decay.md` (DT-1, R2/R4).

Owner column: **O** = owner-only (I cannot do it), **C** = Claude can do it, **B** = both.
Review-by exists so a decision expires into "re-examine" rather than becoming permanent truth.

Last updated 2026-09-24.

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
| L-06 | **Two GitHub credentials exposed in a session transcript** (one fine-grained, one classic) | Rotate once current work completes. Owner handles credential lifecycle; Claude will never rotate | O | 2026-10-01 | OPEN | |

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
| L-11 | **estate-deny-guard defect** — `classify_command` splits the entire command string and tests every whitespace fragment as a candidate path, so prose inside a heredoc trips the secret-file rule on git-write commands | Blocked three legitimate operations this session. Fix: scope the scan to actual git pathspec arguments, and match credential VALUE shapes rather than an English word | C | 2026-10-15 | OPEN | |
| L-12 | **harness-sync skill** and **push-guard** designed but not built | harness-sync bootstraps a second machine from the repo; push-guard surfaces unpushed commits and stale draft PRs. push-guard is the mechanical fix for the owner's recurring abandoned-work problem | C | 2026-10-31 | OPEN | |
| L-13 | **Self-hosted Actions runner** on offload-w2025 | Repo is now private, so Actions minutes are metered. A self-hosted runner on the idle VM costs zero minutes and has no cap | C | 2026-10-31 | OPEN | |
| L-14 | **VM↔home drive letters** not mounted; home drops off the tailnet intermittently | rclone data path works, so this is presentation only. Belongs in harness-sync, not a hand-fix | C | 2026-10-31 | OPEN | |
| L-15 | **basic-memory vault has no versioned backup** — 713 notes, 2.2 MB, not in any git repo | Repo is now private, so committing them is finally safe. 3 notes contain credential-shaped values and need review first | B | 2026-10-05 | OPEN | |

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
| D-03 | pbinfo placed in Honors rather than near the headline | 2026-09-24 | on first drafting | Costs the structural neutralisation of AI-authorship suspicion. If the disclosure approach proves weak in practice, revisit |
