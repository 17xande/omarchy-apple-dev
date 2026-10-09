#!/usr/bin/env bash
# clang for iOS arm64 against the sdk-free sysroot only (no Xcode, no SDK files).
#   sdk-free/cc.sh [-c] main.m -o main.o        NOSDK_MIN=15.0 sets the deployment target (default 17.0)
# Link with:  $SDKFREE_HOME/toolset/ld64.lld -arch arm64 -platform_version ios 17.0 26.0 -syslibroot $SDKFREE_HOME/iPhoneOS.sdk \
#   -lSystem -lobjc -framework UIKit -framework Foundation -o App main.o
set -euo pipefail
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=${NOSDK_SYSROOT:-$SDKFREE_HOME/iPhoneOS.sdk}
CLANG=${SDKFREE_CLANG:-$(dirname "$(readlink -f "$(command -v swift)")")/clang}
MIN=${NOSDK_MIN:-17.0}
FW=()
[ -n "${FLUTTER_FW_DIR:-}" ] && FW=(-F"$FLUTTER_FW_DIR")
exec "$CLANG" -target "arm64-apple-ios$MIN" -isysroot "$SR" -nostdinc \
  -isystem "$SR/usr/include" -isystem "$("$CLANG" -print-resource-dir)/include" \
  -iframework "$SR/System/Library/Frameworks" "${FW[@]}" -fobjc-arc -fobjc-runtime="ios-$MIN" "$@"
