# biomni-hub data-lake layout (Databricks backend)

Default `DATA_ROOT = dbfs:/biomni-hub` (override with `BIOMNI_DBX_DATA_ROOT`).
DBFS is the Phase-1 default because SQL/UC entitlements are unavailable to the
current identity (see README). The layout is identical on a UC Volume — only
the prefix changes to `/Volumes/<catalog>/<schema>/<volume>`.

```
dbfs:/biomni-hub/
├── hub_meta.json          # control-plane store: {projects, current_project}
│                          #   backs create_project / list_projects / switch
├── inputs/                # user uploads (canonical upload_file target)
│   └── <name>             #   base64-put via Files/DBFS API
├── tasks/                 # one dir per task == A1(path=...) working dir
│   └── t_<hex>/           #   task_id
│       ├── <biomni outputs>   # figures, tables, .csv, .png, logs
│       └── ...                # list_result_files -> name+size; fetch_artifact
└── data_lake/             # Biomni's ~11GB reference data lake
                           #   NOT downloaded during provisioning.
                           #   Populated LAZILY on the first real A1 run
                           #   (A1 pulls what it needs), or pre-seeded later
                           #   for the full biomni_e1 image.
```

## Provisioned in Phase-1 (verified)
- `dbfs:/biomni-hub/`            (created)
- `dbfs:/biomni-hub/tasks/`      (created)
- `dbfs:/biomni-hub/inputs/`     (created)
- `dbfs:/biomni-hub/data_lake/`  (created, empty — the 11GB lake is deferred)
- `dbfs:/biomni-hub/hub_meta.json`  (write→read round-trip proven)

## Access pattern
- **Driver (in-cluster)** reaches these via the FUSE mount `/dbfs/biomni-hub/…`
  — this is what `A1(path=...)` writes to. `hub_setup()` `os.makedirs` the FUSE
  path so biomni file IO just works.
- **Adapter (out-of-cluster)** reaches them via the Files/DBFS REST API
  (`dbx_dbfs_put` / `dbx_dbfs_get` / `dbx_dbfs_list`, or the SDK `w.dbfs.*`),
  streaming artifact bytes in ≤1 MB base64 chunks (`fetch_artifact` loops).

## Migrating to a Unity Catalog Volume (later)
When a writable UC Volume is available:
1. `w.files.create_directory('/Volumes/<cat>/<schema>/biomni_hub/…')`
   (or `dbx_volume_mkdir`).
2. Set `BIOMNI_DBX_DATA_ROOT=/Volumes/<cat>/<schema>/biomni_hub`.
3. The adapter swaps `w.dbfs.*` for `w.files.*` on the `/Volumes/` prefix;
   the FUSE view for the driver becomes the same `/Volumes/...` path (no
   `/dbfs/` translation needed). No layout change.
```
