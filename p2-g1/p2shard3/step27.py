from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s27.sh /tmp/s27.sh && bash /tmp/s27.sh', '/tmp/s27.out', timeout=3600)
print(out if out else 'FAILED')
