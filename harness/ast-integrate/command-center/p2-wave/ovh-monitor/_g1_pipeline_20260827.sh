#!/bin/bash
set -e
echo STAGE-RSYNC; date -u
rsync -a --exclude .git --exclude node_modules --exclude __pycache__ --exclude command-center/p2-wave/ovh-monitor /mnt/c/Users/Prekzursil/source/ast-integrate/ /home/prekzursil/p2-g1/
echo RSYNC-OK
echo STAGE-SCHEMA; date -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
python3 /home/prekzursil/p2-g1/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py
echo STAGE-SCHEMA-OK
echo STAGE-MEASURE; date -u
export G1_WORKERS=6
cd /home/prekzursil/p2-g1
python3 -u command-center/p2-wave/seed-stage/g1_remeasure_all.py
echo PIPELINE-EXIT-OK
date -u
