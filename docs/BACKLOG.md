# Backlog

Open work, highest priority first. Remove an entry when it ships or is dropped.

## HIGH PRIORITY 2026-10-07: macOS apps from Omarchy Linux

Joshua wants this on 2026-10-07. Build a real macOS SwiftUI/AppKit app on
Omarchy Linux with the macOS SDK from the same Xcode download. Sign it
(Developer ID or ad hoc), notarize it from Linux through the App Store Connect
notary API, and run it on a Mac (macstudio, or a lab Mac booted into macOS).
Then do the same for a real open-source Mac app, for example NetNewsWire for
Mac.

First step done 2026-10-06: a SwiftUI probe builds for `arm64-apple-macosx14.0` with
SwiftBuild when it gets xtool's settings (`--toolset <bundle>/toolset-swb.json`,
`XCODE_EXTRA_PLATFORM_FOLDERS=<bundle>/Developer/Platforms`, `<bundle>/toolset/bin`
first on PATH); without them it stops with "unable to find platform for 'macosx'".
The binary says `sdk 14.0` (the minimum), the same link issue as iOS (ITMS-90725), but
`asc.py stamp` fixes only iOS load commands. Wrapped in a `.app` and signed ad hoc
with rcodesign, it opened on macstudio with its `MacHello` window. Open: sdk stamp for
macOS, Developer ID signing, notarization, NetNewsWire for Mac.

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
