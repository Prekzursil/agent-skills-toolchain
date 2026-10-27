import shutil, sys
B = chr(92)
UNC = B + B + "wsl.localhost" + B + "Ubuntu" + B
src, dst = sys.argv[1], sys.argv[2]
shutil.copyfile(src, UNC + "tmp" + B + dst)
print("copied -> ", UNC + "tmp" + B + dst)
