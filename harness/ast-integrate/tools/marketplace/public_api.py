"""Public read API that withholds embargoed detail."""
from __future__ import annotations

import json

from marketplace.disclosure import DisclosureRegistry, State


def get_json(reg: DisclosureRegistry, aid: str) -> str:
    rec = reg.get(aid)
    if rec.state is State.DISCLOSED:
        body = {
            "id": rec.id,
            "package_id": rec.package_id,
            "disclosed": True,
            "detail": rec.detail,
            "state": rec.state.value,
        }
    else:
        body = {"id": rec.id, "package_id": rec.package_id, "disclosed": False}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def list_json(reg: DisclosureRegistry) -> str:
    rows = []
    for rec in reg._items.values():
        if rec.state is State.DISCLOSED:
            rows.append(
                {
                    "id": rec.id,
                    "package_id": rec.package_id,
                    "disclosed": True,
                    "detail": rec.detail,
                    "state": rec.state.value,
                }
            )
    return json.dumps({"advisories": rows}, sort_keys=True, separators=(",", ":"))
