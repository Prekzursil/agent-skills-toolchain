#!/bin/bash
set -x
# 1. Extract remaining intel archives
cd /opt/intel
for a in bolt-enum bolteu-github-src databricks-harvest cowork-curated cyberstrike+misc; do
  [ -f "$a.tgz" ] && mkdir -p "extracted/$a" && tar xzf "$a.tgz" -C "extracted/$a" 2>/dev/null &
done
wait

# 2. Build manifest
{ echo "=== FULL STAGED INTEL (host-side /opt/intel/extracted/) ==="; 
  du -sh /opt/intel/extracted/*/* 2>/dev/null; } > /opt/agent-pack/intel-manifest.txt

# 3. Watcher: inject agent-pack into every new pentagi-terminal volume
cat > /usr/local/bin/pentagi-intel-watch.sh << 'EOF'
#!/bin/bash
# Injects /opt/agent-pack into every pentagi-terminal-* work volume once.
while true; do
  for vol in /var/lib/docker/volumes/pentagi-terminal-*-data/_data; do
    [ -d "$vol" ] || continue
    [ -f "$vol/.agent-pack-marker" ] && continue
    cp -r /opt/agent-pack/. "$vol/" 2>/dev/null
    chmod -R a+rX "$vol" 2>/dev/null
    touch "$vol/.agent-pack-marker"
    logger -t pentagi-intel-watch "injected agent-pack into $vol"
  done
  sleep 5
done
EOF
chmod +x /usr/local/bin/pentagi-intel-watch.sh

cat > /etc/systemd/system/pentagi-intel-watch.service << 'EOF'
[Unit]
Description=PentAGI work-volume intel injector
After=docker.service
[Service]
ExecStart=/usr/local/bin/pentagi-intel-watch.sh
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now pentagi-intel-watch.service
sleep 6
systemctl is-active pentagi-intel-watch.service
