# Receipt: a Flutter app built for iOS on Linux and run on an iPad, 2026-10-08

Claim: `flutter/setup.sh` and `flutter/build.sh` build a Flutter app for a
physical iOS device on Omarchy x86_64 with no Mac and no Xcode in the build,
and `xtool install` puts it on a device where it runs.

Host: Omarchy, x86_64 (Intel i7-8650U), kernel 7.2.5. swift-bin 6.4.0, xtool
f0a1f90, pymobiledevice3 11.26.0, Flutter 3.47.6 (Dart 3.13.5, `dart_revision`
04bcd1036c). SDK pieces streamed from Xcode 27.0 (27A266a), iPhoneOS 27.0.
Device: iPad (9th generation, iPad12,1), iPadOS 27.0, over USB.

App: `flutter create --platforms=ios --org com.example hello_omarchy`, plus
`url_launcher`, `shared_preferences`, `sqlite3` and `path_provider`, with
`flutter/sample/main.dart` as `lib/main.dart`. It probes each plugin at
startup and prints the result.

1. `flutter/setup.sh` from an empty work directory: 727 s end to end, 540 s
   of it compiling `gen_snapshot`; 7.1 GB under
   `~/.cache/omarchy-apple-dev/flutter`. Installed as Flutter's
   `ios-release/gen_snapshot_arm64`; `--version`: `Dart SDK version: 3.13.5
   (stable) ... on "linux_simarm64"`. The binary is bit-identical (`cmp`) to
   one built by hand from a separate checkout earlier the same day. A second
   run does nothing and takes 2 s.
2. `flutter/build.sh APP BUILD_STAMP=omarchy-x86_64-20261008T1838Z`: 47 s
   clean. `Runner.ipa` 7,099,426 bytes; `Runner.app` 16,357,020 bytes.

   | File | Bytes |
   |---|---|
   | `Runner` | 155,368 |
   | `Frameworks/App.framework/App` | 3,533,680 |
   | `Frameworks/Flutter.framework/Flutter` | 9,416,288 |
   | `Frameworks/sqlite3.framework/sqlite3` | 1,617,632 |
   | `Frameworks/objective_c.framework/objective_c` | 166,192 |

   The AOT snapshot header reads `0451907c2eaa8467e848c0067bfe8ed4product
   no-asan no-msan no-tsan no-shared_data no-code_comments
   no-dwarf_stack_traces arm64 ios no-compressed-pointers` — byte for byte the
   header of an `App.framework` that Xcode 27.0 built from Flutter 3.47.6 on a
   macOS runner. Flutter's Linux-hosted Android `gen_snapshot` carries the
   same version hash but `arm64 android compressed-pointers`, which is why it
   cannot stand in.
3. `xtool install --usb Runner.ipa`: "Successfully installed!".
4. `pymobiledevice3 developer dvt launch XTL-<team>.com.example.helloOmarchy`:
   `Process launched with pid 1086`. Screenshot
   `flutter-hello-2026-10-08.png` (this directory), taken with
   `developer dvt screenshot`:

   ```
   Build stamp: omarchy-x86_64-20261008T1838Z
   sqlite3 (FFI, native asset): 3.53.4, 6*7=42
   shared_preferences (plugin channel): launch #2
   path_provider: …/Documents
   url_launcher: canLaunchUrl=true
   ```

The failure the first run of this app caught, before `tools/macho-align.py`:

```
path_provider FAILED: Invalid argument(s): Couldn't resolve native function
'DOBJC_initializeApi' in 'package:objective_c/objective_c.dylib' : Failed to
load dynamic library 'objective_c.framework/objective_c': dlopen(...):
'.../Runner.app/Frameworks/objective_c.framework/objective_c' (mis-aligned
LINKEDIT string pool, fileOffset=0x00022ADC)
```

`sqlite3` loaded in that same run with the same misalignment: its dylib is the
package's prebuilt one (`sdk 26.5`, `LC_DYLD_INFO_ONLY`), while `objective_c`
is compiled by its build hook against the 27.0 SDK.

Also run: a private production Flutter app with seven native plugins
(Bluetooth, secure storage, image picker, audio, speech, connectivity, URL
launcher) built in 96 s and launched on the same iPad, restoring its session
from the keychain. Only launch and one screen were checked there.

Not done: debug or profile builds, simulator builds, App Store upload,
aarch64 hosts, any storyboard other than Flutter's stock pair.
