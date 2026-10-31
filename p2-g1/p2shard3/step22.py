from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s22.sh /tmp/s22.sh && bash /tmp/s22.sh', '/tmp/s22.out', timeout=600)
print(out if out else 'FAILED')
