# Build and deploy iOS apps on Omarchy Linux (Apple Silicon and x86_64)

SwiftUI apps built on Omarchy Linux, installed on a physical iPhone over USB,
with no Xcode and no macOS in the loop.

Based on a first successful run on 2026-09-09 with:

| Tool | Version | Source |
|------|---------|--------|
| Swift | 6.3.3 (aarch64-unknown-linux-gnu) | AUR `swift-bin` |
| xtool | 1.19.0 | xtool-org/xtool AppImage |
| pymobiledevice3 | latest from PyPI at install time | venv |
| LLDB | 21.0.0 (Swift toolchain) | bundled with `swift-bin` |
| iOS SDK | iPhoneOS 26.5 | Xcode 26.6 on a Mac, streamed as a directory |

Confirmed on x86_64 (community report, Jon Kinney, 2026-09-15): the same flow
works on a Framework Desktop with an iPhone 16, used for a real client project.

Works with a free Apple ID. Paid membership not required for device installs.

## What you need

- An Apple Silicon or x86_64 Linux box running Omarchy (Arch-based). Both
  architectures are covered: AUR `swift-bin` ships aarch64 and x86_64, and
  xtool publishes an AppImage for each.
- An iOS device and a USB cable.
- An Apple ID (free) for **one download from Apple**: `Xcode.xip` from
  developer.apple.com. The download works from any OS — no Mac, no macOS
  install, and no Xcode install anywhere is needed. The iOS SDK artifacts
  exist only inside Apple's Xcode distribution, so this one download is the
  only external requirement that cannot be automated away.

Version matching matters: the SDK pieces must come from an Xcode whose Swift
matches the installed `swift-bin` (Xcode 26.x for swift 6.3.3 — see
FINDINGS.md item 16), and swift-bin 6.4.0 is not yet usable (item 15).
Download **Xcode 26.x, not 27**.

## Install

```
git clone https://github.com/joshuaswarren/omarchy-apple-dev
cd omarchy-apple-dev
./install-toolchain.sh
```

The script installs the toolchain, applies the SDK-install workarounds
(toolchain-tree ownership, toolchain clang first on PATH), and tells you
exactly what is left if anything is. Safe to re-run. When it stops at the SDK
step, download `Xcode 26.x .xip` from
https://developer.apple.com/download/all/?q=Xcode and re-run:

```
XCODE_XIP=/path/to/Xcode.xip ./install-toolchain.sh
```

Verify with `swift sdk list` (should print `darwin`).

Already have a Mac with a matching Xcode? You can stream just the ~3 GB of
SDK pieces xtool needs instead of the full .xip — see Route B in
`install-toolchain.sh` section 6. Optional; the .xip route above needs no Mac.

## Toolchain swaps (mise/asdf/manual)

Note on mise: its two swift-backend URL bugs are fixed on mise main
([#13293](https://github.com/jdx/mise/pull/13293),
[#13297](https://github.com/jdx/mise/pull/13297)) but not in a tagged
release as of 2026-09-17. With a build past those, `mise install swift`
does work on Omarchy once you supply three curses sonames Arch names
differently (FINDINGS 21):

```
./install-toolchain.sh --curses-compat
export LD_LIBRARY_PATH=~/.local/lib/curses-narrow-compat
mise install swift@6.3.3
```

`--curses-compat` aliases every narrow curses soname the host is missing to
its wide twin inside `~/.local/lib/curses-narrow-compat` (nothing under
`/usr/lib` is touched) and prints the export line. Pass an extracted
toolchain directory to have it verify that every soname resolves:
`./install-toolchain.sh --curses-compat /path/to/swift-6.3.3-RELEASE-ubi9-aarch64`.
The variable has to be in the shell — mise does not apply `mise.toml`
`[env]` to its post-extract `swift --version` check.

This repo still installs AUR `swift-bin`, which resolves the same thing at
package level and needs no shim. Note item 15: a mise-installed 6.4.x
toolchain cannot build against the darwin SDK.

Swapping the Swift toolchain — `mise use -g swift@<ver>`, an asdf switch, or a
manual reinstall — moves Swift to a different absolute path. That does not
touch what you actually paid for: USB pairing records, your Apple ID auth,
and the SDK cache all live in user-global paths and survive by design.

What survives a swap:

- **Pairing** — `~/.pymobiledevice3/` (+ `/var/lib/lockdown` records).
- **Apple ID auth** — `~/.local/share/xtool/`.
- **SDK cache** — `~/.cache/xtool/darwin-<xcodever>.xtoolsdk`, kept by the
  install script. The SDK bundle references the toolchain that registered it,
  so after a swap it must be **re-registered into the current toolchain**:

```
./install-toolchain.sh --repair
```

`--repair` re-registers the cached SDK (no `.xip`, no network) and prints a
survive-status summary: SDK source used, pairing location, auth state. It
exits nonzero with instructions when the cache is missing and no `XCODE_XIP`
is given.

## First app

```
xtool new HelloOmarchy
cd HelloOmarchy
xtool dev run
```

`xtool dev build` alone produces `xtool/HelloOmarchy.app` (arm64 Mach-O).

## Device

Plug the iPhone in, tap Trust when prompted, then:

```
./device-run.sh
```

> **Try Omarchy on Windows:** If this Omarchy installation runs in the virtual
> machine distributed by [tryomarchy.com](https://tryomarchy.com), complete the
> [Windows VM iPhone USB setup](TRYOMARCHY-WINDOWS-USB.md) first. It provides
> working USB passthrough and a patched `usbmuxd` for reliable app installs.
> Bare-metal Omarchy installations do not need that guide.

Wireless deploy is **blocked on iOS 26** for Linux-only setups, tested
exhaustively (FINDINGS.md 17): iOS gives each host its own encrypted
RemotePairing tunnel and offers no way for a Linux host to claim one — a Mac
that once enabled "Connect via Network" holds a working wireless tunnel,
everyone else is refused. USB deploy works everywhere with no Apple-side
gate. When your phone DOES hold a tunnel with some host, `device-run.sh`
documents the pymobiledevice3 tunneld bridge for that case, and
`device-run.sh --rsd` can drive any tunnel endpoint you hold.

## Scripts

- `install-toolchain.sh`: everything up to and including the SDK install;
  `--repair` re-registers the cached SDK into the current toolchain after a
  toolchain swap (see *Toolchain swaps* above); `--curses-compat [ROOT]`
  creates the curses sonames a vendor (mise/swift.org) toolchain needs on
  Arch and optionally verifies ROOT resolves.
- `device-run.sh`: pair, install, launch, LLDB attach; `--network` and
  `--rsd` modes for wireless deploys (unverified).

## Findings

[FINDINGS.md](FINDINGS.md) records the twenty-one findings behind the working
run: what broke and how each was fixed (SDK install failures, a clang version
mismatch that breaks SwiftUI, the unstated prerequisites for debugging on
iOS 17+), the Swift/Xcode version matrix (items 15-16), why a toolchain
swap breaks SDK registration and how `--repair` restores it (item 19), and
the mise/ncurses soname story (items 20-21).

## Notes

- `clang` on PATH must be the Swift toolchain's own clang, not the system
  clang. The SDK install copies the host clang headers into the bundle; a
  version mismatch between host clang and the Swift compiler produces
  `__builtin_bit_cast` size errors when compiling SwiftUI. Both scripts in
  this repo export that PATH themselves; prefix it by hand only when running
  xtool directly in your own shell.
- Building SwiftUI pulls in simd/arm_neon headers; first build takes about a
  minute on an M1.

## License

MIT
