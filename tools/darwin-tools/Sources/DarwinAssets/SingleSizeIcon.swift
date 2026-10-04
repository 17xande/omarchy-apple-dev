import Foundation
import PNG

// Xcode 14+ app icons are one 1024 pt "universal" image with no scale; actool
// derives the device sizes from it. AssetKit 1.0.0 needs every size listed
// with a scale, so expand that form into the sizes the App Store checks.
public enum SingleSizeIcon {
    /// (idiom, point size, scale)
    static let sizes: [(String, String, Int)] = [
        ("iphone", "60x60", 2), ("iphone", "60x60", 3),
        ("ipad", "76x76", 2), ("ipad", "83.5x83.5", 2),
        ("ios-marketing", "1024x1024", 1),
    ]

    /// Returns a catalog AssetKit accepts: `catalog` itself, or an expanded copy
    /// under a temporary directory when its AppIcon uses the single-size form.
    public static func expandIfNeeded(catalog: URL) throws -> URL {
        let fm = FileManager.default
        guard let iconSet = try fm.contentsOfDirectory(at: catalog, includingPropertiesForKeys: nil)
            .first(where: { $0.pathExtension == "appiconset" }) else { return catalog }
        let contentsURL = iconSet.appendingPathComponent("Contents.json")
        // ponytail: dark and tinted variants ("appearances", iOS 18) are dropped; only the
        // default image is expanded. Add them when AssetKit writes appearance renditions.
        guard let contents = try JSONSerialization.jsonObject(with: Data(contentsOf: contentsURL)) as? [String: Any],
              let images = contents["images"] as? [[String: Any]],
              images.allSatisfy({ $0["idiom"] as? String == "universal" && $0["scale"] == nil }),
              let only = images.first(where: { $0["appearances"] == nil }),
              only["size"] as? String == "1024x1024", let filename = only["filename"] as? String
        else { return catalog }
        if images.count > 1 {
            FileHandle.standardError.write(Data("\(iconSet.path): warning: dark and tinted icon variants are not compiled on Linux\n".utf8))
        }

        guard let source = try PNG.Image.decompress(path: iconSet.appendingPathComponent(filename).path) else {
            throw CocoaError(.fileReadNoSuchFile)
        }
        let pixels = source.unpack(as: PNG.RGBA<UInt8>.self)

        let work = fm.temporaryDirectory.appendingPathComponent("xcassets-\(UUID().uuidString)")
        let expanded = work.appendingPathComponent(catalog.lastPathComponent)
        try fm.createDirectory(at: work, withIntermediateDirectories: true)
        try fm.copyItem(at: catalog, to: expanded)
        let outSet = expanded.appendingPathComponent(iconSet.lastPathComponent)

        var entries: [[String: Any]] = []
        for (idiom, size, scale) in sizes {
            let points = Double(size.split(separator: "x")[0])!
            let side = Int((points * Double(scale)).rounded())
            let name = "icon-\(side).png"
            let resized = downsample(pixels, from: source.size.x, to: side)
            // App Store icons must not carry an alpha channel (ITMS-90717).
            let image = PNG.Image(
                packing: resized, size: (side, side),
                layout: .init(format: .rgb8(palette: [], fill: nil, key: nil))
            )
            try image.compress(path: outSet.appendingPathComponent(name).path, level: 9)
            entries.append(["filename": name, "idiom": idiom, "size": size, "scale": "\(scale)x"])
        }
        var newContents = contents
        newContents["images"] = entries
        try JSONSerialization.data(withJSONObject: newContents).write(to: outSet.appendingPathComponent("Contents.json"))
        return expanded
    }

    /// Area-average downsample of a square RGBA image, alpha composited onto black.
    static func downsample(_ src: [PNG.RGBA<UInt8>], from n: Int, to m: Int) -> [PNG.RGBA<UInt8>] {
        var out: [PNG.RGBA<UInt8>] = []
        out.reserveCapacity(m * m)
        for y in 0..<m {
            let y0 = y * n / m, y1 = max(y0 + 1, (y + 1) * n / m)
            for x in 0..<m {
                let x0 = x * n / m, x1 = max(x0 + 1, (x + 1) * n / m)
                var r = 0, g = 0, b = 0
                for sy in y0..<y1 {
                    for sx in x0..<x1 {
                        let p = src[sy * n + sx], a = Int(p.a)
                        r += Int(p.r) * a / 255; g += Int(p.g) * a / 255; b += Int(p.b) * a / 255
                    }
                }
                let count = (y1 - y0) * (x1 - x0)
                out.append(PNG.RGBA(UInt8(r / count), UInt8(g / count), UInt8(b / count)))
            }
        }
        return out
    }
}
