---
description: Quality gate before merge
---

1. Run the unit's own tests; do not substitute a parent suite.
2. Diff coverage against the files this change touched.
3. Gate: refuse merge if a touched path has no test and no explicit waiver.
