from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s25.sh /tmp/s25.sh && bash /tmp/s25.sh', '/tmp/s25.out', timeout=600)
print(out if out else 'FAILED')
