from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s23.sh /tmp/s23.sh && bash /tmp/s23.sh', '/tmp/s23.out', timeout=300)
print(out if out else 'FAILED')
