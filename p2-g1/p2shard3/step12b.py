from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s12.sh /tmp/s12.sh && bash /tmp/s12.sh', '/tmp/s12.out', timeout=900)
print(out if out else 'FAILED')
