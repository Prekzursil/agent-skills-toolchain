from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s33.sh /tmp/s33.sh && bash /tmp/s33.sh', '/tmp/s33.out', timeout=600)
print(out if out else 'FAILED')
