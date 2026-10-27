from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s16.sh /tmp/s16.sh && bash /tmp/s16.sh', '/tmp/s16.out', timeout=300)
print(out if out else 'FAILED')
