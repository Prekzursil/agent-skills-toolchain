#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
( cd command-center/p2-wave/probes/BLD-0057 && timeout 1200 python3 -B emit_model.py > /tmp/bld0057_emit2.txt 2>&1 )
echo "BLD-0057 emit rc=$?"
tail -6 /tmp/bld0057_emit2.txt
