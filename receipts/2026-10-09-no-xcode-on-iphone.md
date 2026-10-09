# Receipt: no-xcode builds run on an iPhone, 2026-10-09

Device: iPhone on iOS 27.0.1, connected by USB to a Linux machine. Apps signed with a development profile
(`tools/sign-dev.sh`), installed and launched with `pymobiledevice3`. Release builds.

| App | Built with | Result on the phone |
|---|---|---|
| Swift console programs (plain, `-Onone`, async/await, default arguments) | `sdk-free/swiftc.sh` and earlier research builds | Installed and launched. Output seen for three: `hello from swift, no SDK` and `[2, 4, 6] ABC`, and `42`. The Swift 6.4 build from `swiftc.sh` printed the same text as the research build. Two programs printed nothing in the 20 s window and left no crash report. |
| Objective-C UIKit hello | `sdk-free/cc.sh` | Label `hello from linux, no SDK` on screen (`2026-10-09-no-xcode-uikit-hello.png`). |
| Flutter counter, release | `sdk-free/flutter-build.sh` | UI renders (`2026-10-09-no-xcode-flutter-counter.png`). |
| Flutter counter + `sqflite`, + `path_provider` (Objective-C plugins) | `sdk-free/flutter-build.sh` | UI renders. |
| Flutter + `shared_preferences` (Swift plugin) | Swift overlay research build | `launch #1`, `stored: yes`; after relaunches `launch #3` (`2026-10-09-no-xcode-swift-plugin-prefs.png`). |
| Flutter + `url_launcher` and `shared_preferences` (Swift plugins) | Swift overlay research build | `launch #1`, then `launch #2` after a relaunch, `canLaunchUrl: true`, both buttons present (`2026-10-09-no-xcode-swift-plugin-urls.png`). |

Not checked: the open and in-app buttons were not tapped. A free Apple ID install was not tried. Debug builds were not
run (they need a debugger on iOS 26 and later). Swift plugin apps in this table came from the research build of the
Swift framework overlays; `sdk-free/swift/overlays.sh` is the installer version of the same build and is not yet
verified end to end (see `2026-10-09-sdk-free-swift-overlays.md`).
