from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s13.sh /tmp/s13.sh && bash /tmp/s13.sh', '/tmp/s13.out', timeout=900)
print(out if out else 'FAILED')
