---
title: README
type: note
permalink: dqverify-repo-20261013/platform/marketplace/fixture/packages/dep-consumer-1.0.0/payload/readme
---

# dep-consumer 1.0.0

Depends on `hello-skill ^1.0.0`, plus one **optional** dependency that is published nowhere.

The optional dependency is not padding: it proves the distinction is real. A required dependency
that resolves to nothing REFUSES the install (`MKT-I12`); an optional one that resolves to nothing
is skipped. A resolver that treated the two identically would either break this package or admit a
missing hard requirement, and both are worse than the extra field.

Removal ordering is also proven here: `mkt remove hello-skill` while this package is installed must
be **REFUSED**, because a dependant still needs it.