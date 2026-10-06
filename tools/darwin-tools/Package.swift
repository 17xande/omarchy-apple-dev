// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "darwin-tools",
    platforms: [.macOS(.v13)],
    dependencies: [
        // AssetKit 1.0.0 plus actool 27.0 parity fixes: named colors in every Xcode color space
        // (FINDINGS.md 24, 27), per-size icon renditions (26), actool's BOM layout and
        // single-size icon form (37), the Liquid Glass pre-render of Icon Composer icons, and HEIC images.
        .package(url: "https://github.com/joshuaswarren/AssetKit", revision: "4fc6c5b8201ff606ce0f12588ef87f4422a06430"),
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
