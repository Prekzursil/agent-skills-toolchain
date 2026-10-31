import os, sys
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
print("isdir:", os.path.isdir(base))
if os.path.isdir(base):
    for e in sorted(os.listdir(base)):
        full = os.path.join(base, e)
        print(("D " if os.path.isdir(full) else "F "), e)
