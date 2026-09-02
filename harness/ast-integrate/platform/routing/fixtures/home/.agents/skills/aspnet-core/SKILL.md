---
name: aspnet-core
description: Build, review, refactor, or architect ASP.NET Core web applications using current official guidance for .NET web development. Use when working on Blazor Web Apps, Razor Pages, MVC, Minimal APIs, controller-based Web APIs, SignalR, gRPC, middleware, dependency injection, configuration, authentication, authorization, testing, performance, deployment, or ASP.NET Core upgrades.
---

# ASP.NET Core

## Overview

Choose the right ASP.NET Core application model, compose the host and request pipeline correctly, and implement features in the framework style Microsoft documents today.

Load the smallest set of references that fits the task. Do not load every reference by default.

## Workflow

1. Confirm the target framework, SDK, and current app model.
2. Open [references/stack-selection.md](references/stack-selection.md) first for new apps or major refactors.
3. Open [references/program-and-pipeline.md](references/program-and-pipeline.md) next for `Program.cs`, DI, configuration, middleware, routing, logging, and static assets.
4. Open exactly one primary app-model reference:
   - [references/ui-blazor.md](references/ui-blazor.md)
   - [references/ui-razor-pages.md](references/ui-razor-pages.md)
   - [references/ui-mvc.md](references/ui-mvc.md)
   - [references/apis-minimal-and-controllers.md](references/apis-minimal-and-controllers.md)
5. Add cross-cutting references only as needed:
   - [references/data-state-and-services.md](references/data-state-and-services.md)
   - [references/security-and-identity.md](references/security-and-identity.md)
   - [references/realtime-grpc-and-background-work.md](references/realtime-grpc-and-background-work.md)
   - [references/testing-performance-and-operations.md](references/testing-performance-and-operations.md)
6. Open [references/versioning-and-upgrades.md](references/versioning-and-upgrades.md) before introducing new platform APIs into an older solution or when migrating between major versions.

### Default Operating Assumptions
### Reference Guide
### Execution Notes
