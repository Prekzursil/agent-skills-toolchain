# Coverage fixture: every fence is executed or explicitly marked.

Works when run:

```bash
echo TST-0111-OK
```

Known-broken when executed (nonzero exit):

```bash
false
```

Excluded with an explicit marker in the fence info string:

```bash NOT-EXECUTABLE
sudo rm -rf / --no-preserve-root
```
