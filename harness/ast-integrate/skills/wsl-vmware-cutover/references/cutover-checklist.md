# Cutover Checklist

1. Inventory source VM, source WSL distro, destination VMware VM, and staging volumes.
2. Create cold backups and name them deterministically.
3. Move bulky Oracle VirtualBox or export artifacts to `D:` first.
4. Convert or import the VMware guest and validate a first boot.
5. Expand guest disk offline if needed before restoring data.
6. Restore Linux home with explicit excludes for caches and Windows-canonical Codex stores.
7. Validate the guest before any source cleanup.
