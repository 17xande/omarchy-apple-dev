#!/usr/bin/env python3
"""Mac (targetRuntime MacOSX.Cocoa) xib -> NIBArchive compiler.

Apple's ibtool 27.0 writes macOS nibs in the same NIBArchive container as iOS
(oracle: NNW Mac xibs compiled on macstudio; the container is tools/nibarchive.py).
Inside, the graph is the classic keyed NSIBObjectData shape: NSRoot (File's
Owner), NSConnections, NSObjectsKeys/Values (each top-level object and its
container), NSOidsKeys/Values (1..n in document order). Rules below are oracle
probes, not app knowledge:

- Document walk: owner NSCustomObject, NSVisibleWindows set, NSConnections; then
  every outlet connection in document order, building its destination object on
  first reference; then NSObjectsKeys (document pre-order: NSApplication proxy,
  views with their cells, each view's constraints after its subtree), the parent
  array, oids, accessibility arrays.
- Windows: NSWindowTemplate with a fixed key order; NSWTFlags = 0x60000000 |
  hidesOnDeactivate<<31 | strut bits (left 0x080000, right 0x100000, top
  0x200000, bottom 0x400000; no position mask means all four);
  NSWindowIsRestorable stores the INVERSE of the restorable attribute.
- Views: NSvFlags = 256 | autoresizing bits (translatesAutoresizingMaskIntoConstraints
  =NO pins 268; hidden adds 0x80000000 and widens the int); custom views encode
  as NSClassSwapper with the mangled _TtC class name.
- Constraints: the iOS ordering rule (tools/ibtool._constraint_order) reproduces
  Apple's Mac order byte for byte; guides are real NSLayoutGuide objects.
- System catalog colors resolve to Generic Gray 2.2 (ICC_DATA, extracted from
  the oracle output); NSControl/NSTextFieldCell flags and the inverted
  NSControlUsesSingleLineMode are probed constants (tests/ibtool/golden-mac).
"""

ICC_DATA = bytes.fromhex("""\
0000119c6170706c020000006d6e74724752415958595a2007dc00080017000f002e000f6163
73704150504c000000006e6f6e65000000000000000000000000000000000000f6d600010000
0000d32d6170706c000000000000000000000000000000000000000000000000000000000000
00000000000000000000000000000000000564657363000000c0000000796473636d0000013c
0000081a637072740000095800000023777470740000097c000000146b545243000009900000
080c64657363000000000000001f47656e6572696320477261792047616d6d6120322e322050
726f66696c650000000000000000000000000000000000000000000000000000000000000000
0000000000000000000000000000000000000000000000000000000000000000000000000000
0000000000000000000000006d6c7563000000000000001f0000000c736b534b0000002e0000
01846461444b0000003a000001b26361455300000038000001ec7669564e0000004000000224
707442520000004a00000264756b55410000002c000002ae667246550000003e000002da6875
485500000034000003187a6854570000001a0000034c6b6f4b5200000022000003666e624e4f
0000003a000003886373435a00000028000003c26865494c00000024000003ea726f524f0000
002a0000040e646544450000004e00000438697449540000004e000004867376534500000038
000004d47a68434e0000001a0000050c6a614a500000002600000526656c47520000002a0000
054c7074504f00000052000005766e6c4e4c00000040000005c8657345530000004c00000608
7468544800000032000006547472545200000024000006866669464900000046000006aa6872
48520000003e000006f0706c504c0000004a0000072e617245470000002c0000077872755255
0000003a000007a4656e55530000003c000007de005601610065006f006200650063006e00e1
002000730069007600e1002000670061006d006100200032002c003200470065006e00650072
00690073006b00200067007200e500200032002c0032002000670061006d006d0061002d0070
0072006f00660069006c00470061006d006d006100200064006500200067007200690073006f
0073002000670065006e00e8007200690063006100200032002e003200431ea5007500200068
00ec006e00680020004d00e000750020007800e1006d0020004300680075006e006700200047
0061006d006d006100200032002e003200500065007200660069006c002000470065006e00e9
007200690063006f002000640061002000470061006d0061002000640065002000430069006e
007a0061007300200032002c00320417043004330430043b044c043d04300020004700720061
0079002d04330430043c043000200032002e003200500072006f00660069006c0020006700e9
006e00e90072006900710075006500200067007200690073002000670061006d006d00610020
0032002c003200c1006c00740061006c00e1006e006f007300200073007a00fc0072006b0065
002000670061006d006d006100200032002e0032901a75287070968e51495ea60032002e0032
82725f6963cf8ff0c77cbc180020d68cc0c90020ac10b9c800200032002e00320020d504b85c
d30cc77c00470065006e0065007200690073006b00200067007200e5002000670061006d006d
006100200032002c0032002d00700072006f00660069006c004f006200650063006e00e10020
01610065006400e1002000670061006d006100200032002e003205d205d005de05d4002005d0
05e405d505e8002005db05dc05dc05d900200032002e003200470061006d0061002000670072
0069002000670065006e0065007200690063010300200032002c00320041006c006c00670065
006d00650069006e006500730020004700720061007500730074007500660065006e002d0050
0072006f00660069006c002000470061006d006d006100200032002c003200500072006f0066
0069006c006f002000670072006900670069006f002000670065006e0065007200690063006f
002000640065006c006c0061002000670061006d006d006100200032002c003200470065006e
0065007200690073006b00200067007200e500200032002c0032002000670061006d006d0061
00700072006f00660069006c666e901a70705ea67cfb65700032002e003263cf8ff065874ef6
4e00822c30b030ec30a430ac30f330de00200032002e0032002030d730ed30d530a130a430eb
039303b503bd03b903ba03cc0020039303ba03c103b90020039303ac03bc03bc03b100200032
002e003200500065007200660069006c002000670065006e00e9007200690063006f00200064
0065002000630069006e007a0065006e0074006f0073002000640061002000470061006d006d
006100200032002c00320041006c00670065006d00650065006e0020006700720069006a0073
002000670061006d006d006100200032002c0032002d00700072006f006600690065006c0050
0065007200660069006c002000670065006e00e9007200690063006f00200064006500200067
0061006d006d0061002000640065002000670072006900730065007300200032002c00320e23
0e310e070e2a0e350e410e010e210e210e320e400e010e230e220e4c0e170e310e480e270e44
0e1b00200032002e003200470065006e0065006c0020004700720069002000470061006d0061
00200032002c00320059006c00650069006e0065006e0020006800610072006d00610061006e
002000670061006d006d006100200032002c00320020002d00700072006f006600690069006c
006900470065006e006500720069010d006b006900200047007200610079002000470061006d
006d006100200032002e0032002000700072006f00660069006c0055006e0069007700650072
00730061006c006e0079002000700072006f00660069006c00200073007a00610072006f015b
00630069002000670061006d006d006100200032002c0032063a06270645062700200032002e
003200200644064806460020063106450627062f064a0020063906270645041e043104490430
044f00200441043504400430044f002004330430043c043c043000200032002c0032002d043f
0440043e04440438043b044c00470065006e0065007200690063002000470072006100790020
00470061006d006d006100200032002e0032002000500072006f00660069006c006500007465
787400000000436f70797269676874204170706c6520496e632e2c2032303132000058595a20
000000000000f35100010000000116cc63757276000000000000040000000005000a000f0014
0019001e00230028002d00320037003b00400045004a004f00540059005e00630068006d0072
0077007c00810086008b00900095009a009f00a400a900ae00b200b700bc00c100c600cb00d0
00d500db00e000e500eb00f000f600fb01010107010d01130119011f0125012b01320138013e
0145014c0152015901600167016e0175017c0183018b0192019a01a101a901b101b901c101c9
01d101d901e101e901f201fa0203020c0214021d0226022f02380241024b0254025d02670271
027a0284028e029802a202ac02b602c102cb02d502e002eb02f50300030b03160321032d0338
0343034f035a03660372037e038a039603a203ae03ba03c703d303e003ec03f9040604130420
042d043b0448045504630471047e048c049a04a804b604c404d304e104f004fe050d051c052b
053a05490558056705770586059605a605b505c505d505e505f6060606160627063706480659
066a067b068c069d06af06c006d106e306f507070719072b073d074f076107740786079907ac
07bf07d207e507f8080b081f08320846085a086e0882089608aa08be08d208e708fb09100925
093a094f09640979098f09a409ba09cf09e509fb0a110a270a3d0a540a6a0a810a980aae0ac5
0adc0af30b0b0b220b390b510b690b800b980bb00bc80be10bf90c120c2a0c430c5c0c750c8e
0ca70cc00cd90cf30d0d0d260d400d5a0d740d8e0da90dc30dde0df80e130e2e0e490e640e7f
0e9b0eb60ed20eee0f090f250f410f5e0f7a0f960fb30fcf0fec1009102610431061107e109b
10b910d710f511131131114f116d118c11aa11c911e81207122612451264128412a312c312e3
1303132313431363138313a413c513e5140614271449146a148b14ad14ce14f0151215341556
1578159b15bd15e0160316261649166c168f16b216d616fa171d17411765178917ae17d217f7
181b18401865188a18af18d518fa19201945196b199119b719dd1a041a2a1a511a771a9e1ac5
1aec1b141b3b1b631b8a1bb21bda1c021c2a1c521c7b1ca31ccc1cf51d1e1d471d701d991dc3
1dec1e161e401e6a1e941ebe1ee91f131f3e1f691f941fbf1fea20152041206c209820c420f0
211c2148217521a121ce21fb22272255228222af22dd230a23382366239423c223f0241f244d
247c24ab24da250925382568259725c725f726272657268726b726e827182749277a27ab27dc
280d283f287128a228d429062938296b299d29d02a022a352a682a9b2acf2b022b362b692b9d
2bd12c052c392c6e2ca22cd72d0c2d412d762dab2de12e162e4c2e822eb72eee2f242f5a2f91
2fc72ffe3035306c30a430db3112314a318231ba31f2322a3263329b32d4330d3346337f33b8
33f1342b3465349e34d83513354d358735c235fd3637367236ae36e937243760379c37d73814
3850388c38c839053942397f39bc39f93a363a743ab23aef3b2d3b6b3baa3be83c273c653ca4
3ce33d223d613da13de03e203e603ea03ee03f213f613fa23fe24023406440a640e74129416a
41ac41ee4230427242b542f7433a437d43c044034447448a44ce45124555459a45de46224667
46ab46f04735477b47c04805484b489148d7491d496349a949f04a374a7d4ac44b0c4b534b9a
4be24c2a4c724cba4d024d4a4d934ddc4e254e6e4eb74f004f494f934fdd5027507150bb5106
5150519b51e65231527c52c75313535f53aa53f65442548f54db5528557555c2560f565c56a9
56f75744579257e0582f587d58cb591a596959b85a075a565aa65af55b455b955be55c355c86
5cd65d275d785dc95e1a5e6c5ebd5f0f5f615fb36005605760aa60fc614f61a261f56249629c
62f06343639763eb6440649464e9653d659265e7663d669266e8673d679367e9683f689668ec
6943699a69f16a486a9f6af76b4f6ba76bff6c576caf6d086d606db96e126e6b6ec46f1e6f78
6fd1702b708670e0713a719571f0724b72a67301735d73b87414747074cc7528758575e1763e
769b76f8775677b37811786e78cc792a798979e77a467aa57b047b637bc27c217c817ce17d41
7da17e017e627ec27f237f847fe5804780a8810a816b81cd8230829282f4835783ba841d8480
84e3854785ab860e867286d7873b879f8804886988ce8933899989fe8a648aca8b308b968bfc
8c638cca8d318d988dff8e668ece8f368f9e9006906e90d6913f91a89211927a92e3934d93b6
9420948a94f4955f95c99634969f970a977597e0984c98b89924999099fc9a689ad59b429baf
9c1c9c899cf79d649dd29e409eae9f1d9f8b9ffaa069a0d8a147a1b6a226a296a306a376a3e6
a456a4c7a538a5a9a61aa68ba6fda76ea7e0a852a8c4a937a9a9aa1caa8fab02ab75abe9ac5c
acd0ad44adb8ae2daea1af16af8bb000b075b0eab160b1d6b24bb2c2b338b3aeb425b49cb513
b58ab601b679b6f0b768b7e0b859b8d1b94ab9c2ba3bbab5bb2ebba7bc21bc9bbd15bd8fbe0a
be84beffbf7abff5c070c0ecc167c1e3c25fc2dbc358c3d4c451c4cec54bc5c8c646c6c3c741
c7bfc83dc8bcc93ac9b9ca38cab7cb36cbb6cc35ccb5cd35cdb5ce36ceb6cf37cfb8d039d0ba
d13cd1bed23fd2c1d344d3c6d449d4cbd54ed5d1d655d6d8d75cd7e0d864d8e8d96cd9f1da76
dafbdb80dc05dc8add10dd96de1cdea2df29dfafe036e0bde144e1cce253e2dbe363e3ebe473
e4fce584e60de696e71fe7a9e832e8bce946e9d0ea5beae5eb70ebfbec86ed11ed9cee28eeb4
ef40efccf058f0e5f172f1fff28cf319f3a7f434f4c2f550f5def66df6fbf78af819f8a8f938
f9c7fa57fae7fb77fc07fc98fd29fdbafe4bfedcff6dffff
""".replace("\n", ""))

import math
import os
import struct
import sys
import xml.etree.ElementTree as ET

_TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS)


def _load_ibtool():
    import importlib.machinery
    import importlib.util
    path = os.path.join(_TOOLS, "ibtool")
    loader = importlib.machinery.SourceFileLoader("ibtool_tool", path)
    spec = importlib.util.spec_from_loader("ibtool_tool", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


I = _load_ibtool()  # Builder primitives, constraint ordering, mangling


def set_target_module(module):
    """The running ibtool's --module (SwiftPM maps <pkg>_<target>); the script
    run and this import are separate module instances, so hand it over."""
    import sys
    print(f"set_target_module({module!r})", file=sys.stderr)
    I.TARGET_MODULE = module
import keyorder  # noqa: E402
import nibarchive as N  # noqa: E402

# NSWindowStyleMask bits (probe: titled 1, closable 2, miniaturizable 4,
# resizable 8, utility 16, docModal 64, fullSizeContentView 32768).
STYLE_MASK = {"titled": 1, "closable": 2, "miniaturizable": 4, "resizable": 8,
              "utility": 16, "docModal": 64, "fullSizeContentView": 32768,
              "nonactivatingPanel": 128, "texturedBackground": 256,
              "unifiedTitleAndToolbar": 4096, "borderless": 0}
STRUTS = {"leftStrut": 0x080000, "rightStrut": 0x100000,
          "topStrut": 0x200000, "bottomStrut": 0x400000}
COLLECTION_BEHAVIOR = {"fullScreenPrimary": 128, "fullScreenAuxiliary": 256,
                      "canJoinAllSpaces": 1, "moveToActiveSpace": 2}
TABBING_MODE = {"automatic": 0, "preferred": 1, "disallowed": 2}
TOOLBAR_STYLE = {"automatic": 0, "expanded": 1, "preference": 2, "unified": 3,
                 "unifiedCompact": 4}
# NSControlTextAlignment (probe: left 0, center 1, right 2, justified 3,
# natural 4) is NOT NSTextAlignment; NSCellFlags2 stores NSTextAlignment << 26.
CONTROL_ALIGN = {"left": 0, "center": 1, "right": 2, "justified": 3, "natural": 4}
TEXT_ALIGN = {"left": 0, "right": 1, "center": 2, "justified": 3, "natural": 4}
# NSLineBreakMode (Foundation): the NSControl key stores the enum, NSCellFlags2
# a 0x200-multiples bit pattern probed per mode (wordWrap 0, clipping 0x400,
# truncatingTail 0x800, truncatingMiddle 0xA00). Keys are the xib attributes.
LINE_BREAK = {"wordWrap": 0, "charWrap": 1, "clipping": 2, "truncatingHead": 3,
              "truncatingTail": 4, "truncatingMiddle": 5}
LINE_BREAK_FLAGS2 = {"wordWrap": 0, "charWrap": 0x200, "clipping": 0x400,
                     "truncatingHead": 0xC00, "truncatingTail": 0x800,
                     "truncatingMiddle": 0xA00}
META_FONTS = {  # metaFont -> (NSSize, NSfFlags); probed names and flags
    "system": (13.0, 1044), "smallSystem": (11.0, 3100),
    "miniSystem": (9.0, 3100), "boldSystem": (13.0, 2072),
    "smallBoldSystem": (11.0, 6204), "label": (10.0, 3100),
    "toolTips": (11.0, 3100), "menu": (13.0, 1558), "message": (13.0, 1044),
    "palette": (11.0, 3100), "titleBar": (13.0, 1044),
    "systemDetail": (11.0, 3100), "cellTitle": (11.0, 3100),
    "systemBold": (13.0, 2072),
}
FONT_NAMES = {"system": ".AppleSystemUIFont", "smallSystem": ".AppleSystemUIFont",
              "miniSystem": ".AppleSystemUIFont", "boldSystem": ".AppleSystemUIFontBold",
              "smallBoldSystem": ".AppleSystemUIFontBold", "systemBold": ".AppleSystemUIFontBold",
              "cellTitle": ".AppleSystemUIFontMedium", "menu": ".AppleSystemUIFont",
              "message": ".AppleSystemUIFont", "palette": ".AppleSystemUIFont",
              "label": ".AppleSystemUIFont", "toolTips": ".AppleSystemUIFont",
              "titleBar": ".AppleSystemUIFont", "systemDetail": ".AppleSystemUIFont"}
# System catalog colors resolve to Generic Gray Gamma 2.2 at compile time
# (oracle probe, Xcode 27.0): name -> (NSWhite payload, NSComponents payload).
CATALOG_COLORS = {
    "controlColor": (b"0.602715373\x00", b"0.6666666667 1"),
    "labelColor": (b"0\x00", b"0 1"),
    "secondaryLabelColor": (b"0.2637968361\x00", b"0.3333333333 1"),
    "tertiaryLabelColor": (b"0.4375036359\x00", b"0.4666666667 1"),
    "quaternaryLabelColor": (b"0.6477062404\x00", b"0.6 1"),
    "textColor": (b"0\x00", b"0 1"),
    "placeholderTextColor": (b"0.6477062404\x00", b"0.6 1"),
    "selectedTextColor": (b"0\x00", b"0 1"),
    "textBackgroundColor": (b"1\x00", b"1 1"),
    "selectedTextBackgroundColor": (b"0.6666666667\x00", b"0.6666666667 1"),
    "keyboardFocusIndicatorColor": (b"0.213Second\x00", b"0.213 1"),
    "controlAccentColor": (b"0.09019608\x00", b"0.352941 0.666667 0.913725 1"),
    "controlTextColor": (b"0\x00", b"0 1"),
    "disabledControlTextColor": (b"0.4375036359\x00", b"0.4666666667 1"),
    "controlBackgroundColor": (b"1\x00", b"1 1"),
    "selectedControlTextColor": (b"0\x00", b"0 1"),
    "windowBackgroundColor": (b"0.9493610263\x00", b"0.9493610263 1"),
    "windowFrameTextColor": (b"0\x00", b"0 1"),
    "underPageBackgroundColor": (b"0.8 got\x00", b"0.8 1"),
    "findHighlightColor": (b"1\x00", b"1 0.9 0.35 1"),
    "unemphasizedSelectedTextBackgroundColor": (b"0.9015956522\x00", b"0.9015956522 1"),
    "alternatingEvenBackgroundColor": (b"1\x00", b"1 1"),
    "alternatingOddBackgroundColor": (b"0.9658410256\x00", b"0.9658410256 1"),
    "linkColor": (b"0.16151028\00", b"0.039216 0.423529 0.815686 1"),
    "separatorColor": (b"0.874618\00", b"0.874618 1"),
    "gridColor": (b"0.8 got\00", b"0.8 1"),
    "headerTextColor": (b"0\x00", b"0 1"),
    "highlightColor": (b"0.8470830959\x00", b"0.733333 0.827451 0.898039 1"),
    "selectedMenuItemTextColor": (b"1\x00", b"1 1"),
    "selectedContentBackgroundColor": (b"0.2826356863\x00", b"0.258824 0.513725 0.870588 1"),
    "unemphasizedSelectedContentBackgroundColor": (b"0.9015956522\x00", b"0.9015956522 1"),
}


def _fmt_g(v):
    return f"{float(v):g}"


def _i32(v):
    return v - 0x100000000 if v > 0x7FFFFFFF else v


def _localizable(b, owner_id, text, where, suffix=".title"):
    """User string in a .lproj output: NSLocalizableString{bytes, NSKey=ownerId.title,
    NSDev}; a pooled plain string elsewhere or for the empty string."""
    if text == "" or not b.localize:
        return b.string(text)
    o = b.new("NSLocalizableString")
    o.add("NS.bytes", N.DATA, text.encode("utf-8"))
    o.add("NSKey", *b.ref(b.string(owner_id + suffix)))
    o.add("NSDev", *b.ref(b.string(text)))
    return o


def _rect(el, key, where):
    r = el.find(f"rect[@key='{key}']")
    if r is None:
        raise I.XibError(f"<{el.tag}> is missing rect {key!r} ({where})")
    return "{{%s, %s}, {%s, %s}}" % (_fmt_g(r.get("x", 0)), _fmt_g(r.get("y", 0)),
                                     _fmt_g(r.get("width")), _fmt_g(r.get("height")))


def _size(el, key, where):
    v = el.find(f"value[@key='{key}']")
    if v is None:
        raise I.XibError(f"<{el.tag}> is missing value {key!r} ({where})")
    return "{%s, %s}" % (_fmt_g(v.get("width")), _fmt_g(v.get("height")))


class _Late:
    """A forward object reference: the destination object is allocated later."""

    def __init__(self):
        self.obj = None


class MacBuilder(I.Builder):
    """Adds the Mac-side object pools (fonts, colors, guides) to the iOS Builder."""

    def __init__(self):
        super().__init__()
        self.fonts = {}
        self.catalog_colors = {}
        self.white_colors = {}
        self.colorspace = None  # shared Generic Gray space
        self.late = []          # unresolved _Late refs
        self.cons_order = {}    # view xib id -> constraint ids in Apple order
        self.localize = False   # oneShot="NO" windows localize user strings


    def ref(self, obj):
        if isinstance(obj, _Late):
            self.late.append(obj)
            return (N.OBJREF, obj)
        return super().ref(obj)

    def int_fit32(self, v):
        if -128 <= v < 128:
            return (N.INT8, v)
        if -32768 <= v < 32768:
            return (N.INT16, v)
        return (N.INT32, v)

    def font(self, fd_el, where):
        meta = fd_el.get("metaFont")
        if meta is None:
            raise I.XibError(f"<font> without metaFont ({where})")
        size, flags = META_FONTS.get(meta, (None, None))
        if size is None:
            raise I.XibError(f"<font> metaFont {meta!r} not probed ({where})")
        if fd_el.get("size"):
            size = float(fd_el.get("size"))
        if meta not in FONT_NAMES:
            raise I.XibError(f"<font> metaFont {meta!r} not probed ({where})")
        key = (meta, size)
        if key in self.fonts:
            return self.fonts[key]
        o = self.new("NSFont")
        o.add("NSName", *self.ref(self.string(FONT_NAMES[meta])))
        o.add("NSSize", *self.float64(size))
        o.add("NSfFlags", N.INT16, flags)
        self.fonts[key] = o
        return o

    def color_space(self):
        if self.colorspace is None:
            cs = self.new("NSColorSpace")
            cs.add("NSID", *self.int8(9))
            cs.add("NSModel", *self.int8(0))
            data = self.new("NSData")
            data.add("NS.bytes", N.DATA, ICC_DATA)
            cs.add("NSICC", *self.ref(data))
            self.colorspace = cs
        return self.colorspace

    def white_color(self, white, comps):
        key = (white, comps)
        if key in self.white_colors:
            return self.white_colors[key]
        o = self.new("NSColor")
        o.add("NSColorSpace", *self.int8(3))
        o.add("NSWhite", N.DATA, white)
        o.add("NSCustomColorSpace", *self.ref(self.color_space()))
        o.add("NSComponents", N.DATA, comps)
        o.add("NSLinearExposure", N.DATA, b"1")
        self.white_colors[key] = o
        return o

    def catalog_color(self, catalog, name, where):
        if catalog != "System":
            raise I.XibError(f"color catalog {catalog!r} not probed ({where})")
        if name == "textColor":
            name = "controlTextColor"  # alias archived under its definition
        if name not in CATALOG_COLORS:
            raise I.XibError(f"System color {name!r} not probed ({where})")
        if name in self.catalog_colors:
            return self.catalog_colors[name]
        o = self.new("NSColor")
        o.add("NSColorSpace", *self.int8(6))
        o.add("NSCatalogName", *self.ref(self.string(catalog)))
        o.add("NSColorName", *self.ref(self.string(name)))
        o.add("NSColor", *self.ref(self.white_color(*CATALOG_COLORS[name])))
        self.catalog_colors[name] = o
        return o


def _classref(b, cls, module, provider):
    if provider == "target" and I.TARGET_MODULE:
        module = I.TARGET_MODULE  # customModuleProvider=target: --module wins
    o = b.new("IBClassReference")
    o.add("IBClassName", *b.ref(b.string(cls)))
    o.add("IBModuleName", *(b.ref(b.string(module)) if module else (N.NIL, None)))
    o.add("IBModuleProvider", *(b.ref(b.string(provider)) if provider else (N.NIL, None)))
    return o


def _custom_object(b, el, class_name, where):
    o = b.new("NSCustomObject")
    o.add("IBClassReference", *b.ref(_classref(b, el.get("customClass") or class_name,
                                               el.get("customModule"),
                                               el.get("customModuleProvider"))))
    o.add("NSClassName", *b.ref(b.string(class_name)))
    return o


def _vflags(el, where, solved=False):
    translates = el.get("translatesAutoresizingMaskIntoConstraints") == "NO"
    if translates:
        v = 268
    else:
        v = 256
        m = el.find("autoresizingMask[@key='autoresizingMask']")
        if m is not None:
            for flag, bit in I.RESIZE_FLAGS.items():
                if m.get(flag) == "YES":
                    v |= bit
    if solved:
        # the canvas solves the content view to fill the window (probe
        # ImportOPMLSheet: width/height stretch bits despite the stale rect)
        v = 256 | I.RESIZE_FLAGS["widthSizable"] | I.RESIZE_FLAGS["heightSizable"]
    hidden = el.get("hidden") == "YES"
    if hidden:
        v |= 0x80000000
        return v - 0x100000000, N.INT64
    return v, N.INT16


GUIDE_IDENT = {"safeArea": "NSViewSafeAreaLayoutGuide",
               "layoutMargins": "NSViewLayoutMarginsGuide"}
GUIDE_TYPE = {"safeArea": 2, "layoutMargins": 1}


def _guide(b, gid, guides, guide_kinds, where):
    """A real NSLayoutGuide, allocated on first reference (probe DetailView pbD)."""
    if gid in guides:
        return guides[gid]
    kind = guide_kinds[gid]
    o = b.new("NSLayoutGuide")
    o.add("NSLayoutGuideIdentifier", *b.ref(b.string(GUIDE_IDENT[kind])))
    o.add("NSShouldBeArchived", *b.boolean(False))
    o.add("NSLayoutGuideNegativeSize", *b.boolean(False))
    o.add("NSLayoutGuideLockedToOwningView", *b.boolean(False))
    syscons = b.new("NSMutableArray")
    syscons.add("NSInlinedValue", *b.boolean(False))
    o.add("NSLayoutGuideSystemConstraints", *b.ref(syscons))
    guides[gid] = o
    return o


def _ref_to(b, item, owner_obj, owner_id, id_map, guides, guide_kinds, where):
    if item is None or item == "-2":
        return b.ref(owner_obj)
    if item in guides:
        return b.ref(guides[item])
    if item in guide_kinds:
        return b.ref(_guide(b, item, guides, guide_kinds, where))
    if item in id_map:
        return b.ref(id_map[item])
    raise I.XibError(f"reference to {item!r} before it is built ({where})")


def _constraint(b, el, owner_obj, owner_id, id_map, guides, guide_kinds, where):
    """Mac NSLayoutConstraint: the iOS value order; guides are real objects."""
    o = b.new("NSLayoutConstraint")
    first = el.get("firstItem")
    o.add("NSFirstItem", *_ref_to(b, first, owner_obj, owner_id, id_map,
                                  guides, guide_kinds, where))
    fa = el.get("firstAttribute")
    if fa is None:
        raise I.XibError(f"<constraint> missing firstAttribute ({where})")
    o.add("NSFirstAttributeV2", *b.int8(I.ATTRIBUTES.get(fa, I.MARGIN_V2.get(fa, 0))))
    o.add("NSFirstAttribute", *b.int8(I.ATTRIBUTES.get(I.MARGIN_BASE.get(fa, fa), 0)))
    rel = I.RELATIONS.get(el.get("relation", "equal"))
    if rel is not None:
        o.add("NSRelation", *b.int8(rel))
    second = el.get("secondItem")
    if second is not None:
        o.add("NSSecondItem", *_ref_to(b, second, owner_obj, owner_id, id_map,
                                       guides, guide_kinds, where))
        sa = el.get("secondAttribute")
        if sa is None:
            raise I.XibError(f"<constraint> secondItem without secondAttribute ({where})")
        o.add("NSSecondAttributeV2", *b.int8(I.ATTRIBUTES.get(sa, I.MARGIN_V2.get(sa, 0))))
        o.add("NSSecondAttribute", *b.int8(I.ATTRIBUTES.get(I.MARGIN_BASE.get(sa, sa), 0)))
    if el.get("symbolic") == "YES":
        o.add("NSSymbolicConstant", *b.ref(b.string("NSSpace")))
        o.add("NSShouldBeArchived", *b.boolean(False))
    elif el.get("constant") is not None:
        c = float(el.get("constant"))
        o.add("NSConstantV2", *b.float64(c))
        o.add("NSShouldBeArchived", *b.boolean(False))
        o.add("NSConstant", *b.float64(c))
    else:
        o.add("NSShouldBeArchived", *b.boolean(False))
    if el.get("id"):
        id_map[el.get("id")] = o
    return o


def _cell(b, el, control, where, owner_id=None, cell_cls="NSTextFieldCell"):
    """<textFieldCell>: NSCellFlags/Flags2 from the probe matrix."""
    o = b.new(cell_cls)
    flags = 0x4000000
    flags2 = TEXT_ALIGN[el.get("alignment", "natural")] << 26
    lb = el.get("lineBreakMode", "wordWrap")
    if lb not in LINE_BREAK:
        raise I.XibError(f"lineBreakMode {lb!r} not probed ({where})")
    flags2 |= LINE_BREAK_FLAGS2[lb]
    if lb != "wordWrap":
        flags |= 0x40
    if el.get("scrollable") == "YES":
        flags |= 0x100000
    if el.get("selectable") == "YES":
        flags |= 0x200000 | 0x1
    if el.get("allowsUndo") == "NO":
        flags2 |= 0x1000
    if el.get("sendsActionOnEndEditing") == "YES":
        flags2 |= 0x400000
    if el.get("usesSingleLineMode") == "YES":
        flags2 |= 0x40
    if el.get("editable") == "YES":
        flags |= 0x90000000 | 0x400000
        flags2 |= 0x400
    elif el.get("editable") is not None:
        flags |= 0x400000
    if flags > 0x7FFFFFFF or flags < -0x80000000:
        o.add("NSCellFlags", N.INT64, flags - 0x100000000 if flags > 0x7FFFFFFF else flags)
    else:
        o.add("NSCellFlags", N.INT32, flags)
    o.add("NSCellFlags2", N.INT32, _i32(flags2))
    title_el = el.find("string[@key='title']")
    title = el.get("title", title_el.text if title_el is not None and title_el.text else "")
    o.add("NSContents", *b.ref(_localizable(b, owner_id or "", title, where)))
    fd = el.find("font[@key='font']")
    if fd is None:
        raise I.XibError(f"<textFieldCell> without <font> ({where})")
    o.add("NSSupport", *b.ref(b.font(fd, where)))
    if el.get("placeholderString") is not None:
        o.add("NSPlaceholderString",
              *b.ref(_localizable(b, el.get("id") or "", el.get("placeholderString"),
                                  where, suffix=".placeholderString")))
    o.add("NSControlView", *b.ref(control))
    for key in ("backgroundColor", "textColor"):
        c = el.find(f"color[@key='{key}']")
        if c is None:
            raise I.XibError(f"<textFieldCell> without {key} color ({where})")
        if c.get("catalog") != "System":
            raise I.XibError(f"{key} color without catalog=System ({where})")
        if key == "backgroundColor" and el.get("drawsBackground") is not None:
            o.add("NSDrawsBackground", *b.boolean(el.get("drawsBackground") != "YES"))
        o.add("NSBackgroundColor" if key == "backgroundColor" else "NSTextColor",
              *b.ref(b.catalog_color(c.get("catalog"), c.get("name"), where)))
    return o


def _field(b, el, where, superview, id_map, parent=None):
    """<textField>: NSTextField with its cell; returns (obj, [(obj, parent)])."""
    guides = {}
    o = b.new("NSTextField")
    o.add("NSNextResponder", *(b.ref(superview) if superview is not None else (N.NIL, None)))
    o.add("NSNibTouchBar", *(N.NIL, None))
    v, vt = _vflags(el, where)
    o.add("NSvFlags", vt, v)
    o.add("NSFrame", *b.ref(b.string(_rect(el, "frame", where))))
    o.add("NSSuperview", *b.ref(superview))
    o.add("NSViewWantsBestResolutionOpenGLSurface", *b.boolean(False))
    if el.get("translatesAutoresizingMaskIntoConstraints") == "NO":
        o.add("NSDoNotTranslateAutoresizingMask", *b.boolean(False))
    h, v2 = el.get("horizontalHuggingPriority"), el.get("verticalHuggingPriority")
    if (h is not None and h != "250") or (v2 is not None and v2 != "750"):
        o.add("NSHuggingPriority",
              *b.ref(b.string("{%s, %s}" % (_fmt_g(h or 250), _fmt_g(v2 or 250)))))
    h, v2 = (el.get("horizontalCompressionResistancePriority"),
             el.get("verticalCompressionResistancePriority"))
    if (h is not None and h != "750") or (v2 is not None and v2 != "750"):
        o.add("NSAntiCompressionPriority",
              *b.ref(b.string("{%s, %s}" % (_fmt_g(h or 750), _fmt_g(v2 or 750)))))
    cons_el = el.find("constraints")
    if cons_el is not None and cons_el.findall("constraint"):
        carr = b.new("NSArray")
        carr.add("NSInlinedValue", *b.boolean(False))
        els = I._constraint_order(el, cons_el.findall("constraint"), where, mac=True)
        for c in els:
            con = _constraint(b, c, o, el.get("id"), id_map, guides, {}, where)
            carr.add("UINibEncoderEmptyKey", *b.ref(con))
        b.cons_order[el.get("id")] = [c.get("id") for c in els]
        o.add("NSViewConstraints", *b.ref(carr))
    o.add("IBNSSafeAreaLayoutGuide", *(N.NIL, None))
    o.add("IBNSLayoutMarginsGuide", *(N.NIL, None))
    o.add("IBNSClipsToBounds", *b.int8(0))
    o.add("NSEnabled", *b.boolean(False))
    cell_el = el.find("textFieldCell[@key='cell']")
    if cell_el is None:
        raise I.XibError(f"<textField> without textFieldCell ({where})")
    cell = _cell(b, cell_el, o, where, owner_id=cell_el.get("id"))
    o.add("NSCell", *b.ref(cell))
    id_map[el.get("id") + "#cell"] = cell
    o.add("NSAllowsLogicalLayoutDirection",
          *b.boolean(not b.localize
                     and (el.get("horizontalHuggingPriority") is not None
                          or cell_el.get("scrollable") == "YES"
                          or (cell_el.get("selectable") == "YES"
                              and el.get("editable") is None))))
    o.add("NSControlSize", *b.int8(0))
    o.add("NSControlContinuous", *b.boolean(True))
    o.add("NSControlRefusesFirstResponder", *b.boolean(True))
    o.add("NSControlUsesSingleLineMode",
          *b.boolean(cell_el.get("usesSingleLineMode") != "YES"))
    align = cell_el.get("alignment", "natural")
    if align not in CONTROL_ALIGN:
        raise I.XibError(f"alignment {align!r} not probed ({where})")
    o.add("NSControlTextAlignment", *b.int8(CONTROL_ALIGN[align]))
    o.add("NSControlLineBreakMode", *b.int8(LINE_BREAK[lb_of(cell_el)]))
    o.add("NSControlWritingDirection", N.INT64, -1)
    o.add("NSControlSendActionMask", *b.int8(4))
    o.add("NSTextFieldAlignmentRectInsetsVersion", *b.int8(2))
    o.add("NSAllowsWritingTools", *b.boolean(False))
    o.add("NSTextFieldAllowsWritingToolsAffordance", *b.boolean(True))
    o.add("NS.resolvesNaturalAlignmentWithBaseWritingDirection", *b.boolean(True))
    id_map[el.get("id")] = o
    cell = id_map[el.get("id") + "#cell"]
    return o, [(o, parent), (cell, o)]


def lb_of(cell_el):
    lb = cell_el.get("lineBreakMode", "wordWrap")
    return lb




def _view(b, el, where, superview=None, id_map=None, guides=None, parent=None):
    """<view>/<customView> -> NSView or NSClassSwapper; returns (obj, pairs).

    Allocation order is Apple's: the object, then subviews depth-first (each
    subview completes, cell included), then this view's frame, constraints
    (probe-ordered), layout guides, IB guide placeholders."""
    guide_kinds = {}
    o = b.new("NSClassSwapper" if el.get("customClass") else "NSView")
    if el.get("customClass"):
        o.add("NSClassName", *b.ref(b.string(I._swift_class(el))))
        o.add("NSOriginalClassName", *b.ref(b.string("NSView")))
    o.add("NSNextResponder", *(b.ref(superview) if superview is not None else (N.NIL, None)))
    o.add("NSNibTouchBar", *(N.NIL, None))
    v, vt = _vflags(el, where, solved=getattr(b, "cv_solved", False))
    o.add("NSvFlags", vt, v)
    id_map[el.get("id")] = o
    keys = [(o, parent)]
    subs = el.find("subviews")
    if subs is not None:
        arr = b.new("NSMutableArray")
        arr.add("NSInlinedValue", *b.boolean(False))
        o.add("NSSubviews", *b.ref(arr))
        for child in subs:
            existing = id_map.get(child.get("id"))
            if existing is not None:
                arr.add("UINibEncoderEmptyKey", *b.ref(existing))
                continue
            sub, sub_pairs = _build_element(b, child, where, superview=o,
                                            id_map=id_map, guides=guides, parent=o)
            arr.add("UINibEncoderEmptyKey", *b.ref(sub))
            keys.extend(sub_pairs)
    if superview is None:
        # ibtool archives the constraint-SOLVED canvas frame here; xibs whose
        # saved frames match the solved layout reproduce byte-for-byte, stale
        # ones differ in the frame strings only (loads identically: Auto Layout
        # re-fits at runtime).
        r = getattr(b, "cv_rect", None)
        if r is not None:
            cr = getattr(b, "cv_content_rect", None)
            wants = getattr(b, "cv_wants_layer", False)
            rw, rh = float(r.get("width")), float(r.get("height"))
            if cr is None:
                o.add("NSFrameSize", *b.ref(b.string(_size_str(el))))
            elif (rw, rh) == cr:
                o.add("NSFrameSize", *b.ref(b.string(
                    "{%s, %s}" % (_fmt_g(cr[0]), _fmt_g(cr[1])))))
            elif rw == cr[0]:
                # canvas with equal widths: frame shifted by the height delta
                o.add("NSFrame", *b.ref(b.string(
                    "{{0, %s}, {%s, %s}}" % (_fmt_g(cr[1] - rh),
                                             _fmt_g(cr[0]), _fmt_g(rh)))))
            elif rh == cr[1]:
                o.add("NSFrameSize", *b.ref(b.string(
                    "{%s, %s}" % (_fmt_g(rw), _fmt_g(cr[1])))))
            else:
                o.add("NSFrameSize", *b.ref(b.string(
                    "{%s, %s}" % (_fmt_g(cr[0]), _fmt_g(cr[1])))))
            if wants:
                o.add("NSViewIsLayerTreeHost", *b.boolean(False))
        else:
            o.add("NSFrameSize", *b.ref(b.string(_size_str(el))))
    else:
        o.add("NSFrame", *b.ref(b.string(_rect(el, "frame", where))))
        o.add("NSSuperview", *b.ref(superview))
    if el.get("alphaValue") is not None:
        o.add("NSViewAlphaValue", *b.float64(float(el.get("alphaValue"))))
    o.add("NSViewWantsBestResolutionOpenGLSurface", *b.boolean(False))
    if superview is not None and el.get("translatesAutoresizingMaskIntoConstraints") == "NO":
        o.add("NSDoNotTranslateAutoresizingMask", *b.boolean(False))
    cons_el = el.find("constraints")
    cons = []
    gl = el.findall("viewLayoutGuide")
    guide_kinds = {}
    if gl:
        for g in gl:
            if g.get("key") not in GUIDE_IDENT:
                raise I.XibError(f"viewLayoutGuide {g.get('key')!r} not probed ({where})")
        guide_kinds.update({_guide_id(el, k): k for k in ("safeArea", "layoutMargins")})
    if cons_el is not None and cons_el.findall("constraint"):
        carr = b.new("NSArray")
        carr.add("NSInlinedValue", *b.boolean(False))
        els = I._constraint_order(el, cons_el.findall("constraint"), where, mac=True)
        for c in els:
            cons.append(_constraint(b, c, o, el.get("id"), id_map, guides,
                                    guide_kinds, where))
        b.cons_order[el.get("id")] = [c.get("id") for c in els]
        for c in cons:
            carr.add("UINibEncoderEmptyKey", *b.ref(c))
        o.add("NSViewConstraints", *b.ref(carr))
        keys.extend((c, o) for c in cons)
    if gl:
        larr = b.new("NSArray")
        larr.add("NSInlinedValue", *b.boolean(False))
        for kind in ("safeArea", "layoutMargins"):
            larr.add("UINibEncoderEmptyKey",
                     *b.ref(_guide(b, _guide_id(el, kind), guides, guide_kinds, where)))
        o.add("NSViewLayoutGuides", *b.ref(larr))
        for kind, key, t in (("safeArea", "IBNSSafeAreaLayoutGuide", 2),
                             ("layoutMargins", "IBNSLayoutMarginsGuide", 1)):
            g = b.new("IBNSViewAutolayoutGuide")
            g.add("IBNSLayoutGuideSystemType", *b.int8(t))
            o.add(key, *b.ref(g))
    else:
        o.add("IBNSSafeAreaLayoutGuide", *(N.NIL, None))
        o.add("IBNSLayoutMarginsGuide", *(N.NIL, None))
    o.add("IBNSClipsToBounds", *b.int8(0))
    return o, keys


def _guide_id(el, kind):
    for g in el.findall("viewLayoutGuide"):
        if g.get("key") == kind:
            return g.get("id")
    return f"{el.get('id')}#{kind}"  # auto margins guide


def _size_str(el):
    r = el.find("rect[@key='frame']")
    if r is None:
        raise I.XibError(f"<{el.tag}> is missing frame rect")
    return "{%s, %s}" % (_fmt_g(r.get("width")), _fmt_g(r.get("height")))


def _build_element(b, el, where, superview, id_map, guides, parent=None):
    """One element: (obj, [(obj, parent)] pairs for NSObjectsKeys/Values)."""
    if el.tag == "textField":
        return _field(b, el, where, superview, id_map, parent=parent)
    if el.tag in ("view", "customView", "stackView"):
        return _view(b, el, where, superview=superview, id_map=id_map,
                     guides=guides, parent=parent)
    if el.tag == "button":
        return _button(b, el, where, superview, id_map, parent=parent)
    if el.tag == "popUpButton":
        return _popup(b, el, where, superview, id_map, parent=parent)
    if el.tag == "window":
        return _window(b, el, where, id_map, parent=parent)
    raise I.XibError(f"unsupported element <{el.tag}> ({where})")


def _window(b, el, where, id_map, parent=None):
    """<window> -> NSWindowTemplate with the probed key order."""
    o = b.new("NSWindowTemplate")
    mask = el.find("windowStyleMask[@key='styleMask']")
    style = 0
    if mask is not None:
        for name, bit in STYLE_MASK.items():
            if mask.get(name) == "YES":
                style |= bit
    o.add("NSWindowStyleMask", *b.int_fit32(style))
    if mask is not None and mask.get("resizable") == "YES" and mask.get("titled") != "YES":
        o.add("NSWindowAllowNontitledResizable", *b.boolean(True))
    o.add("NSWindowBacking", *b.int8(2))
    o.add("NSWindowRect", *b.ref(b.string(_rect(el, "contentRect", where))))
    flags = 0x60000000
    if el.get("hidesOnDeactivate") == "YES":
        flags |= 0x80000000
    pos = el.find("windowPositionMask[@key='initialPositionMask']")
    if pos is not None:
        for name, bit in STRUTS.items():
            if pos.get(name) == "YES":
                flags |= bit
    else:
        flags |= sum(STRUTS.values())
    if flags > 0x7FFFFFFF:
        o.add("NSWTFlags", N.INT64, flags - 0x100000000)
    else:
        o.add("NSWTFlags", N.INT32, flags)
    o.add("NSWindowTitle", *b.ref(_localizable(b, el.get("id") or "",
                                               el.get("title", ""), where)))
    o.add("NSWindowSubtitle", *b.ref(b.string(el.get("subtitle", ""))))
    o.add("NSWindowClass", *b.ref(b.string(el.get("customClass", "NSWindow"))))
    o.add("NSViewClass", *(N.NIL, None))
    ident = el.get("identifier")
    o.add("NSUserInterfaceItemIdentifier",
          *(b.ref(b.string(ident)) if ident else (N.NIL, None)))
    min_sz = max_sz = None
    for v in el.findall("value"):
        if v.get("key") == "minSize":
            min_sz = _size(el, "minSize", where)
        elif v.get("key") == "maxSize":
            max_sz = _size(el, "maxSize", where)
    if max_sz is not None:
        o.add("NSWindowContentMaxSize", *b.ref(b.string(max_sz)))
    if min_sz is not None:
        o.add("NSWindowContentMinSize", *b.ref(b.string(min_sz)))
    cv = el.find("view[@key='contentView']")
    if cv is not None:
        b.cv_rect = cv.find("rect[@key='frame']")
        cr = el.find("rect[@key='contentRect']")
        b.cv_content_rect = (float(cr.get("width")), float(cr.get("height"))) if cr is not None else None
        r0 = cv.find("rect[@key='frame']")
        b.cv_solved = (cr is not None and r0 is not None
                       and (float(r0.get("width")), float(r0.get("height"))) != b.cv_content_rect)
        b.cv_wants_layer = cv.get("wantsLayer") == "YES"
        _cv_obj, cv_pairs = _build_element(b, cv, where, superview=None,
                                           id_map=id_map, guides={}, parent=o)
        b.cv_solved = False
        o.add("NSWindowView", *b.ref(_cv_obj))
    else:
        b.cv_rect = None
        cv_pairs = []
        o.add("NSWindowView", *(N.NIL, None))
    o.add("NSScreenRect", *b.ref(b.string(_rect(el, "screenRect", where))))
    if min_sz is not None:
        # content min/max plus the titled-window title bar (probe win-minmax, +24)
        w, h = min_sz.strip("{}").split(", ")
        o.add("NSMinSize", *b.ref(b.string("{%s, %s}" % (w, _fmt_g(float(h) + 24)))))
    o.add("NSMaxSize", *b.ref(b.string(
        max_sz and "{%s, %s}" % (max_sz.strip("{}").split(", ")[0],
                                 _fmt_g(float(max_sz.strip("{}").split(", ")[1]) + 24))
        or "{10000000000000, 10000000000000}")))
    if el.get("frameAutosaveName") is not None:
        o.add("NSFrameAutosaveName", *b.ref(b.string(el.get("frameAutosaveName"))))
    coll = el.find("windowCollectionBehavior[@key='collectionBehavior']")
    if coll is not None:
        bits = 0
        for name, bit in COLLECTION_BEHAVIOR.items():
            if coll.get(name) == "YES":
                bits |= bit
        o.add("NSWindowCollectionBehavior", N.INT16, bits)
    o.add("NSWindowIsRestorable", *b.boolean(el.get("restorable") == "NO"))
    o.add("NSMinFullScreenContentSize", *b.ref(b.string("{0, 0}")))
    o.add("NSMaxFullScreenContentSize", *b.ref(b.string("{0, 0}")))
    if el.get("tabbingMode"):
        if el.get("tabbingMode") not in TABBING_MODE:
            raise I.XibError(f"tabbingMode {el.get('tabbingMode')!r} not probed ({where})")
        o.add("NSWindowTabbingMode", *b.int8(TABBING_MODE[el.get("tabbingMode")]))
    if el.get("toolbarStyle"):
        if el.get("toolbarStyle") not in TOOLBAR_STYLE:
            raise I.XibError(f"toolbarStyle {el.get('toolbarStyle')!r} not probed ({where})")
        o.add("NSWindowToolbarStyle", *b.int8(TOOLBAR_STYLE[el.get("toolbarStyle")]))
    if el.get("customClass"):
        o.add("IBClassReference", *b.ref(_classref(b, el.get("customClass"), None, None)))
    id_map[el.get("id")] = o
    return o, [(o, parent)] + cv_pairs


def _conn_blocks(objects_el):
    """(source element, <outlet>/<action>) pairs in document pre-order."""
    pairs = []

    def walk(el):
        for c in el.findall("connections"):
            for conn in c:
                pairs.append((el, conn))
        for tag in ("buttonCell", "popUpButtonCell"):
            for cell in el.findall(f"{tag}[@key='cell']"):
                walk(cell)
        cv = el.find("view[@key='contentView']")
        if cv is not None:
            walk(cv)
        subs = el.find("subviews")
        if subs is not None:
            for child in subs:
                walk(child)

    for el in objects_el:
        if el.tag in ("customObject", "window", "customView", "view"):
            walk(el)
    return pairs


def _find_id(root, ident):
    return root.find(f".//*[@id='{ident}']")


def _find_parent(root, ident):
    """The element whose subviews hold ident (ElementTree has no parent pointers)."""
    for el in root.iter():
        subs = el.find("subviews")
        if subs is not None and any(c.get("id") == ident for c in subs):
            return el
    return None


def compile_xib(path):
    """Compile one macOS xib to NIBArchive bytes. Raises XibError."""
    tree = ET.parse(path)
    doc = tree.getroot()
    if doc.get("targetRuntime") != "MacOSX.Cocoa":
        raise I.XibError(f"{path}: targetRuntime {doc.get('targetRuntime')!r} is not MacOSX.Cocoa")
    objects = doc.find("objects")
    if objects is None:
        raise I.XibError(f"{path}: no <objects> element")
    where = os.path.basename(path)
    b = MacBuilder()
    # Oracle (reg-nnw-1818): xibs inside an .lproj directory are built by the
    # localized-variant step (project deployment target 15.0), which wraps user
    # strings in NSLocalizableString and clears NSAllowsLogicalLayoutDirection;
    # xibs outside any .lproj keep plain strings and the default-target flags.
    b.localize = ".lproj" in path

    root = b.new("NSObject")
    ibd = b.new("NSIBObjectData")
    root.add("IB.objectdata", *b.ref(ibd))
    root.add("IB.systemFontUpdateVersion", *b.int8(1))

    id_map = {}      # xib id -> Obj (objects as they get built)
    conn_objs = []   # NSNibOutletConnector objects, document order
    late_pending = []  # (_Late, superview xib id) filled after connections

    owner_el = next((e for e in objects if e.get("id") == "-2"), None)
    if owner_el is None:
        raise I.XibError(f"{path}: no File's Owner (id=-2)")
    if not owner_el.get("customClass"):
        raise I.XibError(f"{path}: File's Owner without customClass ({where})")
    owner = _custom_object(b, owner_el, I._swift_class(owner_el), where)
    id_map["-2"] = owner

    vis = b.new("NSMutableSet")
    vis.add("NSInlinedValue", *b.boolean(False))
    conns_arr = b.new("NSMutableArray")
    conns_arr.add("NSInlinedValue", *b.boolean(False))

    for src_el, conn_el in _conn_blocks(objects):
        if conn_el.tag == "action":
            c = b.new("NSNibControlConnector")
            src = id_map.get(src_el.get("id"))
            if src is None:
                raise I.XibError(f"action source {src_el.get('id')!r} not built ({where})")
            c.add("NSSource", *b.ref(src))
            tgt = conn_el.get("target")
            if tgt is not None and tgt != "-1":
                if tgt not in id_map:
                    raise I.XibError(f"action target {tgt!r} not built ({where})")
                c.add("NSDestination", *b.ref(id_map[tgt]))
            c.add("NSLabel", *b.ref(b.string(conn_el.get("selector"))))
            conns_arr.add("UINibEncoderEmptyKey", *b.ref(c))
            conn_objs.append(c)
            continue
        if conn_el.tag != "outlet":
            raise I.XibError(f"unsupported connection <{conn_el.tag}> ({where})")
        c = b.new("NSNibOutletConnector")
        src = id_map.get(src_el.get("id"))
        if src is None:
            raise I.XibError(f"connection source {src_el.get('id')!r} not built ({where})")
        c.add("NSSource", *b.ref(src))
        dest_id = conn_el.get("destination")
        if dest_id not in id_map:
            el = _find_id(objects, dest_id)
            if el is None or el.tag not in ("window", "view", "customView", "textField", "button", "popUpButton"):
                raise I.XibError(f"connection destination {dest_id!r} not found ({where})")
            parent_el = _find_parent(objects, dest_id)
            if parent_el is not None:
                # A subview built by an outlet before its superview: Apple keeps
                # the superview as a forward reference (probe NothingInspector).
                late = _Late()
                _build_element(b, el, where, superview=late,
                               id_map=id_map, guides={}, parent=late)
                late_pending.append((late, parent_el.get("id")))
            else:
                _build_element(b, el, where, superview=None,
                               id_map=id_map, guides={}, parent=owner)
        c.add("NSDestination", *b.ref(id_map[dest_id]))
        c.add("NSLabel", *b.ref(b.string(conn_el.get("property"))))
        c.add("NSChildControllerCreationSelectorName", *(N.NIL, None))
        conns_arr.add("UINibEncoderEmptyKey", *b.ref(c))
        conn_objs.append(c)
    for late, parent_id in late_pending:
        late.obj = id_map[parent_id]

    # Top-level objects never referenced by a connection (probe: none in NNW).
    for el in objects:
        if el.get("id") in ("-1", "-2", "-3") or el.tag == "placeholder":
            continue
        if el.get("id") not in id_map:
            raise I.XibError(f"top-level <{el.tag} id='{el.get('id')}'> is never "
                             f"referenced; Apple's build order unknown ({where})")

    # NSObjectsKeys follows document pre-order (probe DetailView/NothingInspector),
    # not the lazy build order: window/contentView or view, cell after its control,
    # subviews, then the view's constraints; the parent array mirrors it.
    keys = []

    def collect(el, parent):
        obj = id_map.get(el.get("id"))
        if obj is None:
            return
        keys.append((obj, parent))
        if el.tag in ("textField", "button"):
            keys.append((id_map[el.get("id") + "#cell"], obj))
        if el.tag == "popUpButton":
            cell_el = el.find("popUpButtonCell[@key='cell']")
            menu_el = cell_el.find("menu[@key='menu']")
            # cell -> popup, menu -> cell, items -> menu (probe ImportOPMLSheet)
            keys.append((id_map[el.get("id") + "#cell"], obj))
            keys.append((id_map[menu_el.get("id")], id_map[cell_el.get("id")]))
            for m in menu_el.find("items"):
                keys.append((id_map[m.get("id")], id_map[menu_el.get("id")]))
        cv = el.find("view[@key='contentView']")
        if cv is not None:
            collect(cv, obj)
        subs = el.find("subviews")
        if subs is not None:
            for child in subs:
                collect(child, obj)
        for cid in b.cons_order.get(el.get("id"), []):
            if cid in id_map:
                keys.append((id_map[cid], obj))

    for el in objects:
        if el.get("id") in ("-1", "-2", "-3") or el.tag == "placeholder":
            continue
        collect(el, owner)

    # NSObjectsKeys: NSApplication proxy, then the collected (obj, parent) pairs.
    keys_arr = b.new("NSArray")
    keys_arr.add("NSInlinedValue", *b.boolean(False))
    app_el = next((e for e in objects if e.get("id") == "-3"), None)
    if app_el is None:
        raise I.XibError(f"{path}: no Application object (id=-3)")
    if app_el.get("customClass") != "NSObject":
        raise I.XibError(f"{path}: Application customClass {app_el.get('customClass')!r} "
                         f"not probed ({where})")
    nsapp = _custom_object(b, app_el, "NSApplication", where)
    values = [(nsapp, owner)]
    values.extend(keys)
    keys_arr.add("UINibEncoderEmptyKey", *b.ref(nsapp))
    for obj, _parent in keys:
        keys_arr.add("UINibEncoderEmptyKey", *b.ref(obj))

    values_arr = b.new("NSArray")
    values_arr.add("NSInlinedValue", *b.boolean(False))
    for obj, parent in values:
        values_arr.add("UINibEncoderEmptyKey", *b.ref(parent))

    oids = [owner, nsapp] + [obj for obj, _ in keys] + conn_objs
    oids_keys_arr = b.new("NSArray")
    oids_keys_arr.add("NSInlinedValue", *b.boolean(False))
    for obj in oids:
        oids_keys_arr.add("UINibEncoderEmptyKey", *b.ref(obj))
    oids_values_arr = b.new("NSArray")
    oids_values_arr.add("NSInlinedValue", *b.boolean(False))
    numbers = []
    for i in range(1, len(oids) + 1):
        n = b.new("NSNumber")
        n.add("NS.intval", *b.int8(i))
        numbers.append(n)
        oids_values_arr.add("UINibEncoderEmptyKey", *b.ref(n))
    access_conns = b.new("NSMutableArray")
    access_conns.add("NSInlinedValue", *b.boolean(False))
    access_oids = b.new("NSArray")
    access_oids.add("NSInlinedValue", *b.boolean(False))

    ibd.add("NSRoot", *b.ref(owner))
    ibd.add("NSVisibleWindows", *b.ref(vis))
    ibd.add("NSConnections", *b.ref(conns_arr))
    ibd.add("NSObjectsKeys", *b.ref(keys_arr))
    ibd.add("NSObjectsValues", *b.ref(values_arr))
    ibd.add("NSOidsKeys", *b.ref(oids_keys_arr))
    ibd.add("NSOidsValues", *b.ref(oids_values_arr))
    ibd.add("NSAccessibilityConnectors", *b.ref(access_conns))
    ibd.add("NSAccessibilityOidsKeys", *b.ref(access_oids))
    ibd.add("NSAccessibilityOidsValues", *b.ref(access_oids))
    for late in b.late:
        if late.obj is None:
            raise I.XibError(f"{path}: a forward reference was never filled")
    return _finalize(b, root)


def _finalize(b, root):
    """Key table (__NSSetM order over first-intern order), class table, encode."""
    values, classes, class_idx = [], [], {}
    creation_keys, creation_idx = [], {}
    for o in b.objects:
        o.value_start = len(values)
        for key, v in o.values:
            if key not in creation_idx:
                creation_idx[key] = len(creation_keys)
                creation_keys.append(key)
            v.key_idx = creation_idx[key]
            values.append(v)
        o.value_count = len(values) - o.value_start
        if o.cls not in class_idx:
            class_idx[o.cls] = len(classes)
            classes.append([o.cls, ()])
    arch = N.Archive()
    arch.version = 1
    arch.minor = 10
    arch.keys = [k.encode("ascii") for k in creation_keys]
    arch.classes = [(name.encode("ascii") + b"\x00", extras) for name, extras in classes]
    arch.objects = [N.Object(class_idx[o.cls], o.value_start, o.value_count)
                    for o in b.objects]
    arch.values = values
    key_idx = {k: i for i, k in enumerate(creation_keys)}
    for o in b.objects:
        for key, v in o.values:
            v.key_idx = key_idx[key]
    for v in values:
        if isinstance(v.payload, _Late):
            v.payload = v.payload.obj.idx
    key_bytes = keyorder.key_order(keyorder.first_use_order(arch))
    remap = {k: i for i, k in enumerate(key_bytes)}
    assert len(remap) == len(creation_keys) and all(k in remap for k in creation_keys)
    for v in values:
        v.key_idx = remap[creation_keys[v.key_idx]]
    arch.keys = [k.encode("ascii") for k in key_bytes]
    return N.encode(arch, b"")  # macOS nibs have no LNE trailer


BUTTON_TYPE = {"push": 7, "check": 3, "switch": 3, "radio": 4, "bevel": 7,
               "roundRect": 7, "smallSquare": 7, "help": 7, "momentaryChange": 5}
BEZEL_STYLE = {"rounded": 1, "regularSquare": 2, "helpButton": 9, "recessed": 6,
               "roundedRect": 22, "smallSquare": 12, "texturedRounded": 12}
# (behavior attribute set, button type) -> NSButtonFlags / NSButtonFlags2, as
# compiled by ibtool for the corpus combinations (probe: golden-mac nibs).
BUTTON_BEHAVIOR = {
    ("pushIn", "lightByBackground", "lightByGray"): (0x86804000, 129),
    ("changeContents", "doesNotDimImage", "lightByContents"): (0x48385100, 2),
}


def _key_equivalent(b, cell_el, where):
    s = cell_el.find("string[@key='keyEquivalent']")
    if s is None or not (s.text or "").strip():
        return b.string("")
    import base64
    raw = base64.b64decode(s.text.strip() + "=" * (-len(s.text.strip()) % 4))
    o = b.new("NSString")
    o.add("NS.bytes", N.DATA, raw)
    return o


def _button(b, el, where, superview, id_map, parent=None):
    """<button> -> NSButton with its NSButtonCell."""
    o = b.new("NSButton")
    o.add("NSNextResponder", *(b.ref(superview) if superview is not None else (N.NIL, None)))
    o.add("NSNibTouchBar", *(N.NIL, None))
    v, vt = _vflags(el, where)
    o.add("NSvFlags", vt, v)
    id_map[el.get("id")] = o
    if el.find("subviews") is not None:
        raise I.XibError(f"<button> with subviews not probed ({where})")
    o.add("NSFrame", *b.ref(b.string(_rect(el, "frame", where))))
    if superview is not None:
        o.add("NSSuperview", *b.ref(superview))
    o.add("NSViewWantsBestResolutionOpenGLSurface", *b.boolean(False))
    if el.get("translatesAutoresizingMaskIntoConstraints") == "NO":
        o.add("NSDoNotTranslateAutoresizingMask", *b.boolean(False))
    h, v2 = el.get("horizontalHuggingPriority"), el.get("verticalHuggingPriority")
    if h is not None and v2 is not None:
        o.add("NSHuggingPriority", *b.ref(b.string("{%s, %s}" % (_fmt_g(h), _fmt_g(v2)))))
    h, v2 = (el.get("horizontalCompressionResistancePriority"),
             el.get("verticalCompressionResistancePriority"))
    if h is not None and v2 is not None:
        o.add("NSAntiCompressionPriority",
              *b.ref(b.string("{%s, %s}" % (_fmt_g(h), _fmt_g(v2)))))
    o.add("IBNSSafeAreaLayoutGuide", *(N.NIL, None))
    o.add("IBNSLayoutMarginsGuide", *(N.NIL, None))
    o.add("IBNSClipsToBounds", *b.int8(0))
    o.add("NSEnabled", *b.boolean(False))
    cell_el = el.find("buttonCell[@key='cell']")
    if cell_el is None:
        raise I.XibError(f"<button> without buttonCell ({where})")
    cell = _button_cell(b, cell_el, o, where)
    o.add("NSCell", *b.ref(cell))
    id_map[el.get("id") + "#cell"] = cell
    id_map[cell_el.get("id")] = cell
    o.add("NSAllowsLogicalLayoutDirection", *b.boolean(not b.localize))
    o.add("NSControlSize", *b.int8(0))
    o.add("NSControlContinuous", *b.boolean(True))
    o.add("NSControlRefusesFirstResponder", *b.boolean(True))
    o.add("NSControlUsesSingleLineMode",
          *b.boolean(cell_el.get("usesSingleLineMode") != "YES"))
    align = cell_el.get("alignment", "center")
    if align not in CONTROL_ALIGN:
        raise I.XibError(f"alignment {align!r} not probed ({where})")
    o.add("NSControlTextAlignment", *b.int8(CONTROL_ALIGN[align]))
    lb = cell_el.get("lineBreakMode", "wordWrap")
    if lb not in LINE_BREAK:
        raise I.XibError(f"lineBreakMode {lb!r} not probed ({where})")
    o.add("NSControlLineBreakMode", *b.int8(LINE_BREAK[lb]))
    o.add("NSControlWritingDirection", N.INT64, -1)
    o.add("NSControlSendActionMask", *b.int8(4))
    o.add("IBNSShadowedSymbolConfiguration", *(N.NIL, None))
    return o, [(o, parent), (cell, o)]


def _button_cell(b, el, control, where):
    o = b.new("NSButtonCell")
    flags = 0x4000000
    flags2 = TEXT_ALIGN[el.get("alignment", "center")] << 26
    o.add("NSCellFlags", N.INT32, flags)
    o.add("NSCellFlags2", N.INT32, flags2)
    o.add("NSContents", *b.ref(_localizable(b, el.get("id") or "",
                                            el.get("title", ""), where)))
    fd = el.find("font[@key='font']")
    if fd is None:
        raise I.XibError(f"<buttonCell> without <font> ({where})")
    o.add("NSSupport", *b.ref(b.font(fd, where)))
    o.add("NSControlView", *b.ref(control))
    btype = el.get("type", "momentaryPushIn")
    if btype not in BUTTON_TYPE:
        raise I.XibError(f"button type {btype!r} not probed ({where})")
    behavior = el.find("behavior[@key='behavior']")
    beh = behavior.attrib if behavior is not None else {}
    key = tuple(k for k in beh if beh[k] == "YES" and k not in ("key",))
    if key not in BUTTON_BEHAVIOR:
        raise I.XibError(f"behavior {sorted(key)} not probed ({where})")
    bflags, bflags2 = BUTTON_BEHAVIOR[key]
    o.add("NSButtonFlags", N.INT64, _i32(bflags) if bflags > 0x7FFFFFFF else bflags)
    o.add("NSButtonFlags2", N.INT16, bflags2)
    bezel = el.get("bezelStyle", "rounded")
    if bezel not in BEZEL_STYLE:
        raise I.XibError(f"bezelStyle {bezel!r} not probed ({where})")
    o.add("NSBezelStyle", *b.int8(BEZEL_STYLE[bezel]))
    o.add("NSAlternateContents", *b.ref(b.string("")))
    o.add("NSKeyEquivalent", *b.ref(_key_equivalent(b, el, where)))
    o.add("NSPeriodicDelay", N.INT16, 400)
    o.add("NSPeriodicInterval", *b.int8(75))
    o.add("NSAuxButtonType", *b.int8(BUTTON_TYPE[btype]))
    return o


MENU_CHECKMARK = {"on": ("NSMenuCheckmark", "{18, 16}"), None: ("NSMenuCheckmark", "{18, 16}")}
MENU_MIXED = ("NSMenuMixedState", "{18, 4}")


def _custom_image_resource(b, name, size, where):
    key = (name, size)
    if key in b.images:
        return b.images[key]
    o = b.new("NSCustomResource")
    o.add("NSClassName", *b.ref(b.string("NSImage")))
    o.add("NSResourceName", *b.ref(b.string(name)))
    o.add("IBNamespaceID", *(N.NIL, None))
    val = b.new("NSValue")
    val.add("NS.special", *b.int8(2))
    val.add("NS.sizeval", *b.ref(b.string(size)))
    o.add("IBDesignSize", *b.ref(val))
    o.add("IBDesignImageConfiguration", *(N.NIL, None))
    b.images[key] = o
    return o


def _menu_item(b, item_el, menu, cell, where, localize_owner):
    o = b.new("NSMenuItem")
    o.add("NSMenu", *b.ref(menu if menu is not None else _Late()))
    o.add("NSAllowsKeyEquivalentLocalization", *b.boolean(False))
    o.add("NSAllowsKeyEquivalentMirroring", *b.boolean(False))
    o.add("NSTitle", *b.ref(_localizable(b, localize_owner or item_el.get("id") or "",
                                         item_el.get("title", ""), where)))
    o.add("NSKeyEquiv", *b.ref(b.string("")))
    o.add("NSKeyEquivModMask", N.INT32, 1048576)
    o.add("NSMnemonicLoc", N.INT32, 2147483647)
    if item_el.get("state") == "on":
        o.add("NSState", *b.int8(1))
    on_name, on_size = MENU_CHECKMARK[item_el.get("state") if item_el.get("state") == "on" else None]
    o.add("NSOnImage", *b.ref(_custom_image_resource(b, on_name, on_size, where)))
    o.add("NSMixedImage", *b.ref(_custom_image_resource(b, MENU_MIXED[0], MENU_MIXED[1], where)))
    o.add("NSAction", *b.ref(b.string("_popUpItemAction:")))
    o.add("NSTarget", *b.ref(cell))
    o.add("NSHiddenInRepresentation", *b.boolean(True))
    return o


def _popup(b, el, where, superview, id_map, parent=None):
    """<popUpButton> -> NSPopUpButton + NSPopUpButtonCell + NSMenu (probe ImportOPMLSheet)."""
    o = b.new("NSPopUpButton")
    o.add("NSNextResponder", *(b.ref(superview) if superview is not None else (N.NIL, None)))
    o.add("NSNibTouchBar", *(N.NIL, None))
    v, vt = _vflags(el, where)
    o.add("NSvFlags", vt, v)
    id_map[el.get("id")] = o
    o.add("NSFrame", *b.ref(b.string(_rect(el, "frame", where))))
    if superview is not None:
        o.add("NSSuperview", *b.ref(superview))
    o.add("NSViewWantsBestResolutionOpenGLSurface", *b.boolean(False))
    if el.get("translatesAutoresizingMaskIntoConstraints") == "NO":
        o.add("NSDoNotTranslateAutoresizingMask", *b.boolean(False))
    h, v2 = el.get("horizontalHuggingPriority"), el.get("verticalHuggingPriority")
    if (h is not None and h != "750") or (v2 is not None and v2 != "750"):
        o.add("NSHuggingPriority",
              *b.ref(b.string("{%s, %s}" % (_fmt_g(h or 750), _fmt_g(v2 or 750)))))
    o.add("IBNSSafeAreaLayoutGuide", *(N.NIL, None))
    o.add("IBNSLayoutMarginsGuide", *(N.NIL, None))
    o.add("IBNSClipsToBounds", *b.int8(0))
    o.add("NSEnabled", *b.boolean(False))
    cell_el = el.find("popUpButtonCell[@key='cell']")
    if cell_el is None:
        raise I.XibError(f"<popUpButton> without popUpButtonCell ({where})")
    cell = _popup_cell(b, cell_el, o, where, id_map)
    o.add("NSCell", *b.ref(cell))
    id_map[cell_el.get("id")] = cell
    id_map[el.get("id") + "#cell"] = cell
    o.add("NSAllowsLogicalLayoutDirection", *b.boolean(not b.localize))
    o.add("NSControlSize", *b.int8(0))
    o.add("NSControlContinuous", *b.boolean(True))
    o.add("NSControlRefusesFirstResponder", *b.boolean(True))
    o.add("NSControlUsesSingleLineMode",
          *b.boolean(cell_el.get("usesSingleLineMode") != "YES"))
    align = cell_el.get("alignment", "left")
    if align not in CONTROL_ALIGN:
        raise I.XibError(f"alignment {align!r} not probed ({where})")
    o.add("NSControlTextAlignment", *b.int8(CONTROL_ALIGN[align]))
    lb = cell_el.get("lineBreakMode", "wordWrap")
    if lb not in LINE_BREAK:
        raise I.XibError(f"lineBreakMode {lb!r} not probed ({where})")
    o.add("NSControlLineBreakMode", *b.int8(LINE_BREAK[lb]))
    o.add("NSControlWritingDirection", N.INT64, -1)
    o.add("NSControlSendActionMask", *b.int8(4))
    o.add("IBNSShadowedSymbolConfiguration", *(N.NIL, None))
    return o, [(o, parent), (cell, o)]


def _popup_cell(b, el, control, where, id_map):
    o = b.new("NSPopUpButtonCell")
    o.add("NSCellFlags", N.INT64, -2076180416)
    lb = el.get("lineBreakMode", "wordWrap")
    if lb not in LINE_BREAK:
        raise I.XibError(f"lineBreakMode {lb!r} not probed ({where})")
    o.add("NSCellFlags2", N.INT16, LINE_BREAK_FLAGS2[lb])
    menu_el = el.find("menu[@key='menu']")
    if menu_el is None:
        raise I.XibError(f"<popUpButtonCell> without menu ({where})")
    items = menu_el.find("items")
    if items is None:
        raise I.XibError(f"<menu> without items ({where})")
    sel_id = el.get("selectedItem")
    sel_el = next((m for m in items if m.get("id") == sel_id), items[0] if len(items) else None)
    sel_title = sel_el.get("title", "") if sel_el is not None else ""
    o.add("NSContents", *b.ref(_localizable(b, sel_el.get("id") if sel_el is not None else "",
                                            sel_title, where)))
    fd = el.find("font[@key='font']")
    if fd is None:
        raise I.XibError(f"<popUpButtonCell> without <font> ({where})")
    o.add("NSSupport", *b.ref(b.font(fd, where)))
    o.add("NSControlView", *b.ref(control))
    o.add("NSButtonFlags", N.INT32, 109068288)
    o.add("NSButtonFlags2", N.INT16, 129)
    o.add("NSBezelStyle", *b.int8(1))
    o.add("NSAlternateContents", *b.ref(b.string("")))
    o.add("NSKeyEquivalent", *b.ref(b.string("")))
    o.add("NSPeriodicDelay", N.INT16, 400)
    o.add("NSPeriodicInterval", *b.int8(75))
    o.add("NSAuxButtonType", *b.int8(0))
    if sel_el is None:
        raise I.XibError(f"<popUpButtonCell> without items ({where})")
    late_menu = _Late()
    sel = _menu_item(b, sel_el, late_menu, o, where, el.get("id"))
    o.add("NSMenuItem", *b.ref(sel))
    o.add("NSMenuItemRespectAlignment", *b.boolean(False))
    menu = b.new("NSMenu")
    late_menu.obj = menu
    o.add("NSMenu", *b.ref(menu))
    id_map[menu_el.get("id")] = menu
    id_map[sel_el.get("id")] = sel
    o.add("NSPreferredEdge", *b.int8(1))
    o.add("NSUsesItemFromMenu", *b.boolean(False))
    o.add("NSAltersState", *b.boolean(False))
    o.add("NSArrowPosition", *b.int8(2))
    # menu shell + remaining items in document order (probe ImportOPMLSheet)
    menu.add("NSTitle", *b.ref(b.string("")))
    iarr = b.new("NSMutableArray")
    iarr.add("NSInlinedValue", *b.boolean(False))
    menu.add("NSMenuItems", *b.ref(iarr))
    b.images = getattr(b, "images", {})
    for m in items:
        if m is sel_el:
            iarr.add("UINibEncoderEmptyKey", *b.ref(sel))
            continue
        item = _menu_item(b, m, menu, o, where, el.get("id"))
        id_map[m.get("id")] = item
        iarr.add("UINibEncoderEmptyKey", *b.ref(item))
    return o
