#!/usr/bin/env python3
"""Generate the Swift core stdlib source set (cmake list + gyb) into $SWIFT_GEN/core and print the swiftc file list.
Source: swiftlang/swift, the tag of the installed compiler, stdlib/public/core (Apache-2.0)."""
import os
import re
import subprocess
import sys

SRC = os.environ["SWIFT_SRC"]
CORE = os.path.join(SRC, "stdlib/public/core")
GEN = os.path.join(os.environ["SWIFT_GEN"], "core")
os.makedirs(GEN, exist_ok=True)

cm = open(os.path.join(CORE, "CMakeLists.txt")).read()
# keep only the two list blocks (plain and gyb), take every EMBEDDED/NORMAL entry that names a file
names = re.findall(r"^\s*(?:EMBEDDED|NORMAL)\s+\"?([^\s\"]+\.swift(?:\.gyb)?)\"?\s*(?:#.*)?$", cm, re.M)
# SIMDVector (vector types enabled by default) and the debug-description file are appended separately
names += ["SIMDVector.swift", "SIMDIntegerConcreteOperations.swift.gyb", "SIMDFloatConcreteOperations.swift.gyb",
          "SIMDMaskConcreteOperations.swift.gyb", "SIMDVectorTypes.swift.gyb"]
names = [n for n in dict.fromkeys(names) if not n.startswith("Embedded")]

uni = os.path.join(SRC, "utils/UnicodeData")
files = []
for n in names:
    p = os.path.join(CORE, n)
    if n.endswith(".gyb"):
        out = os.path.join(GEN, n[:-4])
        cmd = [sys.executable, os.path.join(SRC, "utils/gyb.py"), "-DCMAKE_SIZEOF_VOID_P=8",
               "-DunicodeGraphemeBreakPropertyFile=" + os.path.join(uni, "GraphemeBreakProperty.txt"),
               "-DunicodeGraphemeBreakTestFile=" + os.path.join(uni, "GraphemeBreakTest.txt"),
               "--line-directive", "", "-o", out, p]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode:
            print("GYB FAIL", n, r.stderr[-400:], file=sys.stderr)
            sys.exit(1)
        files.append(out)
    else:
        if not os.path.exists(p):
            print("MISSING", n, file=sys.stderr)
            sys.exit(1)
        files.append(p)
print("\n".join(files))
