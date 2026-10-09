#!/usr/bin/env bash
# Swift overlay modules (ObjectiveC, Darwin, Dispatch, CoreGraphics, Foundation) for arm64 iOS without an Xcode
# download, plus the C header trees they import. Programs can then `import Foundation` and Swift Flutter plugins
# compile and link (sdk-free/flutter-build.sh).
# Sources are fetched at run time from pinned open-source tags: apple-oss-distributions (Darwin C headers,
# CoreFoundation headers) and the swift tree at swift-5.3-RELEASE (the last open Foundation/Dispatch overlay;
# patched to compile with the installed swiftc by mk-foundation-src.py and the patches in overlay/).
#
#   sdk-free/swift/overlays.sh    needs: sdk-free/setup.sh + sdk-free/swift/build-stdlib.sh done once; git, cmake, python3
# Output: $SDKFREE_HOME/swift/{darwin,sdkm,ovl,gen53} and the overlay modules installed next to the standard library
# in $SDKFREE_HOME/swift/res. Nothing here runs on or talks to a device. Safe to re-run: finished stages are skipped.
set -euo pipefail

HERE=$(dirname "$(readlink -f "$0")")
SDKFREE_HOME=${SDKFREE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-apple-dev/sdk-free}
SR=$SDKFREE_HOME/iPhoneOS.sdk
SWIFTC=$(command -v swiftc) || { echo "swiftc is not on PATH: run ./install-toolchain.sh first" >&2; exit 1; }
TC=$(dirname "$(dirname "$(readlink -f "$SWIFTC")")")
RES=$SDKFREE_HOME/swift/res
OUT=$SDKFREE_HOME/swift
DARWININC=$OUT/darwin/usr/include
SDKM=$OUT/sdkm
OVL=$OUT/ovl
GEN=$OUT/gen53
CACHE=$SDKFREE_HOME/cache
OSS=$CACHE/oss
S53=$CACHE/swift53
[ -d "$SR/usr/lib/swift" ] || { echo "no Swift runtime stubs in $SR/usr/lib/swift: run sdk-free/setup.sh first" >&2; exit 1; }
[ -f "$RES/iphoneos/Swift.swiftmodule/arm64-apple-ios.swiftmodule" ] || { echo "no Swift module in $RES: run sdk-free/swift/build-stdlib.sh first" >&2; exit 1; }
for t in git python3 cmake; do command -v "$t" >/dev/null || { echo "missing: $t" >&2; exit 1; }; done

# Pinned open-source sources (apple-oss-distributions) for the Darwin C include tree.
OSS_TAGS="Libc Libc-1752.100.10
xnu xnu-12377.1.9
libpthread libpthread-539
libplatform libplatform-375.100.10
libclosure libclosure-96
libmalloc libmalloc-812.100.31
CarbonHeaders CarbonHeaders-18.1
AvailabilityVersions AvailabilityVersions-157.2
Libm Libm-2026
libdispatch libdispatch-1542.0.4
CF CF-1153.18"
# The 5.3 tree: Platform/Darwin/CoreGraphics/Dispatch/Foundation overlay sources, SwiftShims, apinotes test SDK.
S53_TAG=swift-5.3-RELEASE
# the swift source tree fetched by build-stdlib.sh carries gyb
TAG=${SWIFT_SRC_TAG:-$("$SWIFTC" --version 2>&1 | sed -n 's/.*(\(swift-[0-9.]*-RELEASE\)).*/\1/p' | head -n1)}
git ls-remote --exit-code --tags https://github.com/swiftlang/swift "refs/tags/$TAG" >/dev/null 2>&1 ||
  TAG=$(echo "$TAG" | sed 's/-RELEASE$/.0-RELEASE/')

echo "== 1. sources"
while read -r repo tag; do
  [ -n "${repo:-}" ] || continue
  if [ ! -d "$OSS/$repo/.git" ]; then
    git clone -q --depth 1 --branch "$tag" "https://github.com/apple-oss-distributions/$repo" "$OSS/$repo"
  fi
done <<EOT
$OSS_TAGS
EOT
if [ ! -d "$S53/stdlib" ]; then
  git clone -q --depth 1 --filter=blob:none --sparse --branch "$S53_TAG" https://github.com/swiftlang/swift "$S53"
  git -C "$S53" sparse-checkout set stdlib/public/Darwin stdlib/public/Platform stdlib/public/SwiftShims test/Inputs/clang-importer-sdk
fi
if [ ! -d "$CACHE/swift-src-$TAG/utils" ]; then
  echo "the swift source tree is missing: re-run sdk-free/swift/build-stdlib.sh" >&2; exit 1
fi

echo "== 2. Darwin C include tree"
if [ ! -f "$OUT/darwin/.done" ]; then
  D=$DARWININC
  mkdir -p "$D"
  cp -r "$OSS/Libc/include/." "$D/"
  cp -r "$OSS/xnu/bsd/sys" "$D/"
  for d in machine arm net netinet netinet6 uuid; do mkdir -p "$D/$d"; cp -r "$OSS/xnu/bsd/$d/." "$D/$d/"; done
  mkdir -p "$D/mach"; cp -r "$OSS/xnu/osfmk/mach/." "$D/mach/"
  mkdir -p "$D/mach_debug"; cp -r "$OSS/xnu/osfmk/mach_debug/." "$D/mach_debug/"
  mkdir -p "$D/arm"; cp "$OSS/xnu/osfmk/arm/arch.h" "$D/arm/"
  mkdir -p "$D/libkern"; cp -r "$OSS/xnu/libkern/libkern/." "$D/libkern/"
  mkdir -p "$D/os"; cp -r "$OSS/xnu/libkern/os/." "$D/os/" 2>/dev/null || true
  cp -r "$OSS/libpthread/include/." "$D/"
  cp -r "$OSS/libplatform/include/." "$D/"
  cp "$OSS/libclosure/Block.h" "$D/" 2>/dev/null || true
  mkdir -p "$D/malloc"; cp -r "$OSS/libmalloc/include/malloc/." "$D/malloc/"
  for h in Availability.h AvailabilityInternal.h AvailabilityMacros.h ConditionalMacros.h MacTypes.h Endian.h; do
    cp "$OSS/CarbonHeaders/$h" "$D/"
  done
  cp "$OSS/Libm/Source/ARM/math.h" "$D/math.h"
  cp "$OSS/Libm/Source/complex.h" "$D/"
  # availability tables (cmake generator from AvailabilityVersions) and xnu's own generators
  AV=$OSS/av/dst
  if [ ! -d "$AV" ]; then
    cmake -S "$OSS/AvailabilityVersions" -B "$OSS/av/obj" -G "Unix Makefiles" -DSRCROOT="$OSS/AvailabilityVersions" \
      -DOBJROOT="$OSS/av/obj" -DSYMROOT="$OSS/av/sym" -DDSTROOT="$AV" -DDRIVERKIT=0 -DSYSTEM_PREFIX= \
      -DINSTALL_KERNEL_HEADERS=1 -DAV_VERSION=Local >/dev/null
    make -C "$OSS/av/obj" install >/dev/null
  fi
  cp "$AV/usr/include/"Availability*.h "$D/"
  cp "$AV/usr/include/os/availability.h" "$D/os/"
  bash "$OSS/xnu/bsd/sys/make_symbol_aliasing.sh" "$AV" "$D/sys/_symbol_aliasing.h"
  bash "$OSS/xnu/bsd/sys/make_posix_availability.sh" "$D/sys/_posix_availability.h"
  # ObjC runtime headers come from the sysroot (objc4, installed by setup.sh) so the ObjectiveC clang module
  # and the Foundation framework module resolve NSObject through one declaration
  mkdir -p "$D/objc"; cp "$SR"/usr/include/objc/*.h "$D/objc/"
  cp "$HERE/overlay/TargetConditionals.h" "$D/"
  mkdir -p "$D/dispatch"
  cp -r "$OSS/libdispatch/dispatch/." "$D/dispatch/"
  rm -rf "$D/dispatch/generic" "$D/dispatch/generic_static" "$D/dispatch/CMakeLists.txt" "$D/dispatch/Dispatch.apinotes"
  for h in object.h workgroup.h workgroup_base.h workgroup_object.h workgroup_interval.h workgroup_parallel.h clock.h; do
    cp "$OSS/libdispatch/os/$h" "$D/os/"
  done
  cp -r "$OSS/xnu/libsyscall/mach/mach/." "$D/mach/"
  cp "$OSS/xnu/libsyscall/wrappers/gethostuuid.h" "$D/"
  cp "$OSS/xnu/libsyscall/wrappers/spawn/spawn.h" "$D/spawn.h"
  printf '#include <pthread/pthread.h>\n' > "$D/pthread.h"
  printf '#include <pthread/sched.h>\n' > "$D/sched.h"
  # install-time stripping of //Begin-Libc blocks (repo headers carry kernel-only sections)
  find "$D" -name '*.h' -exec sed -i '/^\/\/Begin-Libc/,/^\/\/End-Libc/d' {} +
  # libdispatch headers use xros(...); the generated AvailabilityInternal.h only knows visionos
  cat >> "$D/AvailabilityInternal.h" <<'EOT'
#ifndef __API_AVAILABLE_PLATFORM_xros
#define __API_AVAILABLE_PLATFORM_xros(x) xros,introduced=x
#define __API_DEPRECATED_PLATFORM_xros(x,y) xros,introduced=x,deprecated=y
#define __API_OBSOLETED_PLATFORM_xros(x,y,z) xros,introduced=x,deprecated=y,obsoleted=z
#define __API_UNAVAILABLE_PLATFORM_xros xros,unavailable
#endif
EOT
  # modular builds: avoid the clang-types cycle in machine _types.h
  grep -rl 'USE_CLANG_STDDEF\|USE_CLANG_TYPES\|USE_CLANG_LIMITS' "$D" | xargs -r sed -i \
    's/#define USE_CLANG_STDDEF 1/#define USE_CLANG_STDDEF 0/; s/#define USE_CLANG_TYPES 1/#define USE_CLANG_TYPES 0/; s/#define USE_CLANG_LIMITS 1/#define USE_CLANG_LIMITS 0/'
  # the module map for the Darwin/Dispatch/os/ObjectiveC clang modules (authored, subset over these headers)
  cp "$HERE/overlay/modulemap.darwin" "$D/module.modulemap"
  # libdispatch's apinotes give the dispatch C API its Swift names
  cp "$OSS/libdispatch/dispatch/Dispatch.apinotes" "$D/Dispatch.apinotes"
  # MacTypes' Boolean must import as Swift Bool (6.x has no importer special case for the typedef)
  sed -i 's/^typedef unsigned char                   Boolean;/typedef _Bool                        Boolean;/' "$D/MacTypes.h"
  grep -q "typedef _Bool" "$D/MacTypes.h" || { echo "MacTypes.h Boolean patch failed" >&2; exit 1; }
  touch "$OUT/darwin/.done"
  echo "darwin include tree: $(find "$D" -name '*.h' | wc -l) headers"
fi

echo "== 3. framework module maps over the sysroot headers (sdkm)"
if [ ! -f "$OUT/sdkm/.done" ]; then
  FW=$SDKM/Frameworks
  mkdir -p "$FW"
  for f in CoreFoundation CoreGraphics QuartzCore UIKit UserNotifications CoreMedia Foundation; do
    [ -d "$SR/System/Library/Frameworks/$f.framework/Headers" ] && [ -n "$(ls "$SR/System/Library/Frameworks/$f.framework/Headers" 2>/dev/null)" ] || {
      echo "no sysroot headers for $f: framework module skipped"
      continue
    }
    mkdir -p "$FW/$f.framework/Modules" "$FW/$f.framework/Headers"
    cp -r "$SR/System/Library/Frameworks/$f.framework/Headers/." "$FW/$f.framework/Headers/"
    printf 'framework module %s [system] {\n  umbrella header "%s.h"\n  use ObjectiveC\n  use Darwin\n  export *\n}\n' "$f" "$f" > "$FW/$f.framework/Modules/module.modulemap"
  done
  # libc include prefix: the hand-written Foundation headers rely on it textually
  sed -i '1i #include <limits.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\n#include <stdarg.h>\n#include <string.h>\n#include <stdlib.h>\n#include <math.h>\n#include <errno.h>' "$FW/Foundation.framework/Headers/Foundation.h"
  cat "$HERE/overlay/Foundation.add.h" >> "$FW/Foundation.framework/Headers/Foundation.h"
  python3 "$HERE/overlay-fix-headers.py" foundation "$FW/Foundation.framework/Headers/Foundation.h"
  python3 "$HERE/overlay-fix-headers.py" uikit "$FW/UIKit.framework/Headers/UIKit.h"
  # open-source CoreFoundation public headers replace the hand-written ones
  for h in $(grep -o '<CoreFoundation/[A-Za-z_]*\.h>' "$OSS/CF/CoreFoundation.h" | sed 's/<CoreFoundation\///; s/>//'); do
    [ -f "$OSS/CF/$h" ] && cp "$OSS/CF/$h" "$FW/CoreFoundation.framework/Headers/$h"
  done
  for h in CoreFoundation.h CFAvailability.h CFBase.h CFBridgingExtras.h; do
    [ -f "$OSS/CF/$h" ] && cp "$OSS/CF/$h" "$FW/CoreFoundation.framework/Headers/$h"
  done
  python3 "$HERE/overlay-fix-headers.py" cf "$FW/CoreFoundation.framework/Headers/CFBase.h"
  # the ObjectiveC clang module comes from the darwin include tree's module map (next to the objc headers),
  # so NSObject is declared exactly once for every module
  # shim headers the overlay modules import (SwiftShims modules get real paths here)
  mkdir -p "$SDKM/ovlshims"
  cp "$HERE"/overlay/shims/*.h "$SDKM/ovlshims/"
  S53SHIMS=$S53/stdlib/public/SwiftShims
  {
    for m in Dispatch ObjectiveC OS SafariServices AppKit UIKit XCTest XPC CoreFoundation Network ClockKit CoreMedia; do
      h=$S53SHIMS/${m}OverlayShims.h
      [ -f "$h" ] || continue
      printf 'module _Swift%sOverlayShims {\n  header "%s"\n}\n' "$m" "$h"
    done
    printf 'module _SwiftFoundationOverlayShims {\n  header "%s/ovlshims/FoundationOverlayShimsLite.h"\n}\n' "$SDKM"
  } > "$SDKM/ovlshims/module.modulemap"
  # apinotes: NSData<->Data bridging and the option-enum Swift names
  python3 "$HERE/overlay-apinotes.py" "$S53/test/Inputs/clang-importer-sdk/usr/include" "$FW" "$RES/apinotes"
  touch "$OUT/sdkm/.done"
  echo "sdkm ready: $(find "$SDKM" -name module.modulemap | wc -l) modulemaps"
fi

echo "== 4. gyb-generated 5.3 platform sources"
if [ ! -f "$GEN/NSValue.swift" ]; then
  mkdir -p "$GEN"
  GYB="python3 $CACHE/swift-src-$TAG/utils/gyb.py -D CMAKE_SIZEOF_VOID_P=8"
  $GYB -o "$GEN/Darwin.swift" "$S53/stdlib/public/Platform/Darwin.swift.gyb"
  $GYB -o "$GEN/tgmath.swift" "$S53/stdlib/public/Platform/tgmath.swift.gyb"
  $GYB -o "$GEN/CGFloat.swift" "$S53/stdlib/public/Darwin/CoreGraphics/CGFloat.swift.gyb"
  $GYB -o "$GEN/NSValue.swift" "$S53/stdlib/public/Darwin/Foundation/NSValue.swift.gyb"
fi

# Flags shared by every overlay module build: the clang Darwin module lives in our include tree, the framework
# modules in sdkm, the apinotes ride along with them and in the resource dir.
COMMON=(-target "arm64-apple-ios${NOSDK_SWIFT_MIN:-17.0}" -sdk "$SR" -resource-dir "$RES" -parse-as-library -wmo
  -enable-library-evolution -swift-version 5
  -Xfrontend -disable-availability-checking -Xfrontend -disable-implicit-string-processing-module-import
  -Xcc -fapinotes-modules -Xcc -fapinotes
  -Xcc "-fmodule-map-file=$TC/lib/swift/shims/module.modulemap" -Xcc "-I$TC/lib/swift/shims"
  -I "$OVL" -I "$SDKM/ovlshims" -F "$SDKM/Frameworks" -Xcc -F -Xcc "$SDKM/Frameworks"
  -I "$DARWININC" -Xcc -isystem -Xcc "$DARWININC" -Xcc -isystem -Xcc "$SR/usr/include"
  -Xcc '-D__unused=__attribute__((unused))' -Xcc -DSWIFT_STDLIB_HAS_ENVIRON=1)
install_module() { # name path-of-built-module
  mkdir -p "$RES/iphoneos/$1.swiftmodule" "$OVL/$1.swiftmodule"
  cp "$2" "$OVL/$1.swiftmodule/arm64-apple-ios.swiftmodule"
  cp "$2" "$RES/iphoneos/$1.swiftmodule/arm64-apple-ios.swiftmodule"
  [ -f "${2%.swiftmodule}.swiftdoc" ] && {
    cp "${2%.swiftmodule}.swiftdoc" "$OVL/$1.swiftmodule/arm64-apple-ios.swiftdoc"
    cp "${2%.swiftmodule}.swiftdoc" "$RES/iphoneos/$1.swiftmodule/arm64-apple-ios.swiftdoc"
  }
  return 0
}
build_module() { # name files...
  local m=$1; shift
  mkdir -p "$OVL/$m.build" "$OUT/log"
  "$SWIFTC" -module-name "$m" -O "${COMMON[@]}" -emit-module -emit-module-path "$OVL/$m.build/$m.swiftmodule" "$@" \
    >"$OUT/log/ovl-$m.log" 2>&1 || { tail -n 40 "$OUT/log/ovl-$m.log" >&2; exit 1; }
  install_module "$m" "$OVL/$m.build/$m.swiftmodule"
  echo "$m ok"
}

echo "== 5. overlay modules"
D53=$S53/stdlib/public/Darwin
[ -f "$RES/iphoneos/ObjectiveC.swiftmodule/arm64-apple-ios.swiftmodule" ] || build_module ObjectiveC "$D53/ObjectiveC/ObjectiveC.swift"
[ -f "$RES/iphoneos/Darwin.swiftmodule/arm64-apple-ios.swiftmodule" ] ||
  build_module Darwin "$GEN/Darwin.swift" "$GEN/tgmath.swift" "$D53/../Platform/MachError.swift" \
    "$D53/../Platform/POSIXError.swift" "$D53/../Platform/TiocConstants.swift"
[ -f "$RES/iphoneos/Dispatch.swiftmodule/arm64-apple-ios.swiftmodule" ] ||
  build_module Dispatch "$D53/Dispatch/Block.swift" "$D53/Dispatch/Data.swift" "$D53/Dispatch/Dispatch.swift" "$D53/Dispatch/IO.swift" \
    "$D53/Dispatch/Private.swift" "$D53/Dispatch/Queue.swift" "$D53/Dispatch/Source.swift" "$D53/Dispatch/Time.swift"
[ -f "$RES/iphoneos/CoreGraphics.swiftmodule/arm64-apple-ios.swiftmodule" ] ||
  build_module CoreGraphics "$GEN/CGFloat.swift"
if [ ! -f "$RES/iphoneos/Foundation.swiftmodule/arm64-apple-ios.swiftmodule" ]; then
  FFILES="String NSString NSArray NSDictionary NSSet NSNumber NSFastEnumeration Boxing NSRange NSGeometry ReferenceConvertible
Foundation Data DataProtocol ContiguousBytes Collections+DataProtocol NSData+DataProtocol Pointers+DataProtocol
NSError NSStringEncodings URL"
  SWIFT53_SRC=$S53 SWIFT53_OUT=$CACHE/ovlsrc/Foundation python3 "$HERE/mk-foundation-src.py" $FFILES
  build_module Foundation "$CACHE"/ovlsrc/Foundation/*.swift "$GEN/NSValue.swift"
fi

echo "== 6. SafariServices headers and module map"
for d in "$SR/System/Library/Frameworks" "$SDKM/Frameworks"; do
  F=$d/SafariServices.framework
  [ -f "$F/Headers/SafariServices.h" ] || {
    mkdir -p "$F/Headers"
    cp "$HERE/../headers/System/Library/Frameworks/SafariServices.framework/Headers/SafariServices.h" "$F/Headers/"
  }
done
[ -f "$SR/System/Library/Frameworks/SafariServices.framework/SafariServices.tbd" ] || {
  cp "$HERE/../headers/System/Library/Frameworks/SafariServices.framework/SafariServices.tbd" "$SR/System/Library/Frameworks/SafariServices.framework/"
}
[ -f "$SDKM/Frameworks/SafariServices.framework/Modules/module.modulemap" ] || {
  mkdir -p "$SDKM/Frameworks/SafariServices.framework/Modules"
  cat > "$SDKM/Frameworks/SafariServices.framework/Modules/module.modulemap" <<'EOF'
framework module SafariServices [system] {
  umbrella header "SafariServices.h"
  use ObjectiveC
  use Darwin
  export *
}
EOF
}

echo "Swift overlay modules for arm64-apple-ios${NOSDK_SWIFT_MIN:-17.0} in $RES (compiler $("$SWIFTC" --version 2>&1 | head -n1))"
