# SDK-free Swift overlay port — 2026-10-09

Worktree: `/home/joshuawarren/src/omarchy-apple-dev-wt-mode`, branch `install-mode`.

## Observed

- Ran `sdk-free/swift/overlays.sh` in the Arch chroot through `/home/joshuawarren/tmp/apple-dev/archrun-m.sh --user`, with `SDKFREE_HOME=/qwork/sdkfree-swift`, `SDKFREE_TBD_DIR=/qwork/tbd27`, and the existing `swift/res` modules reused.
- Fetched the pinned source checkouts and generated the Darwin C include tree: `darwin include tree: 1080 headers`.
- Built the sdkm framework module maps and apinotes. `QuartzCore` was skipped because the test sysroot has no QuartzCore headers.
- Swift 6.4 emitted `ObjectiveC`, `Darwin`, `Dispatch`, and `CoreGraphics` modules with no errors in successful runs. Darwin includes the 5.3 Platform sources used by the overlays.
- Foundation does not emit. The latest observed errors include `Foundation.NSData.SearchOptions` not existing; `Int`/`UInt` mismatches in Data, NSSet, and NSString overlay sources; and `Bool` not converting to imported `Boolean` (`UInt8`) in `String.swift:124`.
- One attempted CF header patch used an exact whitespace pattern that did not match `CFBase.h`; this was corrected to a whitespace-tolerant match. The subsequent Foundation compile still reported the `Boolean`/`Bool` error.

## Not run / not verified

- No successful Foundation module build on Swift 6.4.
- No `swiftc.sh` Foundation program compile or Mach-O link.
- No Flutter app with `shared_preferences` and `url_launcher`; no plugin object undefined-symbol check.
- `tests/install-mode.sh` was not run.
- No device execution or device-side test.
- No commit or push has been made.
