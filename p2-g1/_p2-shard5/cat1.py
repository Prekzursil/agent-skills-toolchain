import os, sys
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
for rel in sys.argv[1:]:
    p = os.path.join(base, rel)
    print("======== " + rel + " ========")
    try:
        with open(p, "rb") as f:
            data = f.read()
        print("bytes:", len(data))
        sys.stdout.write(data.decode("utf-8", errors="replace"))
        print()
    except Exception as e:
        print("ERR:", e)
