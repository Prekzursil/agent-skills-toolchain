---
description: Fan-out independent streams then barrier
---

1. Split the request into independent streams with one owner each.
2. Dispatch each stream with its own stop rule.
3. Wait on the barrier until every stream returns or times out.
4. Merge artifacts and refuse if any stream skipped its gate.
