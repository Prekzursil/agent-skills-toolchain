#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"

if ! grep -q '.local/bin' "$HOME/.profile" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
  echo "[+] added ~/.local/bin to ~/.profile"
else
  echo "[=] ~/.local/bin already in ~/.profile"
fi
echo

echo "=== serve --help ==="
claude-science serve --help 2>&1 | head -45
echo

echo "=== socat status ==="
if command -v socat >/dev/null 2>&1; then
  echo "socat: present ($(socat -V 2>/dev/null | head -1))"
else
  echo "socat: MISSING — sandbox needs it; requires: sudo apt-get install -y socat"
fi
