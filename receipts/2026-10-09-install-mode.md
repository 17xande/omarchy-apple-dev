# Receipt: install mode choice (branch install-mode), 2026-10-09

What changed: `install-toolchain.sh` takes `--mode full|no-xcode` (also `OMARCHY_APPLE_MODE`, the saved
`~/.config/omarchy-apple-dev/mode`, or a prompt in a terminal; default `full`). The `no-xcode` mode runs the usual
toolchain steps, then `sdk-free/setup.sh` instead of the Xcode SDK steps. `--repair` re-runs that setup in this mode.
New directory `sdk-free/`: setup, compiler wrapper, Flutter build script, headers, shims, Objective-C Runner.

Checked:

- `tests/install-mode.sh`: 8 of 8. Covers the flag, `--mode=`, other arguments kept, the environment, the saved
  choice, flag over saved choice, flag over environment, and a refused value. The prompt needs a terminal; its text is
  `./install-toolchain.sh --mode-help`.
- `bash -n` on `install-toolchain.sh` and the three `sdk-free` scripts; `shellcheck -S warning` reports one note
  (`sudo` with a redirect in `setup.sh`, the file is the user's own).
- `sdk-free/setup.sh` in the Arch build chroot, with ready-made link stubs instead of an iPhone
  (`SDKFREE_TBD_DIR`): the linker toolset downloaded and checked against its pinned sha256, the Objective-C runtime
  headers fetched at their pinned commit, the sysroot (12 MB) assembled.
- `sdk-free/flutter-build.sh` on a `flutter create` counter app in the same chroot: release and debug both end in an
  unsigned `Runner-unsigned.ipa` (about 4 s warm). After `tools/sign-dev.sh`, `tools/macho-lint.py` reports 3 of 3
  images clean.

Not checked: the step that copies the shared cache from an iPhone (`fetch-symbols`, `ipsw dyld tbd`) as one run
through `setup.sh`; the same two commands were used by hand on earlier days. Nothing built by this mode has run on a
device yet.
