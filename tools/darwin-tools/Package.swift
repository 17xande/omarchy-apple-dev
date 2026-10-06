// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "darwin-tools",
    platforms: [.macOS(.v13)],
    dependencies: [
        // AssetKit 1.0.0 plus actool 27.0 parity fixes: named colors in every Xcode color space
        // (FINDINGS.md 24, 27), per-size icon renditions (26), actool's BOM layout and
        // single-size icon form (37), the Liquid Glass pre-render of Icon Composer icons, HEIC images,
        // alternate app icons, gray and opacity encoding, Display P3 wide-gamut renditions, and actool's
        // BITMAPKEYS descriptors. One ZZZZPackedAsset atlas per scale across all symbol sets (54).
        .package(url: "https://github.com/joshuaswarren/AssetKit", revision: "bece8b6b98250c47605a02e8d0a25c49d31269ac"),
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
