# Ticket: implement live-tree-freeze

Build the live-tree-freeze workflow.

We need a workflow that freezes generated deploy copies after extract.

Proposed workflow: live-tree-freeze

Steps:
1. Record sha256 of each generated path
2. Reject later hand-edits of frozen paths

Requirements: the ticket is not done until the workflow id live-tree-freeze exists.
