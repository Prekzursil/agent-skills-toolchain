"""Read files from the WSL mirror over UNC (forward-slash form)."""
import sys

UNC = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"

def wpath(rel):
    return UNC + "/" + rel

def read_bytes(rel):
    return open(wpath(rel), "rb").read()

if __name__ == "__main__":
    data = read_bytes(sys.argv[1])
    sys.stdout.buffer.write(data)
