# Receipt: LLDB on NetNewsWire iOS, built on Linux, running on an iPhone (2026-10-08)

Setup: the debug app from `CONFIGURATION=debug ship.sh --device TEAM`, signed with `tools/sign-dev.sh`, installed with
`pymobiledevice3 apps install`. LLDB is the Linux Swift 6.4 aarch64 `lldb` (the AUR `swift-bin` tarball, unpacked
into a user prefix on the phone host). The phone's Swift runtime, taken from its dyld shared cache, is the
`--sysroot`. The phone host holds the USB cable.

Session (transcript: `2026-10-08-lldb-nnw-ios-transcript.txt`):

1. `dvt launch` starts the app. `pymobiledevice3 developer debugserver lldb <bundle id>` starts LLDB and runs
   `process connect` and `process attach --pid`. LLDB stops the app at `mach_msg2_trap` on the main thread.
2. `target symbols add` loads the symbols of the local debug build. `breakpoint set -r
   SceneDelegate.*sceneDidEnterBackground` resolves to 2 locations.
3. `process continue`. Launching Settings sends the app to the background.
4. LLDB stops with `stop reason = breakpoint 1.1` in `NetNewsWire-iOS` `@objc SceneDelegate.sceneDidEnterBackground(_:)`.
   The backtrace shows the UIKitCore scene-lifecycle frames above it. `process detach` ends the session.

What did not work, and why this flow:

- A bare `lldb --batch -s file` from the same host never returned from `process connect`. The same flow under
  pymobiledevice3's pty does.
- An app launched suspended at `_dyld_start` stopped on resume with "Resume timed out". Attaching to the running app
  works. The attach takes about two minutes because LLDB reads the app's many libraries from the phone.
- A breakpoint set before `target symbols add` found no locations.
