#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd /tmp

# 1) socat without sudo: download the .deb and extract just the binary
if ! command -v socat >/dev/null 2>&1; then
  echo "=== installing socat WITHOUT sudo (extract from .deb) ==="
  rm -f socat_*.deb
  if apt-get download socat >/tmp/apt-dl.log 2>&1; then
    DEB=$(ls -1 socat_*.deb 2>/dev/null | head -1)
    echo "downloaded: $DEB"
    rm -rf /tmp/socat-x
    dpkg-deb -x "$DEB" /tmp/socat-x
    cp /tmp/socat-x/usr/bin/socat "$HOME/.local/bin/socat"
    chmod +x "$HOME/.local/bin/socat"
    if socat -V >/dev/null 2>&1; then
      echo "socat: OK (no sudo) -> $(socat -V 2>/dev/null | head -1)"
    else
      echo "socat: extracted but a shared lib is missing:"
      ldd "$HOME/.local/bin/socat" 2>/dev/null | grep -i "not found" || true
    fi
  else
    echo "socat: apt-get download failed (stale index?) — head of log:"
    head -4 /tmp/apt-dl.log
  fi
fi
echo "socat resolved to: $(command -v socat || echo STILL-MISSING)"
echo

# 2) start the daemon headless + detached
echo "=== starting claude-science daemon (--no-browser --detached) ==="
claude-science serve --no-browser --detached 2>&1 | head -20
sleep 7
echo
echo "=== status ==="
claude-science status 2>&1 | head
echo
echo "=== LOGIN URL (paste into your Windows browser) ==="
claude-science url 2>&1 | head -5
echo
echo "=== daemon logs (tail) ==="
claude-science logs --tail 2>&1 | tail -18
