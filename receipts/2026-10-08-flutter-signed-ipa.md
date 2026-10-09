# Receipt: Flutter counter app, built and signed on Linux (2026-10-08)

Machine: the x86_64 Arch chroot (16 cores) used for the other receipts, with Flutter 3.47.6 stable (archive sha256
checked against Flutter's release index), swift-bin 6.4.0, the iPhoneOS 27.0 SDK, and the merged Flutter PRs
(`flutter/` at 0b08856: gen_snapshot, shims, the Linux `ibtool`, the FlutterFramework package). The Flutter SDK and
the 7.2 GB Dart checkout sit on a network share, not on the chroot disk.

1. `flutter/setup.sh`: 5 min 23 s from an empty work directory (Dart SDK revision 04bcd1036c, 1145 ninja steps,
   `gen_snapshot_arm64` is now an ELF in Flutter's `ios-release` cache).
2. `flutter create` (iOS only) writes the counter template. `flutter pub add package_info_plus` adds a plugin whose
   manifest depends on `../FlutterFramework`, the case PR #9 fixes.
3. `flutter/build.sh <app>`: 29 s. One native plugin, one generated shell package with the FlutterFramework
   placeholder. Output: an unsigned `Runner.ipa` (6,201,482 bytes), bundle id `dev.omarchy.flutterdemo.counter`,
   iOS 15.0 and later.
4. `tools/provision-dev.py` made the development profile for that bundle id. `tools/sign-dev.sh` signed
   `App.framework`, `Flutter.framework` and `Runner.app` with the development identity: `Runner-dev.ipa`, 6,229,584 bytes.

Checks on the signed ipa:

- `tools/asc.py validate`: 47 of 50 pass. `rcodesign verify Runner`, the CodeDirectory team id, the sealed
  Info.plist and `_CodeSignature/CodeResources`, the entitlements-against-profile match, the signing certificate
  in the profile, the icon set, the SDK version (27.0) and the placeholder check all pass. The three failures are
  the distribution-only checks that a development build must fail: "App Store profile (no device list)",
  "profile get-task-allow is false", "signed get-task-allow is false".
- `tools/macho-lint.py` (new): 3 of 3 Mach-O images clean (`Runner`, `App.framework/App`, `Flutter.framework/Flutter`):
  arm64, iOS platform, string pool 8-byte aligned, string table inside the file, code signature present, and
  `rcodesign verify` passes for each. `App.framework/App` reports SDK 15.0 and `Flutter.framework/Flutter` 26.2;
  the main executable reports 27.0.

Not done: no install on a device (the phone was with its owner). Not tried: App Store upload.

Prerequisites this run found that a minimal Arch install lacks: `llvm` (already in the README) and `rsync`
(`flutter assemble` stops with "Failed to find rsync"). `build.sh` and the README now name `rsync`.
