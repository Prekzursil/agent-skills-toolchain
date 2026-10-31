/* Template C pur pentru probleme competitive programming (fara STL).
 * Inlocuieste freopen() cu nimic daca judece foloseste stdin/stdout.
 * Aloca dinamic cu malloc/free; declarare arrayuri globale e mai rapida pentru N mare. */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUFSIZE (1 << 20)

static char buffer[BUFSIZE];
static int idx_buf = 0, size_buf = 0;

static char readCharFast() {
    if (idx_buf >= size_buf) {
        size_buf = (int)fread(buffer, 1, BUFSIZE, stdin);
        idx_buf = 0;
        if (size_buf == 0) return 0;
    }
    return buffer[idx_buf++];
}

static int readIntFast() {
    char c = readCharFast();
    while (c <= ' ' && c) c = readCharFast();
    int sign = 1;
    if (c == '-') { sign = -1; c = readCharFast(); }
    int x = 0;
    while (c > ' ') {
        x = x * 10 + (c - '0');
        c = readCharFast();
    }
    return x * sign;
}

static long long readLongFast() {
    char c = readCharFast();
    while (c <= ' ' && c) c = readCharFast();
    int sign = 1;
    if (c == '-') { sign = -1; c = readCharFast(); }
    long long x = 0;
    while (c > ' ') {
        x = x * 10 + (c - '0');
        c = readCharFast();
    }
    return x * sign;
}

int main(void) {
    /* Schimba sau elimina aceste 2 linii daca judece foloseste stdin/stdout */
    freopen("problema.in", "r", stdin);
    freopen("problema.out", "w", stdout);

    /* === Citire === */
    int N = readIntFast();
    int *a = (int *)malloc((size_t)N * sizeof(int));
    for (int i = 0; i < N; i++) a[i] = readIntFast();

    /* === Procesare === */
    long long answer = 0;
    /* ... algoritmul tau ... */

    /* === Output ===
     * Pentru output mare: foloseste un buffer manual si fwrite la sfarsit.
     *   char *out = (char *)malloc((size_t)Q * 16);
     *   int pos = 0;
     *   for (int i = 0; i < Q; i++) pos += sprintf(out + pos, "%d\n", results[i]);
     *   fwrite(out, 1, pos, stdout);
     *   free(out);
     */
    printf("%lld\n", answer);

    free(a);
    return 0;
}
