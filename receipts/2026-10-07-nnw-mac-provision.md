# Developer ID provisioning for the NetNewsWire Mac app — receipts, 2026-10-07

Branch `nnw-mac-bundle` (provision helper commit b905e01 + push fix, this
receipt). Helper: `tools/provision-mac.py` (uses `tools/asc.py` token/call).
Ship: `ship-mac.sh --notarize` in chroot `~/oad-bundle` against adapter
`~/nnw-mac5/omarchy-xtool`, Developer ID Application: Creatuity Corp.
(9LX44YXXVX), certificate resource id G349BR5A3A (serial 2A7E018432C273C780DC3ED0CA12FB18).

## The app id cannot be `com.ranchero.NetNewsWire-Evergreen`

Explicit App IDs are globally unique across teams; Ranchero owns this one.

```
POST /v1/bundleIds -> HTTP 409 ENTITY_ERROR.ATTRIBUTE.INVALID
"An App ID with Identifier 'com.ranchero.NetNewsWire-Evergreen' is not
 available. Please enter a different string."
```

The team's 37 bundle ids contain no `com.ranchero.*` entry. The ship uses team
ids mirroring the upstream nesting (xtool.yml edit, adapter only):

- app `com.joshuaswarren.omarchyappledev.netnewswire` (the team's existing
  "Omarchy NNW Test" app record)
- `com.joshuaswarren.omarchyappledev.netnewswire.SubscribeToFeed`
- `com.joshuaswarren.omarchyappledev.netnewswire.Mac.ShareExtension`

All three registered as platform MAC_OS by provision-mac.py (the name attribute
must be alphanumeric plus spaces — dots are refused, so the name is the
identifier with dots replaced).

## Capability creates via /v1/bundleIdCapabilities

- `PUSH` — not an enum value:
  `HTTP 409 ENTITY_ERROR.ATTRIBUTE.TYPE "'PUSH' is not a valid value for the
  attribute 'capabilityType'. Expected one of: 'ICLOUD', 'IN_APP_PURCHASE',
  'GAME_CENTER', 'PUSH_NOTIFICATIONS', 'WALLET', ..."`. The correct type is
  `PUSH_NOTIFICATIONS`; its create succeeds and the profile then grants
  `aps-environment = production`.
- `ICLOUD` bare create:
  `HTTP 409 "The identifier '2DK9DY854A' cannot have the CloudkitVersion
  'null'."` — needs capabilitySettings; the accepted body is
  `settings: [{"key": "ICLOUD_VERSION", "options": [{"key": "XCODE_6"}]}]`
  (option entries carry only `key`; a `value` key is refused as an unknown
  property).
- `APP_GROUPS` — bare create accepted on all three ids.

## What a MAC_APP_DIRECT profile actually grants

Decoded `build/provision/app.provisionprofile` (dev-id profile, expires 2044):

```
com.apple.application-identifier       9LX44YXXVX.com.joshuaswarren...netnewswire
com.apple.developer.team-identifier    9LX44YXXVX
com.apple.security.application-groups  ["9LX44YXXVX.*"]
com.apple.developer.ubiquity-kvstore-identifier  "9LX44YXXVX.*"
com.apple.developer.icloud-container-identifiers  []   (empty)
com.apple.developer.ubiquity-container-identifiers []  (empty)
com.apple.developer.icloud-services    "*"
com.apple.developer.aps-environment    "production"   (after PUSH_NOTIFICATIONS)
```

The public API cannot attach specific App Groups or iCloud containers, so the
groups wildcard covers only team-prefixed names and the container lists are
empty. Signed entitlements therefore keep what the profile backs and drop the
rest (`build/NetNewsWire-ship.entitlements`):

- kept: aps-environment production, ubiquity-kvstore-identifier
  `9LX44YXXVX.com.ranchero.NetNewsWire` (matches the `9LX44YXXVX.*` wildcard),
  app-sandbox, user-selected read-write, automation apple-events, network
  client, the two temporary-exception arrays
- dropped with the reason: aps (until PUSH_NOTIFICATIONS), the three icloud-*
  keys + ubiquity-container (no containers attachable), application-groups
  (claimed `group.com.ranchero.NetNewsWire-Evergreen` matches no grant; no
  Swift source reads the group)

## Ship runs (three)

1. ship with trimmed entitlements — notary Accepted, but provisioning had read
   the trimmed `build/NetNewsWire.entitlements` (ship-mac.sh expands
   ENTITLEMENTS to that path) and the embedded profile predated aps.
2. aps-environment added to the claims; ship Accepted; macstudio refused to
   spawn: `open` -> `RBSRequestErrorDomain Code=5 "Launch failed."
   NSPOSIXErrorDomain 163 "Launchd job spawn failed"` — the app claimed
   aps-environment while the embedded profile lacked it. A missing-profile
   spawn failure presents as launchd error 163, not a SIGKILL after launch.
3. provision-mac.py re-run with the claims file (rewrites build/provision/),
   ship again — Accepted. Embedded profile carries aps-environment production.

## macstudio verification (M1 Max, macOS 26.6.2)

```
$ spctl -a -vv NetNewsWire.app
NetNewsWire.app: accepted
source=Notarized Developer ID
origin=Developer ID Application: Creatuity Corp. (9LX44YXXVX)
$ codesign -d --entitlements - --xml NetNewsWire.app   (plutil)
  "com.apple.developer.aps-environment" => "production"
  "com.apple.developer.ubiquity-kvstore-identifier" => "9LX44YXXVX.com.ranchero.NetNewsWire"
  "com.apple.security.app-sandbox" => true ...
$ open NetNewsWire.app && sleep 6 && pgrep -x NetNewsWire
96682
$ pluginkit -m -v | grep -i netnewswire
  com.joshuaswarren.omarchyappledev.netnewswire.Mac.ShareExtension(7.1.5) ... PlugIns/NetNewsWire Share Extension.appex
  com.joshuaswarren.omarchyappledev.netnewswire.SubscribeToFeed(7.1.5) ... PlugIns/Subscribe to Feed.appex
```

Dock (autohide disabled for the capture, restored to autohide=1 afterwards):

```
$ osascript -e 'tell application "System Events" to tell process "Dock"
  to get {position, size} of UI element "NetNewsWire" of list 1'
2944, 1346, 68, 84
```

Screenshots (`~/tmp/apple-dev/nnw-mac-shots/`, also on macstudio
`~/tmp/nnw-mac-teamid/`):

- `nnw-teamid-main.png` — the three-pane main window of the final build:
  toolbar with search, Smart Feeds (Today 31, All Unread 365, Starred),
  On My Mac with ten real feeds, favicons and unread counts (Daring Fireball 48,
  Michael Tsai 100, Six Colors 75, ...), timeline placeholder "No selection".
  Sidebar counts populate over the network, so the sandboxed app fetches fine.
- `nnw-second-window.png` — Sparkle's "Check for updates automatically?" sheet
  on first run, showing the app icon (the actool-built AppIcon.icns).
- `nnw-teamid-dock.png` + `nnw-teamid-dock-icon.png` — the Dock with the
  NetNewsWire satellite icon and its running-app dot (captured during the
  first notarized launch; bundle id and icon are identical in the final build,
  only the embedded entitlements differ).

## Cleanup

- predecessor's private JWT probes deleted from the chroot home:
  asclib.py, probe2-7.py
- session probes deleted: cap-probe.py, icloud-probe.py, prov-dump.py,
  push-probe.py, refresh-prov.sh (after use)
- macstudio keeps the running NetNewsWire.app, its source zip
  (NetNewsWire3.zip), the four screenshots, and old-runs/ holding the two
  superseded bundles and zips from the redeploy swaps (moved, not deleted:
  recursive rm on macstudio needs manual approval)
