# Swift in no-xcode mode

`install-toolchain.sh --mode no-xcode` builds Swift programs for arm64 iOS without an Xcode download.

What the installer does for Swift:

1. `sdk-free/setup.sh` cuts link stubs for the Swift runtime libraries on the iPhone (`libswiftCore`,
   `libswift_Concurrency`, `libswiftFoundation`, `libswiftUIKit` and more) into the sysroot.
2. `sdk-free/swift/build-stdlib.sh` builds the Swift module interfaces (`Swift`, `SwiftOnoneSupport`,
   `_Concurrency`, `_StringProcessing`, `_RegexParser`) with the installed swiftc. The source is the open-source
   Swift tree at the release tag that swiftc reports. The build takes about 6 minutes and needs git and python3.
3. `sdk-free/swiftc.sh [-Onone] -o out main.swift ...` compiles and links. The program uses the Swift runtime
   that is on the iPhone. The deployment target is iOS 17.0 (`NOSDK_SWIFT_MIN` changes it).

Supported now: Swift programs that import only the standard library, `_Concurrency` and `_StringProcessing`
(console programs, actors, async/await, regex).

Not supported yet: `import Foundation`, `import UIKit`, `import Darwin` and Swift Flutter plugins
(`shared_preferences_foundation`, `url_launcher_ios`). These need Swift overlay modules over the iPhone's own
frameworks. Plugins written in Objective-C work today. Use `--mode full` for Swift apps that import system frameworks.

Paths: everything lives under `$SDKFREE_HOME` (default `~/.local/share/omarchy-apple-dev/sdk-free`). Re-running a
script is safe.
