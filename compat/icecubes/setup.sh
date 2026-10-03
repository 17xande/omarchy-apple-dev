#!/usr/bin/env bash
# Check out IceCubesApp at the tested commit and add the xtool adapter (FINDINGS.md item 24).
# Usage: compat/icecubes/setup.sh DIR    then: cd DIR/omarchy-xtool && ulimit -n 65536 && xtool dev build
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
dir=${1:?usage: setup.sh DIR}
ICECUBES=9efcb16e720f337a401cf61c8e300dd043368282
EMOJITEXT=3b11459a19c9406176a08b0f0599b98f88113296   # Dimillian/EmojiText branch fix-ios26

git clone -q https://github.com/Dimillian/IceCubesApp "$dir"
git -C "$dir" checkout -q "$ICECUBES"
mkdir -p "$dir/omarchy-xtool/Sources/IceCubesApp"
cp "$here/Package.swift" "$dir/omarchy-xtool/Package.swift"
printf 'version: 1\nbundleID: com.example.IceCubesApp\ninfoPath: ../IceCubesApp/Info.plist\n' > "$dir/omarchy-xtool/xtool.yml"
ln -sfn ../../../IceCubesApp "$dir/omarchy-xtool/Sources/IceCubesApp/App"
ln -sfn ../../../IceCubesAppIntents "$dir/omarchy-xtool/Sources/IceCubesApp/Intents"
# xtool 1.20.1 cannot build branch-pinned dependencies: use a local checkout of the branch.
git clone -q https://github.com/Dimillian/EmojiText "$dir/omarchy-xtool/vendor/EmojiText"
git -C "$dir/omarchy-xtool/vendor/EmojiText" checkout -q "$EMOJITEXT"
sed -i 's#\.package(url: "https://github.com/Dimillian/EmojiText", branch: "fix-ios26")#.package(path: "../../omarchy-xtool/vendor/EmojiText")#' \
  "$dir/Packages/DesignSystem/Package.swift"
git -C "$dir" diff --stat
