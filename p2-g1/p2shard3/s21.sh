#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
echo "===cp1252 recheck==="
cd command-center/p2-wave/probes/BLD-0010 && python3 -c "
import json, runtime as R
con = R.cp1252_console()
print('pass:', con['pass'], 'static_fail_n:', len(con['static_print_literals_fail']), 'banners_ok:', con['banners_ok'], 'encoder_fires:', con['encoder_fires_on_u23f3'])
" 2>&1 | tail -3
cd /home/prekzursil/p2-g1
echo "===BLD-0010 write_receipts==="
cd command-center/p2-wave/probes/BLD-0010 && timeout 600 python3 -B write_receipts.py 2>&1 | tail -12; echo "WR-RC:$?"
