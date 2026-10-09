"""Set MinimumOSVersion in every <name>.framework/Info.plist under a directory (Flutter does it with plutil on a Mac)."""
import plistlib
import sys
from pathlib import Path

root, minimum = Path(sys.argv[1]), sys.argv[2]
for plist in sorted(root.glob("*.framework/Info.plist")):
    with open(plist, "rb") as f:
        info = plistlib.load(f)
    info["MinimumOSVersion"] = minimum
    with open(plist, "wb") as f:
        plistlib.dump(info, f)
    print("MinimumOSVersion", minimum, "->", plist.parent.name)
