V=/var/lib/docker/volumes/pentagi-terminal-4-data/_data
mkdir -p $V/bolt-intel
cp -r /opt/bolt-shared/* $V/bolt-intel/
cat > $V/README-INTEL.txt <<XEOF
=== ENGAGEMENT INTEL AVAILABLE IN THIS SANDBOX ===
/work/bolt-intel/            curated engagement pack (SSOT, AUTHORIZATION, ASSESSMENT-PLAN-SOTA, LANE-REGISTER, INDEX, config.md, schema JSONs)
/work/intel/                 full staged intel tree (populating, check back):
    intel/bolt/                full Bolt engagement folder (enum, pulls, lanes)
    intel/bolteu-github/       Bolt GitHub org source harvest
    intel/databricks-harvest/  Databricks harvest exports
    intel/cowork-bolt/         Bolt-relevant cowork material
    intel/cyberstrike*/        cyberstrike config + sessions
The /opt/bolt mount referenced in the task prompt maps to /work/bolt-intel/ here.
Re-list /work/intel/ periodically as folders appear when transfers complete.
XEOF
chmod -R a+rX $V/bolt-intel
ls $V/
