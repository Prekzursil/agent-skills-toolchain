# Conflict Map

## Host stack checks

- Hyper-V enabled or detected
- VBS running
- WSL present and active
- Docker Desktop using WSL or Hyper-V
- VMware Workstation version and driver state

## Failure classes

- import succeeds, guest boot fails
- import fails before VM creation
- `vmware-vmx` crashes on launch
- `vmrun` cannot authenticate into a running guest
