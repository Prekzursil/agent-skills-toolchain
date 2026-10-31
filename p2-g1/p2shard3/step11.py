from wslrun import wsl_bash
script = '''#!/bin/bash
cd /home/prekzursil/p2-g1
echo ===GREP===
grep -rn "True was expected" command-center/p2-wave/probes/BLD-0057/ | head
echo ===BLD-0010-PROBE1===
cat command-center/p2-wave/probes/BLD-0010/probe1_env_console_dst.py
'''
open('s11.sh', 'w', newline='\n').write(script)
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s11.sh /tmp/s11.sh && bash /tmp/s11.sh', '/tmp/s11.out', timeout=600)
print(out if out else 'FAILED')
