#!/bin/bash
cd /home/prekzursil/p2-g1
echo ===GREP===
grep -rn "True was expected" command-center/p2-wave/probes/BLD-0057/ | head
echo ===BLD-0010-PROBE1===
cat command-center/p2-wave/probes/BLD-0010/probe1_env_console_dst.py
