from wslrun import wsl_bash
import subprocess
subprocess.run(['cp', 's12.sh', r'\wsl.localhost\Ubuntu\tmp\s12.sh'])
out = wsl_bash('bash /tmp/s12.sh', '/tmp/s12.out', timeout=900)
print(out if out else 'FAILED')
