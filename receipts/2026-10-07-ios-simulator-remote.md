# Receipt: iOS app built on Linux, run in a Mac's Simulator from Linux, 2026-10-07

Claim: `tools/simctl-remote.sh` builds an xtool-style SwiftPM app for the
iOS **simulator** in the Linux chroot, installs and launches it in the
Simulator on a Mac over ssh, and returns a screenshot to the Linux host.

Verified end to end 2026-10-07 with `apps/HelloOmarchy` (SwiftUI) and
a Mac (M1 Max, macOS 26.6.2, Xcode 27.0, iOS 26.5 simulator runtime,
iPhone 17 Pro booted headless):

- Build (chroot, `swift build --swift-sdk arm64-apple-ios-simulator`):
  `Build complete! (12.70 secs)` — the darwin SDK bundle already declares the
  `arm64-apple-ios-simulator` destination.
- Link: SwiftPM refuses to ad-hoc sign executables for this destination on
  Linux ("Ad Hoc code signing is not allowed with SDK '…/swift-sdk.json'"),
  so the script links the whole-module object with the toolchain clang +
  `ld64.lld -Wl,-adhoc_codesign` + `libclang_rt.iossim`. Result:
  `Mach-O 64-bit arm64 executable`, 70,992 B; `codesign -dv` on the Mac
  accepts the lld ad-hoc signature as-is (no re-sign).
- Run: `simctl install booted` → INSTALL-OK; `simctl launch` → pid 2854;
  `simctl io booted screenshot` → PNG pulled back to Linux.
- Screenshot (`hello-sim-2026-10-07.png`, this directory): 1206x2622, shows
  the app's real UI — status bar, globe symbol, "Hello, world!" — rendered
  by the simulator on the Mac, viewed on the Linux host.

License: all Apple software (Xcode, simulator runtime) executes on Apple
hardware under the Xcode and Apple SDKs Agreement; Linux only compiles the
app and drives `simctl` over ssh (one operator, one Mac).
