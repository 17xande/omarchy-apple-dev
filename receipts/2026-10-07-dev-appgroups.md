# Receipt: dev-profile App Groups for the NNW iOS dev bundle ids, 2026-10-07

Branch `dev-appgroups` (based on main acd373c). Portal work ran in main
Helium on macstudio over raw CDP 50293 with the `/tmp/devid-w7c` bun helpers;
profile recreation ran here through the ASC API (`tools/provision-dev.py`).
Team Creatuity Corp `9LX44YXXVX`; API key `63LQ3S8AY8` (App Manager).

## Why

The dev-signed NNW iOS install traps at launch:
`ExtensionContainersFile.filePath` calls
`FileManager.containerURL(forSecurityApplicationGroupIdentifier:)` with the
Info.plist `AppGroup` value, `containerURL!` forces the unwrap, and a dev
profile without the group returns nil. NNW reads the group from Info.plist
`AppGroup` (`iOS/Resources/Info.plist`: `$(APP_GROUP_ID)` =
`group.$(ORGANIZATION_IDENTIFIER).NetNewsWire.iOS$(APP_GROUP_SUFFIX)`).

## What exists now

- App IDs registered via API (`asc.py bundle_id()`):
  `com.joshuawarren.omarchyappledev.nnwios` = QLC4BX97D7,
  `.Share-Extension` = FBV9U9P444,
  `.SpringboardWidgets` = PW39WK8B87.
- App Group registered in the portal UI:
  `group.com.joshuawarren.omarchyappledev.nnwios`
  (description "omarchy apple dev nnw ios").
- The group attached to all three App IDs through
  Identifiers → App ID → Edit → Capabilities → App Groups → checkbox →
  Configure → tick the group → Continue → Save → Confirm; each edit page
  reads back "Enabled App Groups (1)".
- Development profiles deleted and recreated by name with
  `tools/provision-dev.py --bundle-id <3 ids>
  --out <chroot>/.config/omarchy-apple-dev/development
  --expect-group group.com.joshuawarren.omarchyappledev.nnwios`
  (dev certificate 7RQ4B526UF reused, 5 ENABLED team devices attached):

    profile 3QT36RHKJS -> com.joshuawarren.omarchyappledev.nnwios.mobileprovision
    profile 9J37PFAA6D -> com.joshuawarren.omarchyappledev.nnwios.Share-Extension.mobileprovision
    profile 2K9GN4W85K -> com.joshuawarren.omarchyappledev.nnwios.SpringboardWidgets.mobileprovision

  Each profile's Entitlements (decoded from the written bytes) carry
  `com.apple.security.application-groups: ['group.com.joshuawarren.omarchyappledev.nnwios']`;
  `--expect-group` exits nonzero otherwise. All expire 2027-10-07.

## Apple refusal (verbatim)

Registering `group.com.ranchero.NetNewsWire.iOS` — the group name the current
device build's Info.plists actually carry — is refused:

    There were errors in the data supplied. Please correct and re-submit.
    An Application Group with Identifier 'group.com.ranchero.NetNewsWire.iOS'
    is not available. Please enter a different string.

So the ranchero-suffixed `AppGroup` can never be granted to this team.

## Gap that remains (generator, not portal)

`xcodeproj2xtool.py` resolves `$(APP_GROUP_ID)` from the NNW xcconfig
verbatim, so the generated Info.plists keep
`AppGroup = group.com.ranchero.NetNewsWire.iOS` even with `--bundle-id`
(the observed device-artifacts build confirms it). Until the generator rebases
`AppGroup` to `group.` + the overridden bundle id, even a profile carrying the
new group leaves the same `containerURL!` trap. The portal side is done; the
Info.plist side needs the one-line generator fix.

## Exact UI steps that worked

1. `developer.apple.com/account` (root only; deep URLs boot an empty shell)
   → "Identifiers" card.
2. List page → "Add new identifier" → radio "App Groups" → Continue.
3. Description (no `-.@"&*'"` characters) + Identifier (the form renders the
   fixed `group.` prefix; type only the suffix) → Continue → Register.
4. App ID attach: list → row of the bundle id → Edit → scroll the
   Capabilities table to "App Groups" → tick checkbox → "Configure" → tick
   the group row → Continue → Save → Confirm (modal) → back at the list.
5. React forms ignore synthetic DOM events; every click above is
   `Input.dispatchMouseEvent` (cdpclick.js) at `getBoundingClientRect()`
   coordinates, typed text via per-char `Input.dispatchKeyEvent`.

Screenshots (portal pages only): private repo
`docs/lanes/apple-dev/notes/2026-10-07-dev-appgroups/*.jpg` — ag-form,
ag-list, ag-refusal, ag-dialog, appid-ag-enabled, widget-dialog.
