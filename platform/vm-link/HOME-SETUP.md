HOME-PC SIDE SETUP  (desktop-a60s9gp, 100.97.16.36)
Generated on offload-w2025, 2026-09-23 20:37

The VM (offload-w2025, 100.117.115.55) is on the tailnet and already serving its
C: on :2022 and D: on :2023, key auth, tailnet-bound. Do the mirror on home.

0. Bring Tailscale online on this PC (it shows offline). Confirm: tailscale status
   lists offload-w2025 at 100.117.115.55.

1. Install tools:
   rclone : https://downloads.rclone.org/rclone-current-windows-amd64.zip  (unzip rclone.exe to a PATH dir)
   WinFsp : latest .msi from https://github.com/winfsp/winfsp/releases

2. Generate a HOME mount key (empty passphrase). In PowerShell 7 use an arg array,
   NOT -N '""' (that sets a literal passphrase):
     $a=@('-t','ed25519','-f',"$HOME\.ssh\home_to_vm",'-N','','-C','home_to_vm')
     & ssh-keygen @a
   Send the .pub line back so the VM can authorize it:  ~\.ssh\home_to_vm.pub

3. Authorize the VM to mount THIS PC. Put this line in ~\.ssh\authorized_keys :
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPPT/1i2hUeJVZY/NckSV17211haev8bbdYclV46lZ16 vm_to_home@offload-w2025

4. Serve home disks, tailnet-bound (mirror of the VM). Host key with empty passphrase:
     $a=@('-t','ed25519','-f','C:\ProgramData\vm-link\host_ed25519','-N','','-C','home-hostkey'); & ssh-keygen @a
   Then two servers bound to 100.97.16.36 only (never 0.0.0.0):
     rclone serve sftp C:\ --addr 100.97.16.36:2022 --user link --authorized-keys ~\.ssh\authorized_keys --key C:\ProgramData\vm-link\host_ed25519 --vfs-cache-mode writes
     rclone serve sftp D:\ --addr 100.97.16.36:2023 --user link --authorized-keys ~\.ssh\authorized_keys --key C:\ProgramData\vm-link\host_ed25519 --vfs-cache-mode writes

5. Mount the VM's disks here as V: and W: (uses home_to_vm key):
     rclone config create vmC sftp host 100.117.115.55 port 2022 user link key_file ~\.ssh\home_to_vm
     rclone config create vmD sftp host 100.117.115.55 port 2023 user link key_file ~\.ssh\home_to_vm
     rclone mount vmC:/ V: --vfs-cache-mode writes
     rclone mount vmD:/ W: --vfs-cache-mode writes

Once step 2's pubkey is on the VM and home is serving, the VM mounts home as L: and M:.

6. MAKE IT PERSISTENT  <-- this step was missing, and is why the link kept dying.
   Step 4 above starts rclone in a FOREGROUND shell. That process dies with the
   shell, the session, or the machine. The VM has had a boot-triggered task
   (vm-link-serve) since day one; home never got one.

   Copy home-serve.cmd and install-home-service.ps1 into C:\ProgramData\vm-link\
   then, in an ELEVATED PowerShell 7:

     pwsh -File C:\ProgramData\vm-link\install-home-service.ps1

   Idempotent. Boot + logon triggers, auto-restart every minute. It self-verifies
   by checking ports 2022/2023 are listening and prints SUCCESS:home-link-persistent
   only if they are. Uninstall with -Uninstall.
