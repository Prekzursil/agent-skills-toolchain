# Metaswarm Guided Setup

Interactive, Claude-guided setup for metaswarm in your project. Detects your stack, asks targeted questions, and customizes everything automatically.

## Usage

```text
/metaswarm-setup
```

---

## Phase 1: Bootstrap Check

Before anything else, verify that metaswarm components are installed.

### Step 1.1 — Check for plugin directory

Use the Glob tool to check if `.claude/plugins/metaswarm/` exists:

```
Glob: .claude/plugins/metaswarm/**/*
```

- If files are found, metaswarm components are installed. Proceed to Step 1.2.
- If NO files are found, tell the user: "Metaswarm components aren't installed yet. Let me install them now." Then run via Bash:

```bash
npx metaswarm install
```

Wait for the command to complete. If it fails, tell the user to check their Node.js installation and try `npm install -g metaswarm` manually.

### Step 1.2 — Check for existing project profile
