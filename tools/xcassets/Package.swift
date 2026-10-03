// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "xcassets",
    platforms: [.macOS(.v13)],
    dependencies: [
        .package(url: "https://github.com/xtool-org/AssetKit", exact: "1.0.0"),
        .package(url: "https://github.com/tayloraswift/swift-png", from: "4.5.0"),
    ],
    targets: [
        .executableTarget(
            name: "xcassets",
            dependencies: [
                .product(name: "AssetKit", package: "AssetKit"),
                .product(name: "PNG", package: "swift-png"),
            ]
        ),
    ]
)
