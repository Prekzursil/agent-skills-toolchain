#!/bin/bash
# Extract staged intel and build agent pack
set -x
mkdir -p /opt/agent-pack/bolt-intel /opt/intel/extracted
cp /opt/bolt-shared/* /opt/agent-pack/bolt-intel/ 2>/dev/null

# Extract bolt-core (credentials + docs) into the agent pack now
mkdir -p /opt/agent-pack/intel-core
tar xzf /opt/intel/bolt-core.tgz -C /opt/agent-pack/intel-core/ 2>/dev/null

cat > /opt/agent-pack/README-INTEL.txt << 'EOF'
=== ENGAGEMENT INTEL IN THIS SANDBOX ===
/work/bolt-intel/     curated engagement pack: SSOT_2026-09-06.md (creds: Databricks PATs, JWTs, AWS keys),
                     AUTHORIZATION.md (full force, no exclusions), ASSESSMENT-PLAN-SOTA.md, LANE-REGISTER.md,
                     INDEX.md, config.md, schema JSONs
/work/intel-core/     bolt core: credentials/, _org_tmp/, admin-crack-2026-09-19/, engagement *.md docs
/work/intel-manifest.txt  manifest of the FULL staged intel archive (12G, host-side)

The task prompt's /opt/bolt/ mount == /work/bolt-intel/ here.
For bulk material in the manifest (enum pulls 3G, GitHub source 1.2G, databricks-harvest 1.5G,
cowork research), ask the flow operator to inject specific paths into /work/on-demand/.
EOF
ls -la /opt/agent-pack/ /opt/agent-pack/intel-core/
