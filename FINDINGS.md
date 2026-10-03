# Findings: getting an iOS build and debug loop working on Omarchy Linux

Everything below came out of one session on 2026-09-09, taking a 13" M1 MacBook Pro
running Omarchy from a bare install to a SwiftUI app running and debuggable on an
iPhone 16 Pro Max (iOS 26.6.1). Fourteen things broke in the first run, and a
fifteenth surfaced on 2026-09-16, with items 16-20 following the same day;
item 21 came from the 2026-09-17 mise retest, and item 22 from the 2026-10-03
retest on xtool 1.20.1, which supersedes items 15 and 16. Item 23 is the App
Store path (build, sign, validate; upload unproven).
Each is recorded with the error text, the root cause where it was found, and the fix. `install-toolchain.sh`
applies every fix that can be automated (items 1 to 7); only Apple ID sign-in and
sudo consent genuinely need a human.

Versions of the first run: Swift 6.3.3 (AUR `swift-bin`), xtool 1.19.0, LLDB 21.0.0,
pymobiledevice3 from PyPI, iPhoneOS SDK 26.5 taken from Xcode 26.6. Current
working set (item 22): swift-bin 6.4.0, xtool 1.20.1, iPhoneOS SDK 27.0 from Xcode 27.0.

Confirmed on x86_64 (community report, Jon Kinney, 2026-09-15): the same flow
works on a Framework Desktop with an iPhone 16, used for a real client project.

## Toolchain

**1. No Swift in the Omarchy or Arch repos.** AUR `swift-bin` is the binary package:
about 3.3 GB installed, roughly 7 minutes. It ships clang and LLDB too.

**2. LLDB will not start: `libpython3.9.so.1.0: cannot open shared object file`.**
`swift-bin` lists a matching `python3xx` as an optional dependency and LLDB is the
thing that needs it; the install script reads that note off the installed package
and installs it (python39 through 6.3.x, python312 from 6.4).

**3. `usbmuxd.socket` does not exist on Arch.** Guides tell you to enable it.
`usbmuxd.service` is static here and udev starts it when a device is plugged in.
Nothing to enable; `systemctl is-active usbmuxd` reads `active` once the phone is
connected.

## SDK

**4. `xtool sdk install` dies partway through copying.** It failed at 76,600 files
with `NSCocoaErrorDomain Code=513 "You don't have permission to save the file"`
while copying `/usr/lib/clang/22/include/fuzzer`. Root cause: swift-corelibs
`FileManager.copyItem` preserves ownership, so it calls `lchown` to root, which is
EPERM for a normal user. Fix: take ownership of the toolchain trees first,
`sudo chown -R "$USER:" /usr/lib/clang /usr/lib/swift` (the colon matters:
copyItem restores the group too, so it must be the user's login group). The
install script did this automatically before the SDK install. Obsolete since xtool
1.19.2 (xtool PR #255 copies with `preserveOwner: false`); the script no longer
touches ownership (item 22).

**5. The SDK installs "successfully" and then SwiftUI will not compile.** The error
is `size of '__builtin_bit_cast' source type 'int' does not match destination type
'int64_t'` inside the simd/arm_neon C++ module. Root cause: xtool copies the clang
headers it finds on PATH into the SDK bundle. The system clang here is 22.1.8 while
the Swift compiler's own clang frontend is 21.0.0, and the headers are not
compatible across that gap. Fix: run the SDK install with the toolchain's clang
first on PATH. The install script puts the bin directory of the `swift` on PATH
first (`/usr/lib/swift/bin` on swift-bin 6.3, `/usr/lib/swift/usr/bin` on 6.4).

**6. A poisoned module cache survives the fix.** After rebuilding the SDK correctly,
the same project in the same directory kept failing with the same error. Fix: build
in a clean project directory, or delete `.build/arm64-apple-ios` before rebuilding.
The install script prints this cleanup note after the SDK install.

**7. No `.xip` and no Apple ID are needed for the SDK.** xtool 1.19.0 accepts a path
to an extracted `Xcode.app` directory, not only an `Xcode.xip`
(`SDKCommand.swift`: "Path to Xcode.xip, Xcode.app, or darwin.xtoolsdk"). If any
machine on your network has Xcode installed, stream the pieces xtool wants (about
3 GB) instead of downloading a multi-gigabyte archive behind a sign-in.

## Signing and install

**8. `xtool auth` password mode works with a free Apple ID.** Mode 1 uses private
APIs; mode 0 wants a paid membership and an API key. 2FA is prompted once. If your
Apple ID belongs to more than one team, it asks which team to sign under.

**9. `xtool dev run` is the whole loop.** Build, unpack, prepare device, provision,
sign, package, connect, install, verify. It took 11 seconds on this M1 with a warm
build, and the app launched on the phone with no further steps.

## Debugging, iOS 17 and later

These four are the ones that cost the most time, because the tools report the same
generic error for several different unmet prerequisites.

**10. `pymobiledevice3 developer debugserver start-server` fails on iOS 26**, even
with `--rsd` passed correctly. It prints a five-item list of possible causes, none
of which applies. Use `pymobiledevice3 developer debugserver lldb <bundle-id>
--rsd <address> <port>` instead: it starts debugserver and drives LLDB itself.

**11. The same generic error appears when the personalized developer image is not
mounted.** Check with `pymobiledevice3 mounter list` (an empty `[]` means nothing is
mounted), then `pymobiledevice3 mounter auto-mount`. It fetches a personalized image
through TSS and mounts it in a few seconds.

**12. `debugserver lldb` takes the bundle id as a positional argument.** There is no
`--bundle-id` option; passing one exits 2.

**13. The RemoteXPC tunnel needs root.** `sudo pymobiledevice3 lockdown start-tunnel`
creates `tun0` and prints the RSD address and port to pass to every later
`--rsd` call. Without sudo it cannot create the interface.

**14. Expect a long wait on attach, not a hang.** LLDB parses symbol tables out of
the device's shared cache before the process stops. On this 16 GB M1 that took about
90 seconds, printing a long stream of "Reading binary from memory" lines. The
successful result looks like this:

```
Attaching to pid 45977
platform select remote-ios
process connect connect://[fd57:f2c9:d44a::1]:63592
process attach --pid 45977
* thread #1, queue = 'com.apple.main-thread', stop reason = signal SIGSTOP
```

## Known regression, 2026-09-16 (superseded 2026-10-03 by item 22)

**15. Swift 6.4.0 cannot build against the xtool darwin SDK.** AUR `swift-bin`
6.4.0 installs fine, the SDK registers fine (`swift sdk list` prints `darwin`),
and then every app build dies at planning with `error: unable to find platform
for 'iphoneos'`. Proven by an isolated A/B on one machine, one user, one SDK
bundle: the build fails under 6.4.0 with both xtool 1.19.0 and 1.19.2, and
succeeds the moment the system runs swift-bin 6.3.3 again. The bundle metadata
is identical in both cases (schemaVersion 4.0, same toolset.json), so the
regression is on the SwiftPM side. Workaround: run swift-bin 6.3.3 (build it
from the AUR package's git history). Confirmed on aarch64 and x86_64 with xtool
1.19.x. xtool 1.20 fixed it (item 22).

**16. The streamed SDK's Xcode must match the Linux Swift version.** The SDK
pieces carry Apple's prebuilt swiftmodules, and the Linux compiler refuses a
module built by a newer Apple Swift: an iOS 27.0 SDK from Xcode 27 (Apple
Swift 6.4) fails under swift 6.3.3 with `this SDK is not supported by the
compiler (the SDK is built with 'Apple Swift version 6.4 ...', while this
compiler is 'Swift version 6.3.3 ...')`. The matrix, all tested 2026-09-16:

| Linux toolchain | SDK source | Result |
|---|---|---|
| swift 6.3.3 | Xcode 26.6 (iOS 26.5) | builds; Mach-O produced |
| swift 6.3.3 | Xcode 27 (iOS 27.0) | rejected: SDK built by Apple Swift 6.4 |
| swift 6.4.0 | Xcode 26.6 (iOS 26.5) | planning failure, item 15 |
| swift 6.4.0 | Xcode 27 (iOS 27.0) | planning failure, item 15 |

Rule: the SDK's Xcode must ship the same Swift minor as the Linux toolchain:
Xcode 26 for Swift 6.3, Xcode 27 for Swift 6.4. On xtool 1.20.1, swift 6.4.0 +
Xcode 27 builds (item 22); swift 6.4.0 + Xcode 26.6 was not retested.

## Toolchain swaps, 2026-09-16

**18. makepkg and SwiftPM can fill /tmp's tmpfs.** On Omarchy, /tmp is a
small tmpfs (4 GB here). Unpacking AUR sources (swift-bin is ~800 MB
compressed, 3.3 GB installed) or building a SwiftUI app dies mid-extract
with `I/O error 122` / `No space left on device` when it fills. Fix: point
TMPDIR at the real disk — `TMPDIR=$HOME/tmp makepkg -si`; the same variable
covers SwiftPM's scratch files.

**19. Toolchain swaps (mise/asdf/manual) used to end in a full multi-GB
reinstall; `install-toolchain.sh --repair` now recovers from cache.**
Tested on a fresh x86_64 Omarchy VM by pinning swift 6.3.3 at /usr/lib/swift
(AUR swift-bin), registering the SDK, then removing that package and running
swift from a second install under
~/.local/share/mise/installs/swift/6.3.3 (the layout mise would create).

What survives a swap by design: USB pairing (`~/.pymobiledevice3/`), Apple
ID auth (`~/.local/share/xtool/`), and even the SDK registration itself —
the bundle in `~/.swiftpm/swift-sdks/darwin.artifactbundle` is user-global
and its metadata uses bundle-relative paths (`toolset.json`:
`"rootPath": "toolset/bin"`, `"linker": {"path": "ld64.lld"}`; the absolute
paths live only in `swift sdk configure --show-configuration` output,
resolved at use time). After the swap, `swift sdk list` still prints
`darwin` and a clean project still builds end to end.

What actually breaks:

1. **mise cannot complete a Swift install on Omarchy** — see item 20.
   As of 2026-09-17 the URL bugs are fixed on mise main; the remaining
   wall is `libncurses.so.6` (Arch ships `libncursesw.so.6` only). A
   "clean mise swap" on Omarchy still means AUR `swift-bin` at a
   different path, or a swift.org tarball plus that soname.
2. **The project-side module cache**: after any toolchain change, building
   in an existing project can die on stale precompiled modules — same
   failure class as item 6. Fix: delete that project's `.build`.
3. **Loss of the SDK registration** (`swift sdk remove darwin`, a wiped
   `~/.swiftpm`, a partial install) used to require the `Xcode.xip` again —
   and users delete the .xip after installing, so recovery meant
   re-downloading 3 GB from Apple behind a sign-in. That was the reinstall
   circus.

The fix in `install-toolchain.sh`: the SDK step now runs `xtool sdk build`
once and keeps the resulting portable bundle at
`~/.cache/xtool/darwin-<xcodever>.xtoolsdk`; the registered copy is made
FROM that cache, so first install and every later repair exercise the same
path. Whenever `swift sdk list` lacks darwin on a re-run, the script
re-registers from the cache — no .xip, no network.
`install-toolchain.sh --repair` does just that part, against whatever
toolchain the current shell resolves (mise included), verifies pairing and
auth, prints a survive-status summary (SDK source used / pairing path /
auth state), and exits nonzero with instructions when the cache is missing
and no XCODE_XIP is given. The version matrix (items 15-16) still applies:
--repair re-registers the same bundle; it cannot make a 6.4.0 toolchain
consume an Xcode 26.x SDK.

## Working sequence

```bash
# once
./install-toolchain.sh          # handles python dep, fuse3, PATH, SDK install
xtool auth                      # mode 1, Apple ID, 2FA, pick team

# per app; the toolchain's own bin dir first (item 5)
export PATH="$(dirname "$(readlink -f "$(command -v swift)")"):$PATH"
xtool new HelloOmarchy && cd HelloOmarchy
xtool dev run

# debugging, phone connected, Developer Mode on
pymobiledevice3 mounter auto-mount
sudo pymobiledevice3 lockdown start-tunnel     # note the RSD address and port
pymobiledevice3 developer debugserver lldb <bundle-id> --rsd <address> <port>
```

## Where it stands

Closed 2026-09-10, after this list was written: the source-level breakpoint.
`ContentView.describe(tick:)` at `ContentView.swift:27` was hit on device, source
lines printed, `p tick` returned `(Int) 1`. A static SwiftUI app still cannot be
breakpointed usefully: instrument the app with a `.task` timer loop so execution
reaches the breakpoint without a physical tap. Single-stepping is untested
(`next` reported an unchanged frame line, inconclusive) and needs the phone
connected for five minutes.

New on 2026-09-16 (Milestone 3): `install-toolchain.sh` applies items 1 to 7 by
itself and was proven end to end by a fresh-user install on a second M1 Omarchy
machine and in a clean x86_64 Arch container, through `swift sdk list` and a
Mach-O sample build. `device-run.sh` gained a `--network` mode (same-LAN
wireless deploy, xtool native) and an `--rsd HOST PORT PKG` mode (install to an
explicit address); both are written from the tool sources and are UNVERIFIED
until run against a phone.

**17. Wireless deploy on iOS 26 requires a host-specific RemotePairing tunnel that only a Mac can currently establish (tested exhaustively 2026-09-16).** With Developer Mode on, USB-paired, unlocked, same SSID/subnet, `EnableWifiConnections` true, an active USB RSD tunnel (`lockdown start-tunnel` succeeded), and DDI mounted, an iPhone on iOS 26.6.2 never becomes wirelessly deployable from Linux: pulling the USB cable kills the tunnel and nothing re-establishes over WiFi.

What the phone actually does on the network: every host that wants wireless debugging gets its OWN encrypted RemotePairing tunnel, advertised per-host as `<uuid>._rp-tunnel._tcp` with an ephemeral port (observed 55518/55520) on IPv6 link-local/ULA addresses. A macOS host that once enabled "Connect via Network" holds a live tunnel (devicectl: Transport `localNetwork`) — the phone accepts only that host; connections from other IPs to the tunnel port are refused. The pre-iOS-17 paths are dead on 26.6.2: `_remoted._tcp` is advertised only over USB; legacy `_apple-mobdev2._tcp` is advertised but its listener (tcp/32498) never binds; tcp/62078 accepts and then resets the lockdown handshake; usbmuxd2's WiFi heartbeat fails on the same wall. `pymobiledevice3 remote pair` needs the device to advertise `_remotepairing-manual-pairing._tcp`, which no iOS 26.6.2 settings screen we could find produces (the `remote pair-host` device-initiated flow is iOS 27+).

Practical guidance: use USB (proven end to end by this repo). Wireless works only for hosts the phone already tunneled with via a Mac/Xcode; for that case `pymobiledevice3 remote tunneld` on a Mac that holds the tunnel, plus `--tunnel UDID@HOST:PORT` from Linux, is the bridge pattern (documented in device-run.sh). The Linux side is otherwise ready: with usbmuxd2 (AUR `usbmuxd2-git` + the -git libimobiledevice stack) and pymobiledevice3, a future iOS that reopens device-side pairing needs zero new plumbing here.

**Update (same day, researched after the verdict):** the iOS 27 door is
already implemented client-side. `pymobiledevice3 remote pair-host`
advertises this machine as a pairable host; on an iOS 27 device with
Developer Mode on, Settings → Developer → **Paired Macs** shows it under
"Other Devices" — tap, enter the printed 6-digit code, and the pairing
record is reused by `remote start-tunnel` for the wireless tunnel. All of
that ships in pymobiledevice3 11.12+ (the version this repo installs).
Untested here only because no iOS 27 device was on hand.


**20. mise's swift backend is broken on Omarchy — two distinct bugs (tested
2026-09-16, mise 2026.8.8).** (1) For distros outside its known map
(ubuntu/amzn/ubi/fedora), `src/plugins/core/swift.rs` builds the artifact
platform as the raw `os-release` `ID`+`VERSION_ID`, producing
`swift-6.3.3-RELEASE-omarchy4.0.1rc2-aarch64.tar.gz` → download.swift.org
404. Omarchy's `ID_LIKE=arch` is ignored. (2) On arm64, the download
directory only gets its required `-aarch64` suffix for ubuntu builds
(`platform_directory()`), so even with `mise settings set swift.platform
ubi9` the URL misses (`ubi9/…` 404s; the artifact lives under
`ubi9-aarch64/`). URL matrix verified against download.swift.org: x64
ubuntu2404/ubi9/fedora39 = 200; arm64 only `ubuntu2404-aarch64` = 200.
With `swift.platform=ubuntu24.04` on arm64 the download succeeds but mise's
runtime verification fails on Arch (`bin/swift` exit 127) and the install
rolls back — likely a shared-library mismatch in the ubuntu build. Filed upstream:
https://github.com/jdx/mise/discussions/13289 (fabricated names, ID_LIKE ignored)
and /13291 (arm64 directory suffix).

**Update 2026-09-17, retest on jwm1 (Omarchy 4.0.1rc2 aarch64).** jdx
merged [#13293](https://github.com/jdx/mise/pull/13293) (directory suffix)
and [#13297](https://github.com/jdx/mise/pull/13297) (release-index +
`ID_LIKE` + UBI fallback). Neither is in a tagged release yet: latest tag
`v2026.9.10` published 2026-09-16 17:25Z, before both merges. Retested
with a git build at `533346cc` (crate still reports 2026.9.10, built
2026-09-17).

Control, system mise 2026.8.8: still 404s on
`swift-6.3.3-RELEASE-omarchy4.0.1rc2-aarch64.tar.gz`.

Git build: warns `swift 6.3.3 publishes no build for omarchy 4.0.1rc2; using ubi9`,
then downloads
`https://download.swift.org/swift-6.3.3-release/ubi9-aarch64/swift-6.3.3-RELEASE/swift-6.3.3-RELEASE-ubi9-aarch64.tar.gz`
(the `-aarch64` directory 13291 asked for). Extract succeeds. Post-install
`swift --version` then fails:
`error while loading shared libraries: libncurses.so.6`. Arch/Omarchy
ships `libncursesw.so.6` only; `/usr/lib/libncurses.so.6` is absent.
mise rolls the install back. This is the third issue jdx asked confirmed
in #13289: the ubi9 artifact does not run on Arch as-is.

Status: 13289 and 13291 are fixed on main. The runtime failure is a
narrow-vs-wide ncurses naming split, not a mise bug — and it is
solvable; see item 21.

**21. mise CAN install and run Swift on Omarchy: the ubi9 build needs three
narrow curses sonames Arch does not ship (proven 2026-09-17, jwm1).**

Every missing soname in the whole ubi9 6.3.3 toolchain, found by `ldd`-ing
all of `usr/bin` and `usr/lib/*.so*`:

| ubi9 binary wants | Arch ships |
|---|---|
| `libncurses.so.6` | `libncursesw.so.6` |
| `libform.so.6` | `libformw.so.6` |
| `libpanel.so.6` | `libpanelw.so.6` |

Three, all with wide-char twins. (`libtinfo.so.6` is already present on
Arch; `/usr/lib/libncurses.so` is an 18-byte linker script, not a runtime
library.) Arch's wide-only ncurses is deliberate policy; Debian/Ubuntu
ship one wide-compiled ncurses that provides *both* sonames, which is why
the vendor tarball runs there and not here.

The substitution is sound, not a gamble: `liblldb.so` imports **zero**
wide-char curses symbols (`_wch`/`_wstr`/`cchar` count = 0) — only the
narrow subset the wide build also exports — it records **no symbol-version
requirement** on any of the three, and `ldd -r` against the wide libs
resolves everything with no undefined symbols and no version warnings.

Shipped as `install-toolchain.sh --curses-compat` (2026-09-17): it aliases
whichever narrow curses sonames the host lacks to their wide twins in
`~/.local/lib/curses-narrow-compat`, optionally verifies an extracted
toolchain root with `ldd -r`, and prints the export line. No root, no
`/usr/lib` mutation.

```bash
./install-toolchain.sh --curses-compat
export LD_LIBRARY_PATH=~/.local/lib/curses-narrow-compat
mise install swift@6.3.3
```

Verified on that path with the `533346cc` build: `mise install swift@6.3.3`
passes its own `swift --version` gate (`Swift version 6.3.3
(swift-6.3.3-RELEASE)`, `Target: aarch64-unknown-linux-gnu`), `mise ls
swift` lists 6.3.3, `lldb --version` reports 21.0.0, and
`mise exec swift@6.3.3 -- swift build` builds a SwiftPM executable in
1.47 s.

`LD_LIBRARY_PATH` must reach the install subprocess. Two supported ways on
mise main (b467f28c, 2026-09-18, all four fixes merged and live-verified on
a second Omarchy arm64 host): the shell export shown above, or the tool
option jdx named as the supported knob —

```toml
[tools]
swift = { version = "6.3.3", install_env = { LD_LIBRARY_PATH = "{{env.HOME}}/.local/lib/curses-narrow-compat" } }
[env]
LD_LIBRARY_PATH = "{{env.HOME}}/.local/lib/curses-narrow-compat"
```

`install_env` covers the install-time verification (its values now render
templates, mise #13314); `[env]` covers runtime exec. `[env]` alone was
never applied to install subprocesses — by design, since `[env]` may depend
on tools that are not installed yet. Bare installs now fail with every
missing soname named at once (`this swift build needs shared libraries
missing from this host: libform.so.6, libncurses.so.6, libpanel.so.6`,
mise #13315/#13319) instead of a bare exit 127. Not in a tagged mise
release yet; main only.

Two more host notes from the second machine: current Arch also needs
`libxml2.so.2` aliased to `.so.16` for `swift-package`/`swift-build`
(resolves clean under `ldd -r`; xml-heavy lldb features unexercised), and
`lldb` needs a real `libpython3.9.so.1.0` — genuinely not aliasable
(`_Py_IsFinalizing` no longer exists in python 3.14); copy it from the
Rocky/Alma 9 `python3-libs` rpm if absent.


Residual risk, closed 2026-09-18: the curses TUI itself was the remaining
unknown and it PASSES. On jw16 (M1 Max, Omarchy arm64) the ubi9 lldb ran
`gui` under the aliases: full chrome rendered (menu bar, Sources/Threads
panes), F1 opened the dropdown menu, arrow+Enter selection worked, and
Exit returned cleanly to the `(lldb)` prompt. Draw, input, and teardown
all run through the wide libraries.

Two host-package notes from that machine, distinct from the ncurses
shim: current Arch ships libxml2 `.so.16` (2.15) so the ubi9 lldb also
needs a `libxml2.so.2` alias — empirically clean (`ldd -r` resolves, no
xml-symbol failures; loader prints harmless "no version information"
warnings) but xml-dependent lldb features are unexercised. And it needs
a REAL `libpython3.9.so.1.0` — no alias works there (`_Py_IsFinalizing`
is gone from python 3.14; genuine ABI break). On this install python39
is already present via swift-bin's dependency chain; machines without it
can copy `libpython3.9.so.1.0` from the Rocky/Alma 9 `python3-libs` rpm
into the compat directory.


This does not change what this repo installs. AUR `swift-bin` already did
the same reconciliation properly at package level — its `swift` links
`libncursesw.so` directly — and it remains `install-toolchain.sh`'s path.
Items 15 and 16 are superseded by item 22 (xtool 1.20.1 + Swift 6.4 + Xcode 27).

## xtool 1.20, 2026-10-03

**22. xtool 1.20.1 + swift-bin 6.4.0 + Xcode 27 builds; the 6.3.3 pin is over.**
xtool 1.20.0 (2026-09-21) added Swift 6.4 support by driving SwiftBuild instead
of SwiftPM's `--swift-sdk` path, which is where item 15's planning failure lived.
Retested in a clean Arch x86_64 root (archlinux-bootstrap, 2026-10-03) with the
repo's own `install-toolchain.sh` as a brand-new user, SDK pieces streamed from
an Xcode 27.0 (27A266a) install:

| Linux toolchain | xtool | SDK source | Result |
|---|---|---|---|
| swift-bin 6.4.0-2 | 1.20.1 | Xcode 27.0 (iOS 27.0) | debug and release build; Mach-O arm64 |

Three install-path changes fell out of the retest:

1. swift-bin 6.4.0-2 moved the toolchain binaries to `/usr/lib/swift/usr/bin`.
   A hardcoded `/usr/lib/swift/bin` leaves clang off PATH, and `xtool sdk
   install` stops with `Error: Could not find executable 'clang' in PATH`.
   Both scripts now derive the directory from `readlink -f $(command -v swift)`,
   which also covers mise installs.
2. The step 3 chown (item 4) is not needed with xtool 1.20.1: the fresh user
   built and registered the SDK while `/usr/lib/swift` stayed `root`-owned.
   The old step also died on hosts without a system clang
   (`chown: cannot access '/usr/lib/clang'`), so it is deleted.
3. The xtool AppImage runtime needs `fusermount3` (`Error: No suitable
   fusermount binary found on the $PATH`); the script installs `fuse3`.

xtool 1.20's SDK builder also reads `Contents/Info.plist`, `version.plist` and
each `Platforms/*.platform/Info.plist`; the Route B piece list now includes them.
The SDK cache is named after the iOS SDK inside it
(`darwin-iPhoneOS27.0.xtoolsdk`) instead of the input file name. The version
rule of item 16 still holds: Xcode 27 for Swift 6.4, Xcode 26 for Swift 6.3.
Device install and LLDB on this pair are not yet re-run on hardware.
Receipt: `receipts/2026-10-03-xtool-1.20-swift-6.4-x86_64.md`.

## App Store path, 2026-10-03

**23. An App Store `.ipa` can be built, signed and validated on Linux; the
upload itself is unproven.** xtool signs only with development profiles and
compiles no asset catalogs, so `ship.sh` adds the rest. Proven in the clean
Arch x86_64 root by a brand-new user: `install-toolchain.sh`, `xtool new`, a
single-size 1024 AppIcon, `ship.sh` → 35/35 offline checks pass. Apple's own
tools on a Mac accept the result: `codesign --verify --deep --strict` reports
`valid on disk` and `satisfies its Designated Requirement`, `codesign -dvvv`
shows `TeamIdentifier`, sealed resources v2 and the entitlements, and
`assetutil --info` parses the `Assets.car`. Each validator check also fails
on a deliberately broken build (no team id, Info.plist edited after
signing, `get-task-allow` true, no Assets.car or profile).

What had to be built, and why:

1. **App icon.** xtool has no `.xcassets` support (xtool#219). AssetKit 1.0.0
   (xtool-org) compiles catalogs, but rejects Xcode 14+'s default
   single-size icon (`AppIcon 'AppIcon' declares size 1024x1024 but no
   source file matched`), and does not resize. `tools/xcassets` expands that
   form into 60@2x, 60@3x, 76@2x and the 1024 App Store icon (no alpha
   channel, ITMS-90717) and then calls AssetKit.
2. **iPad Pro icon (open).** AssetKit sets every app icon's "Icon Index" to
   1, so 76@2x and 83.5@2x get the same rendition key and only one survives
   lookup (`assetutil` shows two 152 px pad renditions). `actool` from Xcode
   27 on the same images gives Icon Index 1 (60), 2 (76), 3 (83.5) and
   5 (1024), plus one "MultiSized Image" entry per idiom, which AssetKit
   does not emit. Until AssetKit keys icons by size, iPad apps fail the
   167 px check; iPhone-only apps pass.
3. **Build-environment keys.** App Store processing reads `DTXcode`,
   `DTXcodeBuild`, `DTSDKName`, `DTSDKBuild`, `DTPlatform*`, `DTCompiler`;
   xtool writes none. `asc.py stamp` takes the SDK values from the darwin
   bundle and the Xcode values from `Contents/version.plist`, which
   `install-toolchain.sh` now keeps next to the SDK cache. A `.xip` install
   hides that file: set `XCODE_VERSION` and `XCODE_BUILD`.
4. **Distribution signing.** `rcodesign` 0.29.0 (pinned, checksummed) signs
   with any key, certificate and entitlements. Without `--team-name` the
   CodeDirectory carries no team id (`TeamIdentifier=not set` in
   `codesign -dvvv`); `ship.sh` passes it from the profile.
5. **Identity.** With an App Store Connect key, `asc.py identity` creates an
   Apple Distribution certificate from a CSR made on this machine and an
   `IOS_APP_STORE` profile. Without one, `asc.py test-identity` makes a
   self-signed stand-in of the same shape, which is what the run above
   used.
6. **Upload.** The App Store Connect API has a build-upload resource
   (`POST /v1/buildUploads`, `POST /v1/buildUploadFiles`, chunked `PUT`s,
   `PATCH uploaded`, then poll for `COMPLETE`/`FAILED` with Apple's errors),
   so no Transporter and no macOS. `/v1/apps` is GET-only, so the app record
   is a one-time web step. A throwaway key unknown to Apple gets a clean
   `401 NOT_AUTHORIZED`, which proves the token and HTTP path up to auth.

Unproven until a real key and app record exist: certificate and profile
creation, Apple's processing of a Linux-built `.ipa` (DT keys, an
AssetKit `Assets.car` without MultiSized entries, rcodesign's
Apple-certificate signature), and a TestFlight install.
Receipt: `receipts/2026-10-03-ship-offline-validation.md`.
