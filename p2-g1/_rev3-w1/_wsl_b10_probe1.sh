#!/bin/bash
cd /mnt/c/Users/Prekzursil/p2-g1
timeout 180 python3 -B command-center/p2-wave/probes/BLD-0010/probe1_env_console_dst.py > /tmp/b10p1.out 2>&1
echo "WSL_EXIT=$?" >> /tmp/b10p1.out
tail -3 /tmp/b10p1.out
