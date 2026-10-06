// Linux stand-in for Apple's actool, covering the two invocations SwiftBuild makes for an asset
// catalog in a Swift package: asset symbol generation, and compilation to Assets.car through
// AssetKit. File formats follow Xcode 27's actool 27.0 (FINDINGS.md item 24).
import AssetKit
import DarwinAssets
import Foundation

let actoolVersion = (bundle: "25098", short: "27.0")

func fail(_ message: String) -> Never {
    print("/* com.apple.actool.errors */\n: error: \(message)\n")
    exit(1)
}

// MARK: - Arguments

var catalogs: [String] = []
var options: [String: [String]] = [:]
let valueFlags: Set<String> = [
    "--compile", "--output-format", "--export-dependency-info", "--output-partial-info-plist",
    "--minimum-deployment-target", "--platform", "--app-icon", "--accent-color", "--bundle-identifier",
    "--generate-swift-asset-symbols", "--generate-objc-asset-symbols", "--generate-asset-symbol-index",
    "--generate-swift-asset-symbol-extensions", "--enable-on-demand-resources", "--development-region",
    "--target-device", "--alternate-app-icon", "--launch-image", "--widget-background-color",
    "--include-language", "--sticker-pack-strings-file", "--standalone-icon-behavior", "--ui-framework-family",
    "--lightweight-asset-runtime-mode", "--flattened-app-icon-path", "--filter-for-device-model",
    "--filter-for-device-os-version", "--filter-for-thinning-device-configuration", "--asset-pack-output-specifications",
]
var args = CommandLine.arguments.dropFirst().makeIterator()
while let arg = args.next() {
    if valueFlags.contains(arg) {
        guard let value = args.next() else { fail("missing value for \(arg)") }
        options[arg, default: []].append(value)
    } else if arg.hasPrefix("--") {
        options[arg, default: []].append("")
    } else {
        catalogs.append(arg)
    }
}
@MainActor func option(_ name: String) -> String? { options[name]?.last }

if options["--version"] != nil {
    let plist: [String: Any] = ["com.apple.actool.version": ["bundle-version": actoolVersion.bundle,
                                                              "short-bundle-version": actoolVersion.short]]
    let format: PropertyListSerialization.PropertyListFormat = option("--output-format") == "binary1" ? .binary : .xml
    FileHandle.standardOutput.write(try PropertyListSerialization.data(fromPropertyList: plist, format: format, options: 0))
    exit(0)
}

guard let outputDir = option("--compile").map({ URL(fileURLWithPath: $0) }) else { fail("--compile is required") }
guard !catalogs.isEmpty else { fail("no .xcassets input") }
// Resolve symlinks: generated adapters link catalogs into the package, and Foundation on Linux lists a
// symlinked directory's children as non-directories, which silently emptied Mastodon's Preview Assets car.
let inputs = catalogs.map { URL(fileURLWithPath: $0).resolvingSymlinksInPath() }
try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

func report(_ outputs: [URL]) {
    print("/* com.apple.actool.compilation-results */")
    for url in outputs { print(url.path) }
    print("")
}

// MARK: - Asset symbols

let symbolFlags = ["--generate-swift-asset-symbols", "--generate-objc-asset-symbols", "--generate-asset-symbol-index"]
if symbolFlags.contains(where: { options[$0] != nil }) {
    let assets = try inputs.flatMap { try AssetSymbols.collect(catalog: $0) }
    var written: [URL] = []
    if let path = option("--generate-asset-symbol-index") {
        try AssetSymbols.index(assets).write(to: URL(fileURLWithPath: path))
        written.append(URL(fileURLWithPath: path))
    }
    if let path = option("--generate-objc-asset-symbols") {
        try Data(AssetSymbols.objc(assets, bundleID: option("--bundle-identifier") ?? "").utf8)
            .write(to: URL(fileURLWithPath: path))
        written.append(URL(fileURLWithPath: path))
    }
    if let path = option("--generate-swift-asset-symbols") {
        try Data(AssetSymbols.swift(assets).utf8).write(to: URL(fileURLWithPath: path))
        written.append(URL(fileURLWithPath: path))
    }
    report(written.sorted { $0.path < $1.path })
    exit(0)
}

// MARK: - Compile

// SwiftBuild passes every catalog of a target in one call; AssetKit compiles one catalog and
// only some asset types. Everything left out is reported as a warning.
let prepared = try CatalogMerge.prepare(inputs, appIcon: option("--app-icon"))
let (source, singleSizeBundle) = try SingleSizeIcon.expandIfNeeded(
    catalog: prepared.catalog, appIcon: option("--app-icon") ?? "AppIcon",
    idioms: options["--target-device"] ?? ["iphone", "ipad"])
defer {
    for url in Set([prepared.catalog, source]) {
        try? FileManager.default.removeItem(at: url.deletingLastPathComponent())
    }
}
if !prepared.skipped.isEmpty {
    print("/* com.apple.actool.document.warnings */")
    for item in prepared.skipped {
        let parts = item.split(separator: ":", maxSplits: 1)
        print("\(parts[0]): warning: skipped by the Linux actool:\(parts.count > 1 ? parts[1] : "")")
    }
    print("")
}
var iconComposer = prepared.iconComposer
iconComposer?.idioms = options["--target-device"] ?? ["iphone", "ipad"]
let result = try await XCAssetCompiler(deploymentTarget: option("--minimum-deployment-target") ?? "17.0")
    .compile(catalog: source, iconComposer: iconComposer)
var outputs: [URL] = []
if result.renditionCount > 0 {
    // actool 27.0 writes no Assets.car when no rendition survives; an empty car stalls App Store processing.
    let car = outputDir.appendingPathComponent("Assets.car")
    try result.carData.write(to: car)
    outputs.append(car)
}

var partial: [String: Any] = [:]
if let icon = singleSizeBundle ?? result.appIconBundle, option("--app-icon") == icon.primaryIconName {
    partial.merge(icon.infoPlistAdditions) { $1 }
    for file in icon.looseFiles {
        let url = outputDir.appendingPathComponent(file.name)
        try file.data.write(to: url)
        outputs.append(url)
    }
}
if let accent = option("--accent-color") {
    partial["NSAccentColorName"] = accent
}
if let path = option("--output-partial-info-plist") {
    let url = URL(fileURLWithPath: path)
    try PropertyListSerialization.data(fromPropertyList: partial, format: .xml, options: 0).write(to: url)
    outputs.append(url)
}
if let path = option("--export-dependency-info") {
    // ld64-style dependency info: 0x00 tool version, 0x10 input, 0x40 output; NUL-terminated strings.
    var deps = Data([0x00]) + Data("actool-\(actoolVersion.bundle)".utf8) + Data([0])
    for input in inputs { deps += Data([0x10]) + Data(input.path.utf8) + Data([0]) }
    for url in outputs { deps += Data([0x40]) + Data(url.path.utf8) + Data([0]) }
    try deps.write(to: URL(fileURLWithPath: path))
}
report(outputs)
