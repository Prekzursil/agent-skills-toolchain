#!/bin/bash
# usage: ahmia.sh "query" [outfile]
Q="$1"; OUT="$2"
TOK=$(curl -sL -m 40 -A "Mozilla/5.0" "https://ahmia.fi/" | grep -oE 'name="[a-z0-9]{4,8}" value="[a-f0-9]{4,8}"' | head -1 | sed 's/name="//;s/" value="/=/;s/"//')
curl -sL -m 60 -A "Mozilla/5.0" "https://ahmia.fi/search/?q=${Q// /+}&${TOK}" -o "${OUT:-/tmp/ahmia.html}"
grep -oE '(<h4>|<cite>|result-icon)[^<]*' "${OUT:-/tmp/ahmia.html}" | head -5 >/dev/null
