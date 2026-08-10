---
name: netlify-deploy
description: Use when deploying a web project to Netlify via npx netlify, linking a repo, or creating preview or production Netlify deploys ; do NOT use for Vercel (use vercel-deploy), Render (use render-deploy), or Cloudflare (use cloudflare-deploy) ; returns Netlify deploy URL.
---

# Netlify Deployment Skill

Deploy web projects to Netlify using the Netlify CLI with intelligent detection of project configuration and deployment context.

## Overview

This skill automates Netlify deployments by:
- Verifying Netlify CLI authentication
- Detecting project configuration and framework
- Linking to existing sites or creating new ones
- Deploying to production or preview environments

## Prerequisites

- **Netlify CLI**: Installed via npx (no global install required)
- **Authentication**: Netlify account with active login session
- **Project**: Valid web project in current directory
- When sandboxing blocks the deployment network calls, rerun with `sandbox_permissions=require_escalated`.
- The deployment might take a few minutes. Use appropriate timeout values.

## Authentication Pattern

The skill uses the **pre-authenticated Netlify CLI** approach:

1. Check authentication status with `npx netlify status`
2. If not authenticated, guide user through `npx netlify login`
3. Fail gracefully if authentication cannot be established

Authentication uses either:
- **Browser-based OAuth** (primary): `netlify login` opens browser for authentication
- **API Key** (alternative): Set `NETLIFY_AUTH_TOKEN` environment variable

## Workflow

### 1. Verify Netlify CLI Authentication

Check if the user is logged into Netlify:

```bash
npx netlify status
```

**Expected output patterns**:
- ✅ Authenticated: Shows logged-in user email and site link status
- ❌ Not authenticated: "Not logged into any site" or authentication error

### 2. Detect Site Link Status
### 3. Link to Existing Site or Create New
### Check if project is Git-based
### If Git-based, extract remote URL
### Format: https://github.com/username/repo or git@github.com:username/repo.git
### Try to link by Git remote
### Create new site interactively
### 4. Verify Dependencies
