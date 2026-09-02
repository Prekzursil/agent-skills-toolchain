from pathlib import Path
import json

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
receipt = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
defs = receipt.get("$defs") or receipt.get("definitions") or {}
doc = {
    "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/TST-0025/benchmark-receipt.local.json",
    "allOf": [
        {"$ref": "#/$defs/generic_report"},
        {
            "type": "object",
            "properties": {
                "report": {
                    "required": ["kind"],
                    "properties": {"kind": {"const": "benchmark-receipt"}},
                }
            },
        },
    ],
    "$defs": defs,
}
out = REPO / "command-center/p2-wave/probes/TST-0025/benchmark-receipt.local.json"
out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print("wrote", out, "bytes", out.stat().st_size)
