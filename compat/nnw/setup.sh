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

python3 "$here/../tools/xcodeproj2xtool.py" "$dir/NetNewsWire.xcodeproj"
# Defaults printed by the generator: APP_ICON=AppIcon; xtool.yml gets
# bundleID com.ranchero.NetNewsWire.iOS and infoPath ../iOS/Resources/Info.plist.
#
# Known walls (2026-10-04, xtool 1.20.1, Xcode 27.0 SDK), in build order:
# - The generator excludes NetNewsWire's 7 storyboards/xibs (no ibtool on
#   Linux) with a warning; the app builds but its UIKit UI cannot load.
# - The build then stops in the Linux actool (AssetKit): it crashes decoding
#   grayscale colorsets written with a "white" component, e.g.
#   iOS/Resources/Assets.xcassets/fullScreenBackgroundColor.colorset
#   ("DecodingError.keyNotFound: Key 'red' not found ... components").
#   Fix belongs in AssetKit (tools/darwin-tools), not in this adapter.
# - Behind that wall (diagnostic with the colorset moved aside): every module
#   compiles, but the final app link fails - all 15 Modules/* packages declare
#   `type: .dynamic` products and SwiftBuild on Linux does not link them:
#   "ld64.lld: error: undefined symbol: $s2os6LoggerV6RSCoreE12nnwSubsystemSSvau"
#   (20 undefined symbols from RSCore/Images/others).
