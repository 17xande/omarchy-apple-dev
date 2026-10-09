# Contributing

Thanks for wanting to help. This repo has one supported target and a small
test loop, so contributions stay simple.

## What we test

Everything here is verified on **Omarchy Linux on Apple Silicon Macs and
x86_64**, which is the only tested and supported target:

- Native Swift and SwiftUI iOS apps built with `xtool` and an Xcode-derived
  SDK, on Omarchy (Arch-based) with AUR `swift-bin`.
- The exact versions in the README table. Version matching matters
  (Xcode 27 pairs with swift-bin 6.4), so say which ones you run.

Other Arch-based distributions will probably work, since this is plain
pacman/AUR plus scripts, but they are untested: reports are welcome, and
we do not promise support for them.

## Reporting a problem

Open an issue with:

- Omarchy version and architecture (aarch64 or x86_64).
- `swift --version` and `xtool --version` output.
- The full output of the command that failed, not a summary.

## Sending a pull request

- Keep the diff small and focused. One fix or one feature per PR.
- Scripts must stay safe to re-run: skip work that is already done.
- No new network fetches in the scripts without saying why.
- Say what you tested and on which machine. A PR that fixes an install
  failure should show the install completing.
- Run `bash -n` on changed shell scripts and `python3 -m py_compile` on
  changed Python tools.
