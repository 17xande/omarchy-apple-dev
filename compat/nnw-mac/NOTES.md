# nnw-mac WIP state (jw16, 2026-10-06, paused for GLM cluster)

- `ObjCPrivateShims.swift` -> copy into `~/nnw-mac/Mac/` (Swift replacements
  for the excluded ObjC category members NSOpenPanel.acceptOPML and
  WKPreferences._developerExtrasEnabled; shims need
  `nonisolated(unsafe)` on the associated-object key).
- `nnw-import-cocoa.patch` -> apply in the NNW clone: 111 files, one
  `import Cocoa` line each, inserted after the header comment block wherever
  NS* types are referenced without importing Cocoa/AppKit (Xcode injects
  these through the bridging header; SwiftPM does not). Also exclude the two
  RSCore package `.process` xibs (WebViewWindow, IndeterminateProgressWindow)
  at the package manifest level, with a warning per file - the Linux ibtool
  cannot compile AppKit nibs and fails closed.
- Build env that reached "Build complete!" (BUILD-EXIT:0, 24 s incremental):
  S=$HOME/.swiftpm/swift-sdks/darwin.artifactbundle
  PATH=$HOME/apple-dev-in/toolchains/swift-6.4.0-RELEASE-ubi10-aarch64/usr/bin:$HOME/.local/bin:$PATH
  XCODE_VERSION=27.0 XCODE_BUILD=27A266a
  ulimit -n 65536
  XCODE_EXTRA_PLATFORM_FOLDERS=$S/Developer/Platforms PATH=$S/toolset/bin:$PATH \
    swift build -c release --build-system swiftbuild --triple arm64-apple-macosx \
    --toolset $S/toolset-swb.json
- Missing piece for a linked Mach-O: the generated manifest has only
  .library products (xtool convention), so swiftbuild stops at
  libNetNewsWire.a and never links the executable. Next step: make
  xcodeproj2xtool emit an executable product for mac app targets (or run
  ld64 manually), then `file` the binary.
