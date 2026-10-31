from wslrun import wsl_bash, read_unc
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s6.sh /tmp/s6.sh && bash /tmp/s6.sh',
               '/tmp/s6.out', timeout=900)
print(out if out else 'FAILED')
