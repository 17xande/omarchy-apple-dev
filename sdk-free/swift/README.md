# Swift in no-xcode mode

`install-toolchain.sh --mode no-xcode` builds Swift modules for arm64 iOS without an Xcode download. The installer builds the standard-library modules, then `sdk-free/swift/overlays.sh` fetches pinned source trees and attempts to build the ObjectiveC, Darwin, Dispatch, CoreGraphics, and Foundation overlays.

The standard-library modules (`Swift`, `SwiftOnoneSupport`, `_Concurrency`, `_StringProcessing`, `_RegexParser`) build from the Swift release tag that the installed `swiftc` reports. `sdk-free/swiftc.sh` compiles and links standard-library-only programs. The deployment target is iOS 17.0 by default; `NOSDK_SWIFT_MIN` changes it.

## Overlay status

On Swift 6.4, the Darwin C include tree and the ObjectiveC, Darwin, Dispatch, and CoreGraphics modules built in the chroot. The Foundation overlay does not yet build. The current compiler errors include mismatched `Int`/`UInt` imports in the Swift 5.3 Foundation sources and a `Boolean`/`Bool` mismatch in `CFStringCreateWithBytes`. `overlays.sh` stops on the Foundation errors. Do not use the overlay build as a completed Foundation or Swift-plugin toolchain yet.

The SafariServices header and link stub are authored for `url_launcher_ios`. A successful `Runner-unsigned.ipa` build with Swift plugins has not been verified. Nothing has run on a device.

The runtime libraries remain on the iPhone. `sdk-free/setup.sh` supplies their link stubs. The overlay build requires `git`, `cmake`, the Swift source cache created by `build-stdlib.sh`, and network access to the pinned public source repositories. Output stays under `$SDKFREE_HOME` (default `~/.local/share/omarchy-apple-dev/sdk-free`).
