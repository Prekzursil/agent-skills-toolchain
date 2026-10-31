from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s35.sh /tmp/s35.sh && bash /tmp/s35.sh', '/tmp/s35.out', timeout=300)
print(out if out else 'FAILED')
