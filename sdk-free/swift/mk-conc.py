#!/usr/bin/env python3
"""Source list for the _Concurrency module (Swift files named in stdlib/public/Concurrency/CMakeLists.txt + gyb) -> conc-files.txt."""
import os
import re
import subprocess
import sys

SRC = os.environ["SWIFT_SRC"]
C = os.path.join(SRC, "stdlib/public/Concurrency")
GEN = os.path.join(os.environ["SWIFT_GEN"], "conc")
os.makedirs(GEN, exist_ok=True)
with open(os.path.join(C, "CMakeLists.txt")) as f:
    cm = f.read()
names = list(dict.fromkeys(re.findall(r"^\s*([A-Za-z0-9_+/]+\.swift(?:\.gyb)?)\s*(?:#.*)?$", cm, re.MULTILINE)))
skip = ("Embedded", "PlatformExecutorCooperative", "PlatformExecutorNone", "PlatformExecutorLinux", "PlatformExecutorWindows", "PlatformExecutorFreeBSD", "PlatformExecutorOpenBSD", "PlatformExecutorAndroid")
files = []
for n in names:
    if n.startswith(skip):
        continue
    p = os.path.join(C, n)
    if not os.path.exists(p):
        print("missing", n, file=sys.stderr)
        continue
    if n.endswith(".gyb"):
        out = os.path.join(GEN, n[:-4])
        r = subprocess.run([sys.executable, os.path.join(SRC, "utils/gyb.py"), "-DCMAKE_SIZEOF_VOID_P=8", "--line-directive", "", "-o", out, p],
                           capture_output=True, text=True, check=False)
        if r.returncode:
            print("gyb fail", n, r.stderr[-300:], file=sys.stderr)
            sys.exit(1)
        files.append(out)
    else:
        files.append(p)
print("\n".join(files))
