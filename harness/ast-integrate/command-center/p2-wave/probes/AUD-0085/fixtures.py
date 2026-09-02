"""Plant deterministic AUD-0085 control fixtures."""
from __future__ import annotations

import json

from common import (
    FX_BOM,
    FX_CORRECT,
    FX_DOUBLE,
    FX_INVALID,
    FX_PLUGIN,
    FIXTURES,
)


def ensure_fixtures() -> dict[str, str]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    double_doc = {
        "id": "AUD-0085-PLANTED-DOUBLE-DECODE",
        "cafe": "caf\u00c3\u00a9",
        "quote": "\u00e2\u20ac\u2122",
        "warn": "\u00e2\u0161\u00a0",
        "note": "Values are UTF-8 that was decoded as cp1252 and saved again.",
    }
    (FIXTURES / "double_decoded.json").write_text(
        json.dumps(double_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    correct_doc = {
        "id": "AUD-0085-PLANTED-CORRECT-UNICODE",
        "fr": "Fran\u00e7ais",
        "jp": "\u65e5\u672c\u8a9e",
        "dash": "\u2014",
        "ru": "\u041f\u0440\u0438\u0432\u0435\u0442",
        "collision": "\u00d7\u00a5",
        "dot": "\u00b7",
    }
    (FIXTURES / "correct_nonascii.json").write_text(
        json.dumps(correct_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    plugin_doc = {
        "name": "aud-0085-control",
        "version": "1.0.0",
        "description": "Fran\u00e7ais control plugin (correct Unicode)",
    }
    (FIXTURES / "plugin.json").write_text(
        json.dumps(plugin_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (FIXTURES / "utf8_bom.json").write_bytes(
        b'\xef\xbb\xbf{"id": "AUD-0085-PLANTED-BOM", "ok": true}\n'
    )
    (FIXTURES / "invalid_utf8.json").write_bytes(
        b'{"id": "AUD-0085-PLANTED-INVALID", "bad": "\xff"}\n'
    )
    return {
        "double_decoded": FX_DOUBLE,
        "correct_nonascii": FX_CORRECT,
        "plugin": FX_PLUGIN,
        "utf8_bom": FX_BOM,
        "invalid_utf8": FX_INVALID,
    }


if __name__ == "__main__":
    print(json.dumps(ensure_fixtures(), indent=2, sort_keys=True))
