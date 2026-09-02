# Planted-command detector control.

A Python fence is mention, not a documented shell command:

```python
print("echo TST-0111-PLANTED-FENCE")
```

The extractor must find this bash fence (unique token):

```bash
echo TST-0111-PLANTED-FENCE
```

A second shell fence so the hand-count is not one:

```sh
true
```
