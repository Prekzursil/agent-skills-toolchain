#!/bin/bash
# usage: torch.sh "query" outfile  (Torch omega requires POST)
Q="$1"; OUT="$2"
PE=$(python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$Q")
for i in 1 2 3 4; do
  curl -sL -m 150 --socks5-hostname 127.0.0.1:9050 -A "Mozilla/5.0" -X POST \
   -d "P=$PE&DEFAULTOP=and&DB=default&FMT=query&xDB=default&xFILTERS=.~~" \
   "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion/cgi-bin/omega/omega" -o "$OUT" && [ -s "$OUT" ] && exit 0
  sleep 6
done
exit 1
