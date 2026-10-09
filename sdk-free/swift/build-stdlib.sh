#!/usr/bin/env bash
# Swift for arm64 iOS without an Xcode download: build the Swift standard library modules (Swift, SwiftOnoneSupport,
# _Concurrency, _RegexParser, _StringProcessing) from the open-source Swift tree that matches the installed compiler.
# The compiler is the swiftc on PATH (swift.org / swift-bin). Only module interfaces are built: the runtime libraries
# (libswiftCore ...) stay on the iPhone, and the sysroot carries link stubs for them (sdk-free/setup.sh).
#
#   sdk-free/swift/build-stdlib.sh          needs: sdk-free/setup.sh done once, git, python3
# Output: $SDKFREE_HOME/swift/res (a Swift resource directory for -resource-dir). Safe to re-run.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
SWIFTC=$(command -v swiftc) || { echo "swiftc is not on PATH: run ./install-toolchain.sh first" >&2; exit 1; }
TC=$(dirname "$(dirname "$(readlink -f "$SWIFTC")")")
OUT=$SDKFREE_HOME/swift
RES=$OUT/res
MIN=${NOSDK_SWIFT_MIN:-17.0}
[ -d "$SR/usr/lib/swift" ] || { echo "no Swift runtime stubs in $SR/usr/lib/swift: run sdk-free/setup.sh with the iPhone connected" >&2; exit 1; }

# The source tree must be the compiler's own release: "Swift version 6.4 (swift-6.4.0-RELEASE)".
TAG=${SWIFT_SRC_TAG:-$("$SWIFTC" --version 2>&1 | sed -n 's/.*(\(swift-[0-9.]*-RELEASE\)).*/\1/p' | head -n1)}
[ -n "$TAG" ] || { echo "cannot read the release tag from: $("$SWIFTC" --version 2>&1 | head -n1)" >&2; exit 1; }
# swiftc says swift-6.4-RELEASE where the repository tag is swift-6.4.0-RELEASE
if ! git ls-remote --exit-code --tags https://github.com/swiftlang/swift "refs/tags/$TAG" >/dev/null 2>&1; then
  TAG=$(echo "$TAG" | sed 's/-RELEASE$/.0-RELEASE/')
fi
SRC=$SDKFREE_HOME/cache/swift-src-$TAG
SP=$SDKFREE_HOME/cache/string-processing-$TAG
echo "== 1. sources for $TAG (Apache-2.0, swiftlang)"
if [ ! -d "$SRC/stdlib" ]; then
  git clone -q --depth 1 --filter=blob:none --sparse --branch "$TAG" https://github.com/swiftlang/swift "$SRC"
  git -C "$SRC" sparse-checkout set stdlib utils include cmake
fi
[ -d "$SP/Sources" ] || git clone -q --depth 1 --branch "$TAG" https://github.com/swiftlang/swift-experimental-string-processing "$SP"

mkdir -p "$OUT/gen" "$RES/iphoneos" "$OUT/log"
ln -sfn "$TC/lib/swift/clang" "$RES/clang"
ln -sfn "$TC/lib/swift/shims" "$RES/shims"

echo "== 2. flags from the source tree"
mapfile -t AV < <(grep '^SwiftStdlib' "$SRC/utils/availability-macros.def" | while IFS= read -r l; do printf '%s\n%s\n' -Xfrontend "-define-availability"; printf '%s\n%s\n' -Xfrontend "$l"; done)
mapfile -t F_CORE < <(python3 "$HERE/features.py" "$SRC" public/core/CMakeLists.txt cmake/modules/SwiftSource.cmake)
mapfile -t F_CONC < <(python3 "$HERE/features.py" "$SRC" public/Concurrency/CMakeLists.txt cmake/modules/SwiftSource.cmake)
DEFS=(-DSWIFT_STDLIB_SUPPORT_BACK_DEPLOYMENT -DSWIFT_ENABLE_REFLECTION -DSWIFT_STDLIB_HAS_DLADDR -DSWIFT_STDLIB_HAS_DLSYM=1
  -DSWIFT_STDLIB_HAS_FILESYSTEM -DSWIFT_STDLIB_HAS_DARWIN_LIBMALLOC=1 -DSWIFT_STDLIB_HAS_ASL -DSWIFT_STDLIB_HAS_STDIN
  -DSWIFT_STDLIB_HAS_ENVIRON -DSWIFT_STDLIB_HAS_LOCALE -DSWIFT_RUNTIME_OS_VERSIONING -DSWIFT_STDLIB_ENABLE_VECTOR_TYPES
  -DSWIFT_STDLIB_HAS_TYPE_PRINTING -DSWIFT_STDLIB_ENABLE_UNICODE_DATA -DSWIFT_THREADING_DARWIN -DSWIFT_LIBRARY_EVOLUTION=1)
COMMON=(-target "arm64-apple-ios$MIN" -sdk "$SR" -resource-dir "$RES" -parse-as-library -wmo -enable-library-evolution -swift-version 5
  -Xfrontend -enable-lexical-lifetimes=false -Xfrontend -target-min-inlining-version -Xfrontend min -Xfrontend -disable-availability-checking
  -Xfrontend -disable-implicit-concurrency-module-import -Xfrontend -disable-implicit-string-processing-module-import
  -Xcc "-fmodule-map-file=$TC/lib/swift/shims/module.modulemap" -Xcc "-I$TC/lib/swift/shims" -Xcc -isystem -Xcc "$SR/usr/include"
  -Xcc '-D__unused=__attribute__((unused))')
install_module() { # name path-of-built-module
  mkdir -p "$RES/iphoneos/$1.swiftmodule"
  cp "$2" "$RES/iphoneos/$1.swiftmodule/arm64-apple-ios.swiftmodule"
  [ -f "${2%.swiftmodule}.swiftdoc" ] && cp "${2%.swiftmodule}.swiftdoc" "$RES/iphoneos/$1.swiftmodule/arm64-apple-ios.swiftdoc"
  return 0
}

echo "== 3. Swift (core standard library)"
if [ ! -f "$RES/iphoneos/Swift.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  SWIFT_SRC=$SRC SWIFT_GEN=$OUT/gen python3 "$HERE/mk-core.py" >"$OUT/core-files.txt"
  mapfile -t FILES <"$OUT/core-files.txt"
  "$SWIFTC" -module-name Swift -parse-stdlib -O -Xfrontend -target-min-inlining-version -Xfrontend min "${AV[@]}" "${DEFS[@]}" \
    -DSWIFT_STDLIB_HAS_COMMANDLINE -DswiftCore_EXPORTS -Xfrontend -enable-experimental-concise-pound-file "${F_CORE[@]}" \
    -Xfrontend -enable-ossa-modules -Xllvm -sil-inline-generics -Xllvm -sil-partial-specialization -enforce-exclusivity=checked \
    "${COMMON[@]}" -emit-module -emit-module-path "$OUT/Swift.swiftmodule" "${FILES[@]}" >"$OUT/log/core.log" 2>&1 ||
    { tail -n 30 "$OUT/log/core.log" >&2; exit 1; }
  install_module Swift "$OUT/Swift.swiftmodule"
fi

echo "== 4. SwiftOnoneSupport"
if [ ! -f "$RES/iphoneos/SwiftOnoneSupport.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  "$SWIFTC" -module-name SwiftOnoneSupport -parse-stdlib -O -Xfrontend -disable-access-control "${AV[@]}" "${DEFS[@]}" \
    "${COMMON[@]}" -emit-module -emit-module-path "$OUT/SwiftOnoneSupport.swiftmodule" \
    "$SRC/stdlib/public/SwiftOnoneSupport/SwiftOnoneSupport.swift" >"$OUT/log/onone.log" 2>&1 ||
    { tail -n 30 "$OUT/log/onone.log" >&2; exit 1; }
  install_module SwiftOnoneSupport "$OUT/SwiftOnoneSupport.swiftmodule"
fi

echo "== 5. _Concurrency"
if [ ! -f "$RES/iphoneos/_Concurrency.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  SWIFT_SRC=$SRC SWIFT_GEN=$OUT/gen python3 "$HERE/mk-conc.py" >"$OUT/conc-files.txt"
  mapfile -t FILES <"$OUT/conc-files.txt"
  "$SWIFTC" -module-name _Concurrency -parse-stdlib -O -Xfrontend -target-min-inlining-version -Xfrontend min "${AV[@]}" "${DEFS[@]}" \
    -DSWIFT_CONCURRENCY_USES_DISPATCH -Xfrontend -enable-ossa-modules -enforce-exclusivity=checked "${F_CONC[@]}" -strict-memory-safety \
    "${COMMON[@]}" -I "$SRC/stdlib/public/Concurrency/InternalShims" \
    -emit-module -emit-module-path "$OUT/_Concurrency.swiftmodule" "${FILES[@]}" >"$OUT/log/conc.log" 2>&1 ||
    { tail -n 30 "$OUT/log/conc.log" >&2; exit 1; }
  install_module _Concurrency "$OUT/_Concurrency.swiftmodule"
fi

echo "== 6. _RegexParser and _StringProcessing"
SPFLAGS=(-O -Xfrontend -enable-lexical-lifetimes=false -enable-experimental-feature Extern -enable-experimental-feature SuppressedAssociatedTypes
  -enable-experimental-feature AllowUnsafeAttribute -strict-memory-safety -I "$SRC/stdlib/public/Concurrency/InternalShims")
if [ ! -f "$RES/iphoneos/_RegexParser.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  mapfile -t RP < <(find "$SP/Sources/_RegexParser" -name '*.swift' | sort)
  "$SWIFTC" -module-name _RegexParser "${AV[@]}" "${SPFLAGS[@]}" "${COMMON[@]}" \
    -emit-module -emit-module-path "$OUT/_RegexParser.swiftmodule" "${RP[@]}" >"$OUT/log/regexparser.log" 2>&1 ||
    { tail -n 30 "$OUT/log/regexparser.log" >&2; exit 1; }
  install_module _RegexParser "$OUT/_RegexParser.swiftmodule"
fi
if [ ! -f "$RES/iphoneos/_StringProcessing.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  mapfile -t SPF < <(find "$SP/Sources/_StringProcessing" -name '*.swift' | sort)
  "$SWIFTC" -module-name _StringProcessing "${AV[@]}" "${SPFLAGS[@]}" "${COMMON[@]}" \
    -emit-module -emit-module-path "$OUT/_StringProcessing.swiftmodule" "${SPF[@]}" >"$OUT/log/stringprocessing.log" 2>&1 ||
    { tail -n 30 "$OUT/log/stringprocessing.log" >&2; exit 1; }
  install_module _StringProcessing "$OUT/_StringProcessing.swiftmodule"
fi
echo "Swift modules for arm64-apple-ios$MIN in $RES (compiler $("$SWIFTC" --version 2>&1 | head -n1))"
