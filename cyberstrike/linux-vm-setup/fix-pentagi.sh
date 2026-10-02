#!/bin/bash
set -e
cd /opt/pentagi
# 1. Switch worker images to kali
sed -i 's|^DOCKER_DEFAULT_IMAGE=.*|DOCKER_DEFAULT_IMAGE=vxcontrol/kali-linux:latest|' .env
sed -i 's|^DOCKER_DEFAULT_IMAGE_FOR_PENTEST=.*|DOCKER_DEFAULT_IMAGE_FOR_PENTEST=vxcontrol/kali-linux:latest|' .env
# 2. extra_hosts for embeddings (host.docker.internal -> docker0)
grep -q "extra_hosts" docker-compose.yml || sed -i '/^  pentagi:/a\    extra_hosts:\n      - "host.docker.internal:172.17.0.1"' docker-compose.yml
grep -E "^DOCKER_DEFAULT_IMAGE" .env
grep -A2 "extra_hosts" docker-compose.yml | head -3
# 3. Recreate
docker compose up -d --force-recreate pentagi 2>&1 | tail -2
