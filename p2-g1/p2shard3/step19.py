from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s19.sh /tmp/s19.sh && bash /tmp/s19.sh', '/tmp/s19.out', timeout=300)
print(out if out else 'FAILED')
