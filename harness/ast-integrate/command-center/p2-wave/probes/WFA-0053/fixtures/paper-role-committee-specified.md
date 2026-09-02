# Role-committee protocol (local corpus fixture; not a copyrighted reprint)

The council has exactly 5 participants: a proposer, two critics, a judge, and a secretary.

Turn structure is sequential: the proposer writes first, then the two critics speak in parallel, then the judge rules; that triple is one round.

The stopping rule is: stop when the judge issues ACCEPT, or after 3 rounds, whichever comes first (ACCEPT OR rounds>=3).

Scoring is exact-match accuracy against the gold label on the GSM8K test set.

Conflicts of interest: the judge never sees which critic wrote which objection.

Information partitioning: critics do not see each other's drafts until the round barrier.

Role mandates: the proposer may only propose; critics may only object or abstain; the judge may only accept or reject.

Nested subcouncil: none; this protocol is a single council, not a council-of-councils.

Deliberation protocol: round 1 is a premortem; later rounds are standard debate.

Speaking quotas: each critic may speak at most 200 words per round.

Minimum engagement: each critic must produce at least one objection or an explicit abstention each round.

Voting and belief aggregation: the judge decides; critics may abstain; quorum is both critics having spoken; there is no delegation.
