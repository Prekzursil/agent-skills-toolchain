from wslrun import wsl_bash, read_unc
# write a search script file to avoid shell mangling
script = '''#!/bin/bash
find /home/prekzursil/p2-g1 -iname "*receipt_core*" 2>/dev/null
echo ---
grep -rln "failure.classification" /home/prekzursil/p2-g1/command-center --include="*.py" 2>/dev/null | head
echo ---
grep -rln "receipt_core" /home/prekzursil/p2-g1/command-center/p2-wave --include="*.py" 2>/dev/null | head
'''
with open('find_receipt.sh', 'w', newline='\n') as f:
    f.write(script)
import subprocess
r = subprocess.run(['wsl.exe', '-d', 'Ubuntu', 'bash', '-c',
    'cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/find_receipt.sh /tmp/fr.sh && bash /tmp/fr.sh > /tmp/shard3_receipt.txt 2>&1'],
    capture_output=True, timeout=300)
print('cp rc', r.returncode, r.stderr[-200:] if r.stderr else b'')
out = read_unc('/tmp/shard3_receipt.txt')
print(out)
