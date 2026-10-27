#!/bin/bash
echo "===WSL gh token validity==="
T=$(python3 -c "import yaml;print((yaml.safe_load(open('/home/prekzursil/.config/gh/hosts.yml')) or {}).get('github.com',{}).get('oauth_token',''))" 2>/dev/null)
if [ -n "$T" ]; then
  CODE=$(curl -s -o /dev/null -m 15 -w '%{http_code}' -H "Authorization: Bearer $T" https://api.github.com/repos/Prekzursil/agent-skills-toolchain)
  echo "wsl-hosts-token repo GET -> $CODE"
  CODE2=$(curl -s -o /dev/null -m 15 -w '%{http_code}' -H "Authorization: Bearer $T" https://api.github.com/user)
  echo "wsl-hosts-token /user -> $CODE2"
else
  echo "no token in wsl gh hosts"
fi
ls -la /home/prekzursil/.netrc 2>/dev/null || echo "no .netrc"
git config --global --get credential.helper 2>/dev/null || echo "no git cred helper"
