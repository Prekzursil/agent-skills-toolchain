#!/usr/bin/env python3
"""Pack the delivery surfaces G-1/ready_units actually read.

MUST run on the box BEFORE teardown. probes/ alone is not enough.
"""
from __future__ import annotations

from subprocess import run

CMD = r"""
set -e
rm -f /tmp/p2-delivery.tgz
cd /opt/p2/ast-integrate
tar czf /tmp/p2-delivery.tgz \
  --exclude=node_modules --exclude=__pycache__ --exclude='*.pyc' \
  command-center/receipts \
  command-center/adversarial \
  command-center/research \
  command-center/audit \
  command-center/schema \
  command-center/confirmation \
  command-center/wfa \
  command-center/synthesis \
  command-center/design \
  tools \
  platform \
  command-center/p2-wave/probes \
  command-center/READY-UNITS.json \
  command-center/UNIT-ARTIFACT-MANIFEST.json
ls -lh /tmp/p2-delivery.tgz
echo PACK-DELIVERY-OK
"""


def main() -> None:
    print("run this ON THE BOX:\n", CMD)


if __name__ == "__main__":
    main()
