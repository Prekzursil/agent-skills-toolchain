from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s15.sh /tmp/s15.sh && bash /tmp/s15.sh', '/tmp/s15.out', timeout=900)
print(out if out else 'FAILED')
