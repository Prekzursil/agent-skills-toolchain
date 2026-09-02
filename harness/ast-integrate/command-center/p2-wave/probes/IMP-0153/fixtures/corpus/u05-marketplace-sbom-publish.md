# Requirements for marketplace-sbom-publish

The system shall invoke the marketplace-sbom-publish workflow after each measured close.
New workflow to implement: marketplace-sbom-publish

We introduce marketplace-sbom-publish as the missing capability for this lane.

Steps:
1. Pack identity, version, licence, and SBOM fields
2. Refuse .git, caches, transcripts, and credentials in the tarball
