---
description: Execute an already-approved multi-plan
---

1. Load the approved plan set; refuse if any plan lacks a stop rule.
2. Execute ready plans; hold dependents until upstream receipts exist.
3. Barrier: do not merge until every planned stream has a receipt.
