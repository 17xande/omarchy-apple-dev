#!/usr/bin/env bash
# Mode "no Xcode download": build the link-and-header sysroot from your own iPhone, no Xcode.xip anywhere.
#
#   sdk-free/setup.sh          needs the iPhone connected, unlocked, paired, Developer Mode on (sudo for the USB tunnel)
#
# Result under $SDKFREE_HOME (default ~/.local/share/omarchy-apple-dev/sdk-free):
#   iPhoneOS.sdk/   link stubs (.tbd) cut from the shared cache of the connected iPhone, public Objective-C runtime
#                   headers, and the headers this repo ships in sdk-free/headers
#   toolset/        ld64.lld and dsymutil (xtool-org/darwin-tools-linux-llvm, pinned)
#   bin/actool      asset catalog compiler (built from tools/darwin-tools)
# Safe to re-run: finished pieces are skipped.
#
# Test and CI hooks: SDKFREE_TBD_DIR=<dir with ready-made .tbd files> skips the iPhone; SDKFREE_ACTOOL=<path> skips
# the actool build.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
REPO=$(dirname "$HERE")
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
VENV=${VENV:-$HOME/pymobile3-venv}
PMD3=$VENV/bin/pymobiledevice3
IPSW=$HOME/.local/bin/ipsw
mkdir -p "$SDKFREE_HOME"

# Images whose link stubs the sysroot carries (install name -> stub file).
IMAGES="/usr/lib/libSystem.B.dylib /usr/lib/libobjc.A.dylib /usr/lib/libc++.1.dylib /usr/lib/libc++abi.dylib
/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation
/System/Library/Frameworks/Foundation.framework/Foundation
/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics
/System/Library/Frameworks/QuartzCore.framework/QuartzCore
/System/Library/Frameworks/UIKit.framework/UIKit
/System/Library/Frameworks/UIKitCore.framework/UIKitCore"

echo "== 1. linker toolset (ld64.lld, dsymutil)"
TOOLSET_VERSION=v1.1.0
case "$(uname -m)" in
  x86_64) ts_arch=x86_64 ts_sha=a5166f2d56ac45707e5ef2f3c20a41a94af8ef0c0456354224dd08656e874188 ;;
  aarch64) ts_arch=aarch64 ts_sha=a6fc628a1db47ff6f209d32e66aec72eb77112d3f0b1ac1fcf5f6af7f34a9d08 ;;
  *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac
if [ ! -x "$SDKFREE_HOME/toolset/ld64.lld" ]; then
  tmp=$(mktemp -d)
  curl -fsSL "https://github.com/xtool-org/darwin-tools-linux-llvm/releases/download/$TOOLSET_VERSION/toolset-$ts_arch.tar.gz" \
    -o "$tmp/toolset.tar.gz"
  echo "$ts_sha  $tmp/toolset.tar.gz" | sha256sum -c --quiet
  tar -xzf "$tmp/toolset.tar.gz" -C "$tmp"
  mkdir -p "$SDKFREE_HOME/toolset"
  install -m755 "$tmp"/bin/ld64.lld "$tmp"/bin/dsymutil "$SDKFREE_HOME/toolset/"
fi
echo "toolset in $SDKFREE_HOME/toolset"

echo "== 2. Objective-C runtime headers (public source, pinned commit)"
OBJC4_REPO=https://github.com/apple-oss-distributions/objc4
OBJC4_SHA=fb265098298302243cd7eeaa1f63f0ba7786dd9a
OBJC4=$HOME/.cache/omarchy-apple-dev/objc4-$OBJC4_SHA
if [ ! -d "$OBJC4/.git" ]; then
  git init -q "$OBJC4"
  git -C "$OBJC4" fetch -q --depth 1 "$OBJC4_REPO" "$OBJC4_SHA"
  git -C "$OBJC4" checkout -q FETCH_HEAD
fi

echo "== 3. link stubs from the iPhone"
tbd=$SDKFREE_HOME/cache/tbd
if [ -n "${SDKFREE_TBD_DIR:-}" ]; then
  tbd=$SDKFREE_TBD_DIR
elif [ ! -f "$tbd/UIKit.tbd" ]; then
  "$PMD3" lockdown info >/dev/null 2>&1 || {
    echo "No paired iPhone found. Connect it, unlock it, tap Trust, turn on Developer Mode, then run this again." >&2
    exit 1
  }
  [ -x "$IPSW" ] || { echo "ipsw is missing: run ./install-toolchain.sh first" >&2; exit 1; }
  info=$("$PMD3" lockdown info)
  dsc=$SDKFREE_HOME/cache/dsc
  if ! find "$dsc" -name dyld_shared_cache_arm64e -print -quit 2>/dev/null | grep -q .; then
    echo "Copying the shared cache from the iPhone (about 7 GB, once; it is deleted after the stubs are cut)"
    log=$(mktemp)
    sudo "$PMD3" lockdown start-tunnel >"$log" 2>&1 &
    trap 'sudo pkill -f "lockdown start-tunne[l]" || true' EXIT
    for _ in $(seq 30); do grep -q "RSD Port" "$log" && break; sleep 1; done
    host=$(grep -o "RSD Address: [^ ]*" "$log" | awk '{print $3}')
    port=$(grep -o "RSD Port: [0-9]*" "$log" | awk '{print $3}')
    [ -n "$port" ] || { cat "$log" >&2; exit 1; }
    "$PMD3" developer fetch-symbols download "$dsc" --rsd "$host" "$port"
  fi
  cache=$(find "$dsc" -name dyld_shared_cache_arm64e -print -quit)
  mkdir -p "$tbd"
  for image in $IMAGES; do
    "$IPSW" dyld tbd "$cache" "$image" -o "$tbd" >/dev/null
  done
  echo "stubs written to $tbd; the cache in $dsc can be deleted"
  printf '%s\n' "$info" >"$SDKFREE_HOME/cache/device-info.json"
fi

echo "== 4. assemble the sysroot"
mkdir -p "$SR/usr/include/objc" "$SR/usr/lib" "$SR/System/Library/Frameworks"
for h in objc.h objc-api.h NSObject.h NSObjCRuntime.h runtime.h message.h Protocol.h; do
  cp "$OBJC4/runtime/$h" "$SR/usr/include/objc/"
done
cp "$OBJC4/APPLE_LICENSE" "$SR/usr/include/objc/APPLE_LICENSE"
# ipsw writes arm64e stubs; third-party apps are arm64, which exports the same names.
cut_stub() { sed 's/\[ arm64e-ios \]/[ arm64-ios, arm64e-ios ]/g' "$1" >"$2"; }
cut_stub "$tbd/libSystem.B.dylib.tbd" "$SR/usr/lib/libSystem.tbd"
cut_stub "$tbd/libobjc.A.dylib.tbd" "$SR/usr/lib/libobjc.tbd"
cut_stub "$tbd/libc++.1.dylib.tbd" "$SR/usr/lib/libc++.tbd"
cut_stub "$tbd/libc++abi.dylib.tbd" "$SR/usr/lib/libc++abi.tbd"
for f in UIKit UIKitCore Foundation CoreFoundation CoreGraphics QuartzCore; do
  mkdir -p "$SR/System/Library/Frameworks/$f.framework"
  cut_stub "$tbd/$f.tbd" "$SR/System/Library/Frameworks/$f.framework/$f.tbd"
done
cp -R "$HERE/headers/." "$SR/"
# Flutter reads the platform and build from the SDK directory
if [ -f "$SDKFREE_HOME/cache/device-info.json" ]; then
  python3 - "$SDKFREE_HOME/cache/device-info.json" "$SR/System/Library/CoreServices/SystemVersion.plist" <<'PY'
import json, plistlib, sys
info = json.load(open(sys.argv[1]))
plist = {"ProductName": "iPhone OS", "ProductVersion": info["ProductVersion"], "ProductBuildVersion": info["BuildVersion"]}
with open(sys.argv[2], "wb") as f:
    plistlib.dump(plist, f)
PY
fi
echo "sysroot: $SR ($(du -sh "$SR" | cut -f1))"

echo "== 5. asset catalog compiler"
mkdir -p "$SDKFREE_HOME/bin"
if [ -n "${SDKFREE_ACTOOL:-}" ]; then
  install -m755 "$SDKFREE_ACTOOL" "$SDKFREE_HOME/bin/actool"
elif [ ! -x "$SDKFREE_HOME/bin/actool" ]; then
  command -v swift >/dev/null || { echo "swift is not on PATH: run ./install-toolchain.sh first" >&2; exit 1; }
  (cd "$REPO/tools/darwin-tools" && swift build -c release --product actool >/dev/null)
  install -m755 "$REPO/tools/darwin-tools/.build/release/actool" "$SDKFREE_HOME/bin/actool"
fi
echo "Done. Build a Flutter app with: $HERE/flutter-build.sh <flutter app dir>"
