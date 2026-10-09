# Receipt: Swift standard library in no-xcode mode (branch install-mode), 2026-10-09

What changed: `sdk-free/swift/build-stdlib.sh` builds the arm64 iOS modules `Swift`, `SwiftOnoneSupport`,
`_Concurrency`, `_StringProcessing` and `_RegexParser` from the Swift 6.4.0 sources that match the installed
compiler. `sdk-free/swiftc.sh` compiles and links. `sdk-free/setup.sh` cuts 13 Swift runtime link stubs from the
iPhone's shared cache. `install-toolchain.sh` runs the stdlib build as step 5b in no-xcode mode.

Checked in the Arch build chroot (swiftc `swift-6.4-RELEASE`, link stubs cut from an iOS 27.0.1 cache):

- `build-stdlib.sh`: exit 0, about 6 minutes.
- `swiftc.sh` builds three Swift console programs (plain, async/await with actors, default arguments) and a
  `-Onone` build. Each is an arm64 Mach-O, minos 17.0, with load commands libSystem, libobjc, libswiftCore,
  libswift_Concurrency, libswift_StringProcessing and libswift_RegexParser. Sizes 68 to 71 KB.
- `tools/macho-lint.py` on the signed ipas: 1 of 1 images clean for each.
- `tests/install-mode.sh`: 8 of 8.

Not checked: nothing Swift from this mode has run on a device yet (the phone test is pending). Foundation, UIKit and
Darwin overlays and Swift Flutter plugins are not ported (`sdk-free/swift/README.md`).
