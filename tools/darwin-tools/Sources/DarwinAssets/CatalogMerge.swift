import AssetKit
import Foundation

/// Prepare actool's input catalogs for AssetKit: AssetKit compiles one catalog, knows imagesets,
/// colorsets and one appiconset, and rejects anything else. Copy every catalog side by side into
/// one temporary catalog, keeping only what AssetKit can compile and listing what was left out.
public enum CatalogMerge {
    public struct DuplicateEntry: Error, CustomStringConvertible {
        public let name: String
        public var description: String { "\(name) is defined in more than one asset catalog" }
    }

    public struct Prepared {
        /// The merged catalog, inside its own temporary directory.
        public let catalog: URL
        /// Entries left out, as "<catalog>/<relative path>: <reason>".
        public let skipped: [String]
        /// The --app-icon Icon Composer source, compiled layered by
        /// XCAssetCompiler instead of through the appiconset path.
        public let iconComposer: IconComposerCompiler.Input?
    }

    /// - Parameter appIcon: the one .appiconset to keep (actool's --app-icon); others are skipped.
    public static func prepare(_ catalogs: [URL], appIcon: String?) throws -> Prepared {
        let fm = FileManager.default
        let merged = fm.temporaryDirectory
            .appendingPathComponent("actool-\(UUID().uuidString)")
            .appendingPathComponent("Merged.xcassets")
        try fm.createDirectory(at: merged, withIntermediateDirectories: true)
        try Data(#"{"info":{"author":"xcode","version":1}}"#.utf8)
            .write(to: merged.appendingPathComponent("Contents.json"))
        var skipped: [String] = []
        var iconComposer: IconComposerCompiler.Input? = nil

        func copy(_ dir: URL, into dest: URL, catalog: URL) throws {
            for child in try fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: [.isDirectoryKey])
            where child.lastPathComponent != "Contents.json" {
                let target = dest.appendingPathComponent(child.lastPathComponent)
                let where_ = "\(catalog.path)/\(child.path.dropFirst(catalog.path.count + 1))"
                let isDir = (try? child.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
                switch child.pathExtension {
                case "imageset":
                    if let format = unsupportedImageFormat(child) {
                        skipped.append("\(where_): .\(format) images are not supported by AssetKit")
                    } else {
                        try place(child, at: target)
                    }
                case "colorset":
                    if try !copyColorSet(child, to: target) {
                        skipped.append("\(where_): no color defined")
                    }
                case "symbolset":
                    try place(child, at: target)
                case "appiconset":
                    if child.deletingPathExtension().lastPathComponent == appIcon {
                        try place(child, at: target)
                    } else {
                        skipped.append("\(where_): not the --app-icon set")
                    }
                case "icon":
                    // Icon Composer source. The one matching --app-icon is
                    // compiled layered; others (alternate icons) are skipped.
                    if child.deletingPathExtension().lastPathComponent == appIcon {
                        iconComposer = recordIconComposerIcon(child, appIcon: appIcon, where_: where_, skipped: &skipped)
                    } else {
                        skipped.append("\(where_): alternate .icon icons are not supported by AssetKit")
                    }
                case "" where isDir:
                    try fm.createDirectory(at: target, withIntermediateDirectories: true)
                    let folderContents = child.appendingPathComponent("Contents.json")
                    if fm.fileExists(atPath: folderContents.path) {
                        try fm.copyItem(at: folderContents, to: target.appendingPathComponent("Contents.json"))
                    }
                    try copy(child, into: target, catalog: catalog)
                default:
                    skipped.append("\(where_): \(child.pathExtension.isEmpty ? "not an asset" : ".\(child.pathExtension) is not supported by AssetKit")")
                }
            }
        }

        func place(_ source: URL, at target: URL) throws {
            guard !fm.fileExists(atPath: target.path) else { throw DuplicateEntry(name: target.lastPathComponent) }
            try fm.copyItem(at: source, to: target)
        }

        /// The first source file extension AssetKit cannot read (it reads PNG, JPEG, SVG and PDF).
        func unsupportedImageFormat(_ imageSet: URL) -> String? {
            guard let data = try? Data(contentsOf: imageSet.appendingPathComponent("Contents.json")),
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let images = json["images"] as? [[String: Any]] else { return nil }
            return images.compactMap { ($0["filename"] as? String).map { URL(fileURLWithPath: $0).pathExtension.lowercased() } }
                .first { !["png", "jpg", "jpeg", "svg", "pdf"].contains($0) }
        }

        /// Copies a colorset without its color-less entries (Xcode's empty AccentColor placeholder).
        func copyColorSet(_ source: URL, to target: URL) throws -> Bool {
            let json = try JSONSerialization.jsonObject(with: Data(contentsOf: source.appendingPathComponent("Contents.json")))
            guard var contents = json as? [String: Any], let colors = contents["colors"] as? [[String: Any]] else {
                try place(source, at: target)
                return true
            }
            let defined = colors.filter { $0["color"] != nil }
            guard !defined.isEmpty else { return false }
            try place(source, at: target)
            contents["colors"] = defined
            try JSONSerialization.data(withJSONObject: contents).write(to: target.appendingPathComponent("Contents.json"))
            return true
        }

        for catalog in catalogs {
            if catalog.pathExtension == "icon" {
                // An Icon Composer .icon passed as its own catalog input
                // (SwiftBuild passes folder.iconcomposer.icon paths through).
                iconComposer = recordIconComposerIcon(
                    catalog, appIcon: appIcon, where_: catalog.path, skipped: &skipped)
                continue
            }
            try copy(catalog, into: merged, catalog: catalog)
        }
        return Prepared(catalog: merged, skipped: skipped, iconComposer: iconComposer)
    }

    /// Records an Icon Composer `.icon` as the layered app-icon input when
    /// it is the `--app-icon`; other .icon files (alternate icons) are
    /// skipped with a warning. Idioms are filled in by the caller from
    /// actool's --target-device flags.
    static func recordIconComposerIcon(
        _ icon: URL, appIcon: String?, where_: String, skipped: inout [String]
    ) -> IconComposerCompiler.Input? {
        let name = icon.deletingPathExtension().lastPathComponent
        guard let appIcon = appIcon else {
            skipped.append("\(where_): no --app-icon to attach it to")
            return nil
        }
        guard name == appIcon else {
            skipped.append("\(where_): alternate .icon icons are not supported by AssetKit")
            return nil
        }
        return IconComposerCompiler.Input(name: appIcon, directory: icon, idioms: [])
    }
}
