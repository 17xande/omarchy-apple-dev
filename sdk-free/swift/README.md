# Swift in no-xcode mode

`install-toolchain.sh --mode no-xcode` builds Swift programs for arm64 iOS without an Xcode download.

What the installer does for Swift:

1. `sdk-free/setup.sh` cuts link stubs for the Swift runtime libraries on the iPhone (`libswiftCore`,
   `libswift_Concurrency`, `libswiftFoundation`, `libswiftUIKit` and more) into the sysroot.
2. `sdk-free/swift/build-stdlib.sh` builds the Swift module interfaces (`Swift`, `SwiftOnoneSupport`,
   `_Concurrency`, `_StringProcessing`, `_RegexParser`) with the installed swiftc. The source is the open-source
   Swift tree at the release tag that swiftc reports. The build takes about 6 minutes and needs git and python3.
3. `sdk-free/swift/overlays.sh` builds the framework overlay modules (`ObjectiveC`, `Darwin`, `Dispatch`,
   `CoreGraphics`, `Foundation`) so `import Foundation` works and Swift Flutter plugins compile. Sources are
   fetched at run time from pinned tags: the Darwin C headers and CoreFoundation headers from
   apple-oss-distributions, the Foundation/Dispatch overlay sources from the Swift tree at
   `swift-5.3-RELEASE` (patched by `mk-foundation-src.py` and the patches in `overlay/`). Needs git, cmake and
   python3. Output installs next to the standard library in `$SDKFREE_HOME/swift/res`.
4. `sdk-free/swiftc.sh [-Onone] -o out main.swift ...` compiles and links. The program uses the Swift runtime
   and the frameworks that are on the iPhone. The deployment target is iOS 17.0 (`NOSDK_SWIFT_MIN` changes it).
5. `sdk-free/flutter-build.sh` compiles Swift Flutter plugins found in the app's `.flutter-plugins-dependencies`
   and registers them by runtime class name; `sdk-free/swift/chk-undef.sh` checks a plugin object's
   Foundation/ObjC symbols against the sysroot stubs.

Supported now: standard-library programs; `import Foundation` programs (String/NSString, Data, URL, NSArray,
NSSet bridging); Flutter apps whose plugins are Swift (`shared_preferences_foundation`, `url_launcher_ios`) or
Objective-C, release and debug.

Not supported: `import UIKit` Swift code beyond what the plugins use through the imported headers, overlays for
other frameworks (Combine, WebKit, ...), and `NSDictionary(dictionary:)` calls in user code (a Swift 6.4 IRGen
crash, receipts/2026-10-09). The SafariServices headers are written for `url_launcher_ios`. Nothing here runs on
a device; the linker only proves that every referenced symbol exists in the stubs cut from the phone.

Paths: everything lives under `$SDKFREE_HOME` (default `~/.local/share/omarchy-apple-dev/sdk-free`). Re-running a
script is safe: finished stages are skipped.
