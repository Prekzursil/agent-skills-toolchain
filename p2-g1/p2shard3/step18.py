from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s18.sh /tmp/s18.sh && bash /tmp/s18.sh', '/tmp/s18.out', timeout=600)
print(out if out else 'FAILED')
