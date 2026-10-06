# Backlog

Open work, highest priority first. Remove an entry when it ships or is dropped.

## HIGH PRIORITY 2026-10-07: macOS apps from Omarchy Linux

Joshua wants this on 2026-10-07. Build a real macOS SwiftUI/AppKit app on
Omarchy Linux with the macOS SDK from the same Xcode download. Sign it
(Developer ID or ad hoc), notarize it from Linux through the App Store Connect
notary API, and run it on a Mac (macstudio, or a lab Mac booted into macOS).
Then do the same for a real open-source Mac app, for example NetNewsWire for
Mac.

First step done 2026-10-06: a SwiftUI probe (`--swift-sdk arm64-apple-macosx`) builds
only with `--build-system native`; SwiftBuild stops with "unable to find platform for
'macosx'". lld warns that it does not support macOS, and the binary says `sdk 14.0`
(the minimum), not 27.0. Wrapped in a `.app`, signed ad hoc with rcodesign, it opened
on macstudio with its `MacHello` window. Open: SwiftBuild platform, sdk version,
Developer ID signing, notarization.

## 2026-10-07: device-run.sh --lldb breakpoint proof

Run `device-run.sh --lldb` once more on jw16 (10-minute phone window; the
shared cache for iOS 27.0.1 24A446 is already copied). Show the breakpoint hit
and `frame variable greeting launches`, then update FINDINGS.md 56 and
GETTING-STARTED.md step 3.

## iOS Simulator on Omarchy Linux

Added 2026-10-06 (lane lead request). Compare the approaches and name the
hardest blocker of each:

- A Darling-style macOS userland compatibility layer that runs CoreSimulator and
  `launchd_sim`. Likely blockers: `launchd_sim`, Metal and IOSurface for
  rendering, and the signed simulator runtimes.
- A macOS VM on an Apple Silicon Linux host that runs the Simulator. Likely
  blocker: Hypervisor access for a macOS guest from Linux.
- Any better route found during the comparison.

Then build the smallest proof for the most promising approach.
