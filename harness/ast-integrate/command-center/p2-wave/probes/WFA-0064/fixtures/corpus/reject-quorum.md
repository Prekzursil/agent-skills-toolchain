# REJECT-bound review-quorum candidate

## DEFINE `orphan.reject-quorum`
orphan.reject-quorum is a workflow mechanism: a merge stage that cannot run until a named review quorum of independent reviewers has recorded PASS. Discriminating example: a single author self-ack does not satisfy the quorum; two distinct reviewer ids must vote, and the merge is refused while the vote set is short.
