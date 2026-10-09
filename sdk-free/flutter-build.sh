#!/usr/bin/env bash
# Flutter app for an iPhone without an Xcode download: Objective-C Runner, C/Objective-C plugins, release or debug.
#   sdk-free/flutter-build.sh [--debug] <flutter app dir>
#   PLUGIN_SRC="<dir> ..."   plugin source directories whose *.m files are compiled into the Runner
#   PLUGIN_LIBS="sqlite3"    system libraries those plugins link (each needs a stub in the sysroot)
# Needs: sdk-free/setup.sh done once, flutter/setup.sh done once (the iOS gen_snapshot for release builds), flutter on
# PATH, the llvm and rsync packages (flutter/README.md).
# Output: <app>/build/ios-sdkfree/<mode>/Runner.app and Runner-unsigned.ipa; sign it with tools/provision-dev.py +
# tools/sign-dev.sh, or `xtool install` for a free Apple ID.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
REPO=$(dirname "$HERE")
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
MODE=release
if [ "${1:-}" = "--debug" ]; then MODE=debug; shift; fi
APP=$(readlink -f "${1:?usage: flutter-build.sh [--debug] <flutter app dir>}")
MIN=15.0
BID=${BUNDLE_ID:-$(sed -n 's/^[[:space:]]*PRODUCT_BUNDLE_IDENTIFIER = \([^;]*\);.*/\1/p' "$APP/ios/Runner.xcodeproj/project.pbxproj" |
  grep -v RunnerTests | head -n1)}
OUT=$APP/build/ios-sdkfree/$MODE
ASM=$OUT/assemble
ACTOOL=${SDKFREE_ACTOOL:-$SDKFREE_HOME/bin/actool}
CLANG_DIR=$(dirname "$(readlink -f "$(command -v swift)")")
PLUGIN_SRC=${PLUGIN_SRC:-}
PLUGIN_LIBS=${PLUGIN_LIBS:-}

[ -d "$SR" ] || { echo "no sysroot at $SR: run $HERE/setup.sh first" >&2; exit 1; }
for t in flutter python3 zip rsync; do command -v "$t" >/dev/null || { echo "missing: $t" >&2; exit 1; }; done
FLUTTER_ROOT=$(dirname "$(dirname "$(readlink -f "$(command -v flutter)")")")
if [ "$MODE" = release ]; then
  file -b "$FLUTTER_ROOT/bin/cache/artifacts/engine/ios-release/gen_snapshot_arm64" 2>/dev/null | grep -q ELF ||
    { echo "Flutter's iOS gen_snapshot is not the Linux build: run $REPO/flutter/setup.sh" >&2; exit 1; }
fi
[ -n "$BID" ] || { echo "no bundle id found; set BUNDLE_ID" >&2; exit 1; }

mkdir -p "$OUT/obj" "$OUT/inc" "$OUT/sbc" "$OUT/icons" "$ASM"
export PATH="$HERE/shims:$CLANG_DIR:$PATH" SDKFREE_HOME NOSDK_SYSROOT=$SR XCRUN_SHIM_LOG=$OUT/shims.log
unset SDKROOT

echo "== 1. flutter assemble ($MODE)"
track=false; [ "$MODE" = debug ] && track=true
(cd "$APP" && flutter pub get >/dev/null && flutter assemble --no-version-check --output="$ASM" \
  -dTargetPlatform=ios -dTargetFile=lib/main.dart -dBuildMode="$MODE" -dIosArchs=arm64 -dSdkRoot="$SR" \
  -dTrackWidgetCreation="$track" -dCodesignIdentity=- "${MODE}_ios_bundle_flutter_assets") >"$OUT/assemble.log" 2>&1 ||
  { tail -n 30 "$OUT/assemble.log" >&2; exit 1; }

echo "== 2. Objective-C Runner and plugins"
cp "$APP/ios/Runner/GeneratedPluginRegistrant.h" "$APP/ios/Runner/GeneratedPluginRegistrant.m" "$OUT/inc/"
incs=(-I"$OUT/inc" -I"$HERE/runner")
for d in $PLUGIN_SRC; do
  incs+=(-I"$d"); [ -d "$d/include" ] && incs+=(-I"$d/include")
  name=$(basename "$d")
  mkdir -p "$OUT/inc/$name"
  for pub in "$d"/include/"$name"/*Public.h; do
    [ -f "$pub" ] && printf '#import "%s"\n' "$pub" >"$OUT/inc/$name/$(basename "$pub" Public.h).h"
  done
done
compile() { NOSDK_MIN=$MIN FLUTTER_FW_DIR=$ASM "$HERE/cc.sh" -g -O0 "$@"; }
for f in "$HERE/runner/main.m" "$HERE/runner/AppDelegate.m" "$HERE/runner/SceneDelegate.m" "$OUT/inc/GeneratedPluginRegistrant.m"; do
  compile -Wall -Wno-unused-variable -Wno-deprecated -c "${incs[@]}" "$f" -o "$OUT/obj/$(basename "$f" .m).o"
done
for d in $PLUGIN_SRC; do
  for f in "$d"/*.m; do
    compile -w -include Foundation/Foundation.h -c "${incs[@]}" "$f" -o "$OUT/obj/plugin-$(basename "$f" .m).o"
  done
done

echo "== 3. link"
libs=(); for l in $PLUGIN_LIBS; do libs+=(-l"$l"); done
"$SDKFREE_HOME/toolset/ld64.lld" -arch arm64 -platform_version ios "$MIN" 26.0 -syslibroot "$SR" \
  -F"$ASM" -F"$SR/System/Library/Frameworks" -L"$SR/usr/lib" \
  -lSystem -lobjc "${libs[@]}" -framework Flutter -framework UIKit -framework Foundation \
  -rpath @executable_path/Frameworks -ObjC -o "$OUT/Runner" "$OUT"/obj/*.o 2>&1 |
  grep -v "does not support linking for platform iOS" || true
[ -s "$OUT/Runner" ] || { echo "link failed" >&2; exit 1; }

echo "== 4. icons, storyboards, Info.plist"
PATH="$CLANG_DIR:$PATH" "$ACTOOL" "$APP/ios/Runner/Assets.xcassets" --compile "$OUT/icons" --platform iphoneos \
  --app-icon AppIcon --minimum-deployment-target "$MIN" --target-device iphone --target-device ipad \
  --output-partial-info-plist "$OUT/icons/icon.plist" --output-format human-readable-text >/dev/null
BUNDLE=$OUT/Runner.app
mkdir -p "$BUNDLE/Base.lproj"
for sb in "$APP"/ios/Runner/Base.lproj/*.storyboard; do
  python3 "$REPO/tools/ibtool" --module Runner --minimum-deployment-target "$MIN" --target-device iphone \
    --target-device ipad --output-partial-info-plist "$OUT/sbc/$(basename "$sb").plist" "$sb" \
    --compilation-directory "$OUT/sbc" >/dev/null
done
python3 "$REPO/tools/ibtool" --module Runner --target-device iphone --target-device ipad \
  --link "$BUNDLE/Base.lproj" "$OUT"/sbc/*.storyboardc >/dev/null
python3 "$HERE/fixplist.py" "$APP/ios/Runner/Info.plist" "$OUT/Info.src.plist"
python3 "$REPO/flutter/tools/gen-info-plist.py" "$OUT/Info.src.plist" "$OUT/icons/icon.plist" "$BUNDLE/Info.plist" \
  "$BID" 1.0.0 1 "$MIN" "$SR" 1,2

echo "== 5. bundle and ipa"
cp "$OUT/Runner" "$BUNDLE/Runner"
cp "$OUT/icons/Assets.car" "$OUT"/icons/AppIcon*.png "$BUNDLE/"
mkdir -p "$BUNDLE/Frameworks"
cp -a "$ASM/App.framework" "$ASM/Flutter.framework" "$BUNDLE/Frameworks/"
for f in "$ASM"/native_assets/*.framework; do [ -d "$f" ] && cp -a "$f" "$BUNDLE/Frameworks/"; done
python3 "$HERE/setmin.py" "$BUNDLE/Frameworks" "$MIN" >/dev/null
cp "$APP/ios/Flutter/AppFrameworkInfo.plist" "$BUNDLE/" 2>/dev/null || true
printf 'APPL????' >"$BUNDLE/PkgInfo"
mkdir -p "$OUT/ipa/Payload"
cp -a "$BUNDLE" "$OUT/ipa/Payload/"
(cd "$OUT/ipa" && zip -qry "$OUT/Runner-unsigned.ipa" Payload)
echo "built $OUT/Runner-unsigned.ipa ($BID, $MODE, iOS $MIN+)"
