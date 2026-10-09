#!/usr/bin/env bash
# One-time (per Flutter version) setup for building Flutter iOS apps on Linux.
#
#   flutter/setup.sh
#
# Flutter ships its iOS AOT compiler, gen_snapshot, as a macOS binary only.
# This builds the same compiler from the Dart SDK at the revision the Flutter
# on PATH pins, targeting iOS from a Linux host, and puts it where Flutter
# looks for it. Safe to re-run: each step is skipped when already done.
#
# Network: depot_tools (chromium.googlesource.com) and the Dart SDK with its
# build dependencies (dart.googlesource.com, 7 GB on disk) — there is no
# prebuilt Linux-hosted iOS gen_snapshot to download instead. `gclient sync`
# also runs the Dart SDK's DEPS hooks, which download prebuilt build tools from
# Google storage (among them the clang, gn and ninja the build uses, sysroots
# and a bootstrap Dart SDK) and execute them during the build. `flutter
# precache --ios` fetches Flutter's own iOS engine artifacts.
#
# This modifies the Flutter install: gen_snapshot_arm64 under
# bin/cache/artifacts/engine/ios-release is replaced, the original kept beside
# it as gen_snapshot_arm64.macos. Move that file back to undo it.
#
# Env: FLUTTER (default: flutter on PATH), FLUTTER_IOS_WORK (default:
# ~/.cache/omarchy-apple-dev/flutter).
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
FLUTTER=${FLUTTER:-$(command -v flutter)} || { echo "flutter is not on PATH; set FLUTTER=/path/to/flutter/bin/flutter" >&2; exit 1; }
flutter_root=$(dirname "$(dirname "$(readlink -f "$FLUTTER")")")
work=${FLUTTER_IOS_WORK:-$HOME/.cache/omarchy-apple-dev/flutter}
mkdir -p "$work"

case "$(uname -m)" in
  x86_64) sim_arch=simarm64; out_dir=ProductSIMARM64 ;;
  aarch64) sim_arch=arm64; out_dir=ProductARM64 ;;
  *) echo "unsupported host architecture $(uname -m)" >&2; exit 1 ;;
esac

dart_rev=$(sed -n "s/^ *'dart_revision': '\([0-9a-f]*\)',.*/\1/p" "$flutter_root/DEPS")
[ -n "$dart_rev" ] || { echo "could not read dart_revision from $flutter_root/DEPS" >&2; exit 1; }
echo "== Flutter at $flutter_root pins Dart $dart_rev"

echo "== 1. Flutter's iOS engine artifacts"
cache=$flutter_root/bin/cache/artifacts/engine/ios-release
if [ ! -d "$cache/Flutter.xcframework" ]; then
  "$FLUTTER" precache --ios --no-android --no-web --no-linux --no-windows --no-macos --no-fuchsia --no-universal
fi

built=$work/gen_snapshot-$dart_rev
if [ ! -x "$built" ]; then
  echo "== 2. Dart SDK source at $dart_rev"
  [ -d "$work/depot_tools" ] ||
    git clone -q --depth 1 https://chromium.googlesource.com/chromium/tools/depot_tools.git "$work/depot_tools"
  export PATH="$work/depot_tools:$PATH" DEPOT_TOOLS_UPDATE=0
  mkdir -p "$work/dart"
  cat >"$work/dart/.gclient" <<GCLIENT
solutions = [
  {
    "name": "sdk",
    "url": "https://dart.googlesource.com/sdk.git",
    "deps_file": "DEPS",
    "managed": True,
    "custom_vars": {"download_emscripten": False, "checkout_llvm": False},
  },
]
GCLIENT
  sdk=$work/dart/sdk
  if [ "$(git -C "$sdk" rev-parse HEAD 2>/dev/null || true)" != "$dart_rev" ]; then
    # A previous revision's patch would block the checkout; it is re-applied below.
    [ ! -d "$sdk/.git" ] || git -C "$sdk" checkout -q -- runtime/BUILD.gn runtime/runtime_args.gni
    (cd "$work/dart" && gclient sync --no-history -D -r "sdk@$dart_rev")
  fi

  echo "== 3. gen_snapshot targeting iOS, hosted on Linux"
  if ! grep -q dart_target_os_override "$sdk/runtime/runtime_args.gni"; then
    git -C "$sdk" apply "$here/patches/dart-ios-target-on-linux.patch"
  fi
  (cd "$sdk" && python3 tools/build.py -m product -a "$sim_arch" \
    --gn-args='dart_target_os_override="ios"' gen_snapshot)
  install -m755 "$sdk/out/$out_dir/gen_snapshot" "$built"
fi

echo "== 4. Put it where Flutter looks"
for mode in ios-release ios-profile; do
  dir=$flutter_root/bin/cache/artifacts/engine/$mode
  [ -d "$dir" ] || continue
  if [ -f "$dir/gen_snapshot_arm64" ] && ! cmp -s "$dir/gen_snapshot_arm64" "$built"; then
    [ -f "$dir/gen_snapshot_arm64.macos" ] || mv "$dir/gen_snapshot_arm64" "$dir/gen_snapshot_arm64.macos"
  fi
  # ios-profile needs a profile-mode build of the VM; only release is produced here.
  [ "$mode" = ios-release ] && install -m755 "$built" "$dir/gen_snapshot_arm64"
done
"$cache/gen_snapshot_arm64" --version 2>&1 | head -n1
echo "Done. Build an app with: $here/build.sh <flutter app dir>"
