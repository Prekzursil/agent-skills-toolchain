import shutil, sys
B = chr(92)
UNC = B + B + "wsl.localhost" + B + "Ubuntu" + B + "tmp" + B
import os
src_dir = r"C:\Users\Prekzursil\source\ast-integrate\_s0"
for name in os.listdir(src_dir):
    if name.endswith(".py") and name not in ("ucp.py", "wslrun.py", "syncall.py"):
        shutil.copyfile(os.path.join(src_dir, name), UNC + name)
        print("synced", name)
