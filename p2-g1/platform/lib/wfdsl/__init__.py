"""wfdsl - reference implementation for the Workflow DSL and work-unit contracts.

Schemas live in ``platform/schema/``; this package is the executable half:

* :mod:`wfdsl.schemas`      - offline schema registry + per-profile validators
* :mod:`wfdsl.expr`         - the stopping/convergence expression grammar (parse + evaluate)
* :mod:`wfdsl.semantics`    - the cross-field / referential rules JSON Schema cannot express
* :mod:`wfdsl.resolve`      - optional catalog-``defaults`` resolution
* :mod:`wfdsl.capabilities` - capability-map coverage checker
* :mod:`wfdsl.mutations`    - the both-states mutation battery
* :mod:`wfdsl.validate`     - CLI

Nothing here reaches the network: :func:`wfdsl.schemas.registry` refuses to retrieve any
URI that is not one of the local schema documents.
"""

from __future__ import annotations

__all__ = [
    "capabilities",
    "expr",
    "mutations",
    "resolve",
    "schemas",
    "semantics",
    "validate",
]

__version__ = "1.0.0"
