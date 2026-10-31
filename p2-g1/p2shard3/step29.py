from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s29.sh /tmp/s29.sh && bash /tmp/s29.sh', '/tmp/s29.out', timeout=300)
print(out if out else 'FAILED')
