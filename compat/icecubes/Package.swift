// swift-tools-version: 6.2
// xtool adapter for the IceCubesApp app target. App sources stay where they are
// (Sources/IceCubesApp/* are symlinks); only this directory is added.
import PackageDescription

let local = ["NetworkClient", "Timeline", "Account", "Models", "Notifications", "Env", "Explore", "Lists",
             "Conversations", "AppAccount", "StatusKit", "DesignSystem", "MediaUI"]

let package = Package(
    name: "IceCubesApp",
    defaultLocalization: "en",
    platforms: [.iOS("18.5")],
    products: [.library(name: "IceCubesApp", targets: ["IceCubesApp"])],
    dependencies: local.map { .package(name: $0, path: "../Packages/\($0)") } + [
        .package(url: "https://github.com/evgenyneu/keychain-swift", from: "24.0.0"),
        .package(url: "https://github.com/SFSafeSymbols/SFSafeSymbols", from: "7.0.0"),
        .package(url: "https://github.com/wishkit/wishkit-ios.git", from: "5.1.2"),
        .package(url: "https://github.com/RevenueCat/purchases-ios-spm", from: "5.86.0"),
        .package(url: "https://github.com/kean/Nuke", exact: "13.2.0"),
    ],
    targets: [
        .target(
            name: "IceCubesApp",
            dependencies: local.map { .product(name: $0, package: $0) } + [
                .product(name: "KeychainSwift", package: "keychain-swift"),
                .product(name: "SFSafeSymbols", package: "SFSafeSymbols"),
                .product(name: "WishKit", package: "wishkit-ios"),
                .product(name: "RevenueCat", package: "purchases-ios-spm"),
                .product(name: "Nuke", package: "Nuke"),
                .product(name: "NukeUI", package: "Nuke"),
            ],
            exclude: ["App/App/IceCubesApp.entitlements", "App/App/IceCubesApp-release.entitlements",
                      "App/Info.plist"],
            resources: [
                .process("App/Assets.xcassets"),
                .process("App/Resources"),
                .copy("App/Embeds"),
            ],
            swiftSettings: [.swiftLanguageMode(.v6), .defaultIsolation(MainActor.self)]
        ),
    ]
)
