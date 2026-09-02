# Fixture: short rollback rehearsal

## Step FB-1: Snapshot

```action
{"kind": "mkdir", "path": "$REHEARSAL/snap"}
```

```action
{"kind": "mkdir", "path": "$REHEARSAL/live"}
```

```action
{"kind": "write_text", "path": "$REHEARSAL/snap/marker.txt", "text": "SNAPSHOT-OK\n"}
```

```action
{"kind": "copy", "src": "$REHEARSAL/snap/marker.txt", "dest": "$REHEARSAL/live/marker.txt"}
```

```postcondition
{"kind": "bytes_match", "path": "$REHEARSAL/live/marker.txt", "other": "$REHEARSAL/snap/marker.txt", "scope": "rehearsal"}
```

## Step FB-2: Corrupt

```action
{"kind": "write_text", "path": "$REHEARSAL/live/marker.txt", "text": "CORRUPT\n"}
```

```postcondition
{"kind": "file_exists", "path": "$REHEARSAL/live/marker.txt", "contains": "CORRUPT", "scope": "rehearsal"}
```

## Step FB-3: Restore

```action
{"kind": "copy", "src": "$REHEARSAL/snap/marker.txt", "dest": "$REHEARSAL/live/marker.txt"}
```

```postcondition
{"kind": "bytes_match", "path": "$REHEARSAL/live/marker.txt", "other": "$REHEARSAL/snap/marker.txt", "scope": "rehearsal"}
```
