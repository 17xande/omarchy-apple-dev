#!/usr/bin/env python3
"""Install Foundation.apinotes / CoreGraphics.apinotes next to the framework headers so the Swift importer
bridges NSData<->Data and names the option enums. Source documents are the swift project's open test-SDK
versions (fetched with the swift-5.3 tree); we add the bridging and SwiftName entries the overlay build needs.
Text transform on the YAML: no dependency on a YAML library.
  overlay-apinotes.py <test-sdk-dir> <sdkm/Frameworks> <res-apinotes-dir>
"""
import os
import sys

MOCK, FW, RESNOTES = sys.argv[1], sys.argv[2], sys.argv[3]

with open(os.path.join(MOCK, "Foundation.apinotes")) as f:
    s = f.read()
for marker, entry in [
    ("Classes:", '- Name: NSData\n  SwiftBridge: Data\n'),
    ("Tags:", '- Name: NSDataReadingOptions\n  SwiftName: NSData.ReadingOptions\n'
              '- Name: NSDataWritingOptions\n  SwiftName: NSData.WritingOptions\n'
              '- Name: NSDataSearchOptions\n  SwiftName: NSData.SearchOptions\n'
              '- Name: NSDataBase64EncodingOptions\n  SwiftName: NSData.Base64EncodingOptions\n'
              '- Name: NSDataBase64DecodingOptions\n  SwiftName: NSData.Base64DecodingOptions\n'
              '- Name: NSStringCompareOptions\n  SwiftName: NSString.CompareOptions\n'
              '- Name: NSStringEnumerationOptions\n  SwiftName: NSString.EnumerationOptions\n'
              '- Name: NSStringEncodingConversionOptions\n  SwiftName: NSString.EncodingConversionOptions\n'
              '- Name: NSURLBookmarkCreationOptions\n  SwiftName: NSURL.BookmarkCreationOptions\n'
              '- Name: NSURLBookmarkResolutionOptions\n  SwiftName: NSURL.BookmarkResolutionOptions\n'),
]:
    if marker not in s:
        sys.exit("overlay-apinotes: Foundation.apinotes drifted, no '%s' key" % marker)
    s = s.replace(marker, marker + "\n" + entry.rstrip("\n"), 1)
dests = [os.path.join(FW, "Foundation.framework", d, "Foundation.apinotes") for d in ("Headers", "Modules")] + \
        [os.path.join(FW, "Foundation.framework", "Foundation.apinotes"), os.path.join(RESNOTES, "Foundation.apinotes")]
for d in dests:
    os.makedirs(os.path.dirname(d), exist_ok=True)
    with open(d, "w") as f:
        f.write(s)

with open(os.path.join(MOCK, "CoreGraphics.apinotes")) as f:
    cg = f.read()
d = os.path.join(RESNOTES, "CoreGraphics.apinotes")
os.makedirs(os.path.dirname(d), exist_ok=True)
with open(d, "w") as f:
    f.write(cg)
print("apinotes installed", file=sys.stderr)
