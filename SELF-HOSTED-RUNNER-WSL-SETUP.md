---
title: SELF-HOSTED-RUNNER-WSL-SETUP
type: note
permalink: dqverify-repo-20261013/self-hosted-runner-wsl-setup
---

# Self-Hosted GitHub Actions Runner on WSL (Windows)

**Purpose:** Run Phase 1/Phase 2 quality.yml gates without GitHub Actions billing costs. This document covers setting up a self-hosted Linux runner on WSL (Windows Subsystem for Linux) and registering it with this repository.

## Prerequisites

- Windows 10/11 with WSL 2 enabled
- Ubuntu 22.04 LTS (or similar) installed in WSL
- Administrator access to Windows
- Git installed in WSL

## Step 1: Update WSL and Install Dependencies

In PowerShell (as Administrator):

```powershell
wsl --update
```

In WSL bash:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git python3 python3-pip python3-venv jq
```

## Step 2: Create a Dedicated User for the Runner

In WSL bash:

```bash
# Create a runner user
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG sudo github-runner

# Switch to the runner user
sudo su - github-runner
```

## Step 3: Download and Install the GitHub Actions Runner

In WSL bash (as `github-runner` user):

```bash
# Create directory for the runner
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the latest runner (check https://github.com/actions/runner/releases for version)
# As of 2026-09-24, version 2.319.0 is stable
curl -o actions-runner-linux-x64-2.319.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.319.0/actions-runner-linux-x64-2.319.0.tar.gz

# Extract
tar xzf ./actions-runner-linux-x64-2.319.0.tar.gz

# Verify integrity (optional, but recommended)
# Check the release page for the SHA256 checksum and verify

# Install dependencies
./bin/installdependencies.sh
```

## Step 4: Register the Runner

1. **Get registration token:**
   - Go to https://github.com/Prekzursil/agent-skills-toolchain/settings/actions/runners
   - Click "New self-hosted runner" → Linux
   - Copy the registration token (starts with `AQAB_...`)

2. **Register in WSL bash (as `github-runner` user):**

```bash
cd ~/actions-runner

# Run the configuration script
./config.sh

# When prompted, provide:
# - URL: https://github.com/Prekzursil/agent-skills-toolchain
# - Token: [paste the token from Step 1]
# - Runner name: wsl-ubuntu (or any descriptive name)
# - Runner group: default
# - Labels: self-hosted,linux (important for matching workflow runs-on)
# - Work directory: _work (press enter to accept default)
```

## Step 5: Run the Runner as a Service

Run the runner as a background systemd service so it auto-starts and restarts on failure.

### Option A: systemd Service (Recommended)

In WSL bash (as `root`):

```bash
sudo su -

# Create a systemd service file
cat > /etc/systemd/system/github-actions-runner.service << 'EOF'
[Unit]
Description=GitHub Actions Runner
After=network.target

[Service]
Type=simple
User=github-runner
WorkingDirectory=/home/github-runner/actions-runner
ExecStart=/home/github-runner/actions-runner/run.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable github-actions-runner
systemctl start github-actions-runner

# Verify it's running
systemctl status github-actions-runner
```

View logs:
```bash
journalctl -u github-actions-runner -f
```

### Option B: Manual Background Process

Alternatively, run directly in WSL bash (as `github-runner` user):

```bash
cd ~/actions-runner
nohup ./run.sh > runner.log 2>&1 &
```

To stop:
```bash
./run.sh stop
```

## Step 6: Verify Registration

Go to https://github.com/Prekzursil/agent-skills-toolchain/settings/actions/runners and confirm the runner appears as "Idle" with labels `self-hosted, linux`.

## Step 7: Test the Runner

Run quality.yml with the self-hosted runner via workflow_dispatch:

```bash
cd /home/user/agent-skills-toolchain

# Option 1: Use GitHub CLI
gh workflow run quality.yml -R Prekzursil/agent-skills-toolchain --ref main -f runner-type=self-hosted

# Option 2: Via GitHub web UI
# Go to Actions → quality → Run workflow → set "Runner type" to "self-hosted"
```

Watch the run at: https://github.com/Prekzursil/agent-skills-toolchain/actions/workflows/quality.yml

## Troubleshooting

### Runner doesn't appear in settings

- Check WSL bash (as `github-runner`):
  ```bash
  cd ~/actions-runner
  ./run.sh --help
  ```
- Verify network connectivity: `ping github.com`
- Check if token expired (tokens are valid for 1 hour; get a new one if needed)

### Runner shows "Offline"

- Check service status: `systemctl status github-actions-runner`
- View logs: `journalctl -u github-actions-runner -n 50`
- Verify labels include `linux`: `grep -i labels ~/actions-runner/.runner`

### Jobs timeout or hang

- WSL might need more resources; allocate more CPU/memory in `.wslconfig`:
  ```
  [wsl2]
  memory=8GB
  processors=4
  ```
- Restart WSL: `wsl --shutdown` then open a new WSL terminal

### Python/ruff/npm tools not found in job

- The runner uses the runner user's PATH; verify tools are installed globally:
  ```bash
  which python3 node npm
  pip3 list | grep ruff
  ```
- If missing, install in the runner user's environment:
  ```bash
  sudo apt install -y nodejs npm
  pip3 install ruff basedpyright
  ```

## Maintenance

### Updating the Runner

```bash
cd ~/actions-runner
./config.sh remove --unattended --token [token]
# Then follow Step 3-4 again with the new version
```

### Stopping the Runner

```bash
systemctl stop github-actions-runner
# Or: cd ~/actions-runner && ./run.sh stop
```

### Re-enabling After Stop

```bash
systemctl start github-actions-runner
# Or: cd ~/actions-runner && nohup ./run.sh > runner.log 2>&1 &
```

## Limits & Notes

- **Network:** Ensure WSL has stable internet connectivity to GitHub
- **Timeout:** Jobs default to 6 hours; can be configured per-job in workflow
- **Concurrency:** This single runner can handle one job at a time; add more runners for parallel jobs
- **Cost:** Zero GitHub Actions billing for this repo once runner is active
- **Security:** The runner has read access to this repo's contents; keep the machine secure

## Next: Run Phase 1 Quality Gates

Once verified, trigger quality.yml with self-hosted runner:

```bash
gh workflow run quality.yml -R Prekzursil/agent-skills-toolchain --ref main -f runner-type=self-hosted
```

Check status at: https://github.com/Prekzursil/agent-skills-toolchain/actions

## See Also

- [GitHub Actions: Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [WSL Documentation](https://docs.microsoft.com/en-us/windows/wsl/)
- [quality.yml workflow](../.github/workflows/quality.yml) — the gate definitions