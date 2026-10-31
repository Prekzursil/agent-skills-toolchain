#!/bin/bash
cd ~/p2-g1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="platform/lib:$PYTHONPATH"
python3 -B platform/lib/receipt_schema_gate.py \
  command-center/receipts/AUD-0044.json command-center/receipts/AUD-0047.json \
  command-center/receipts/AUD-0053.json command-center/receipts/AUD-0055.json \
  command-center/receipts/AUD-0057.json command-center/receipts/AUD-0064.json \
  command-center/receipts/AUD-0066.json command-center/receipts/AUD-0069.json \
  command-center/receipts/AUD-0071.json command-center/receipts/AUD-0072.json \
  command-center/receipts/AUD-0075.json command-center/receipts/AUD-0080.json \
  --repo-root . 2>&1
echo "GATE-RC=$?"
