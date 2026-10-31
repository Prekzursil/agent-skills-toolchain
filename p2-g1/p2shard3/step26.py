from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s26.sh /tmp/s26.sh && bash /tmp/s26.sh', '/tmp/s26.out', timeout=2400)
print(out if out else 'FAILED')
