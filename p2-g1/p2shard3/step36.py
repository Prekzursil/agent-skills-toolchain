from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s36.sh /tmp/s36.sh && bash /tmp/s36.sh', '/tmp/s36.out', timeout=300)
print(out if out else 'FAILED')
