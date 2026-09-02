set -euo pipefail
cd /opt/p2/ast-integrate
export PYTHONDONTWRITEBYTECODE=1
python3 -B command-center/p2-wave/probes/RES-0017/emit.py
python3 -B command-center/p2-wave/probes/RES-0017/write_receipts.py
python3 -B command-center/p2-wave/_measure_one_delivered.py RES-0017
