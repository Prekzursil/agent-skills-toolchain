#!/bin/bash
set -e
apt-get install -y -qq socat 2>/dev/null | tail -1
cat > /usr/local/bin/gateway-bridge.sh << 'EOF'
#!/bin/bash
# Forward docker0 gateway (172.17.0.1) :31100 -> loopback reverse tunnel
exec socat TCP-LISTEN:31100,bind=172.17.0.1,fork,reuseaddr TCP:127.0.0.1:31100
EOF
chmod +x /usr/local/bin/gateway-bridge.sh
cat > /etc/systemd/system/gateway-bridge.service << 'EOF'
[Unit]
Description=CyberStrike gateway bridge for docker sandboxes
After=network.target docker.service
[Service]
ExecStart=/usr/local/bin/gateway-bridge.sh
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now gateway-bridge.service
sleep 2
systemctl is-active gateway-bridge.service
ss -tln | grep "172.17.0.1:31100"
