"""Round-1 probe 3: dump receipt_core + the sub-object defs I must populate."""
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
rec = json.load(open(os.path.join(ROOT, "platform/schema/receipt.schema.json"), encoding="utf-8"))
defs = rec["$defs"]
for k in ("receipt_core", "artifact", "probe", "evidence_item", "test_result",
          "negative_control", "reviewer", "defect", "manifest_registration",
          "downstream_consumer", "retry", "failure", "timestamps", "residual_unknown",
          "verdict", "confidence_band", "terminal_state", "sentinel", "disposition",
          "failure_classification_code", "vendor_id", "unit_id"):
    print("\n" + "=" * 22, k, "=" * 22)
    print(json.dumps(defs.get(k), indent=1)[:5200])
