# Receipt: `$(AppIdentifierPrefix)` resolution for Linux-built iOS bundles, 2026-10-07

Branch `nnw-ios-prefix` in the omarchy-apple-dev clone
(`~/oad-prefix` on the omp-studio-local chroot, from `main` d993142).
FINDINGS.md 62.

## Symptom

`xtool install` of a dev-signed NetNewsWire iOS (bundle id
`com.joshuawarren.omarchyappledev.nnwios`, 2026-10-07 15:45Z) launched into a
trap in `AppDelegate.application(_:didFinishLaunchingWithOptions:)`:
`iOS/AppDefaults.swift:47` force-casts
`Bundle.main.object(forInfoDictionaryKey: "AppIdentifierPrefix")` — and the
key was absent. Xcode expands `$(AppIdentifierPrefix)` (`<TeamID>.`) from the
signing team at build time; the generator dropped the unresolvable key
instead. `Modules/Secrets/Sources/Secrets/CredentialsManager.swift:25` reads
the same key.

## xtool behaviour (checked first)

`xtool` (Sources/XToolSupport, XKit, vendored XcodeGen) contains no
`$(...)` substitution: grep finds `AppIdentifierPrefix` only in xtool's own
entitlements template and XcodeGen test fixtures. `xtool install` signs and
embeds a profile but never rewrites Info.plist values, so the fill has to
happen before install. `xtool auth` prints `- Team ID: <ID>` for the key it
signs device installs with.

## Design

1. `tools/xcodeproj2xtool.py` now expands placeholders in every string value
   (nested dictionaries and arrays included), resolves `PRODUCT_MODULE_NAME`
   (c99extidentifier of the target name, as Xcode's
   `$(PRODUCT_NAME:c99extidentifier)` default), keeps
   `$(AppIdentifierPrefix)`/`$(TeamIdentifierPrefix)` wherever they appear,
   and still drops every other unresolvable value.
2. `tools/fill-team-prefix.py` fills the placeholders from the team —
   `--team ID`, `--from-xtool-auth`, or `--profile FILE.mobileprovision`
   (`ApplicationIdentifierPrefix`). It walks an .app plus its
   `PlugIns/*.appex`.
3. `ship.sh` runs it right after `asc.py identity` yields the profile's
   `com.apple.developer.team-identifier`, before rcodesign seals the plists.
4. A device install runs it before `xtool install`, taking the team from
   `xtool auth` (the key xtool signs with) or a development profile made by
   `tools/provision-dev.py`.
5. `asc.py validate` FAILs an ipa whose Info.plists carry any surviving
   `$(...)` (all bundles, nested paths reported).

## Evidence

- Generator self-test: 42 checks pass, including the two new ones
  (`team-prefix placeholder kept for the signing step`,
  `nested PRODUCT_MODULE_NAME resolved`).
- NNW adapter regenerated in place from `NetNewsWire.xcodeproj`
  (`--bundle-id com.joshuawarren.omarchyappledev.nnwios`): the diff against
  the previous output is exactly one added key per Info.plist
  (`AppIdentifierPrefix = $(AppIdentifierPrefix)` in the app, share, and
  widget plists); `xtool.yml`, `xtool.env`, `Package.swift` are byte-identical.
- Fill round-trip: `fill-team-prefix.py --team Z6P74P6T99` on a copy of the
  release .app fills the app and both appexes to `Z6P74P6T99.`.
- Validator: a synthetic ipa with
  `NSExtension.Principal = $(PRODUCT_MODULE_NAME).Thing` fails validate with
  `FAIL Info.plists have no unresolved $(...) placeholders:
  Info.plist:.NSExtension.Principal`, exit 1.
- Device artifacts (chroot `~/device-artifacts/`, all carry the placeholder,
  ready for the on-device fill):
  - `nnwios-release.app` — 21.6 MB, `xtool dev build --configuration release`
  - `nnwios-debug.app` — 29.6 MB, debug (`-Onone`, symbols; `AppDelegate.swift`
    paths present in the binary), for LLDB
  - `icecubes-dev.app` — 151.5 MB, bundle id
    `com.joshuawarren.omarchyappledev.icecubes`, four extensions rebased,
    principal classes resolved
  - `icecubes-asc-20261006.app` — 219.9 MB, the shipped ASC bundle kept for
    the sweep below

## Info.plist sweep, shipped bundles

NetNewsWire iOS, ASC ipa 7.1.4 (202610071321), app + extensions: no `$(...)`
anywhere. Missing-but-referenced keys:

| Bundle | Key | Referenced by | State in shipped build |
|---|---|---|---|
| App | `AppIdentifierPrefix` | `iOS/AppDefaults.swift:47`, `Secrets/CredentialsManager.swift:25` | missing — startup trap; fixed by this change |
| Share extension | `AppIdentifierPrefix` | carried from the shared plist | missing, nothing in the extension reads it — harmless |
| Widget | `AppIdentifierPrefix` | carried from the shared plist | missing, nothing reads it — harmless |
| App | `AppGroup`, `OrganizationIdentifier`, `UserAgent`, `UserAgentExtended`, `DeveloperEntitlements`, `CFBundleIcons` | source `infoDictionary` lookups | all present |
| Share/Widget | `AppGroup`, `OrganizationIdentifier` | `ExtensionFeedAddRequestFile.swift:20` et al. | present |

IceCubesApp, ASC bundle 2026-10-06 (`icecubes-asc-20261006.app`):

| Bundle | Key | Value shipped | Effect |
|---|---|---|---|
| `IceCubesActionExtension.appex` | `NSExtension.NSExtensionPrincipalClass` | `$(PRODUCT_MODULE_NAME).ActionRequestHandler` | unresolved — extension dead; fixed by this change |
| `IceCubesNotifications.appex` | `NSExtension.NSExtensionPrincipalClass` | `$(PRODUCT_MODULE_NAME).NotificationService` | unresolved — extension dead; fixed |
| `IceCubesShareExtension.appex` | `NSExtension.NSExtensionPrincipalClass` | `$(PRODUCT_MODULE_NAME).ShareViewController` | unresolved — extension dead; fixed |
| `IceCubesAppWidgetsExtensionExtension.appex` | — | no principal class (SwiftUI `@main`) | correct |
| App | `CFBundleShortVersionString` | present | only source `infoDictionary` lookup (`AboutView.swift:20`, `SettingsTab.swift:347`) |

## Device fill at install time (no phone touched)

```sh
python3 fill-team-prefix.py --from-xtool-auth nnwios-release.app
xtool install --udid 00008130-000978E630E1401C nnwios-release.app
```

See `~/phone-plan.md` in the chroot builder home for the full 17:45Z window.
