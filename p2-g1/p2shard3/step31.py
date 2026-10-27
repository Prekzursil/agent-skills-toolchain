from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s31.sh /tmp/s31.sh && bash /tmp/s31.sh', '/tmp/s31.out', timeout=900)
print(out if out else 'FAILED')
