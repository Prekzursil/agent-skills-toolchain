from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s38.sh /tmp/s38.sh && bash /tmp/s38.sh', '/tmp/s38.out', timeout=300)
print(out if out else 'FAILED')
