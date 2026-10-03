// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "darwin-tools",
    platforms: [.macOS(.v13)],
    dependencies: [
        // AssetKit 1.0.0 plus named-color fixes (actool's CSI layout, system colors); FINDINGS.md item 24.
        .package(url: "https://github.com/joshuaswarren/AssetKit", revision: "890b8ef031a46099e394682b682eed3541b5cf96"),
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
        // ship.sh: compile the app's AppIcon catalog into the built .app.
        .executableTarget(name: "xcassets", dependencies: ["DarwinAssets", .product(name: "AssetKit", package: "AssetKit")]),
        // Linux stand-in for Apple's actool, for SwiftBuild under xtool.
        .executableTarget(name: "actool", dependencies: ["DarwinAssets", .product(name: "AssetKit", package: "AssetKit")]),
    ]
)
