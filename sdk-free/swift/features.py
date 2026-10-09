"""Print the swiftc flags a Swift standard-library module is built with, read from the Swift source tree's own CMake files,
so the flags follow the compiler release instead of a copy that goes stale.

  features.py SRC_DIR CMAKE_FILE...   -> one flag per line (-enable-experimental-feature X, -enable-upcoming-feature Y)

SRC_DIR is the swift checkout (it holds stdlib/ and utils/). CMAKE_FILE paths are relative to stdlib/.
"""
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
experimental, upcoming = [], []
for name in sys.argv[2:]:
    text = (src / "stdlib" / name).read_text()
    experimental += re.findall(r'"-enable-experimental-feature"\s+"([A-Za-z0-9]+)"', text)
    upcoming += re.findall(r'"-enable-upcoming-feature"\s+"([A-Za-z0-9]+)"', text)
for feature in dict.fromkeys(experimental):
    if feature != "Embedded":
        print("-enable-experimental-feature")
        print(feature)
for feature in dict.fromkeys(upcoming):
    print("-enable-upcoming-feature")
    print(feature)
