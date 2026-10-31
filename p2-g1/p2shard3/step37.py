from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s37.sh /tmp/s37.sh && bash /tmp/s37.sh', '/tmp/s37.out', timeout=300)
print(out if out else 'FAILED')
