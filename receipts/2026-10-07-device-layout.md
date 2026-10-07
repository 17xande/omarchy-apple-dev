# Receipt: ship.sh --device (Xcode root-level resources), 2026-10-07

Branch `device-layout`, based on main e8bfc0d. Chroot clone
`~/oad-devlayout`; proofs ran in the chroot on the existing adapters
(`~/reg-nnw-1318/adapter-fix`, `~/reg-icecubes-1310/adapter-fix`).

## What ran

    # NetNewsWire, guard first (no team):
    archrun.sh --user '... cd ~/reg-nnw-1318/adapter-fix && bash ~/oad-devlayout/ship.sh --device'
    → exit 1 at step 6: unresolved $(...) placeholders:
      Info.plist:AppIdentifierPrefix,
      PlugIns/NetNewsWire iOS Share Extension.appex/Info.plist:AppIdentifierPrefix,
      PlugIns/NetNewsWire iOS Widget Extension.appex/Info.plist:AppIdentifierPrefix

    # NetNewsWire, with team (logs: host ~/tmp/apple-dev/devlayout-nnw-team.log):
    archrun.sh --user '... ship.sh --device 9LX44YXXVX'
    → exit 0 in 18.9 s (release build 5.79 s incremental)
    == 5. Team prefix == filled AppIdentifierPrefix in the app and both appexes
       (AppIdentifierPrefix = "9LX44YXXVX." read back from all three plists)
    == 6. Placeholder check == no unresolved $(...) placeholders
    device app ready: xtool/NetNewsWire-iOS.app

    # IceCubes, with team (log: ~/tmp/apple-dev/devlayout-ice.log):
    archrun.sh --user '... cd ~/reg-icecubes-1310/adapter-fix && bash ~/oad-devlayout/ship.sh --device 9LX44YXXVX'
    → exit 0 in 91.8 s (release build 33.89 s); nothing to fill (IceCubes
      plists carry no team-prefix placeholders); placeholder check green.

## Layout vs the TestFlight builds (and the manual fix)

Method: the signed ship builds were copied to `~/scratch-devlayout/`
(`nnw-testflight.app`, `ice-testflight.app`) before the device runs, then
compared with `layout-diff.py` (top-level root entries + full recursive trees).
The device root is the TestFlight root plus the resource bundle minus
catalogs/Info.plist — exactly the manual fix's result (root Assets.car from a
ship build + `rsync --ignore-existing --exclude Assets.car --exclude
Info.plist <bundle>/ <app>/`).

NetNewsWire (ref 186 files → device 190):

- +28 root entries: eight themes (`*.nnwtheme`), four RTF, four
  keyboard-shortcut plists, ContentRules.json, DefaultFeeds.opml,
  PrivacyInfo.xcprivacy, blank.html, core.css, main.js, main_ios.js,
  newsfoot.js, page.html, template.html, stylesheet.css, en.lproj.
- Extension roots: share extension xib cells, widget `widget-sample.json`,
  `en.lproj/Localizable.strings`.
- App root Assets.car 7,116,032 B — same size as the ship build's (same actool,
  same catalogs); `cp -an` kept it, no car collision.
- Every bundle entry sits at a root: "bundle entries still absent from root:
  none".
- Only-in-ref files: `_CodeSignature/`, `embedded.mobileprovision`,
  `Metadata.appintents/` (App Store steps skipped) and the app's dylibs as
  wrapped `Frameworks/<Name>.framework/` (device keeps the loose `lib*.dylib`
  that step 4 wraps for App Store processing).

IceCubes (ref 227 files → device 338):

- +141 files: `Embeds/` fonts and sounds, 19 `*.lproj` trees at the app root,
  per-appex `InfoPlist.strings` / `Localizable.strings(.stringsdict)`, and the
  widget's 18,715 B bundle `Assets.car` promoted to the widget appex root — no
  `EXTENSION_APP_ICONS` entry meant step 3 compiled nothing for the widget, so
  `cp -an` left its compiled catalog where Xcode puts one (the target's root).
- App root Assets.car 70,251,424 B, same as the ship build's.
- "bundle entries still absent from root: none". Only-in-ref: `_CodeSignature/`,
  `embedded.mobileprovision`, `Metadata.appintents/`. Vendored package bundles
  (RevenueCat, SQLite.swift, TelemetryDeck, WishKit) stay in the bundle, as in
  the manual fix: the rule covers the target's own `<App>_<Target>.bundle`.

## App Store path untouched

`ship.sh` (no flag) and `--upload` run the same steps 1-8 as main e8bfc0d; the
device block exits before step 4. No App Store-only key (DT* stamp), framework
wrapping, App Intents metadata or signing happens in device mode, so nothing
flat that stalled App Store processing can reach an upload through it.

## Cleanup

`~/scratch-devlayout/` (141 MB of reference apps + diff script) deleted after
the diffs; the two raw logs stay at `~/tmp/apple-dev/devlayout-*.log`. The
device apps remain in the adapters' `xtool/` (rebuildable, 39 MB + 168 MB).
