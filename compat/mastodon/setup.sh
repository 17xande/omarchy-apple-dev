#!/usr/bin/env bash
# Check out Mastodon for iOS at the tested commit and generate its xtool adapter.
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

python3 "$here/../../tools/xcodeproj2xtool.py" "$dir/Mastodon.xcodeproj"
echo "next: cd $dir/omarchy-xtool && ulimit -n 65536 && xtool dev build"
