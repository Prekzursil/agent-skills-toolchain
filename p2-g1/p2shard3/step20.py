from wslrun import wsl_bash
import subprocess
# copy fix script into WSL then run
subprocess.run(['cp', 's20.py', 's20_copy.py'])
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s20.py /tmp/s20.py && python3 /tmp/s20.py', '/tmp/s20.out', timeout=600)
print(out if out else 'FAILED')
