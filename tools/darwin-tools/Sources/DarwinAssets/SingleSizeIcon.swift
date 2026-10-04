import AssetKit
import Foundation
import PNG

// Xcode 14+ app icons are one 1024 pt "universal" image with no scale; actool
// derives everything from it. AssetKit needs one explicit entry, so rewrite
// that form into the exact shape Apple's actool produces for it:
//
// - one catalog entry (iphone, 1024x1024, 1x, source renamed icon.png) so
//   AssetKit emits Apple's two renditions (the 1024 bitmap + a MultiSized
//   container listing it),
// - loose AppIcon60x60@2x.png (120 px) and AppIcon76x76@2x~ipad.png (152 px)
//   downsamples, as Apple writes for this form,
// - an AppIconBundle with Apple's partial-plist shape.
//
// Classic appiconsets that list every size are left untouched (the classic
// multi-rendition car is what those apps have always shipped).
public enum SingleSizeIcon {
    public struct Expanded {
        /// Catalog for AssetKit (temporary directory).
        public var catalog: URL
        /// Apple-shaped bundle overriding AssetKit's appIconBundle.
        public var bundle: AppIconBundle
    }

    /// Returns `catalog` itself, or an expanded copy under a temporary
    /// directory when its AppIcon uses the single-size form.
    public static func expandIfNeeded(catalog: URL, appIcon: String) throws -> (URL, AppIconBundle?) {
        let fm = FileManager.default
        guard let iconSet = try fm.contentsOfDirectory(at: catalog, includingPropertiesForKeys: nil)
            .first(where: { $0.pathExtension == "appiconset" }) else { return (catalog, nil) }
        let contentsURL = iconSet.appendingPathComponent("Contents.json")
        guard let contents = try JSONSerialization.jsonObject(with: Data(contentsOf: contentsURL)) as? [String: Any],
              let images = contents["images"] as? [[String: Any]],
              images.allSatisfy({ $0["idiom"] as? String == "universal" && $0["scale"] == nil }),
              let only = images.first(where: { $0["appearances"] == nil }),
              only["size"] as? String == "1024x1024", let filename = only["filename"] as? String
        else { return (catalog, nil) }
        if images.count > 1 {
            FileHandle.standardError.write(Data("\(iconSet.path): warning: dark and tinted icon variants are not compiled on Linux\n".utf8))
        }

        let sourceURL = iconSet.appendingPathComponent(filename)
        guard let source = try PNG.Image.decompress(path: sourceURL.path) else {
            throw CocoaError(.fileReadNoSuchFile)
        }
        let pixels = source.unpack(as: PNG.RGBA<UInt8>.self)

        let work = fm.temporaryDirectory.appendingPathComponent("xcassets-\(UUID().uuidString)")
        let expanded = work.appendingPathComponent(catalog.lastPathComponent)
        let outSet = expanded.appendingPathComponent("AppIcon.appiconset")
        try fm.createDirectory(at: outSet, withIntermediateDirectories: true)

        // Catalog entry matching Apple's single-size car shape: one iphone
        // 1024 entry named icon.png -> one bitmap rendition (scale 1, index 1)
        // plus a MultiSized container listing it.
        try fm.copyItem(at: sourceURL, to: outSet.appendingPathComponent("icon.png"))
        let newContents: [String: Any] = [
            "images": [["filename": "icon.png", "idiom": "iphone", "size": "1024x1024", "scale": "1x"]],
            "info": ["author": "xcode", "version": 1],
        ]
        try JSONSerialization.data(withJSONObject: newContents)
            .write(to: outSet.appendingPathComponent("Contents.json"))
        try Data(#"{"info":{"author":"xcode","version":1}}"#.utf8)
            .write(to: expanded.appendingPathComponent("Contents.json"))

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
        additions["CFBundleIcons~ipad"] = [
            "CFBundlePrimaryIcon": [
                "CFBundleIconFiles": ["AppIcon60x60", "AppIcon76x76"],
            ] as [String: any Sendable],
        ] as [String: any Sendable]
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
