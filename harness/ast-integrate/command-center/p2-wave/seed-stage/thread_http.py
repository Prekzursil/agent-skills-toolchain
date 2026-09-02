from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

os.chdir("/tmp")
print("THREAD-HTTP-READY", flush=True)
ThreadingHTTPServer(("0.0.0.0", 8000), SimpleHTTPRequestHandler).serve_forever()
