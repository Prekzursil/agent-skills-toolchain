#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
echo "===AUD-0095 emit==="
( cd command-center/p2-wave/probes/AUD-0095 && timeout 900 python3 -B emit_artifact.py > /tmp/aud0095_emit.txt 2>&1 )
echo "AUD-0095 emit rc=$?"
tail -8 /tmp/aud0095_emit.txt
echo "===AUD-0095 write_receipts==="
( cd command-center/p2-wave/probes/AUD-0095 && timeout 900 python3 -B write_receipts.py > /tmp/aud0095_wr.txt 2>&1 )
echo "AUD-0095 WR rc=$?"
tail -8 /tmp/aud0095_wr.txt
echo "===BLD-0057 emit_model==="
( cd command-center/p2-wave/probes/BLD-0057 && timeout 900 python3 -B emit_model.py > /tmp/bld0057_emit.txt 2>&1 )
echo "BLD-0057 emit rc=$?"
tail -12 /tmp/bld0057_emit.txt
