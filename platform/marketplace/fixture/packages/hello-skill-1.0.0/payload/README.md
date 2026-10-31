---
title: README
type: note
permalink: dqverify-repo-20261013/platform/marketplace/fixture/packages/hello-skill-1.0.0/payload/readme
---

# hello-skill 1.0.0

The control package of the fixture marketplace.

It declares exactly one permission, `fs:read:packages/hello-skill/**`, which the fixture trust
policy's ceiling (`fs:read:packages/**`) subsumes. Nothing here is interesting on purpose: when a
gate refuses this package, the gate is wrong.

## Role in the proof

1. published into the fixture registry with a real Ed25519 signature
2. installed from the registry, with all thirteen gates recorded in the receipt
3. its signature and SBOM verified from the installed copy
4. revoked by the moderation board, after which the same install refuses with `MKT-I04`