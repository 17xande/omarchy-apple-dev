import AssetKit
import Foundation
import PNG

// Xcode 14+ app icons are one 1024 pt "universal" image with no scale; actool
// derives everything from it. AssetKit keys renditions per idiom and per
// appearance, so rewrite that form into the exact shape Apple's actool
// compiles for it (verified against Apple's actool 27.0 output for the NNW
// catalog, oracle/nnwcar/apple):
//
// - one 1024x1024 1x entry per target device and appearance variant
//   (default, dark, tinted), source filenames kept: actool stores them in
//   the CSI name field,
// - loose AppIcon60x60@2x.png (120 px) and AppIcon76x76@2x~ipad.png (152 px)
//   downsamples, as Apple writes for this form,
// - an AppIconBundle with Apple's partial-plist shape.
//
// Everything else in the catalog is preserved: only the AppIcon.appiconset
// is replaced, so imagesets and colorsets keep compiling.
//
// Classic appiconsets that list every size are left untouched (the classic
// multi-rendition car is what those apps have always shipped).
public enum SingleSizeIcon {
    /// Returns `catalog` itself, or an expanded copy under a temporary
    /// directory when its AppIcon uses the single-size form. `idioms` are
    /// actool's `--target-device` values.
    public static func expandIfNeeded(catalog: URL, appIcon: String, idioms: [String]) throws -> (URL, AppIconBundle?) {
        let fm = FileManager.default
        guard let iconSet = try fm.contentsOfDirectory(at: catalog, includingPropertiesForKeys: nil)
            .first(where: { $0.pathExtension == "appiconset" }) else { return (catalog, nil) }
        let contentsURL = iconSet.appendingPathComponent("Contents.json")
        guard let contents = try JSONSerialization.jsonObject(with: Data(contentsOf: contentsURL)) as? [String: Any],
              let images = contents["images"] as? [[String: Any]],
              !images.isEmpty,
              images.allSatisfy({
                  $0["idiom"] as? String == "universal"
                      && $0["scale"] == nil
                      && $0["size"] as? String == "1024x1024"
              }),
              let base = images.first(where: { $0["appearances"] == nil }),
              let baseFilename = base["filename"] as? String
        else { return (catalog, nil) }

        let sourceURL = iconSet.appendingPathComponent(baseFilename)
        guard let source = try PNG.Image.decompress(path: sourceURL.path) else {
            throw CocoaError(.fileReadNoSuchFile)
        }
        let pixels = source.unpack(as: PNG.RGBA<UInt8>.self)

        // Copy the merged catalog, replacing only the appiconset.
        let work = fm.temporaryDirectory.appendingPathComponent("xcassets-\(UUID().uuidString)")
        let expanded = work.appendingPathComponent(catalog.lastPathComponent)
        try fm.copyItem(at: catalog, to: expanded)
        let outSet = expanded.appendingPathComponent(iconSet.lastPathComponent)

        // Entries matching Apple's compiled shape: every variant keyed once
        // per target idiom, source filename preserved (actool puts it in the
        // CSI name field; assetutil surfaces it as RenditionName).
        let entries: [[String: Any]] = idioms.flatMap { idiom in
            images.filter { $0["filename"] != nil }.map { image in
                image.merging(["idiom": idiom, "scale": "1x"]) { $1 }
            }
        }
        let newContents: [String: Any] = [
            "images": entries,
            "info": ["author": "xcode", "version": 1],
        ]
        try JSONSerialization.data(withJSONObject: newContents, options: [.prettyPrinted, .sortedKeys])
            .write(to: outSet.appendingPathComponent("Contents.json"))

        // Loose PNGs Apple writes for this form: the home-screen sizes.
        var loose: [LooseFile] = []
        let looseSpecs: [(points: Double, scale: Int, file: String)] = [
            (60, 2, "AppIcon60x60@2x.png"), (76, 2, "AppIcon76x76@2x~ipad.png"),
        ]
        for spec in looseSpecs {
            let side = Int((spec.points * Double(spec.scale)).rounded())
            let down = downsampleRGBA(pixels, from: source.size.x, to: side)
            let image = PNG.Image(
                packing: down, size: (side, side),
                layout: .init(format: .rgba8(palette: [], fill: nil)))
            let file = work.appendingPathComponent(spec.file)
            try image.compress(path: file.path, level: 9)
            let data = try Data(contentsOf: file)
            loose.append(LooseFile(name: spec.file, data: data))
        }

        let primary: [String: any Sendable] = [
            "CFBundlePrimaryIcon": [
                "CFBundleIconFiles": ["AppIcon60x60"],
                "CFBundleIconName": appIcon,
            ] as [String: any Sendable],
        ]
        var additions: [String: any Sendable] = ["CFBundleIcons": primary]
        var ipad: [String: any Sendable] = ["CFBundleIconFiles": ["AppIcon60x60", "AppIcon76x76"]]
        if idioms.contains("ipad") { ipad["CFBundleIconName"] = appIcon }
        additions["CFBundleIcons~ipad"] = ["CFBundlePrimaryIcon": ipad] as [String: any Sendable]
        let bundle = AppIconBundle(
            primaryIconName: appIcon,
            infoPlistAdditions: additions,
            looseFiles: loose)
        return (expanded, bundle)
    }

    /// Area-average downsample of a square RGBA image, preserving alpha
    /// (premultiplied accumulate, then un-premultiply per target pixel).
    static func downsampleRGBA(
        _ src: [PNG.RGBA<UInt8>], from n: Int, to m: Int
    ) -> [PNG.RGBA<UInt8>] {
        var out: [PNG.RGBA<UInt8>] = []
        out.reserveCapacity(m * m)
        for y in 0..<m {
            let y0 = y * n / m, y1 = max(y0 + 1, (y + 1) * n / m)
            for x in 0..<m {
                let x0 = x * n / m, x1 = max(x0 + 1, (x + 1) * n / m)
                var r = 0, g = 0, b = 0, a = 0, count = 0
                for sy in y0..<y1 {
                    for sx in x0..<x1 {
                        let p = src[sy * n + sx], alpha = Int(p.a)
                        r += Int(p.r) * alpha; g += Int(p.g) * alpha; b += Int(p.b) * alpha
                        a += alpha; count += 1
                    }
                }
                let outAlpha = a / count
                let unpre: (Int) -> UInt8 = { channel in
                    outAlpha == 0 ? 0 : UInt8(min(255, (channel / count) * 255 / outAlpha))
                }
                out.append(PNG.RGBA(unpre(r), unpre(g), unpre(b), UInt8(outAlpha)))
            }
        }
        return out
    }
}
