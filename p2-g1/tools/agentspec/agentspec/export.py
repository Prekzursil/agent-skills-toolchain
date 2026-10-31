"""Export a workflow JSON; refuse credential-shaped literals."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentspec.violations import PARAM_CREDENTIAL_LITERAL

_CRED_RE = re.compile(
    r"(ghp_|github_pat_|sk-|xox[baprs]-|AKIA|BEGIN [A-Z ]*PRIVATE KEY)",
    re.I,
)


class ExportRefused(RuntimeError):
    def __init__(self, ids: list[str], message: str = "") -> None:
        self.ids = list(ids)
        super().__init__(message or ",".join(self.ids))


def set_credential_pattern(pattern) -> None:
    global _CRED_RE
    if isinstance(pattern, re.Pattern):
        _CRED_RE = pattern
    else:
        _CRED_RE = re.compile(str(pattern))


def export_workflow(workflow: Any, dest: str | Path) -> Path:
    dest = Path(dest)
    ids: list[str] = []
    params_out = []
    for p in getattr(workflow, "params", ()) or ():
        default = getattr(p, "default", None)
        secret = getattr(p, "secret_ref", None)
        if default and _CRED_RE.search(str(default)):
            ids.append(PARAM_CREDENTIAL_LITERAL)
        if secret is not None:
            params_out.append(
                {
                    "id": p.id,
                    "kind": "secret_ref",
                    "required": bool(getattr(p, "required", False)),
                    "ref": {
                        "source": getattr(secret, "source", "env"),
                        "name": getattr(secret, "name", ""),
                    },
                }
            )
        else:
            row = {
                "id": p.id,
                "kind": getattr(p, "kind", "string"),
                "required": bool(getattr(p, "required", False)),
            }
            if default is not None:
                row["default"] = default
            params_out.append(row)
    if ids:
        raise ExportRefused(ids)
    doc = {
        "id": getattr(workflow, "id", ""),
        "spec_version": getattr(workflow, "spec_version", "1"),
        "params": params_out,
        "units": [{"id": u} if isinstance(u, str) else {"id": getattr(u, "id", str(u))} for u in getattr(workflow, "units", ())],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return dest
