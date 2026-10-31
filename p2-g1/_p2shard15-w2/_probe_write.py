a = 'it\'s {"kind":"partial"}'
b = "x\n\r\n tail"
c = b"binary \r\n test"
print(len(a), len(b), len(c))
print(a)
print(repr(b))
