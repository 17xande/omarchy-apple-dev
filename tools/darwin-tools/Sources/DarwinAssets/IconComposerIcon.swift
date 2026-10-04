import AssetKit
import Foundation
import PNG

/// Renders an Icon Composer `.icon` app icon for the Linux actool: flatten
/// `icon.json` (light appearance) onto a 1024x1024 canvas and materialize a
/// classic single-size appiconset for `SingleSizeIcon` to expand.
///
/// Rendered: the background fill (system-light/system-dark presets, solid,
/// vertical linear gradients) and every visible layer's PNG (or SVG via
/// AssetKit's rsvg-convert rasterizer) at `position.scale` and
/// `translation-in-points`, groups in order, layer fills alpha-masked by the
/// layer image. Not rendered (one `warning:` line each): glass, shadows,
/// translucency, blur materials, non-normal blend modes, and dark/tinted
/// variants - light appearance only.
public enum IconComposerIcon {
    public struct Rendered {
        /// Temporary catalog directory containing `<appIcon>.appiconset` in
        /// the single-size 1024 form `SingleSizeIcon.expandIfNeeded` accepts.
        public var catalog: URL
        public var warnings: [String]
    }

    /// The icon canvas is 1024 pt; one point is one pixel here.
    static let canvasSide = 1024

    // MARK: - Entry point

    /// - Parameter catalog: a directory named `<name>.icon` holding
    ///   `icon.json` and an `Assets/` folder.
    public static func render(catalog: URL, appIcon: String) throws -> Rendered {
        let fm = FileManager.default
        let json = try JSONSerialization.jsonObject(with: Data(contentsOf: catalog.appendingPathComponent("icon.json")))
        guard let json = json as? [String: Any] else {
            throw CocoaError(.propertyListReadCorrupt)
        }

        var warnings: [String] = []
        func warn(_ feature: String) {
            let line = "\(feature) not rendered on Linux"
            if !warnings.contains(line) { warnings.append(line) }
        }

        var canvas = [Pixel](repeating: .clear, count: canvasSide * canvasSide)

        // Background fill (top-level fill-specializations).
        renderFill(lightFill(json["fill-specializations"] as? [[String: Any]]), into: &canvas, rect: nil)

        if hasVariantSpecializations(json["fill-specializations"] as? [[String: Any]]) {
            warn("dark and tinted variants are")
        }

        // Layers, groups in order.
        let groups = json["groups"] as? [[String: Any]] ?? []
        for group in groups {
            if group["shadow"] != nil { warn("shadows are") }
            if (group["specular"] as? Bool) == true { warn("specular highlights are") }
            if (group["blur-material"] as? Int) != nil { warn("blur materials are") }
            if let blur = group["blur-material-specializations"] as? [[String: Any]], !blur.isEmpty {
                warn("blur materials are")
            }
            if let translucency = group["translucency-specializations"] as? [[String: Any]],
               !translucency.isEmpty {
                warn("translucency is")
            }
            if group["lighting"] != nil { warn("glass lighting is") }
            if hasVariantSpecializations(group["blend-mode-specializations"] as? [[String: Any]]) {
                warn("dark and tinted variants are")
            }

            let layers = group["layers"] as? [[String: Any]] ?? []
            for layer in layers {
                if layer["hidden"] as? Bool == true { continue }
                if layer["glass"] as? Bool == true { warn("glass is") }
                if hasVariantSpecializations(layer["blend-mode-specializations"] as? [[String: Any]]) {
                    warn("non-normal blend modes are")
                }
                if hasVariantSpecializations(layer["fill-specializations"] as? [[String: Any]]) {
                    warn("dark and tinted variants are")
                }

                guard let imageName = layer["image-name"] as? String else { continue }
                let imageURL = catalog.appendingPathComponent("Assets").appendingPathComponent(imageName)
                let layerImage: LayerImage
                do {
                    layerImage = try LayerImage.load(imageURL)
                } catch {
                    let line = "layer \(imageName) is not rendered on Linux (\(error))"
                    if !warnings.contains(line) { warnings.append(line) }
                    continue
                }

                let position = layer["position"] as? [String: Any] ?? [:]
                let scale = position["scale"] as? Double ?? 1
                let translation = position["translation-in-points"] as? [Double] ?? [0, 0]
                draw(layerImage,
                     fill: lightFill(layer["fill-specializations"] as? [[String: Any]]),
                     scale: scale,
                     translation: (translation.first ?? 0, translation.count > 1 ? translation[1] : 0),
                     onto: &canvas)
            }
        }

        // Materialize the single-size appiconset SingleSizeIcon expands.
        let work = fm.temporaryDirectory.appendingPathComponent("xcassets-\(UUID().uuidString)")
        let merged = work.appendingPathComponent("Merged.xcassets")
        let iconSet = merged.appendingPathComponent("\(appIcon).appiconset")
        try fm.createDirectory(at: iconSet, withIntermediateDirectories: true)
        try Data(#"{"info":{"author":"xcode","version":1}}"#.utf8)
            .write(to: merged.appendingPathComponent("Contents.json"))

        let image = PNG.Image(
            packing: flatten(canvas), size: (canvasSide, canvasSide),
            layout: .init(format: .rgb8(palette: [], fill: nil, key: nil)))
        try image.compress(path: iconSet.appendingPathComponent("icon-1024.png").path, level: 9)
        let contents: [String: Any] = [
            "images": [["filename": "icon-1024.png", "idiom": "universal", "size": "1024x1024"]],
            "info": ["author": "xcode", "version": 1],
        ]
        try JSONSerialization.data(withJSONObject: contents)
            .write(to: iconSet.appendingPathComponent("Contents.json"))
        return Rendered(catalog: merged, warnings: warnings)
    }

    // MARK: - Specialization decode

    /// The light-appearance value of a specialization list: the first entry
    /// without an "appearance" key. Dark/tinted entries carry the value for
    /// other appearances and are covered by the caller's warning.
    static func lightFill(_ specializations: [[String: Any]]?) -> Any? {
        specializations?.first(where: { $0["appearance"] == nil })?["value"]
    }

    static func hasVariantSpecializations(_ specializations: [[String: Any]]?) -> Bool {
        specializations?.contains { $0["appearance"] != nil } == true
    }

    // MARK: - Colors

    struct Color {
        var red: Double, green: Double, blue: Double, alpha: Double

        /// Parses Icon Composer color strings: "srgb:r,g,b,a" and
        /// "display-p3:r,g,b,a" (converted to sRGB; both share the sRGB
        /// transfer curve, so only the RGB primaries matrix differs).
        static func parse(_ string: String) throws -> Color {
            let parts = string.split(separator: ":", maxSplits: 1)
            guard parts.count == 2 else { throw CocoaError(.propertyListReadCorrupt) }
            let values = parts[1].split(separator: ",")
                .compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
            guard values.count == 4 else { throw CocoaError(.propertyListReadCorrupt) }
            let color = Color(red: values[0], green: values[1], blue: values[2], alpha: values[3])
            return parts[0] == "display-p3" ? color.convertedDisplayP3ToSRGB() : color
        }

        func convertedDisplayP3ToSRGB() -> Color {
            // Linearize (Display P3 uses the sRGB transfer curve), apply the
            // Display P3 -> sRGB primaries matrix, re-encode.
            func linear(_ c: Double) -> Double {
                c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
            }
            func encode(_ c: Double) -> Double {
                let v = c <= 0.0031308 ? c * 12.92 : 1.055 * pow(c, 1 / 2.4) - 0.055
                return min(max(v, 0), 1)
            }
            let r = linear(red), g = linear(green), b = linear(blue)
            let m: [[Double]] = [
                [1.2249402, -0.2249404, 0.0],
                [-0.0420570, 1.0420571, 0.0],
                [-0.0196376, -0.0786361, 1.0982735],
            ]
            let s = [
                m[0][0] * r + m[0][1] * g + m[0][2] * b,
                m[1][0] * r + m[1][1] * g + m[1][2] * b,
                m[2][0] * r + m[2][1] * g + m[2][2] * b,
            ]
            return Color(red: encode(s[0]), green: encode(s[1]), blue: encode(s[2]), alpha: alpha)
        }
    }

    // MARK: - Fills

    /// A resolved fill: one color, or the stops of a vertical gradient.
    enum Fill {
        case solid(Color)
        case gradient([Color])
    }

    /// Resolves a fill value: preset names, `{"solid": "..."}`, or
    /// `{"linear-gradient": ["...", ...]}`. Unknown values ("automatic") mean
    /// no fill for the light appearance.
    static func resolveFill(_ value: Any?) -> Fill? {
        if let name = value as? String {
            switch name {
            case "system-light":
                // Apple's system preset, decoded from the actool 27.0
                // oracle's Named Gradient + Color renditions: white to
                // 92.5% gray, top to bottom.
                return .gradient([Color(red: 1, green: 1, blue: 1, alpha: 1),
                                  Color(red: 0.925, green: 0.925, blue: 0.925, alpha: 1)])
            case "system-dark":
                return .gradient([Color(red: 0.192, green: 0.192, blue: 0.192, alpha: 1),
                                  Color(red: 0.078, green: 0.078, blue: 0.078, alpha: 1)])
            default:
                return nil
            }
        }
        guard let dict = value as? [String: Any] else { return nil }
        if let solid = dict["solid"] as? String, let color = try? Color.parse(solid) {
            return .solid(color)
        }
        if let stops = dict["linear-gradient"] as? [String] {
            return .gradient(stops.compactMap { try? Color.parse($0) })
        }
        return nil
    }

    static func sampleGradient(_ stops: [Color], t: Double) -> Color {
        guard stops.count > 1 else { return stops.first ?? Color(red: 0, green: 0, blue: 0, alpha: 1) }
        let scaled = t * Double(stops.count - 1)
        let index = min(Int(scaled), stops.count - 2)
        let fraction = scaled - Double(index)
        let a = stops[index], b = stops[index + 1]
        return Color(
            red: a.red + (b.red - a.red) * fraction,
            green: a.green + (b.green - a.green) * fraction,
            blue: a.blue + (b.blue - a.blue) * fraction,
            alpha: a.alpha + (b.alpha - a.alpha) * fraction)
    }

    // MARK: - Pixels

    /// Straight-alpha 8-bit pixel with source-over compositing.
    struct Pixel {
        var r: UInt8 = 0, g: UInt8 = 0, b: UInt8 = 0, a: UInt8 = 0

        static let clear = Pixel()

        mutating func composite(color: Color) {
            let sa = UInt8((min(max(color.alpha, 0), 1) * 255).rounded())
            let sr = UInt8((min(max(color.red, 0), 1) * 255).rounded())
            let sg = UInt8((min(max(color.green, 0), 1) * 255).rounded())
            let sb = UInt8((min(max(color.blue, 0), 1) * 255).rounded())
            blend(source: (sr, sg, sb), sourceAlpha: sa)
        }

        mutating func blend(source s: (UInt8, UInt8, UInt8), sourceAlpha sa: UInt8) {
            let inv = 255 - Int(sa)
            func over(_ d: UInt8, _ v: UInt8) -> UInt8 {
                UInt8((Int(v) * Int(sa) + Int(d) * inv + 127) / 255)
            }
            r = over(r, s.0); g = over(g, s.1); b = over(b, s.2)
            a = UInt8(min(255, Int(sa) + Int(a) * inv / 255))
        }
    }

    struct Rect {
        var x: Int, y: Int, side: Int
    }

    /// Paints a fill over the full canvas (rect == nil) or a layer rect.
    static func renderFill(_ value: Any?, into canvas: inout [Pixel], rect: Rect?) {
        guard let fill = resolveFill(value) else { return }
        let side = rect?.side ?? canvasSide
        let x0 = rect?.x ?? 0, y0 = rect?.y ?? 0
        for y in 0..<side {
            let t = side > 1 ? Double(y) / Double(side - 1) : 0
            let color: Color
            switch fill {
            case .solid(let c): color = c
            case .gradient(let stops): color = sampleGradient(stops, t: t)
            }
            for x in 0..<side {
                let index = (y0 + y) * canvasSide + (x0 + x)
                guard index >= 0 && index < canvas.count else { continue }
                canvas[index].composite(color: color)
            }
        }
    }

    // MARK: - Layers

    /// A decoded layer image (the 1024 pt layer canvas at pixel resolution).
    struct LayerImage {
        var width: Int
        var pixels: [Pixel]

        /// In-memory PNG source for swift-png, which reads from files or
        /// conforming streams.
        private struct MemoryBytestream: PNG.BytestreamSource {
            var bytes: [UInt8]
            var offset: Int = 0
            mutating func read(count: Int) -> [UInt8]? {
                guard offset + count <= bytes.count else { return nil }
                defer { offset += count }
                return Array(bytes[offset..<offset + count])
            }
        }

        /// Loads a layer image: PNG natively, SVG through AssetKit's
        /// rsvg-convert rasterizer when it is installed.
        static func load(_ url: URL) throws -> LayerImage {
            if url.pathExtension.lowercased() == "svg" {
                let png = try RsvgConvertRasterizer()
                    .rasterize(svgData: Data(contentsOf: url),
                               pixelWidth: UInt32(canvasSide), pixelHeight: UInt32(canvasSide))
                return try decode(png)
            }
            return try decode(try Data(contentsOf: url))
        }

        static func decode(_ bytes: Data) throws -> LayerImage {
            var source = MemoryBytestream(bytes: [UInt8](bytes))
            let image = try PNG.Image.decompress(stream: &source)
            let rgba = image.unpack(as: PNG.RGBA<UInt8>.self)
            var pixels = [Pixel]()
            pixels.reserveCapacity(rgba.count)
            for p in rgba {
                pixels.append(Pixel(r: p.r, g: p.g, b: p.b, a: p.a))
            }
            return LayerImage(width: image.size.x, pixels: pixels)
        }
    }

    /// Draws one layer: fill (if any) alpha-masked by the image, or the image
    /// itself, scaled about the canvas center and translated in points.
    static func draw(
        _ layer: LayerImage, fill: Any?, scale: Double,
        translation: (Double, Double), onto canvas: inout [Pixel]
    ) {
        let side = max(1, Int((Double(canvasSide) * scale).rounded()))
        let x0 = (canvasSide - side) / 2 + Int(translation.0.rounded())
        let y0 = (canvasSide - side) / 2 + Int(translation.1.rounded())
        let fill = resolveFill(fill)

        for y in 0..<side {
            let canvasY = y0 + y
            guard canvasY >= 0, canvasY < canvasSide else { continue }
            let sy = (Double(y) + 0.5) * Double(layer.width) / Double(side) - 0.5
            let sy0 = max(0, min(layer.width - 1, Int(sy.rounded(.down))))
            let sy1 = max(0, min(layer.width - 1, sy0 + 1))
            let fy = max(0, min(1, sy - Double(sy0)))
            for x in 0..<side {
                let canvasX = x0 + x
                guard canvasX >= 0, canvasX < canvasSide else { continue }
                let sx = (Double(x) + 0.5) * Double(layer.width) / Double(side) - 0.5
                let sx0 = max(0, min(layer.width - 1, Int(sx.rounded(.down))))
                let sx1 = max(0, min(layer.width - 1, sx0 + 1))
                let fx = max(0, min(1, sx - Double(sx0)))
                let p = bilinear(layer, sx0, sy0, sx1, sy1, fx, fy)
                if p.a == 0 { continue }
                var out = canvas[canvasY * canvasSide + canvasX]
                if let fill {
                    let t = side > 1 ? Double(y) / Double(side - 1) : 0
                    var color: Color
                    switch fill {
                    case .solid(let c): color = c
                    case .gradient(let stops): color = sampleGradient(stops, t: t)
                    }
                    color.alpha *= Double(p.a) / 255
                    out.composite(color: color)
                } else {
                    out.blend(source: (p.r, p.g, p.b), sourceAlpha: p.a)
                }
                canvas[canvasY * canvasSide + canvasX] = out
            }
        }
    }

    static func bilinear(
        _ layer: LayerImage, _ x0: Int, _ y0: Int, _ x1: Int, _ y1: Int,
        _ fx: Double, _ fy: Double
    ) -> Pixel {
        func lerp(_ a: Pixel, _ b: Pixel, _ t: Double) -> Pixel {
            func mix(_ u: UInt8, _ v: UInt8) -> UInt8 {
                UInt8((Double(u) + (Double(v) - Double(u)) * t).rounded())
            }
            return Pixel(r: mix(a.r, b.r), g: mix(a.g, b.g), b: mix(a.b, b.b), a: mix(a.a, b.a))
        }
        let top = lerp(layer.pixels[y0 * layer.width + x0], layer.pixels[y0 * layer.width + x1], fx)
        let bottom = lerp(layer.pixels[y1 * layer.width + x0], layer.pixels[y1 * layer.width + x1], fx)
        return lerp(top, bottom, fy)
    }

    // MARK: - Flatten

    /// The canvas already holds the composited result over an opaque
    /// background; drop alpha for the App Store RGB form.
    static func flatten(_ canvas: [Pixel]) -> [PNG.RGBA<UInt8>] {
        var out = [PNG.RGBA<UInt8>]()
        out.reserveCapacity(canvas.count)
        for p in canvas {
            out.append(PNG.RGBA(p.r, p.g, p.b))
        }
        return out
    }
}
