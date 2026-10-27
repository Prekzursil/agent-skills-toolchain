import ctypes, os, tempfile
BS = chr(92)
PFX = BS * 2 + '?' + BS
from pathlib import Path
root = Path(tempfile.mkdtemp(prefix='nultest-'))
target = PFX + str(root / 'NUL')
GENERIC_WRITE = 0x40000000; GENERIC_READ = 0x80000000; CREATE_ALWAYS = 2; OPEN_EXISTING = 3
k32 = ctypes.windll.kernel32
h = k32.CreateFileW(target, GENERIC_WRITE, 0, None, CREATE_ALWAYS, 0, None)
if h in (-1, 0xFFFFFFFFFFFFFFFF):
    print('CREATE-FAILED err', ctypes.get_last_error())
else:
    data = b'reserved-nul-body' + b'\n'
    import ctypes as c2
    written = c2.c_ulong(0)
    k32.WriteFile(h, data, len(data), c2.byref(written), None)
    k32.CloseHandle(h)
    print('CREATE-OK wrote', written.value)
names = [e.name for e in os.scandir(root)]
print('SCANDIR:', names)
h = k32.CreateFileW(target, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
if h in (-1, 0xFFFFFFFFFFFFFFFF):
    print('READ-FAILED')
else:
    buf = ctypes.create_string_buffer(64); got = ctypes.c_ulong(0)
    k32.ReadFile(h, buf, 64, ctypes.byref(got), None)
    k32.CloseHandle(h)
    print('READ-BACK:', buf.raw[:got.value])
deep_name = 'L' * 250
deep = PFX + str(root / deep_name)
h2 = k32.CreateFileW(deep, GENERIC_WRITE, 0, None, CREATE_ALWAYS, 0, None)
print('LONGPATH-CREATE:', 'OK' if h2 not in (-1, 0xFFFFFFFFFFFFFFFF) else 'FAILED err=%d' % ctypes.get_last_error())
if h2 not in (-1, 0xFFFFFFFFFFFFFFFF): k32.CloseHandle(h2)
# plain (non-prefix) read of NUL via python open should hit the device or fail
try:
    with open(root / 'NUL', 'rb') as f:
        d = f.read(32)
    print('PLAIN-OPEN-NUL:', d[:24])
except OSError as e:
    print('PLAIN-OPEN-NUL OSError:', e)
