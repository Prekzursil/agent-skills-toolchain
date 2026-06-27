# Template Python pentru probleme competitive programming.
# Functioneaza pe Python 3.4+ (judecele vechi precum pbinfo folosesc 3.4).
# Pentru CodeForces / AtCoder unde aveti acces la PyPy, foloseste PyPy daca posibil.

from array import array


class FastScanner(object):
    """Citire rapida din bytes. Tinta: ~10^7 inturi pe secunda.
    Pentru date mai mari, citeste tot fisierul intr-un buffer si parseaza octet cu octet."""

    def __init__(self, data):
        self.data = data
        self.n = len(data)
        self.i = 0

    def read_int(self):
        # Hoist locals — important pentru viteza in CPython
        data = self.data
        n = self.n
        i = self.i
        while i < n and data[i] <= 32:
            i += 1
        sign = 1
        if i < n and data[i] == 45:  # '-'
            sign = -1
            i += 1
        x = 0
        while i < n and data[i] > 32:
            x = x * 10 + data[i] - 48
            i += 1
        self.i = i
        return sign * x


# === Citire: foloseste stdin SAU fisier numit dupa cum cere judece ===
# Varianta stdin (Codeforces, AtCoder, LeetCode-style):
#   fs = FastScanner(sys.stdin.buffer.read())
#
# Varianta fisiere (pbinfo, Infoarena):
fin = open("problema.in", "rb")
fs = FastScanner(fin.read())
fin.close()

# === Parse ===
N = fs.read_int()
a = array("i", [0]) * N  # 4 bytes/element, mult mai bine decat list
for i in range(N):
    a[i] = fs.read_int()

# === Procesare ===
# Sfaturi pentru bucle rapide:
# - In bucle hot, hoist atributele de obiect in variabile locale
# - Foloseste array.array sau bytearray in loc de lists pentru date numerice
# - Evita range() in cele mai interioare bucle, foloseste while cu contor manual
# - Vezi references/python-speed.md pentru trucuri mai avansate

answer = 0
# ... algoritmul tau ...

# === Output: batch in lista, .join la final ===
# Pentru un singur output:
#   fout = open("problema.out", "w"); fout.write(str(answer) + "\n"); fout.close()
#
# Pentru multi-output:
#   out = []
#   for ...: out.append(str(val))
#   fout = open("problema.out", "w"); fout.write("\n".join(out) + "\n"); fout.close()

fout = open("problema.out", "w")
fout.write(str(answer) + "\n")
fout.close()
