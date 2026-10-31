"""``mkt`` -- the executable half of the Phase 6 marketplace.

Schemas live in ``platform/marketplace/schema/`` and are the single source of truth for
every shape; this package is the code that produces, gates and consumes them.

* :mod:`mkt.canon`       - canonical bytes, digests, atomic writes, path containment
* :mod:`mkt.crypto`      - pure-Python Ed25519 publisher signatures (no runtime dependency)
* :mod:`mkt.versions`    - semver parsing and the small range grammar
* :mod:`mkt.permissions` - permission subsumption and the excessive-permission verdict
* :mod:`mkt.schemas`     - offline schema registry + validators (no network)
* :mod:`mkt.registry`    - canonical index: load, verify, search, resolve, federate
* :mod:`mkt.sbom`        - SBOM build + bidirectional verification against the payload
* :mod:`mkt.publish`     - the publish pipeline and its blocking preconditions
* :mod:`mkt.install`     - install / update / remove / rollback, lockfile, enforcement gates
* :mod:`mkt.bundle`      - offline export / import
* :mod:`mkt.moderation`  - moderation cases, disputes, and the revocations they authorise
* :mod:`mkt.lint`        - the marketplace linter (MKT-L01..MKT-L20)
* :mod:`mkt.scaffold`    - package scaffolder
* :mod:`mkt.cli`         - the publisher CLI (``python -m mkt``)
* :mod:`mkt.mutations`   - the both-states mutation battery that proves the gates are load-bearing

Nothing in this package reaches the network. There is no HTTP transport by design: the
registry, its mirrors and its bundles are all filesystem roots, and the honest scope of
that decision is recorded in ``MARKETPLACE-BUILD.md``.
"""

from __future__ import annotations

__all__ = [
    "bundle",
    "canon",
    "cli",
    "crypto",
    "install",
    "lint",
    "moderation",
    "mutations",
    "permissions",
    "publish",
    "registry",
    "sbom",
    "scaffold",
    "schemas",
    "versions",
]

SCHEMA_VERSION = "1.0.0"
