from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s14.sh /tmp/s14.sh && bash /tmp/s14.sh', '/tmp/s14.out', timeout=600)
print(out if out else 'FAILED')
