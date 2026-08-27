# Mechanism Selection

## Use `rsync`

- source and target are directory trees
- excludes must reduce what is copied
- resumability matters
- metadata preservation matters

## Use tar

- a single archive artifact is the goal
- the receiver expects a tarball
- post-copy extraction is acceptable

## Use `robocopy`

- both ends are Windows-visible paths
- restartable copy matters more than POSIX metadata
- you need mirror or retry controls

## Use offline attach

- target is a guest disk image or offline block device
- booting the guest is unnecessary or unsafe
- filesystem surgery and direct placement beat guest-side copy
