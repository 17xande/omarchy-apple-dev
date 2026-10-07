#!/usr/bin/env bash
# Build an xtool-style SwiftPM iOS app for the *simulator* on Linux, then
# install, launch and screenshot it in a Mac's Simulator over ssh.
#
#   tools/simctl-remote.sh [chroot-app-dir]
#
#     chroot-app-dir   app package, relative to the builder home inside the
#                      Arch chroot (default: apps/HelloOmarchy)
#
# Environment:
#   ARCHRUN       chroot runner        (default ~/tmp/apple-dev/archrun.sh)
#   SIM_MAC       Mac ssh target, required (user@host of a Mac with Xcode)
#   SIM_DEVICE    simulator name       (default "iPhone 17 Pro")
#   SIM_BUNDLE_ID bundle identifier    (default: the app's xtool.yml bundleID)
#   SIM_OUT       screenshot path      (default /tmp/<name>-sim.png)
#   DEPLOY_TARGET iOS deployment target (default 17.0)
#
# How the build works: SwiftPM refuses to ad-hoc sign an executable for this
# destination on Linux, so the app target is built as a library and the
# whole-module object is linked with the SDK bundle's ld64.lld (ad-hoc signing
# is its arm64 default) plus libclang_rt.iossim from the same toolchain.
# CoreSimulator accepts the lld ad-hoc signature as-is; the Mac never re-signs.
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
ARCHRUN=${ARCHRUN:-$HOME/tmp/apple-dev/archrun.sh}
SIM_MAC=${SIM_MAC:?set SIM_MAC to the ssh target of a Mac with Xcode, for example user@mac}
SIM_DEVICE=${SIM_DEVICE:-iPhone 17 Pro}
dir=${1:-apps/HelloOmarchy}
name=$(basename "$dir")
dt=${DEPLOY_TARGET:-17.0}
stage=/tmp/simstudy-$name
out=${SIM_OUT:-/tmp/$name-sim.png}
ch=$HOME/tmp/apple-dev/arch/root.x86_64/home/builder

[ -x "$ARCHRUN" ] || { echo "archrun not found: $ARCHRUN" >&2; exit 1; }
bid=${SIM_BUNDLE_ID:-$(awk '/^bundleID:/{print $2}' "$ch/$dir/xtool.yml" 2>/dev/null || true)}
: "${bid:?no bundle id: set SIM_BUNDLE_ID or add xtool.yml to the app}"

# 1. Build and bundle inside the chroot. The scratch copy gets an executable
#    product (xtool packages declare a library product; the link is ours).
$ARCHRUN --user bash -s <<EOF
set -euo pipefail
cd \$HOME
b=\$HOME/simbuild-$name
rm -rf "\$b"
mkdir -p "\$b"
cp -a "$dir/Package.swift" "$dir/Sources" "\$b/"
[ -f "$dir/xtool.yml" ] && cp -a "$dir/xtool.yml" "\$b/"
cd "\$b"
S=\$HOME/.swiftpm/swift-sdks/darwin.artifactbundle
export XCODE_EXTRA_PLATFORM_FOLDERS=\$S/Developer/Platforms PATH=\$S/toolset/bin:\$PATH
swift build -c release --swift-sdk arm64-apple-ios-simulator | tail -1
SDK=\$(echo \$S/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator*.sdk | awk '{print \$NF}')
RT=\$(echo \$S/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/*/lib/darwin | awk '{print \$NF}')
SW=\$(dirname \$(readlink -f \$(command -v swift)))
"\$SW/clang" -target arm64-apple-ios$dt-simulator -isysroot "\$SDK" -arch arm64 \
  -fuse-ld=\$S/toolset/bin/ld64.lld -Wl,-adhoc_codesign \
  -Wl,-platform_version,ios-simulator,$dt,27.0 \
  -L"\$SDK/usr/lib/swift" -L"\$RT" -lclang_rt.iossim \
  -o "\$b/$name.app.bin" "\$b/.build/release/$name.o"
mkdir -p "\$b/$name.app"
cp "\$b/$name.app.bin" "\$b/$name.app/$name"
cat > "\$b/$name.app/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>$name</string>
<key>CFBundleIdentifier</key><string>$bid</string>
<key>CFBundleName</key><string>$name</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSRequiresIPhoneOS</key><true/>
<key>UIDeviceFamily</key><array><integer>1</integer><integer>2</integer></array>
<key>UILaunchScreen</key><dict/>
</dict></plist>
PLIST
printf 'APPL?????' > "\$b/$name.app/PkgInfo"
tar czf "\$HOME/$name-sim.tgz" -C "\$b" $name.app
EOF

# 2. Push, install, launch, screenshot on the Mac.
ssh "$SIM_MAC" "mkdir -p $stage"
ionice -c3 nice -n 19 scp -l 320000 -q "$ch/$name-sim.tgz" "$SIM_MAC:$stage/"
ssh "$SIM_MAC" bash -s <<REMOTE
set -euo pipefail
cd $stage && tar xzf $name-sim.tgz
xcrun simctl boot '$SIM_DEVICE' 2>/dev/null || true
xcrun simctl install booted '$stage/$name.app'
pid=\$(xcrun simctl launch booted '$bid' | awk '{print \$2}')
sleep 3
xcrun simctl io booted screenshot '$stage/$name-sim.png' >/dev/null
echo "launched pid \$pid"
REMOTE
ionice -c3 nice -n 19 scp -l 320000 -q "$SIM_MAC:$stage/$name-sim.png" "$out"
echo "screenshot: $out"
