#!/usr/bin/env bash
# Check out Mastodon for iOS at the tested commit and generate the xtool adapter
# with tools/xcodeproj2xtool.py (third real project; exercises the WidgetKit
# widget extension, share / notification-service / intents / open-in extensions
# and the Core Data model in MastodonSDK's CoreDataStack target).
#
# Two Xcode conveniences the Linux build lacks, handled here:
# 1. MetaTextKit is branch-pinned inside MastodonSDK's manifest; xtool cannot
#    resolve branch requirements (FINDINGS 24.1). The adapter checks the branch
#    out locally and points the manifest at the checkout.
# 2. MastoParse and LightChart are branch-pinned in the Xcode project itself;
#    after generating, the adapter's Package.swift lines are pinned to the
#    branch-head revisions the same way item 24.1 pins them.
# The generator does the rest: 5 embedded extensions as extra targets/products
# and xtool.yml entries, Info.plist build-setting placeholders.
#
# App icon (Mastodon ships an Icon Composer .icon; Linux actool is gaining
# .icon support separately) and Core Data momc are out of scope: the build
# stops at the momc task with the documented error.
#
# Usage: compat/mastodon/setup.sh DIR
#   then: cd DIR/omarchy-xtool && ulimit -n 65536 && xtool dev build
#   ship: cd DIR/omarchy-xtool && ship.sh
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
dir=${1:?usage: setup.sh DIR}
MAS=c52a63091abe557724a1e588149f3172466756e5

if [ -d "$dir/.git" ]; then
	cur=$(git -C "$dir" rev-parse HEAD)
	if [ "$cur" != "$MAS" ]; then
		git -C "$dir" fetch -q origin "$MAS"
		git -C "$dir" checkout -q "$MAS"
	fi
else
	git clone -q https://github.com/mastodon/mastodon-ios "$dir"
	git -C "$dir" checkout -q "$MAS"
fi
if [ -e "$dir/omarchy-xtool/Package.swift" ]; then
	echo "error: $dir/omarchy-xtool already holds an adapter; move it away to regenerate" >&2
	exit 1
fi

# 1. MetaTextKit: branch -> local checkout (icecubes' EmojiText pattern)
if [ ! -d "$dir/checkouts/MetaTextKit" ]; then
	rev=$(git ls-remote https://github.com/mastodon/MetaTextKit.git refs/heads/2.2.5-xcode16 | cut -f1)
	mkdir -p "$dir/checkouts"
	git clone -q https://github.com/mastodon/MetaTextKit "$dir/checkouts/MetaTextKit"
	git -C "$dir/checkouts/MetaTextKit" checkout -q "$rev"
fi
sed -i 's|\.package(url: "https://github.com/mastodon/MetaTextKit.git", branch: "2.2.5-xcode16")|.package(name: "MetaTextKit", path: "../checkouts/MetaTextKit")|' \
	"$dir/MastodonSDK/Package.swift"
grep -q 'path: "../checkouts/MetaTextKit"' "$dir/MastodonSDK/Package.swift"

python3 "$here/../../tools/xcodeproj2xtool.py" "$dir/Mastodon.xcodeproj"

# 2. project-declared branch requirements -> branch-head revisions
pin() { # url branch  (rewrites the generated adapter's Package.swift line)
	local r
	r=$(git ls-remote "$1" "refs/heads/$2" | cut -f1)
	sed -i "s|\.package(url: \"$1\", branch: \"$2\")|.package(url: \"$1\", revision: \"$r\")|" \
		"$dir/omarchy-xtool/Package.swift"
}
pin https://github.com/mastodon/MastoParse.git main
pin https://github.com/Bearologics/LightChart.git master
if grep -n 'branch:' "$dir/omarchy-xtool/Package.swift"; then
	echo "error: branch requirements remain in the adapter manifest" >&2
	exit 1
fi

# Core Data: the build stops here. momc is a Darwin tool with no Linux
# equivalent; record the exact error and report it as a platform wall.
#   error: Could not determine generated file paths for Core Data code
#   generation: The command `(cd .../MastodonSDK && env -i ... momc ...)`
#   (xtool's error formatter truncates the command at ~2400 chars)

# Defaults printed by the generator: APP_ICON=AppIcon; xtool.yml gets
# bundleID org.joinmastodon.app, product Mastodon, infoPath Info.plist, and
# five extensions entries.
echo "next: cd $dir/omarchy-xtool && ulimit -n 65536 && xtool dev build"

