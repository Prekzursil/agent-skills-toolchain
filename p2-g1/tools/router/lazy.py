#!/usr/bin/env python3
"""Lazy capability loader: ALWAYS-ON bodies at turn zero; LAZY bodies on select (IMP-0369)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from router.tokenizer import TOKENIZER_ID, count_tokens  # noqa: E402

MODE_LAZY = "LAZY"
MODE_EAGER = "EAGER"
KIND_BODY = "body"
TRIGGER_TURN_ZERO_ALWAYS_ON = "turn-zero-always-on"
TRIGGER_SELECT = "select"
TRIGGER_EAGER = "eager"


def _caps_from(index: Any) -> list[dict[str, Any]]:
    if isinstance(index, dict) and "capabilities" in index:
        return list(index["capabilities"])
    if isinstance(index, list):
        return list(index)
    raise TypeError("capabilities index")


def always_on_ids(caps: list[dict[str, Any]]) -> list[str]:
    return [
        str(c.get("capability_id") or c.get("id"))
        for c in caps
        if str(c.get("load_mode") or "").upper() in {"ALWAYS-ON", "ALWAYS_ON", "EAGER"}
    ]


class GatewayLoader:
    def __init__(self, caps: list[dict[str, Any]] | dict[str, Any], mode: str = MODE_LAZY) -> None:
        self.caps = _caps_from(caps)
        self.mode = mode
        self.loaded: list[str] = []
        self.payload = ""

    def _body(self, cap: dict[str, Any]) -> str:
        return str(cap.get("body") or "")

    def _inject(self, cap: dict[str, Any]) -> None:
        cid = str(cap.get("capability_id") or cap.get("id"))
        if cid in self.loaded:
            return
        self.loaded.append(cid)
        body = self._body(cap)
        if self.payload:
            self.payload += "\n"
        self.payload += body

    def turn_zero(self) -> dict[str, Any]:
        self.loaded = []
        self.payload = ""
        trace: list[dict[str, Any]] = []
        if self.mode == MODE_EAGER:
            for cap in self.caps:
                self._inject(cap)
                trace.append({"id": str(cap.get("capability_id") or cap.get("id")), "mode": "EAGER"})
        else:
            for cap in self.caps:
                if str(cap.get("load_mode") or "").upper() in {"ALWAYS-ON", "ALWAYS_ON"}:
                    self._inject(cap)
                    cid = str(cap.get("capability_id") or cap.get("id"))
                    body = self._body(cap)
                    trace.append(
                        {
                            "id": cid,
                            "capability_id": cid,
                            "kind": KIND_BODY,
                            "mode": "ALWAYS-ON",
                            "trigger": TRIGGER_TURN_ZERO_ALWAYS_ON,
                            "tokens": count_tokens(body),
                        }
                    )
        return {
            "loaded_body_ids": list(self.loaded),
            "load_trace": trace,
            "payload": self.payload,
        }

    def body_ids(self) -> list[str]:
        return list(self.loaded)

    def tokens(self) -> int:
        return count_tokens(self.payload)

    def select(self, cap_id: str) -> str:
        for cap in self.caps:
            if str(cap.get("capability_id") or cap.get("id")) == cap_id:
                self._inject(cap)
                return self.payload
        raise KeyError(cap_id)


def measure_turn_zero(caps: list[dict[str, Any]] | dict[str, Any], select_ids: list[str] | None = None) -> dict[str, Any]:
    rows = _caps_from(caps)
    always = always_on_ids(rows)
    lazy = GatewayLoader(rows, MODE_LAZY)
    eager = GatewayLoader(rows, MODE_EAGER)
    lazy.turn_zero()
    eager.turn_zero()
    lazy_tokens = count_tokens(lazy.payload)
    eager_tokens = count_tokens(eager.payload)
    after_ids = list(lazy.loaded)
    after_tokens = lazy_tokens
    if select_ids:
        for sid in select_ids:
            lazy.select(sid)
        after_ids = list(lazy.loaded)
        after_tokens = count_tokens(lazy.payload)
    accidental = [cid for cid in lazy.loaded if cid not in always and cid not in (select_ids or [])]
    all_ids = [str(c.get("capability_id") or c.get("id")) for c in rows]
    return {
        "tokenizer_id": TOKENIZER_ID,
        "index_capability_count": len(rows),
        "lazy_turn_zero_tokens": lazy_tokens,
        "eager_turn_zero_tokens": eager_tokens,
        "token_delta_eager_minus_lazy": eager_tokens - lazy_tokens,
        "lazy_cheaper": lazy_tokens < eager_tokens,
        "lazy_turn_zero_bytes": len(lazy.payload.encode("utf-8")),
        "eager_turn_zero_bytes": len(eager.payload.encode("utf-8")),
        "lazy_turn_zero_body_ids": [cid for cid in lazy.loaded if cid in always],
        "eager_turn_zero_body_ids": list(eager.loaded),
        "always_on_ids": always,
        "lazy_bodies_equal_always_on": [cid for cid in lazy.loaded if cid in always] == always
        or set(cid for cid in lazy.loaded if cid in always) == set(always),
        "eager_loaded_all_bodies": set(eager.loaded) == set(all_ids),
        "accidental_eager_ids": [c for c in accidental if c not in (select_ids or [])],
        "lazy_after_select_body_ids": after_ids,
        "lazy_after_select_tokens": after_tokens,
        "tokens": {
            "lazy": lazy_tokens,
            "eager": eager_tokens,
            "after_select": after_tokens,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--compare", action="store_true")
    p.add_argument("--select", action="append", default=[])
    args = p.parse_args(argv)
    doc = json.loads(Path(args.index).read_text(encoding="utf-8"))
    report = measure_turn_zero(doc, select_ids=list(args.select))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
