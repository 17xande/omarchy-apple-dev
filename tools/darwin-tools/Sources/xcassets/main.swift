// Compile an .xcassets catalog into a built .app: Assets.car, the loose app
// icon PNGs, and the CFBundleIcons keys merged into the app's Info.plist.
// xtool does not compile asset catalogs yet (xtool-org/xtool#219).
import AssetKit
import DarwinAssets
import Foundation

let args = CommandLine.arguments
guard args.count == 4 else {
    FileHandle.standardError.write(Data("usage: xcassets <Catalog.xcassets> <App.app> <deployment-target>\n".utf8))
    exit(2)
}
let source = URL(fileURLWithPath: args[1])
let app = URL(fileURLWithPath: args[2])

let catalog = try SingleSizeIcon.expandIfNeeded(catalog: source)
defer { if catalog != source { try? FileManager.default.removeItem(at: catalog.deletingLastPathComponent()) } }
let result = try await XCAssetCompiler(deploymentTarget: args[3]).compile(catalog: catalog)
try result.carData.write(to: app.appendingPathComponent("Assets.car"))
print("Assets.car: \(result.carData.count) bytes")

if let icon = result.appIconBundle {
    for file in icon.looseFiles {
        try file.data.write(to: app.appendingPathComponent(file.name))
    }
    let infoURL = app.appendingPathComponent("Info.plist")
    var format = PropertyListSerialization.PropertyListFormat.xml
    let plist = try PropertyListSerialization.propertyList(
        from: Data(contentsOf: infoURL), options: [], format: &format
    )
    guard var info = plist as? [String: Any] else {
        FileHandle.standardError.write(Data("\(infoURL.path): not a dictionary\n".utf8))
        exit(1)
    }
    info.merge(icon.infoPlistAdditions) { $1 }
    try PropertyListSerialization.data(fromPropertyList: info, format: format, options: 0).write(to: infoURL)
    print("App icon \(icon.primaryIconName): \(icon.looseFiles.count) loose PNGs, Info.plist updated")
}
