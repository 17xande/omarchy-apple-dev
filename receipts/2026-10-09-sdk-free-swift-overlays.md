# SDK-free Swift overlay port — 2026-10-09

Worktree: `/home/joshuawarren/src/omarchy-apple-dev-wt-mode`, branch `install-mode`.
Commits: `a7f2a83` (Build SDK-free Swift overlays) and the follow-up 6.4 fixes on top, pushed to `origin/install-mode`.

## Outcome

The Swift overlay pipeline (Darwin C include tree; ObjectiveC, Darwin, Dispatch, CoreGraphics, Foundation
overlays; SafariServices headers; Swift-plugin Flutter builds) works on the installed Swift 6.4 in the chroot.
`import Foundation` programs compile and link; a Flutter app with `shared_preferences` and `url_launcher` builds
to a `Runner-unsigned.ipa`. Nothing ran on a device.

## What ran (chroot via archrun-m.sh, builder user)

Env: `SDKFREE_HOME=/qwork/sdkfree-swift`, `SDKFREE_TBD_DIR=/qwork/tbd27`, stdlib `res/` reused from the earlier successful run, toolchain swift 6.4 (`swift-6.4-RELEASE`), iOS 27.0.1 link stubs.

- `sdk-free/swift/overlays.sh` end to end (measured wall times from the last full runs):
  - Stage 1–2 (sources, Darwin include tree): first run about 35 s including 11 shallow git clones and the AvailabilityVersions cmake generator; `darwin include tree: 1080 headers`. Cached reruns skip this stage.
  - Stage 3 (sdkm framework module maps, header fixes, apinotes): seconds.
  - Stage 4 (gyb): seconds.
  - Stage 5 (overlay modules): ObjectiveC/Darwin/Dispatch seconds; CoreGraphics seconds; Foundation about 50–95 s including the source patch step. `Foundation ok`.
  - Stage 6 (SafariServices headers/module map): seconds.
  - All five overlay modules (ObjectiveC, Darwin, Dispatch, CoreGraphics, Foundation) emit with 0 errors on Swift 6.4 and install into `res/iphoneos`.
- `tests/install-mode.sh`: 8/8 pass (`ok` on every case).
- `sdk-free/swiftc.sh` with `import Foundation` (String→NSString, Data, URL, NSArray, NSSet bridging, `print`): compiles and links, release and `-Onone`, to a Mach-O 64-bit arm64 executable in about 3 s. `llvm-otool -L` load commands: `/usr/lib/libSystem.B.dylib`, `/usr/lib/libobjc.A.dylib`, `/usr/lib/swift/libswiftCore.dylib`, `libswift_Concurrency`, `libswift_StringProcessing`, `libswift_RegexParser`, and `Foundation.framework` — every one is stub-backed in the sysroot (`tbd27`).
- Flutter app `swift-plugins-app` (`flutter create`, dependencies `shared_preferences`, `url_launcher`; plugins
  `shared_preferences_foundation` 2.5.7 and `url_launcher_ios` 6.4.2 from the pub cache) built with
  `sdk-free/flutter-build.sh` in the chroot: both Swift plugin objects compiled (`shared_preferences_foundation`
  2 files, `url_launcher_ios` 5 files), Runner linked, `Runner-unsigned.ipa` (6.8 MB, bundle id
  `dev.omarchy.swiftport.swiftplugins`, release) in about 50 s wall clock including `flutter assemble`.
- `sdk-free/swift/chk-undef.sh` on the plugin objects: `swiftplugin-shared_preferences_foundation.o` — 14
  Foundation/ObjC class symbols checked, 0 missing; `swiftplugin-url_launcher_ios.o` — 22 checked, 0 missing
  (against the iOS 27.0.1 stubs in `/qwork/tbd27`).
- Runner load commands (`llvm-otool -L`): `/usr/lib/libSystem.B.dylib`, `/usr/lib/libobjc.A.dylib`,
  `/usr/lib/swift/libswiftCore.dylib`, `/usr/lib/swift/libswift_Concurrency.dylib`, `@rpath/Flutter.framework/Flutter`,
  UIKit, Foundation, CoreFoundation, SafariServices — every system entry is stub-backed in the sysroot
  (SafariServices by the authored stub committed with this change). The generated registrant registers
  `shared_preferences_foundation.SharedPreferencesPlugin` and `url_launcher_ios.URLLauncherPlugin` by runtime name.
- Link warnings: the two plugin objects build at iOS 17.0 while the Runner declares 15.0 (ld64.lld warns; same as
  w71's measured build; set `NOSDK_SWIFT_MIN` to 15.0 to silence).

Nothing in this work ran on a device. The link stubs come from the connected-phone capture cut earlier by `sdk-free/setup.sh` (`SDKFREE_TBD_DIR`), and the symbol check compares against those stubs only.

## 6.4 deltas against w71's 6.3.3 pipeline (diagnosed, not per-site patched)

w71's working `sdkm/Frameworks/Foundation.h` and the repo headers are byte-identical where the overlay compiles, so the Int/UInt and Bool errors are importer changes in 6.4, fixed by making the generated Swift view match what Apple's SDK shows:

1. The 6.4 importer maps `NSUInteger` members to `UInt`; the 5.3 overlay sources pass `Int`. `overlay-fix-headers.py` and `Foundation.add.h` now declare the affected count/length/size members as `NSInteger` in the Swift-facing sdkm copies only (sysroot copies untouched; same ABI).
2. The 6.4 importer has no special case for the C `Boolean` typedef, so `MacTypes.h`, `CFBase.h`, and the `Boolean` typedef in `Foundation.h` now declare `_Bool` in the generated trees (imports as `Bool`).
3. `NSDataSearchOptions` needed the apinotes `SwiftName: NSData.SearchOptions` (matches `Data.SearchOptions`).
4. The 6.4 clang driver rejects two module maps defining the same `ObjectiveC` module, so the duplicate `sdkm/include/module.modulemap` is gone; the ObjectiveC module comes from the darwin tree's module map only.
5. w71's framework module maps carry `[system]` and the darwin tree carries `Dispatch.apinotes`; the port now reproduces both.

## Known open items

- `NSDictionary(dictionary:)` (the bridged `initWithDictionary:` ObjC initializer) crashes Swift 6.4 IRGen (`useFirstFieldIfTransparentUnion` in AArch64 ABI classification) during code generation of a program using it. The program compiles without that call. This is a compiler crash, not a header problem; not worked around.
- `install-toolchain.sh` step 5c is intentionally non-fatal while the pipeline is young; tighten when it has a clean install run.
- QuartzCore gets no framework module (the sysroot carries no QuartzCore headers); nothing in the current plugins imports it.
