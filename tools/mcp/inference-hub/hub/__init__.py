"""inference-hub: the resident concurrent inference hub on 127.0.0.1:8901.

Stdlib-only. The registry SSOT is ``.agents/models.json``; every module here
reads it through :class:`hub.registry.Registry`. Secrets travel by environment
variable NAME only: nothing in this package writes a credential value or prompt
text to a log, a ledger row or an error message.

Core (non-HTTP) modules:

* :mod:`hub.errors`    - the 19-class tool-error taxonomy and :class:`HubError`.
* :mod:`hub.redaction` - outbound secret scanning and value-free log payloads.
* :mod:`hub.ledger`    - the daily JSONL call ledger (prompt digest, never text).
* :mod:`hub.budget`    - per-call cost estimates and the daily USD cap gate.
* :mod:`hub.registry`  - registry snapshots, model resolution, deny lists, halt.
"""

from __future__ import annotations

from hub.budget import BudgetGate, estimate_cost
from hub.errors import ERROR_CLASSES, RETRYABLE, HubError, classify_http_status
from hub.ledger import Ledger, prompt_digest, resolve_ledger_root
from hub.redaction import Finding, Redactor, redact_obj, redact_text
from hub.registry import Registry, RegistrySnapshot, ResolvedModel

__version__ = "0.1.0"

__all__ = [
    "ERROR_CLASSES",
    "RETRYABLE",
    "BudgetGate",
    "Finding",
    "HubError",
    "Ledger",
    "Redactor",
    "Registry",
    "RegistrySnapshot",
    "ResolvedModel",
    "__version__",
    "classify_http_status",
    "estimate_cost",
    "prompt_digest",
    "redact_obj",
    "redact_text",
    "resolve_ledger_root",
]
