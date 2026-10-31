#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
echo "===BLD-0010 write_receipts==="
( cd command-center/p2-wave/probes/BLD-0010 && timeout 900 python3 -B write_receipts.py > /tmp/bld0010_wr.txt 2>&1 )
echo "BLD-0010 WR rc=$?"
tail -6 /tmp/bld0010_wr.txt
echo "===BLD-0037 emit==="
( cd command-center/p2-wave/probes/BLD-0037 && timeout 600 python3 -B emit.py > /tmp/bld0037_emit.txt 2>&1 )
echo "BLD-0037 emit rc=$?"
tail -4 /tmp/bld0037_emit.txt
echo "===BLD-0037 write_receipts==="
( cd command-center/p2-wave/probes/BLD-0037 && timeout 900 python3 -B write_receipts.py > /tmp/bld0037_wr.txt 2>&1 )
echo "BLD-0037 WR rc=$?"
tail -6 /tmp/bld0037_wr.txt
