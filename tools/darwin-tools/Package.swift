// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "darwin-tools",
    platforms: [.macOS(.v13)],
    dependencies: [
        // AssetKit 1.0.0 plus actool 27.0 parity fixes: named colors in every Xcode color space
        // (FINDINGS.md 24, 27) and per-size icon renditions (Icon Index, MultiSized Image; FINDINGS.md 26).
        .package(url: "https://github.com/joshuaswarren/AssetKit", revision: "55efa5da613f30730540ad948a95def9794ded91"),
        .package(url: "https://github.com/tayloraswift/swift-png", from: "4.5.0"),
    ],
    targets: [
        .target(
            name: "DarwinAssets",
            dependencies: [
                .product(name: "AssetKit", package: "AssetKit"),
                .product(name: "PNG", package: "swift-png"),
            ]
        ),
        // Linux stand-in for Apple's actool: SwiftBuild under xtool, and ship.sh for the app icon.
        .executableTarget(name: "actool", dependencies: ["DarwinAssets", .product(name: "AssetKit", package: "AssetKit")]),
    ]
)
