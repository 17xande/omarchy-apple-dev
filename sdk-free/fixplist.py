"""Objective-C classes have no module prefix: turn "$(PRODUCT_MODULE_NAME).SceneDelegate" into "SceneDelegate"."""
import plistlib
import sys


def fix(v):
    if isinstance(v, str):
        return v.replace("$(PRODUCT_MODULE_NAME).", "")
    if isinstance(v, dict):
        return {k: fix(x) for k, x in v.items()}
    if isinstance(v, list):
        return [fix(x) for x in v]
    return v


with open(sys.argv[1], "rb") as f:
    data = plistlib.load(f)
with open(sys.argv[2], "wb") as f:
    plistlib.dump(fix(data), f)
