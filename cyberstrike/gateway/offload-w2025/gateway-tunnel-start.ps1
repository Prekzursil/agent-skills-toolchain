# Reverse-tunnels the cyberstrike gateway (127.0.0.1:31100) to offload-linux
# so PentAGI sandbox workers reach it via 172.17.0.1:31100 (socat bridge there).
$ssh = (Get-Command ssh).Source
while ($true) {
  & $ssh -N -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -R 127.0.0.1:31100:127.0.0.1:31100 offload-linux 2>$null
  Start-Sleep -Seconds 10
}
