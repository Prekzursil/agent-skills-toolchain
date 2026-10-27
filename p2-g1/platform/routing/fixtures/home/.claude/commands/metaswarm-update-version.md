# Update Metaswarm

Update metaswarm to the latest version, refresh component files, and re-detect project context.

## Usage

```text
/metaswarm-update-version
```

## Steps

### 1. Check Current Version

- Read `.metaswarm/project-profile.json` and extract `metaswarm_version`
- If the file doesn't exist, stop and tell the user:
  > No project profile found. Run `/metaswarm-setup` first to initialize metaswarm.
- Display the current version to the user

### 2. Fetch Latest Version

- Run `npm view metaswarm version` to get the latest published version
- Compare current vs. latest:
  - **If current == latest**: tell the user they're already up to date and stop
  - **If current < latest**: continue to the next step

### 3. Show What's New

- Run `npx metaswarm@latest changelog --from <current-version>` to show changes between versions
- If that fails, try `npx metaswarm@latest changelog` and filter entries after the current version
