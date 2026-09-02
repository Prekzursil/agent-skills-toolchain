---
description: Start a bounded agent loop
---

1. Declare max iterations and the convergence predicate.
2. Run one iteration; record the observation that feeds the predicate.
3. Stop when the predicate holds or max iterations is reached; never spin open-ended.
