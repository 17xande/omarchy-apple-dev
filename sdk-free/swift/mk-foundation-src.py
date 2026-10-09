#!/usr/bin/env python3
"""Copy the open swift-5.3 Foundation overlay files we use and apply the 6.x / SDK-free patches.
Sources: SWIFT53_SRC (a swiftlang/swift swift-5.3-RELEASE checkout), output SWIFT53_OUT.
Patches are plain string replacements; a missing `old` is an error so source drift is noticed."""
import os
import shutil
import sys

SRC = os.path.join(os.environ["SWIFT53_SRC"], "stdlib/public/Darwin/Foundation")
OUT = os.environ["SWIFT53_OUT"]
os.makedirs(OUT, exist_ok=True)

FILES = sys.argv[1:] or ["String", "NSString", "NSArray", "NSDictionary", "NSSet", "NSNumber", "NSFastEnumeration", "Boxing",
                         "NSRange", "NSGeometry", "ReferenceConvertible"]

# (file, old, new): exact replacements; a missing `old` is an error so a drift in the source is noticed
PATCHES = [
    ("NSStringEncodings", "    return String.localizedName(of: self)", "    return \"String.Encoding(\\(rawValue))\""),
    ("NSNumber", "if let nsDecimalNumber: NSDecimalNumber = self as? NSDecimalNumber {\n            return AnyHashable(nsDecimalNumber.decimalValue)\n        } else if self === kCFBooleanTrue", "if self === kCFBooleanTrue"),
    ("NSError", "      _errorDomainUserInfoProviderQueue.sync {\n        if NSError.userInfoValueProvider(forDomain: domain) != nil { return }\n        NSError.setUserInfoValueProvider(forDomain: domain) { (error, key) in", "      _errorDomainUserInfoProviderQueue.sync { () -> Void in\n        if NSError.userInfoValueProvider(forDomain: domain) != nil { return }\n        NSError.setUserInfoValueProvider(forDomain: domain) { (error: Error, key: String) -> Any? in"),
    ("NSDictionary", "      result = x as [NSObject : AnyObject] as? Dictionary\n      return result != nil", "      var d = Dictionary<Key, Value>(minimumCapacity: x.count)\n      for k in x.allKeys {\n        guard let kk = k as? Key, let v = x.object(forKey: k), let vv = v as? Value else { result = nil; return false }\n        d[kk] = vv\n      }\n      result = d\n      return true"),
    ("NSDictionary", "return Mirror(reflecting: self as [NSObject : AnyObject])", "return Mirror(self, children: [:])"),
    ("NSError", "    hasher.combine(_nsError)\n  }\n\n  @_alwaysEmitIntoClient public var hashValue: Int {\n    return _nsError.hashValue", "    hasher.combine(_nsError.hash)\n  }\n\n  @_alwaysEmitIntoClient public var hashValue: Int {\n    return _nsError.hash"),
    ("Foundation", "@_exported import Foundation // Clang module", "@_exported import Foundation // Clang module\n@_exported import ObjectiveC"),
    ("Foundation", "extension NSObject : CustomStringConvertible {}", "// (removed: description does not bridge in this setup yet)"),
    ("Foundation", "extension NSObject : CustomDebugStringConvertible {}", "// (removed)"),
    ("String", "extension String: CVarArg {}",
     "extension String: CVarArg {\n  public var _cVarArgEncoding: [Int] { return (self as NSString)._cVarArgEncoding }\n}"),
    ("NSSet", "extension Set: CVarArg {}",
     "extension Set: CVarArg {\n  public var _cVarArgEncoding: [Int] { return (self as NSSet)._cVarArgEncoding }\n}"),
    ("NSArray", "extension Array: CVarArg {}",
     "extension Array: CVarArg {\n  public var _cVarArgEncoding: [Int] { let o = self as NSArray; _autorelease(o); return _encodeBitsAsWords(o) }\n}"),
    ("NSDictionary", "extension Dictionary: CVarArg {}",
     "extension Dictionary: CVarArg {\n  public var _cVarArgEncoding: [Int] { let o = self as NSDictionary; _autorelease(o); return _encodeBitsAsWords(o) }\n}"),
]

# blocks removed: (file, text that starts the block). The block ends at the brace that closes the first '{' after the start text.
REMOVE = [
    ("NSString", "  public class func localizedStringWithFormat("),
    ("NSRange", "    public init?(_ string: __shared String) {"),
    ("NSError", "public struct MachError : _BridgedStoredNSError {"),
    ("NSError", "  public var failureURLPeerTrust: SecTrust? {"),
    ("Data", "    @inlinable // This is @inlinable as a convenience initializer.\n    public init(contentsOf url: __shared URL, options: Data.ReadingOptions = []) throws {"),
    ("Data", "    public func write(to url: URL, options: Data.WritingOptions = []) throws {"),
    ("Foundation", "extension AnyHashable : _ObjectiveCBridgeable {"),
    ("NSSet", "extension NSOrderedSet {"),
    ("NSSet", "extension NSOrderedSet : ExpressibleByArrayLiteral {"),
    ("NSSet", "extension NSOrderedSet : Sequence {"),
    ("NSString", "  public convenience init(\n    format: __shared NSString, locale: Locale?, _ args: CVarArg...\n  ) {"),
]


def remove_block(text, start):
    i = text.find(start)
    if i < 0:
        return None
    j = text.index("{", i)
    depth = 0
    k = j
    while k < len(text):
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[:i] + text[k + 1:]
        k += 1
    return None


for name in FILES:
    src = os.path.join(SRC, name + ".swift")
    if not os.path.exists(src):
        print("missing", name, file=sys.stderr)
        sys.exit(1)
    shutil.copy(src, os.path.join(OUT, name + ".swift"))
for f, old, new in PATCHES:
    p = os.path.join(OUT, f + ".swift")
    if not os.path.exists(p):
        continue
    with open(p) as fh:
        s = fh.read()
    if old not in s:
        print("PATCH MISS", f, old[:40], file=sys.stderr)
        sys.exit(1)
    with open(p, "w") as fh:
        fh.write(s.replace(old, new))
# every file sees the ObjectiveC overlay (imports are file-scoped; the real SDK autoloads it through the clang module)
for name in FILES:
    p = os.path.join(OUT, name + ".swift")
    with open(p) as fh:
        t = fh.read()
    t = t.replace("@_exported import Foundation // Clang module", "@_exported import Foundation // Clang module\n@_exported import ObjectiveC", 1)
    with open(p, "w") as fh:
        fh.write(t)
REPEAT = [("NSError", "extension MachErrorCode"), ("NSError", "extension MachError")]
for f, start in REMOVE + REPEAT:
    p = os.path.join(OUT, f + ".swift")
    if not os.path.exists(p):
        continue
    with open(p) as fh:
        t = fh.read()
    r = remove_block(t, start)
    if r is None:
        if (f, start) in REPEAT:
            continue
        print("REMOVE MISS", f, start[:50], file=sys.stderr)
        sys.exit(1)
    while (f, start) in REPEAT:
        r2 = remove_block(r, start)
        if r2 is None:
            break
        r = r2
    with open(p, "w") as fh:
        fh.write(r)
# member functions / initializers removed from URL.swift (resource-values and bookmark API: needs URLResourceKey etc.; not used by the plugins)
import re as _re
URL_DROP = ["removeAllCachedResourceValues", "removeCachedResourceValue", "promisedItemResourceValues", "setResourceValue", "setResourceValues",
            "getResourceValue", "bookmarkData", "resourceValues", "writeBookmarkData", "setTemporaryResourceValue", "checkPromisedItemIsReachable",
            "startAccessingSecurityScopedResource", "stopAccessingSecurityScopedResource"]
pth = os.path.join(OUT, "URL.swift")
if os.path.exists(pth):
    with open(pth) as fh:
        t = fh.read()
    for _ in range(3):
        for nme in URL_DROP:
            while True:
                m = _re.search(r"\n    public (?:mutating |static )?func " + nme + r"\b", t)
                if not m:
                    break
                r = remove_block(t[m.start() + 1:], "public")
                if r is None:
                    break
                t = t[:m.start() + 1] + r
    for start in ["    @available(swift, obsoleted: 4.2)\n    public init?(resolvingBookmarkData", "public struct URLResourceValues {", "    public init(resolvingBookmarkData", "    public init(resolvingAliasFileAt"]:
        while True:
            r = remove_block(t, start)
            if r is None:
                break
            t = r
    t += "\nfileprivate struct URLComponents {\n    var path: String = \"\"\n    var url: URL? = nil\n    init?(url: URL, resolvingAgainstBaseURL: Bool) { return nil }\n}\n"
    with open(pth, "w") as fh:
        fh.write(t)
print(len(FILES), "files into", OUT)
