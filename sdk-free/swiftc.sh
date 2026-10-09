#!/usr/bin/env bash
# Swift for arm64 iOS without an Xcode download: compile and link Swift files into one executable.
#   sdk-free/swiftc.sh [-Onone] -o HelloSwift main.swift [more.swift ...]
# Needs sdk-free/setup.sh and sdk-free/swift/build-stdlib.sh done once. The program links the Swift runtime that is on
# the iPhone (libswiftCore and the other libswift*.dylib files). Swift code that imports Foundation or UIKit needs the
# overlay modules (sdk-free/swift/README.md).
set -euo pipefail
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
RES=$SDKFREE_HOME/swift/res
MIN=${NOSDK_SWIFT_MIN:-17.0}
SWIFTC=$(command -v swiftc)
TC=$(dirname "$(dirname "$(readlink -f "$SWIFTC")")")
OPT=-O
OUT=a.out
FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    -o) OUT=$2; shift 2 ;;
    -Onone) OPT=-Onone; shift ;;
    -O) OPT=-O; shift ;;
    *) FILES+=("$1"); shift ;;
  esac
done
[ ${#FILES[@]} -gt 0 ] || { echo "usage: swiftc.sh [-Onone] -o OUT file.swift ..." >&2; exit 2; }
[ -d "$RES/iphoneos/Swift.swiftmodule" ] || { echo "no Swift modules in $RES: run sdk-free/swift/build-stdlib.sh" >&2; exit 1; }
obj=$(mktemp -d)
trap 'rm -rf "$obj"' EXIT
IMPORTS=(-I "$SDKFREE_HOME/swift/ovl")
[ -d "$SDKFREE_HOME/swift/ovl" ] || IMPORTS=()
"$SWIFTC" "$OPT" -wmo -swift-version 5 -enable-bare-slash-regex -target "arm64-apple-ios$MIN" -sdk "$SR" -resource-dir "$RES" \
  "${IMPORTS[@]}" -Xcc "-fmodule-map-file=$TC/lib/swift/shims/module.modulemap" -Xcc "-I$TC/lib/swift/shims" -Xcc -isystem -Xcc "$SR/usr/include" -module-name "$(basename "$OUT" | tr -c 'A-Za-z0-9_\n' _)" \
  -emit-object -o "$obj/main.o" "${FILES[@]}"
libs=(-lSystem -lobjc -lswiftCore -lswift_Concurrency -lswift_StringProcessing -lswift_RegexParser)
[ "$OPT" = -Onone ] && libs+=(-lswiftSwiftOnoneSupport)
"$SDKFREE_HOME/toolset/ld64.lld" -arch arm64 -platform_version ios "$MIN" 26.0 -syslibroot "$SR" \
  -L"$SR/usr/lib" -L"$SR/usr/lib/swift" "${libs[@]}" -rpath /usr/lib/swift -o "$OUT" "$obj/main.o" 2>&1 |
  grep -v "does not support linking for platform iOS" || true
[ -s "$OUT" ] || { echo "link failed" >&2; exit 1; }
echo "built $OUT"
