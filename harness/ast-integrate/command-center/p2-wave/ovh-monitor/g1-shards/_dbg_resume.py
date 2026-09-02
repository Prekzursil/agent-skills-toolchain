import sys
sys.path.insert(0, "/home/prekzursil/p2-g1/tools/command-center")
import resume_sha_gate as G
print("type", type(G.AutoAcceptResume))
print("val", G.AutoAcceptResume)
print("has resume", hasattr(G.AutoAcceptResume, "resume"))
