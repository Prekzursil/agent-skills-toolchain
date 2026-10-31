# Owner question packet

Format: one foundation-level question per entry (spec 11364-11370).
A compound question is not shippable. A missing default is not shippable.
Answers belong in OWNER-DECISIONS.md and are never re-asked.

- generated_at: 2026-08-28T02:17:57Z
- source_path: command-center/receipts/CNF-0160.json
- source_status: PRESENT
- open_entry_count: 1

## Entry: C-IRRED-SPLIT-007

- question: When vendor triangulation leaves C-IRRED-SPLIT-007 unresolved, should the claim close as AMBIGUOUS-CLAIM rather than take a majority or casting vote
- recommendation: Close C-IRRED-SPLIT-007 as AMBIGUOUS-CLAIM. Do not treat any vendor as a casting vote on C-IRRED-SPLIT-007
- strongest_tradeoff: A majority or casting vote would manufacture a verdict the triangulation rule forbids; leaving the claim open blocks every consumer that requires a terminal status
- default_if_unanswered: Close as AMBIGUOUS-CLAIM; do not count the claim as CONFIRMED or REFUTED
- impact: Downstream confirmation rates must keep this id out of both the CONFIRMED and REFUTED denominators until an owner answer or a re-run of the named settling experiment changes the row
- command: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0161/settle_claim.py --claim C-IRRED-SPLIT-007
- expected_observation: The three recorded vendor verdicts pairwise differ, or the CNF-0160 row still carries an unresolved status.
- discriminating_outcome: Pairwise-distinct verdicts => keep AMBIGUOUS-CLAIM; any two agreeing => the claim is no longer owner-escalation material.
- cost: one local process, under 30s, no vendor rail, no credential
- question_fingerprint: e673d72c4cdc4375
