#!/usr/bin/env bash
# Build a macOS .app from the SwiftPM package in the current directory, sign it, and notarize it.
#
#   ship-mac.sh             build and sign: Developer ID if the identity below exists, else ad hoc
#   ship-mac.sh --notarize  also notarize and staple the ticket. Needs a Developer ID identity and
#                             ASC_KEY_PATH=/path/to/AuthKey_XXXXXXXXXX.p8 ASC_ISSUER_ID=<uuid> ASC_KEY_ID=XXXXXXXXXX
#
# PRODUCT: the executable product (default: the package's only executable).
# BUNDLE_ID (default com.example.<PRODUCT>), VERSION (default 1.0), BUILD_NUMBER (default UTC yyyymmddHHMM),
# MACOS_MIN (default 14.0). DEVELOPER_ID_DIR holds key.pem + cert.pem of a "Developer ID Application"
# certificate (default ~/.config/omarchy-apple-dev/developer-id). Apple lets only the Account Holder create
# that certificate, in the developer portal; the API key cannot (FINDINGS.md 57).
# Output: build/<PRODUCT>.app and build/<PRODUCT>.zip.
set -euo pipefail

notarize=0
case "${1:-}" in
  --notarize) notarize=1 ;;
  "") ;;
  *) echo "usage: ship-mac.sh [--notarize]" >&2; exit 2 ;;
esac

PATH="$(dirname "$(readlink -f "$(command -v swift)")"):$HOME/.local/bin:$PATH"
sdk="$HOME/.swiftpm/swift-sdks/darwin.artifactbundle"
idir="${DEVELOPER_ID_DIR:-$HOME/.config/omarchy-apple-dev/developer-id}"
product="${PRODUCT:-$(swift package describe --type json | python3 -c '
import json, sys
exe = [p["name"] for p in json.load(sys.stdin)["products"] if "executable" in p["type"]]
sys.exit("set PRODUCT: no single executable product") if len(exe) != 1 else print(exe[0])')}"
min="${MACOS_MIN:-14.0}"

echo "== 1. Release build (arm64-apple-macosx$min) =="
# SwiftBuild finds the macOS platform only through the SDK bundle's platform folders and toolset.
XCODE_EXTRA_PLATFORM_FOLDERS="$sdk/Developer/Platforms" PATH="$sdk/toolset/bin:$PATH" \
  swift build -c release --build-system swiftbuild --triple "arm64-apple-macosx$min" \
  --toolset "$sdk/toolset-swb.json" --product "$product"
bin=".build/arm64-apple-macosx/release"

echo "== 2. App bundle =="
app="build/$product.app"
mkdir -p build
[ ! -e "$app" ] || rm -r "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$bin/$product" "$app/Contents/MacOS/$product"
for b in "$bin"/*.bundle; do [ -d "$b" ] && cp -R "$b" "$app/Contents/Resources/"; done
python3 - "$app/Contents/Info.plist" "$product" "${BUNDLE_ID:-com.example.$product}" "${VERSION:-1.0}" \
  "${BUILD_NUMBER:-$(date -u +%Y%m%d%H%M)}" "$min" <<'PY'
import plistlib, sys
path, name, ident, version, build, minos = sys.argv[1:]
plistlib.dump({
    "CFBundleExecutable": name, "CFBundleIdentifier": ident, "CFBundleName": name,
    "CFBundlePackageType": "APPL", "CFBundleShortVersionString": version, "CFBundleVersion": build,
    "LSMinimumSystemVersion": minos, "NSPrincipalClass": "NSApplication",
    "CFBundleSupportedPlatforms": ["MacOSX"],
}, open(path, "wb"))
PY

echo "== 3. Sign =="
if [ -f "$idir/key.pem" ] && [ -f "$idir/cert.pem" ]; then
  # --for-notarization: hardened runtime and a secure timestamp.
  rcodesign sign --pem-file "$idir/key.pem" --pem-file "$idir/cert.pem" --for-notarization "$app"
elif [ "$notarize" = 1 ]; then
  echo "--notarize needs a Developer ID identity in $idir (key.pem, cert.pem)" >&2; exit 1
else
  echo "no Developer ID identity in $idir: signing ad hoc (runs on your own Macs only)"
  rcodesign sign "$app"
fi

if [ "$notarize" = 1 ]; then
  echo "== 4. Notarize =="
  : "${ASC_KEY_ID:?--notarize needs ASC_KEY_ID}" "${ASC_ISSUER_ID:?--notarize needs ASC_ISSUER_ID}"
  : "${ASC_KEY_PATH:?--notarize needs ASC_KEY_PATH (the .p8 file)}"
  key_json=$(mktemp)
  trap 'rm -f "$key_json"' EXIT
  rcodesign encode-app-store-connect-api-key -o "$key_json" "$ASC_ISSUER_ID" "$ASC_KEY_ID" "$ASC_KEY_PATH" >/dev/null 2>&1
  rcodesign notary-submit --api-key-file "$key_json" --max-wait-seconds 3600 --staple "$app"
fi

(cd build && rm -f "$product.zip" && zip -qry "$product.zip" "$product.app")
echo "wrote $app and build/$product.zip"
