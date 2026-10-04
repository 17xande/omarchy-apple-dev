#!/usr/bin/env bash
# Build an App Store .ipa from the xtool project in the current directory,
# validate it offline, and optionally upload it to App Store Connect.
#
#   ship.sh            build, sign, validate (no Apple account needed: signs with
#                      a local TEST identity unless ASC_KEY_ID is set)
#   ship.sh --upload   the same with your Apple identity, then upload. Needs:
#                        ASC_KEY_PATH=/path/to/AuthKey_XXXXXXXXXX.p8
#                        ASC_ISSUER_ID=<issuer uuid>  ASC_KEY_ID=XXXXXXXXXX
#                      and the app record created once in App Store Connect.
#
# BUILD_NUMBER sets CFBundleVersion (default: UTC yyyymmddHHMM, always increasing).
# XCODE_VERSION/XCODE_BUILD stamp DTXcode when the SDK came from a .xip.
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
PY="$HOME/pymobile3-venv/bin/python"
ASC="$here/tools/asc.py"
ACTOOL="$HOME/.swiftpm/swift-sdks/darwin.artifactbundle/Developer/Platforms/iPhoneOS.platform/Developer/usr/bin/actool"
PATH="$(dirname "$(readlink -f "$(command -v swift)")"):$HOME/.local/bin:$PATH"
export PATH

upload=0
case "${1:-}" in
  --upload) upload=1 ;;
  "") ;;
  *) echo "usage: ship.sh [--upload]" >&2; exit 2 ;;
esac
if [ "$upload" = 1 ]; then
  : "${ASC_KEY_ID:?--upload needs ASC_KEY_ID}" "${ASC_ISSUER_ID:?--upload needs ASC_ISSUER_ID}"
  : "${ASC_KEY_PATH:?--upload needs ASC_KEY_PATH (the .p8 file)}"
  export ASC_KEY_ID ASC_ISSUER_ID ASC_KEY_PATH
fi

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
echo "== 1. Release build =="
xtool dev build --configuration release
app=$(find xtool -maxdepth 1 -name '*.app' -print -quit)
[ -n "$app" ] || { echo "no .app under xtool/" >&2; exit 1; }

echo "== 2. App icon catalog =="
# As in Xcode's app target, actool --app-icon puts the icon into the app's own Assets.car and
# Info.plist. Search the app target (Sources/<App>) first, then the top of the project (4 levels:
# ./AppIcon.icon, ./Resources/Assets.xcassets/AppIcon.appiconset); deeper catalogs belong to
# vendored packages and their test apps. APP_ICON names the set (default AppIcon). actool takes
# the .xcassets dir for an appiconset, and the Icon Composer .icon dir itself.
icon=${APP_ICON:-AppIcon}
catalogs=()
for src in "Sources/$(basename "$app" .app)" .; do
  [ -d "$src" ] || continue
  depth=; [ "$src" = . ] && depth="-maxdepth 4"
  # shellcheck disable=SC2086
  mapfile -t catalogs < <(find -L "$src" $depth \( -name .build -o -name xtool \) -prune -o \
    \( -name "$icon.appiconset" -o -name "$icon.icon" \) -type d -print | while read -r found; do
      case "$found" in
        *.appiconset) dirname "$found" ;;
        *) echo "$found" ;;
      esac
    done | sort -u)
  [ "${#catalogs[@]}" = 0 ] || break
done
case "${#catalogs[@]}" in
  0) echo "no $icon.appiconset or $icon.icon in the project; App Store upload needs an app icon" ;;
  1)
    min=$("$PY" -c 'import plistlib,sys; print(plistlib.load(open(sys.argv[1],"rb"))["MinimumOSVersion"])' "$app/Info.plist")
    "$ACTOOL" "${catalogs[0]}" --compile "$app" --platform iphoneos --app-icon "$icon" \
      --minimum-deployment-target "$min" --output-partial-info-plist "$stage/icon.plist"
    "$PY" -c 'import plistlib,sys; p=sys.argv[1]; d=plistlib.load(open(p,"rb")); d.update(plistlib.load(open(sys.argv[2],"rb")))
plistlib.dump(d, open(p,"wb"), fmt=plistlib.FMT_BINARY)' "$app/Info.plist" "$stage/icon.plist"
    ;;
  *) echo "more than one $icon.appiconset or $icon.icon: ${catalogs[*]}" >&2; exit 1 ;;
esac

echo "== 3. App Store Info.plist keys =="
"$PY" "$ASC" stamp "$app" "${BUILD_NUMBER:-$(date -u +%Y%m%d%H%M)}"

echo "== 4. Distribution identity and signature =="
sign_dir=xtool/ship-signing
if [ -n "${ASC_KEY_ID:-}" ]; then
  "$PY" "$ASC" identity "$app" "$sign_dir"
else
  "$PY" "$ASC" test-identity "$app" "$sign_dir"
fi
team=$("$PY" -c 'import plistlib,sys; print(plistlib.load(open(sys.argv[1],"rb"))["com.apple.developer.team-identifier"])' \
  "$sign_dir/entitlements.plist")
rcodesign sign --pem-file "$sign_dir/key.pem" --certificate-der-file "$sign_dir/cert.der" --team-name "$team" \
  --entitlements-xml-file "$sign_dir/entitlements.plist" "$app"

echo "== 5. Package =="
name=$(basename "$app" .app)
ipa="$PWD/xtool/$name.ipa"
mkdir "$stage/Payload"
cp -a "$app" "$stage/Payload/"
rm -f "$ipa"
(cd "$stage" && zip -qry "$ipa" Payload)
echo "wrote $ipa"

echo "== 6. Offline App Store validation =="
"$PY" "$ASC" validate "$ipa"

if [ "$upload" = 1 ]; then
  echo "== 7. Upload to App Store Connect =="
  "$PY" "$ASC" upload "$ipa"
fi
