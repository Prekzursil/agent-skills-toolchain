---
name: winui-app
description: Bootstrap, develop, and design modern WinUI 3 desktop applications with C# and the Windows App SDK using official Microsoft guidance, WinUI Gallery patterns, Windows App SDK samples, and CommunityToolkit components. Use when creating a brand new app, preparing a machine for WinUI, reviewing, refactoring, planning, troubleshooting, environment-checking, or setting up WinUI 3 XAML, controls, navigation, windowing, theming, accessibility, responsiveness, performance, deployment, or related Windows app design and development work.
---

# WinUI App

Use this skill for WinUI 3 and Windows App SDK work that needs grounded setup guidance, app bootstrap, modern Windows UX decisions, or concrete implementation patterns.

## Required Flow

1. Classify the task as environment/setup, new-app bootstrap, design, implementation, review, or troubleshooting.
2. If the task is about preparing a machine for WinUI, auditing readiness, or creating a brand new app, start with the bundled setup-and-scaffold flow in this skill before broader design, implementation, or troubleshooting work:
   - Pick the app name when the request is for a new app.
   - Use the exact name the user gave when it is already a safe folder name.
   - If the user did not give a name, derive a short PascalCase name from the request and state what you chose.
   - Create the project in the user's current workspace unless they asked for another location.
   - Do not use `--force` unless the user explicitly asked to overwrite existing files.
   - Run the bundled WinGet configuration from the skill directory so the relative path stays exactly `config.yaml`:

```powershell
winget configure -f config.yaml --accept-configuration-agreements --disable-interactivity
```

   - Treat the configuration as intended to enable Developer Mode, install or update Visual Studio Community 2026, and install the Managed Desktop, Universal, and Windows App SDK C# components needed for WinUI development.
   - Assess the configuration result before continuing. Continue on success. If it fails, inspect the output instead of guessing. If the `winui` template is already available and the toolchain is usable, note the partial failure and continue. If prerequisites are still missing, stop and report the blocker clearly.

### Common Routes
### Environment Rules
### Reference Rules
