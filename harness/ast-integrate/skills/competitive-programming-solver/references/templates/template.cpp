// Template C++ pentru probleme competitive programming.
// Inlocuieste freopen() cu nimic daca judece foloseste stdin/stdout (Codeforces, etc.)
// Pe pbinfo si Infoarena, pastreaza freopen cu numele fisierelor.

#include <cstdio>
#include <vector>
#include <string>
#include <algorithm>

using namespace std;

struct FastScanner {
    static const int BUFSIZE = 1 << 20;  // 1 MB buffer
    int idx, size;
    char buf[BUFSIZE];

    FastScanner() : idx(0), size(0) {}

    inline char readChar() {
        if (idx >= size) {
            size = (int)fread(buf, 1, BUFSIZE, stdin);
            idx = 0;
            if (size == 0) return 0;
        }
        return buf[idx++];
    }

    int readInt() {
        char c = readChar();
        while (c <= ' ' && c) c = readChar();
        int sign = 1;
        if (c == '-') { sign = -1; c = readChar(); }
        int x = 0;
        while (c > ' ') {
            x = x * 10 + (c - '0');
            c = readChar();
        }
        return x * sign;
    }

    long long readLong() {
        char c = readChar();
        while (c <= ' ' && c) c = readChar();
        int sign = 1;
        if (c == '-') { sign = -1; c = readChar(); }
        long long x = 0;
        while (c > ' ') {
            x = x * 10 + (c - '0');
            c = readChar();
        }
        return x * sign;
    }
};

int main() {
    // Schimba aceste 2 linii sau elimina-le complet daca judecele foloseste stdin/stdout
    freopen("problema.in", "r", stdin);
    freopen("problema.out", "w", stdout);

    FastScanner fs;

    // === Citire ===
    int N = fs.readInt();
    vector<int> a(N);
    for (int i = 0; i < N; i++) a[i] = fs.readInt();

    // === Procesare ===
    // ... aici e algoritmul tau ...
    long long answer = 0;

    // === Output (buffered pentru viteza) ===
    // Pentru output multi-linie cu multe valori, foloseste string buffer:
    //
    //   string out;
    //   out.reserve((size_t)Q * 16);
    //   char buf[32];
    //   for (int i = 0; i < Q; i++) {
    //       int len = sprintf(buf, "%d\n", results[i]);
    //       out.append(buf, buf + len);
    //   }
    //   fwrite(out.data(), 1, out.size(), stdout);
    //
    // Pentru un singur raspuns, printf simplu e bine:
    printf("%lld\n", answer);
    return 0;
}
