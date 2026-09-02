# Release notes (PR-ONLY distributable)

UNSIGNED: this artifact is not signed. No owner-held signing key is present on this executor, and REL-0012 creates, uses, and rotates no key. Digest-bound in-toto/SLSA provenance is the consumer check. Publication (registry upload and marketplace signature) is out of scope under PR-ONLY.

## Consumer verification

A consumer establishes origin by running:

    python3 command-center/p2-wave/probes/REL-0012/verify.py \
      --artifact <zip> --provenance <json> \
      --build-tree <dir> --release-notes <notes>

The command must pass on the untampered zip and fail after a one-byte flip. The provenance `gitCommit` must equal `git rev-parse HEAD` in the recorded build tree.
