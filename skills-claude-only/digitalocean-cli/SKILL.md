---
name: digitalocean-cli
description: Deploy and manage DigitalOcean resources using the doctl CLI. Use when
  the user mentions DigitalOcean, DO, droplets, doctl, or DO App Platform.
permalink: dqverify-repo-20261013/skills-claude-only/digitalocean-cli/skill
---

# DigitalOcean CLI

Deploy and manage DigitalOcean resources directly via the `doctl` CLI through the Bash tool. Replaces the DigitalOcean MCP server with native CLI calls.

## Prerequisites

Verify doctl is installed:

```bash
command -v doctl && doctl version
```

If not installed, guide the user to https://docs.digitalocean.com/reference/doctl/how-to/install/.

## Authentication

```bash
# Authenticate with API token (interactive prompt)
doctl auth init

# Verify authentication
doctl account get
```

The user needs a DigitalOcean API token from https://cloud.digitalocean.com/account/api/tokens.

## Droplets (Compute)

### List droplets

```bash
doctl compute droplet list

# With specific output format
doctl compute droplet list --format ID,Name,PublicIPv4,Status
```

### Create a droplet

```bash
doctl compute droplet create <name> \
  --region <region> \
  --size <size> \
  --image <image>

# Example: Ubuntu droplet
doctl compute droplet create my-server \
  --region nyc3 \
  --size s-1vcpu-1gb \
  --image ubuntu-22-04-x64 \
  --ssh-keys <key-id>
```

### Manage droplets

```bash
# Get droplet details
doctl compute droplet get <id>

# Delete a droplet (confirm with user first)
doctl compute droplet delete <id> --force

# List available sizes
doctl compute size list

# List available regions
doctl compute region list

# List available images
doctl compute image list --public
```

### SSH keys

```bash
# List SSH keys
doctl compute ssh-key list

# Import an SSH key
doctl compute ssh-key import <name> --public-key-file ~/.ssh/id_rsa.pub
```

## App Platform

### List apps

```bash
doctl apps list
```

### Deploy an app

```bash
# Create app from spec file
doctl apps create --spec <spec-file.yaml>

# Update an existing app
doctl apps update <app-id> --spec <spec-file.yaml>

# Get app details
doctl apps get <app-id>
```

### App logs and deployments

```bash
# View app logs
doctl apps logs <app-id>

# List deployments
doctl apps list-deployments <app-id>

# Get deployment details
doctl apps get-deployment <app-id> <deployment-id>
```

### Create a basic app spec

A minimal `.do/app.yaml` for a static site:

```yaml
name: my-app
static_sites:
  - name: web
    github:
      repo: <owner>/<repo>
      branch: main
    build_command: npm run build
    output_dir: dist
```

## Kubernetes (DOKS)

```bash
# List clusters
doctl kubernetes cluster list

# Create a cluster
doctl kubernetes cluster create <name> \
  --region <region> \
  --node-pool "name=default;size=s-2vcpu-4gb;count=3"

# Get kubeconfig
doctl kubernetes cluster kubeconfig save <cluster-id>

# List node pools
doctl kubernetes cluster node-pool list <cluster-id>
```

## Databases

```bash
# List database clusters
doctl databases list

# Create a database cluster
doctl databases create <name> \
  --engine pg \
  --region nyc3 \
  --size db-s-1vcpu-1gb \
  --num-nodes 1

# Get connection details
doctl databases connection <db-id>
```

## Domains and DNS

```bash
# List domains
doctl compute domain list

# Create a domain
doctl compute domain create <domain>

# List DNS records
doctl compute domain records list <domain>

# Create a DNS record
doctl compute domain records create <domain> \
  --record-type A \
  --record-name @ \
  --record-data <ip-address>
```

## Networking

```bash
# List load balancers
doctl compute load-balancer list

# List firewalls
doctl compute firewall list

# List floating IPs
doctl compute floating-ip list
```

## Spaces (Object Storage)

```bash
# List Spaces (requires s3cmd or AWS CLI configured for DO Spaces)
doctl compute cdn list
```

## Useful Flags

Common flags that work across most commands:

```bash
--format <fields>   # Customize output columns
--no-header         # Omit column headers
--output json       # JSON output
-t <token>          # Use a specific API token
--context <name>    # Use a named auth context
```

## Error Handling

**"Unable to authenticate"**
- Run `doctl auth init` and provide a valid API token.
- Verify the token has the required scopes.

**"Service not available in region"**
- Check available regions: `doctl compute region list`
- Some services are region-limited.

**"Rate limit exceeded"**
- DigitalOcean API has rate limits. Wait and retry.
- Use `--output json` to inspect rate limit headers.