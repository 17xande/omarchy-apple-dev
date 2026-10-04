// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "darwin-tools",
    platforms: [.macOS(.v13)],
    dependencies: [
        // AssetKit 1.0.0 plus named-color fixes (actool's CSI layout, system colors; FINDINGS.md 24)
        // and per-size icon renditions (Icon Index, MultiSized Image; FINDINGS.md 26).
        .package(url: "https://github.com/joshuaswarren/AssetKit", revision: "0521ae7c9d991713c0e9f4ade9f555815345dc0b"),
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
