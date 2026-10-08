# Flutter apps for iOS, built on Linux

`flutter build ios` needs Xcode. These scripts build a Flutter app for a
physical iPhone or iPad on Omarchy with no Mac and no Xcode, on top of the
toolchain `install-toolchain.sh` sets up, and hand the result to
`xtool install`.

Verified 2026-10-08 on x86_64 with Flutter 3.47.6, swift-bin 6.4.0, the
iPhoneOS 27.0 SDK and an iPad on iPadOS 27.0 (FINDINGS.md item 64, receipt
`receipts/2026-10-08-flutter-ios.md`). Release mode, arm64 device builds only.
aarch64 hosts are untested.

## Use

```
./install-toolchain.sh            # once, as for any app in this repo
sudo pacman -S --needed llvm      # llvm-strip, llvm-lipo, llvm-otool, llvm-install-name-tool, llvm-ar
flutter/setup.sh                  # once per Flutter version (7 GB, 12 min here)
flutter/build.sh --install /path/to/flutter/app [KEY=VALUE ...]
```

The `llvm` package is the one dependency `install-toolchain.sh` does not
bring: the shims forward to its binutils, and neither the Swift toolchain nor
the darwin SDK bundle ships them. `build.sh` names whatever is missing before
it starts.

`KEY=VALUE` arguments become `--dart-define`s. Without `--install` the result
is `<app>/build/ios-linux/Runner.ipa`, unsigned, for `xtool install` or
`ship.sh`-style signing. The bundle id, minimum iOS and version come from the
app's `ios/Runner.xcodeproj` and `pubspec.yaml`; `BUNDLE_ID`, `MIN_IOS`,
`BUILD_NAME` and `BUILD_NUMBER` override them.

A clean build of the stock template with four plugins takes 47 s on a 2018
laptop (i7-8650U).

## What `setup.sh` fetches and changes

- **Network.** depot_tools from chromium.googlesource.com and the Dart SDK
  from dart.googlesource.com, pinned to the `dart_revision` in the installed
  Flutter's `DEPS`: 7 GB on disk. `gclient sync` also runs the Dart SDK's DEPS
  hooks, which download prebuilt build tools from Google storage (the clang,
  gn and ninja the build runs, sysroots, a bootstrap Dart SDK). Those
  prebuilts execute on your machine during the build. `flutter precache --ios`
  then fetches Flutter's own iOS engine artifacts.
- **It modifies the Flutter install.** `gen_snapshot_arm64` under
  `bin/cache/artifacts/engine/ios-release` is replaced by the Linux build; the
  original is kept beside it as `gen_snapshot_arm64.macos`. To undo, move that
  file back over `gen_snapshot_arm64`. A Flutter upgrade restores the macOS
  binary by itself, after which `build.sh` stops with "not the Linux build"
  until `setup.sh` runs again.

## How it works

| Piece | On a Mac | Here |
|---|---|---|
| Dart code to arm64 | `gen_snapshot_arm64`, shipped as a macOS binary only | The same compiler built from the Dart SDK at Flutter's pinned revision, hosted on Linux and targeting iOS (`patches/dart-ios-target-on-linux.patch`, one GN argument). Since Flutter 3.47 it writes the Mach-O dylib itself, so no Apple linker is involved. |
| Assets, engine framework, native assets (`sqlite3`, `objective_c`, ...) | `flutter assemble` from an Xcode build phase | The same `flutter assemble release_ios_bundle_flutter_assets`, unmodified, with `shims/` first on PATH. |
| `xcrun`, `xcodebuild`, `codesign`, `lipo`, `strip`, `otool`, `install_name_tool`, `dsymutil`, `ld` | Xcode | `shims/`: SDK queries answered from the darwin SDK bundle, tools forwarded to LLVM, `codesign` a no-op (xtool signs the finished app). |
| Runner and plugins | Xcode project plus Swift packages | `tools/gen-shell-package.py` writes one SwiftPM package from `.flutter-plugins-dependencies`; SwiftBuild compiles it against `Flutter.framework`. |
| Icons | `actool` | This repo's Linux `actool`. |
| Storyboards | `ibtool` | This repo's Linux `ibtool`. Flutter's two template storyboards compile byte-identical to Xcode's (FINDINGS.md item 65). |
| `Info.plist` | Xcode | `tools/gen-info-plist.py`. |

## Things that would otherwise bite

- **dyld rejects what llvm-strip and llvm-install-name-tool write.** Both
  re-lay out `__LINKEDIT` and can leave the string pool on a 4-byte boundary.
  An image built against the iOS 27 SDK then fails to load with `mis-aligned
  LINKEDIT string pool`; older-SDK images are let through, which hides the
  problem until a locally compiled native asset hits it.
  `tools/macho-align.py` pads the pool to 8 bytes; the `strip` and
  `install_name_tool` shims run it on everything they touch.
- **The Swift toolchain's `ld64.lld` refuses iOS.** `shims/clang-darwin` links
  with the SDK bundle's `ld64.lld` and passes `-mlinker-version`, without
  which clang omits `-platform_version`.
- **`xtool install` waits forever while the app being replaced is running.**
  Quit it first.

## Limits

- Release mode only: no debug build, no hot reload, no profile `gen_snapshot`.
- Every plugin with native iOS code must ship a `Package.swift`; a
  CocoaPods-only plugin stops the build with its name.
- A storyboard edited beyond Flutter's template may use something the Linux
  ibtool does not compile yet; it stops with an `error:` line naming it.
- Not tried: App Store upload of a Flutter app, app extensions, entitlements
  beyond the defaults, simulator builds.
- A Flutter upgrade needs `flutter/setup.sh` again: the snapshot format is
  tied to the exact Dart revision.
