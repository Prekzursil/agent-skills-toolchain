#!/bin/bash
# usage: liveness.sh <onion>  -> prints HTTP code + first <title>
A="$1"
R=$(curl -sL -m 75 --socks5-hostname 127.0.0.1:9050 -A "Mozilla/5.0" "http://$A/" -w "\n__CODE__%{http_code}")
CODE=$(echo "$R" | grep -oE '__CODE__[0-9]+' | grep -oE '[0-9]+')
T=$(echo "$R" | tr -d '\n' | grep -oiE '<title[^>]*>[^<]{0,120}' | head -1 | sed 's/<[tT]itle[^>]*>//I')
echo "$A | HTTP ${CODE:-dead} | ${T:-no-title}"
