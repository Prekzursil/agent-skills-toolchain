---
name: docker-cli
description: Manage Docker containers, images, volumes, and networks using the Docker CLI. Use when the user mentions docker, containers, images, volumes, docker-compose, or Dockerfile.
---

# Docker CLI

Manage Docker containers, images, volumes, and networks directly via the `docker` CLI through the Bash tool. Replaces the Docker MCP server with native CLI calls.

## Prerequisites

Verify Docker is installed and the daemon is running:

```bash
command -v docker && docker info --format '{{.ServerVersion}}'
```

If Docker is not installed, guide the user to https://docs.docker.com/get-docker/.

## Container Management

### List containers

```bash
# Running containers
docker ps

# All containers (including stopped)
docker ps -a
```

### Run a container

```bash
docker run [OPTIONS] <image> [COMMAND]

# Common flags:
#   -d            Run in background (detached)
#   -p HOST:CONT  Publish port
#   -v HOST:CONT  Bind mount volume
#   --name NAME   Assign container name
#   --rm          Remove container on exit
#   -e KEY=VAL    Set environment variable
#   --network NET Join a network

# Example: Run nginx on port 8080
docker run -d -p 8080:80 --name my-nginx nginx
```

### Stop and remove containers

```bash
docker stop <container>
docker rm <container>

# Force remove a running container
docker rm -f <container>
```

### View logs

```bash
docker logs <container>

# Follow logs in real time
docker logs -f <container>

# Show last N lines
docker logs --tail 100 <container>
```

### Execute command in a running container

```bash
docker exec -it <container> <command>

# Example: Open a shell
docker exec -it <container> /bin/sh
```

## Image Management

### List images

```bash
docker images
```

### Build an image

```bash
docker build -t <name>:<tag> .

# Build with a specific Dockerfile
docker build -t <name>:<tag> -f Dockerfile.dev .

# Build with build arguments
docker build --build-arg KEY=VAL -t <name>:<tag> .
```

### Pull and push images

```bash
docker pull <image>:<tag>
docker push <image>:<tag>
```

### Remove images

```bash
docker rmi <image>

# Remove dangling images
docker image prune
```

## Docker Compose

### Start services

```bash
docker compose up

# Detached mode
docker compose up -d

# Rebuild before starting
docker compose up --build
```

### Stop services

```bash
docker compose down

# Also remove volumes
docker compose down -v
```

### View compose logs

```bash
docker compose logs

# Follow specific service
docker compose logs -f <service>
```

### Run one-off commands

```bash
docker compose exec <service> <command>
docker compose run <service> <command>
```

## Volume Management

```bash
# List volumes
docker volume ls

# Create a volume
docker volume create <name>

# Inspect a volume
docker volume inspect <name>

# Remove a volume
docker volume rm <name>
```

## Network Management

```bash
# List networks
docker network ls

# Create a network
docker network create <name>

# Connect a container to a network
docker network connect <network> <container>

# Inspect a network
docker network inspect <name>
```

## System Cleanup

**Always ask the user before running cleanup commands** -- these remove data that may be needed.

```bash
# Remove stopped containers, unused networks, dangling images, and build cache
docker system prune

# Also remove unused volumes (more aggressive)
docker system prune --volumes

# Show disk usage
docker system df
```

## Inspecting Resources

```bash
# Detailed info about any resource
docker inspect <container|image|volume|network>

# Resource stats (live CPU/memory)
docker stats
```

## Error Handling

**"Cannot connect to the Docker daemon"**
- Docker Desktop may not be running. Start it manually.
- On Linux: `sudo systemctl start docker`

**"Permission denied"**
- The user may need to be in the `docker` group: `sudo usermod -aG docker $USER`
- Or prefix commands with `sudo`

**"Port already in use"**
- Another process is using the port. Check with `netstat -tlnp | grep <port>` or choose a different host port.
