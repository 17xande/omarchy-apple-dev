#!/usr/bin/env bash
# Check out NetNewsWire at the tested commit and generate the xtool adapter
# with tools/xcodeproj2xtool.py (second real project; stops at the walls below).
#
# One patch, explained: the iOS app target compiles a single Objective-C file
# (iOS/UIKit Extensions/SFSafariViewController+Extras.m, a crash guard for
# NetNewsWire issue #4857). ObjC sources do not build on Linux and the
# generator excludes them with a warning, so we drop in the same API as a
# Swift extension before generating. The bridging header is inert without it.
# Also fine: the Release -DRELEASE flag is dropped (no "#if RELEASE" in the
# tree) and the Mac app target plus all extensions are simply not generated.
#
# Usage: compat/nnw/setup.sh DIR
#   then: cd DIR/omarchy-xtool && ulimit -n 65536 && xtool dev build
#   ship: cd DIR/omarchy-xtool && APP_ICON=AppIcon ship.sh
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
dir=${1:?usage: setup.sh DIR}
NNW=8c322c287bec510a2ee0ebd0487e0481ad45ad82

git clone -q https://github.com/Ranchero-Software/NetNewsWire "$dir"
git -C "$dir" checkout -q "$NNW"

# NetNewsWire's own prebuild step (Xcode runs it as a build phase; a plain
# xtool build must run it once): expand Sources/Secrets/SecretKey.swift.gyb.
bash "$dir/buildscripts/updateSecrets.sh"

cat > "$dir/iOS/UIKit Extensions/SFSafariViewController+Extras.swift" <<'EOF'
// Linux adapter: replaces SFSafariViewController+Extras.m (ObjC sources are not
// supported by xtool/SwiftPM on Linux). Same API, no exception guard needed in Swift.
import SafariServices

extension SFSafariViewController {
	static func safeSafariViewController(_ url: URL) -> SFSafariViewController? {
		SFSafariViewController(url: url)
	}
}
EOF

# Two files (both added 2026-01) use UIKit types without importing UIKit;
# swiftc rejects that outside Xcode. Same-semantics fix: add the import.
sed -i '5i import UIKit' \
	"$dir/iOS/Settings/TimelineHeaderView.swift" \
	"$dir/iOS/Settings/TimelineCustomizerCollectionViewController.swift"

# iOS/Resources/Info.plist carries Xcode placeholders that Xcode substitutes
# from build settings ($(EXECUTABLE_NAME), $(MARKETING_VERSION), ...); xtool
# merges the plist verbatim, which would break the bundle. Substitute every
# $(VAR) with the value from the xcconfig tree; drop keys with no value (e.g.
# CFBundleExecutable - xtool writes its own).
python3 - "$dir" <<'PYEOF'
import plistlib, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
p = root / "iOS/Resources/Info.plist"
d = plistlib.load(open(p, "rb"))
vals = {}
for f in (root / "xcconfig").rglob("*.xcconfig"):
    for line in f.read_text(errors="replace").splitlines():
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line.split("//")[0])
        if m:
            vals.setdefault(m.group(1), m.group(2).strip().rstrip(";").strip())
for k, v in list(d.items()):
    if not isinstance(v, str):
        continue
    def sub(m):
        return vals.get(m.group(1), m.group(0))
    nv = re.sub(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", sub, v)
    if "$(" in nv:
        del d[k]
    elif nv != v:
        d[k] = nv
plistlib.dump(d, open(p, "wb"))
print("placeholders resolved")
PYEOF

python3 "$here/../tools/xcodeproj2xtool.py" "$dir/NetNewsWire.xcodeproj"
# Defaults printed by the generator: APP_ICON=AppIcon; xtool.yml gets
# bundleID com.ranchero.NetNewsWire.iOS and infoPath ../iOS/Resources/Info.plist.
#
# Status (2026-10-04, Xcode 27.0 SDK): with stock xtool 1.20.1 the app link
# fails on NetNewsWire's `type: .dynamic` packages (FINDINGS.md 27.3). It
# builds end to end and ship.sh passes 38/38 only with three changes that are
# not upstream yet: SDK toolset-swb.json linker extraCLIOptions
# ["-lswiftCore", "-L<sdk>/usr/lib/swift", "-all_load"], and two xtool
# PackLib patches (link each dynamic product into the app; embed each once).
# The generator excludes NetNewsWire's 7 storyboards/xibs (no ibtool on
# Linux) with a warning; the app builds but its UIKit UI cannot load.
