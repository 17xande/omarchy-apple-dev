#!/usr/bin/env python3
"""Generate an xtool adapter package from an Xcode project.

    xcodeproj2xtool.py <path/to/App.xcodeproj> [--target NAME] [--out DIR]

Reads project.pbxproj (OpenStep plist, small stdlib parser) plus the target's
xcconfig files, and writes an adapter directory (default <project root>/omarchy-xtool):

    Package.swift        SwiftPM manifest for the one iOS application target
    xtool.yml            xtool project file (bundleID, infoPath)
    Sources/<Target>/    symlinks to the target's source and resource folders
    Info.plist           only when the project has no Info.plist file and
                         GENERATE_INFOPLIST_FILE = YES (built from INFOPLIST_KEY_*)

Stdlib only. Things it does not support each print one "warning:" line, never
silent: CocoaPods, ObjC sources, run-script phases, Icon Composer .icon assets,
unmapped build settings. App extensions (WidgetKit widgets, share, notification
service, ...) embedded in the selected app target are emitted as extra SwiftPM
targets/products plus `extensions:` entries in xtool.yml; their Info.plist
build-setting placeholders are resolved into written copies. Branch requirements
remain as declared; Package.resolved revisions do not rewrite them.
"""

import argparse
import json
import os
import plistlib
import re
import sys

# ---------------------------------------------------------------- pbxproj parser

TOK_STOP = set('=;,"{}()')


class PlistParser:
    """Parses the OpenStep ASCII plist used by project.pbxproj."""

    def __init__(self, text):
        self.s = text
        self.i = 0

    def error(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        raise ValueError(f"pbxproj line {line}: {msg}")

    def ws(self):
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif s.startswith("/*", self.i):
                e = s.find("*/", self.i + 2)
                self.i = n if e < 0 else e + 2
            elif s.startswith("//", self.i):
                self.i = s.find("\n", self.i)
                if self.i < 0:
                    self.i = n
            else:
                return

    def parse(self):
        self.ws()
        v = self.value()
        self.ws()
        return v

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            self.error("unexpected end of file")
        c = self.s[self.i]
        if c == '"':
            return self.quoted()
        if c == "{":
            return self.dict()
        if c == "(":
            return self.array()
        return self.bare()

    def quoted(self):
        self.i += 1
        out = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == "\\" and self.i + 1 < len(self.s):
                out.append(self.s[self.i + 1])
                self.i += 2
                continue
            if c == '"':
                self.i += 1
                return "".join(out)
            out.append(c)
            self.i += 1
        self.error("unterminated string")

    def dict(self):
        self.i += 1
        d = {}
        while True:
            self.ws()
            if self.i >= len(self.s):
                self.error("unterminated dict")
            if self.s[self.i] == "}":
                self.i += 1
                return d
            k = self.value()
            self.ws()
            if self.i >= len(self.s) or self.s[self.i] != "=":
                self.error("expected = after key")
            self.i += 1
            d[k] = self.value()
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ";":
                self.i += 1

    def array(self):
        self.i += 1
        a = []
        while True:
            self.ws()
            if self.i >= len(self.s):
                self.error("unterminated array")
            if self.s[self.i] == ")":
                self.i += 1
                return a
            a.append(self.value())
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def bare(self):
        s, n = self.s, len(self.s)
        start = self.i
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n" or c in TOK_STOP and not (c == "(" and s[start] == "$"):
                break
            self.i += 1
            if c == ")" and s[start] == "$":
                break
        if self.i == start:
            self.error(f"unexpected character {s[self.i]!r}")
        return s[start : self.i]


def parse_pbxproj(path):
    with open(path, encoding="utf-8") as f:
        return PlistParser(f.read()).parse()


# ---------------------------------------------------------------- xcconfig

def load_xcconfig(path, _seen=None):
    """Returns dict KEY = VALUE, following #include (recursive) in file order."""
    if _seen is None:
        _seen = set()
    path = os.path.normpath(path)
    if not os.path.isfile(path) or path in _seen:
        return {}
    _seen.add(path)
    settings = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("//", 1)[0].strip()
            if not line:
                continue
            m = re.match(r'#include\??\s+"([^"]+)"', line)
            if m:
                inc = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
                settings.update(load_xcconfig(inc, _seen))
                continue
            if line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip().rstrip(";").strip()
    return settings


# ---------------------------------------------------------------- helpers

PROCESSABLE = {
    ".xcassets", ".xcstrings", ".strings", ".stringsdict",
    ".lproj", ".xcdatamodeld",
    ".scnassets", ".intentdefinition", ".appiconset", ".imageset", ".colorset",
}
# Interface Builder sources need Apple's ibtool, which does not exist on Linux
# (the same wall as actool before FINDINGS 24.2). They are copied uncompiled.
IB_EXTS = {".storyboard", ".storyboardc", ".xib", ".nib"}
OBJC_EXTS = {".m", ".mm", ".h", ".hpp", ".c", ".cpp"}


def walk_files(root):
    for base, _dirs, files in os.walk(root):
        for f in files:
            yield os.path.join(base, f)


def has_swift(root):
    return any(f.endswith(".swift") for _b, _d, fs in os.walk(root) for f in fs)


def dir_resource_kind(path):
    """'.process' when the subtree holds compilable resources, else '.copy'."""
    for f in walk_files(path):
        for ext in PROCESSABLE:
            if f.endswith(ext):
                return ".process"
    return ".copy"


def dir_has_ib(path):
    return any(os.path.splitext(f)[1].lower() in IB_EXTS
               for f in walk_files(path))


def package_label(url):
    """SwiftPM's inferred package name for a URL: basename, .git stripped."""
    base = url.rstrip("/").rsplit("/", 1)[-1]
    if base.endswith(".git"):
        base = base[:-4]
    return base


def bump_minor(version):
    m = re.match(r"^(\d+)\.(\d+)", version)
    if not m:
        return version
    return f"{m.group(1)}.{int(m.group(2)) + 1}.0"


def sw_sy(v):
    return json.dumps(v)  # Swift string literals and JSON strings agree here


class Generator:
    def __init__(self, proj_path, target_name=None, out_dir=None):
        self.proj_path = proj_path
        self.proj_dir = os.path.dirname(os.path.abspath(proj_path))
        self.data = parse_pbxproj(os.path.join(proj_path, "project.pbxproj"))
        self.objs = self.data["objects"]
        self.warnings = []
        self.out_dir = out_dir or os.path.join(self.proj_dir, "omarchy-xtool")
        self.target_name = target_name
        self.project = self.objs[self.data["rootObject"]]

    def warn(self, msg):
        line = f"warning: {msg}"
        if line not in self.warnings:
            self.warnings.append(line)

    def path_from_out(self, rel):
        """A project-relative path expressed relative to the output directory."""
        return os.path.relpath(os.path.join(self.proj_dir, rel), self.out_dir)

    # -- settings ---------------------------------------------------------

    def config_settings(self, cfg_list_id):
        """Settings layers for a configuration list, xcconfig first, pbxproj last."""
        layers = []
        cl = self.objs.get(cfg_list_id)
        for cfg_id in (cl or {}).get("buildConfigurations", []):
            cfg = self.objs[cfg_id]
            if cfg.get("name") != "Release":
                continue
            base = cfg.get("baseConfigurationReference")
            anchor = cfg.get("baseConfigurationReferenceAnchor")
            rel = cfg.get("baseConfigurationReferenceRelativePath")
            if base:
                layers.append(self.resolved_ref_path(
                    base, self.build_parent_map()) or "")
            elif anchor and rel:
                layers.append(os.path.join(self.objs[anchor].get("path", ""), rel))
            layers.append(cfg.get("buildSettings", {}))
            break
        return [load_xcconfig(os.path.join(self.proj_dir, l)) if isinstance(l, str) else l
                for l in layers if l]

    def target_merged(self, target):
        """Release settings: project xcconfig < project < target xcconfig < target."""
        layers = self.config_settings(self.project.get("buildConfigurationList"))
        layers += self.config_settings(target.get("buildConfigurationList"))
        return layers

    def setting(self, layers, key):
        for l in layers:
            if l.get(key):
                return l[key]
        return None

    def expand(self, value, layers, _depth=0):
        if _depth > 10 or "$(" not in value:
            return value

        def rep(m):
            name = m.group(1)
            if name == "inherited":
                return ""
            for l in layers:
                if name in l:
                    return self.expand(l[name], layers, _depth + 1)
            return m.group(0)

        return re.sub(r"\$\(([^)]+)\)", rep, value)

    # -- targets ----------------------------------------------------------

    def app_targets(self):
        out = []
        for oid, o in self.objs.items():
            if o.get("isa") == "PBXNativeTarget" and \
                    o.get("productType") == "com.apple.product-type.application":
                out.append((oid, o))
        return out

    def pick_target(self):
        apps = self.app_targets()
        if self.target_name:
            for oid, o in apps:
                if o.get("name") == self.target_name:
                    return oid, o
            raise SystemExit(f"error: no application target named {self.target_name!r} "
                             f"(have: {', '.join(o['name'] for _i, o in apps) or 'none'})")
        ios = []
        for oid, o in apps:
            layers = self.target_merged(o)
            plat = self.setting(layers, "SUPPORTED_PLATFORMS") or \
                self.setting(layers, "SDKROOT") or ""
            if "iphoneos" in plat or "macosx" not in plat:
                ios.append((oid, o))
        if len(ios) == 1:
            return ios[0]
        if not ios:
            ios = apps
            self.warn("no target declares an iOS platform; pick with --target")
        names = [o["name"] for _i, o in ios]
        if len(names) > 1:
            raise SystemExit("error: pass --target NAME; application targets: "
                             + ", ".join(names))
        return ios[0]

    # -- file references (classic groups) ---------------------------------

    def build_parent_map(self):
        parents = {}
        for oid, o in self.objs.items():
            if o.get("isa") == "PBXGroup":
                for c in o.get("children", []):
                    parents[c] = oid
        return parents

    def resolved_ref_path(self, ref_id, parents):
        """Path of a PBXFileReference relative to the project dir, via its
        parent group chain; None when it is not a '<group>'-rooted file."""
        o = self.objs.get(ref_id, {})
        if o.get("isa") != "PBXFileReference" or \
                o.get("sourceTree", "<group>") != "<group>" or not o.get("path"):
            return None
        parts = [o["path"]]
        cur = parents.get(ref_id)
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            g = self.objs.get(cur, {})
            if g.get("path"):
                parts.append(g["path"])
            cur = parents.get(cur)
        return os.path.join(*reversed(parts))

    def resolved_variant_child_path(self, group_id, child_id, parents):
        """Path of a PBXVariantGroup child (locale file, e.g.
        'Base.lproj/Intents.intentdefinition') relative to the project dir:
        the child's path is relative to the variant group's parent group."""
        if self.objs.get(group_id, {}).get("sourceTree", "<group>") != "<group>":
            return None
        c = self.objs.get(child_id, {})
        if c.get("isa") != "PBXFileReference" or \
                c.get("sourceTree", "<group>") != "<group>" or not c.get("path"):
            return None
        parts = [c["path"]]
        cur, seen = parents.get(group_id), set()
        while cur and cur not in seen:
            seen.add(cur)
            g = self.objs.get(cur, {})
            if g.get("path"):
                parts.append(g["path"])
            cur = parents.get(cur)
        return os.path.join(*reversed(parts))

    def phase_files(self, target, phase_isa):
        parents = self.build_parent_map()
        out = []
        for pid in target.get("buildPhases", []):
            ph = self.objs.get(pid, {})
            if ph.get("isa") == "PBXShellScriptBuildPhase":
                self.warn(f"run-script phase {ph.get('name', pid)!r} not supported "
                          "(Xcode-only codegen); check what it does")
            if ph.get("isa") != phase_isa:
                continue
            for bf_id in ph.get("files", []):
                bf = self.objs.get(bf_id, {})
                ref = bf.get("fileRef")
                if not ref:
                    continue
                robj = self.objs.get(ref, {})
                if robj.get("isa") == "PBXVariantGroup":
                    for c in robj.get("children", []):
                        p = self.resolved_variant_child_path(ref, c, parents)
                        if p:
                            out.append((c, p))
                    continue
                p = self.resolved_ref_path(ref, parents)
                if p:
                    out.append((ref, p))
        return out

    # -- synced groups -----------------------------------------------------

    def synced_group_path(self, group_id):
        """On-disk dir of a PBXFileSystemSynchronizedRootGroup, relative to the
        project dir, via its parent group chain (Xcode nests synced groups like
        classic ones; the raw `path` is only relative to the parent group)."""
        g = self.objs.get(group_id, {})
        base = g.get("path") or g.get("name")
        if not base:
            return None
        parents = self.build_parent_map()
        parts = [base]
        cur, seen = parents.get(group_id), set()
        while cur and cur not in seen:
            seen.add(cur)
            p = self.objs.get(cur, {})
            if p.get("path"):
                parts.append(p["path"])
            cur = parents.get(cur)
        return os.path.join(*reversed(parts))

    def synced_group_plan(self, group_id, target_id, infoplist_rel, gpath):
        """Returns (swift_count, resources, excludes) for one synced root group."""
        g = self.objs[group_id]
        if not gpath or not os.path.isdir(os.path.join(self.proj_dir, gpath)):
            self.warn(f"synced group {gpath!r} not found on disk; skipped")
            return 0, [], []
        root = os.path.join(self.proj_dir, gpath)
        excluded = set()
        for ex_id in g.get("exceptions", []):
            ex = self.objs.get(ex_id, {})
            if ex.get("target") == target_id:
                excluded.update(ex.get("membershipExceptions", []))
        ipf_in_group = None
        if infoplist_rel:
            try:
                cand = os.path.relpath(infoplist_rel, gpath)
                if not cand.startswith(".."):
                    ipf_in_group = cand
            except ValueError:
                pass
        resources, excludes, n_swift = [], [], [0]
        icon_dirs = [0]
        objc_files = []
        ib_files = []

        def classify(dirpath, rel):
            for name in sorted(os.listdir(dirpath)):
                p = os.path.join(dirpath, name)
                r = f"{rel}/{name}" if rel else name
                if os.path.isdir(p) and name.endswith(".icon"):
                    icon_dirs[0] += 1
                    excludes.append(r)
                    continue
                if r in excluded or name.endswith(".entitlements") or \
                        (ipf_in_group and r == ipf_in_group):
                    excludes.append(r)
                    continue
                if os.path.splitext(name)[1].lower() in OBJC_EXTS and \
                        not os.path.isdir(p):
                    objc_files.append(r)
                    excludes.append(r)
                    continue
                if os.path.splitext(name)[1].lower() in IB_EXTS:
                    ib_files.append(r)
                    excludes.append(r)
                    continue
                if os.path.isdir(p):
                    if has_swift(p):
                        n_swift[0] += sum(1 for f in walk_files(p) if f.endswith(".swift"))
                        classify(p, r)
                    elif dir_has_ib(p):
                        # expand: a single .copy dir would still hand Apple's
                        # ibtool probes a storyboard it can never compile
                        classify(p, r)
                    elif os.path.splitext(name)[1].lower() in PROCESSABLE:
                        resources.append((".process", r))
                    else:
                        resources.append((dir_resource_kind(p), r))
                elif name.endswith(".swift"):
                    n_swift[0] += 1
                else:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in PROCESSABLE:
                        resources.append((".process", r))
                    else:
                        resources.append((".copy", r))

        classify(root, "")
        if icon_dirs[0]:
            self.warn(f"synced group {gpath!r}: {icon_dirs[0]} Icon Composer .icon "
                      "assets excluded (Linux actool cannot compile them)")
        if objc_files:
            self.warn(f"synced group {gpath!r}: {len(objc_files)} ObjC/C files "
                      f"excluded (not supported on Linux), e.g. {objc_files[0]}; "
                      "replace them with a Swift shim if target code calls them")
        if ib_files:
            self.warn(f"synced group {gpath!r}: {len(ib_files)} Interface Builder "
                      "resources excluded - Linux has no ibtool to compile them "
                      "(same wall as actool before FINDINGS 24.2); UI built from "
                      "them is missing from the bundle")
        return n_swift[0], resources, excludes

    # -- packages -----------------------------------------------------------

    def resolved_revisions(self):
        p = os.path.join(self.proj_path, "project.xcworkspace", "xcshareddata",
                         "swiftpm", "Package.resolved")
        if not os.path.isfile(p):
            return {}
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            self.warn(f"cannot read Package.resolved ({e})")
            return {}
        revs = {}
        for pin in data.get("pins", []):
            st = pin.get("state", {})
            rev = st.get("revision") or st.get("checkoutRevision")
            if rev:
                revs[pin.get("identity", "")] = rev
                loc = pin.get("location")
                if loc:
                    revs[self.package_identity(loc)] = rev
        return revs

    @staticmethod
    def package_identity(url):
        return package_label(url).lower()

    def requirement(self, ref, revs):
        """Returns the SwiftPM requirement snippet, or None to skip."""
        req = ref.get("requirement", {})
        url = ref.get("repositoryURL", "")
        kind = req.get("kind")
        ident = self.package_identity(url)
        if kind == "upToNextMajorVersion":
            return f"from: {sw_sy(req['minimumVersion'])}"
        if kind == "upToNextMinorVersion":
            lo, hi = req["minimumVersion"], bump_minor(req["minimumVersion"])
            return f"{sw_sy(lo)}..<{sw_sy(hi)}"
        if kind == "exactVersion":
            return f"exact: {sw_sy(req['exactVersion'])}"
        if kind == "versionRange":
            return f"{sw_sy(req['minimumVersion'])}..<{sw_sy(req['maximumVersion'])}"
        if kind == "branch":
            return f"branch: {sw_sy(req.get('branch', ''))}"
            return f"revision: {sw_sy(req.get('revision', ''))}"
        rev = revs.get(ident)
        if rev:
            self.warn(f"no requirement kind for {url}; pinned to Package.resolved revision")
            return f"revision: {sw_sy(rev)}"
        self.warn(f"unsupported package requirement kind {kind!r} for {url}; skipped")
        return None

    def dedupe_resources(self, resources):
        """SwiftPM requires unique resource basenames per target; expand
        directory entries whose basename collides into their children."""
        entries = []
        seen = set()
        for k, p in resources:
            if (k, p) not in seen:
                seen.add((k, p))
                entries.append((k, p))
        for _round in range(6):
            by_base = {}
            for k, p in entries:
                # files inside .lproj dirs are localized variants of one
                # resource; SwiftPM groups them per locale instead of
                # requiring unique names
                if os.path.basename(os.path.dirname(p)).endswith(".lproj"):
                    continue
                by_base.setdefault(os.path.basename(p), []).append((k, p))
            colliding = {b for b, v in by_base.items() if len(v) > 1}
            if not colliding:
                return entries
            out = []
            expanded = False
            for k, p in entries:
                pj = os.path.join(self.proj_dir, p)
                if os.path.basename(p) in colliding and os.path.isdir(pj):
                    expanded = True
                    for name in sorted(os.listdir(pj)):
                        if name.endswith(".entitlements") or name == "Info.plist":
                            # entitlements are never bundle resources, and SwiftPM
                            # forbids Info.plist as a top-level resource
                            continue
                        cp = f"{p}/{name}"
                        ext = os.path.splitext(name)[1].lower()
                        cj = os.path.join(self.proj_dir, cp)
                        ck = ".process" if ext in PROCESSABLE or (
                            os.path.isdir(cj) and
                            dir_resource_kind(cj) == ".process") else ".copy"
                        out.append((ck, cp))
                else:
                    out.append((k, p))
            if not expanded:
                break
            entries = out
        bases = {}
        for _k, p in entries:
            bases.setdefault(os.path.basename(p), 0)
            bases[os.path.basename(p)] += 1
        for b, n in bases.items():
            if n > 1:
                self.warn(f"multiple resources named {b!r} remain; rename one "
                          "(SwiftPM requires unique resource names per target)")
        return entries

    def find_local_package(self, product):
        """Directory (relative to project dir) of the local package for product."""
        local_refs = [(oid, o) for oid, o in self.objs.items()
                      if o.get("isa") == "XCLocalSwiftPackageReference"]
        for _oid, o in local_refs:
            rp = o.get("relativePath", "")
            if os.path.basename(rp.rstrip("/")) == product and \
                    os.path.isfile(os.path.join(self.proj_dir, rp, "Package.swift")):
                return rp
        for base in ("", "Packages", "Modules", "Frameworks"):
            rp = os.path.join(base, product) if base else product
            if os.path.isfile(os.path.join(self.proj_dir, rp, "Package.swift")):
                return rp
        if product.endswith("Dynamic"):
            # local packages referenced only implicitly (Xcode 16 synchronized
            # projects); the dir is named after the static twin
            stripped = product[:-len("Dynamic")]
            for base in ("", "Packages", "Modules", "Frameworks"):
                rp = os.path.join(base, stripped) if base else stripped
                if os.path.isfile(os.path.join(self.proj_dir, rp, "Package.swift")):
                    return rp
        return None

    _module_names_cache = None

    def provided_module_closure(self, rp, prod_name, _stack=None):
        """Modules the declared product prod_name of the local package at rp
        already provides: its targets, the same-package targets they depend
        on (transitively), all library product names of the manifest, and the
        products consumed by any target in the closure - recursing into
        OTHER local packages those products come from (e.g. a path-dep
        checkout whose own targets pull further static products). The import
        scan must not re-declare any of these: they are already carried by
        the declared product, and re-declaring them duplicates static deps
        into every consumer."""
        if self._module_names_cache is None:
            self._module_names_cache = {}
        key = (rp, prod_name)
        if key in self._module_names_cache:
            return self._module_names_cache[key]
        if _stack is None:
            _stack = set()
        if key in _stack:
            return set()
        _stack.add(key)
        try:
            return self._provided_module_closure(rp, prod_name, _stack)
        finally:
            _stack.discard(key)

    def _provided_module_closure(self, rp, prod_name, stack):
        provided = set()
        mf = os.path.join(self.proj_dir, rp, "Package.swift")
        if os.path.isfile(mf):
            text = open(mf, encoding="utf-8", errors="replace").read()
            libraries = {}   # product -> [targets]
            for m in re.finditer(
                    r'\.library\(\s*name:\s*"([^"]+)"(?:,\s*targets:\s*\[([^\]]*)\])?',
                    text):
                inner = m.group(2) or ""
                targets = re.findall(r'"([^"]+)"', inner)
                # `targets: publicLibraryTargets` (a variable) yields no
                # quoted names; the product then covers every target in the
                # manifest, which is the safe superset for the closure.
                if not targets and (not inner.strip() or '"' not in inner):
                    targets = None  # resolved after `targets` is parsed
                libraries[m.group(1)] = targets
                provided.add(m.group(1))
            targets = {}     # target -> {"deps": [...], "products": [...]}
            for m in re.finditer(
                    r'\.target\(\s*name:\s*"([^"]+)"(.*?)(?=\.target\(|'
                    r'\.executableTarget\(|\.testTarget\(|$)', text, re.S):
                body = m.group(2)
                products = re.findall(r'\.product\(\s*name:\s*"([^"]+)"', body)
                deps = [d for d in re.findall(r'"([^"]+)"', body)
                        if d not in products]
                targets[m.group(1)] = {"deps": deps, "products": products}
            queue = list(libraries.get(prod_name) or [])
            if libraries.get(prod_name) is None and targets:
                # product target list is a manifest variable: wrap everything
                queue = list(targets)
            seen = set()
            while queue:
                t = queue.pop()
                if t in seen:
                    continue
                seen.add(t)
                provided.add(t)
                info = targets.get(t) or {}
                for pname in info.get("products", []):
                    provided.add(pname)
                    rp2 = self.discover_local_packages().get(pname)
                    if rp2:
                        provided |= self.provided_module_closure(rp2, pname, stack)
                for d in info.get("deps", []):
                    if d not in seen and d in targets:
                        queue.append(d)
        self._module_names_cache[(rp, prod_name)] = provided
        return provided

    def remote_products_in_manifests(self, local_paths):
        """product name -> (url, requirement snippet) for remotes declared by
        local package manifests (for transitive imports SwiftPM needs declared)."""
        found = {}
        for rp in local_paths:
            mf = os.path.join(self.proj_dir, rp, "Package.swift")
            if not os.path.isfile(mf):
                continue
            text = open(mf, encoding="utf-8", errors="replace").read()
            url_by_name = {}
            reqs = {}
            for m in re.finditer(r'\.package\(\s*url:\s*"([^"]+)"\s*,\s*([^)]+)\)', text):
                url = m.group(1)
                for key in (package_label(url), package_label(url).lower()):
                    url_by_name[key] = url
                    reqs[key] = m.group(2).strip()
            prod_to_pkg = {}
            for m in re.finditer(r'\.product\(\s*name:\s*"([^"]+)"\s*,\s*package:\s*"([^"]+)"', text):
                prod_to_pkg[m.group(1)] = m.group(2)
            for prod, pkg in prod_to_pkg.items():
                if pkg in url_by_name and reqs[pkg]:
                    found[prod] = (url_by_name[pkg], reqs[pkg])
        return found

    # -- target file plan ---------------------------------------------------

    def plan_target_files(self, target_id, target):
        """Returns (symlinks, excludes, resources, swift_rels, objc_hits).

        symlinks: [(link_path_relative_to_out, destination_relative_to_project_dir)]
        excludes/resources: paths relative to Sources/<Target>.
        swift_rels: project-relative paths of the target's .swift files.
        """
        target_dir = f"Sources/{target['name']}"
        symlinks, excludes, resources, swift_rels, objc = [], [], [], [], []
        infoplist_rel = None

        layers = self.target_merged(target)
        # Only the selected app target's ASSETCATALOG_COMPILER_APPICON_NAME
        # names its primary .icon; extensions (and tests) reuse "AppIcon" as
        # a default that must NOT silently consume the app's asset.
        app_icon_name = None
        if target is getattr(self, "target", None):
            name = self.setting(layers, "ASSETCATALOG_COMPILER_APPICON_NAME") or "AppIcon"
            if name and not name.endswith(".icon"):
                app_icon_name = f"{name}.icon"
        ipf = self.setting(layers, "INFOPLIST_FILE")
        if ipf:
            infoplist_rel = os.path.normpath(ipf)

        for gid in target.get("fileSystemSynchronizedGroups", []):
            g = self.objs.get(gid, {})
            gpath = self.synced_group_path(gid) or (g.get("path") or g.get("name"))
            n_swift, res, exc = self.synced_group_plan(gid, target_id, infoplist_rel, gpath)
            if n_swift == 0 and not res:
                if exc:
                    self.warn(f"synced group {gpath!r} has no Swift sources and only "
                              "excluded assets; skipped")
                continue
            link = os.path.join(target_dir, os.path.basename(gpath.rstrip("/")))
            symlinks.append((link, gpath))
            excludes += [f"{os.path.basename(gpath.rstrip('/'))}/{e}" for e in exc]
            resources += [(k, f"{os.path.basename(gpath.rstrip('/'))}/{r}") for k, r in res]
            base = os.path.join(self.proj_dir, gpath)
            swift_rels += [os.path.join(gpath, os.path.relpath(f, base))
                           for f in walk_files(base) if f.endswith(".swift")]

        # An exception set naming this target on a synced group the target
        # does NOT own adds those files to the target (Xcode's way of sharing
        # a few files of another target's folder). For the owner, the same
        # set removes files (handled in synced_group_plan).
        owned = set(target.get("fileSystemSynchronizedGroups", []))
        taken = {os.path.relpath(l, target_dir).split(os.sep)[0] for l, _ in symlinks}
        added = []
        for gid, g in self.objs.items():
            if g.get("isa") != "PBXFileSystemSynchronizedRootGroup" or gid in owned:
                continue
            gpath = self.synced_group_path(gid) or g.get("path") or g.get("name")
            for ex_id in g.get("exceptions", []):
                ex = self.objs.get(ex_id, {})
                if ex.get("isa") != "PBXFileSystemSynchronizedBuildFileExceptionSet" \
                        or ex.get("target") != target_id:
                    continue
                top = os.path.basename(gpath.rstrip("/"))
                if top in taken:
                    top = f"{top}-shared"
                for rel in ex.get("membershipExceptions", []):
                    p = os.path.join(gpath, rel)
                    if rel.endswith((".xcconfig", ".entitlements")) or \
                            not os.path.isfile(os.path.join(self.proj_dir, p)):
                        continue
                    link = os.path.join(target_dir, top, rel)
                    os.makedirs(os.path.dirname(os.path.join(self.out_dir, link)),
                                exist_ok=True)
                    symlinks.append((link, p))
                    ext = os.path.splitext(rel)[1].lower()
                    if ext == ".swift":
                        swift_rels.append(p)
                    elif ext in OBJC_EXTS:
                        excludes.append(f"{top}/{rel}")
                        self.warn(f"{target['name']}: shared ObjC/C file {p!r} "
                                  "excluded (not supported on Linux)")
                    else:
                        resources.append((".process" if ext in PROCESSABLE
                                          else ".copy", f"{top}/{rel}"))
                    added.append(p)
        if added:
            self.warn(f"{target['name']}: {len(added)} file(s) shared from other "
                      f"targets' synced folders added, e.g. {added[0]}")

        src_files = self.phase_files(target, "PBXSourcesBuildPhase")
        res_files = self.phase_files(target, "PBXResourcesBuildPhase")
        src_anc = None
        if src_files:
            members = []
            src_resources = []
            for ref_id, p in src_files:
                ext = os.path.splitext(p)[1].lower()
                if ext == ".swift":
                    members.append(p)
                    swift_rels.append(p)
                elif ext in OBJC_EXTS:
                    objc.append(p)
                else:
                    # Xcode also lists localized resources (variant groups) in
                    # the Sources phase; they go through the resource path below
                    src_resources.append((ref_id, p))
            res_files = src_resources + res_files
            if members:
                # Longest common directory of the members, component-wise.
                # (dirname(commonprefix(m + "/")) breaks for a single member:
                # the trailing slash makes dirname return the file itself.)
                uniq = sorted(set(members))
                if len(uniq) == 1:
                    anc = os.path.dirname(uniq[0])
                else:
                    common = uniq[0].split("/")
                    for m in uniq[1:]:
                        pp = m.split("/")
                        i = 0
                        while i < min(len(common), len(pp)) and common[i] == pp[i]:
                            i += 1
                        common = common[:i]
                    anc = "/".join(common)
                src_anc = anc or None
                if anc and anc != ".":
                    link = os.path.join(target_dir, os.path.basename(anc))
                    symlinks.append((link, anc))
                    res_under = [p for _r, p in res_files
                                 if p == anc or p.startswith(anc + "/")]
                    excl = self.non_member_excludes(anc, members, keep=res_under)
                    excludes += [f"{os.path.basename(anc)}/{e}" for e in excl]
                else:
                    for m in members:
                        self.mirror_file(m, target_dir, symlinks)
        if objc:
            self.warn(f"{len(objc)} ObjC/C source files are not supported and were "
                      f"excluded, e.g. {objc[0]}")

        ib_excluded = []
        for ref_id, p in res_files:
            if os.path.splitext(p)[1].lower() in IB_EXTS:
                ib_excluded.append(p)
                continue
            if p.endswith(".icon"):
                # The app target's primary .icon is symlinked into the
                # adapter root by run() and consumed by ship.sh; alternates
                # stay as copies of a skipped resource.
                if app_icon_name and os.path.basename(p) == app_icon_name:
                    continue
                self.warn(f"Icon Composer asset {p!r} excluded (Linux actool cannot "
                          "compile it)")
                continue
            if src_anc and (p == src_anc or p.startswith(src_anc + "/")):
                pj = os.path.join(self.proj_dir, p)
                kind = ".process" if (
                    os.path.splitext(p)[1].lower() in PROCESSABLE
                    or (os.path.isdir(pj) and dir_resource_kind(pj) == ".process")
                ) else ".copy"
                # The src_anc symlink created above exposes this subtree to
                # SwiftPM at target-relative basename(src_anc)/...; emit the
                # resource in that space so the path always resolves. Emitting
                # p verbatim only works when basename(src_anc) happens to be
                # p's first component (project-root-named groups) and silently
                # breaks otherwise (Mastodon's
                # "Mastodon/Supporting Files/Settings.bundle" never existed in
                # the adapter, so packaging died at CpResource).
                rel = os.path.relpath(p, src_anc)
                rp = os.path.basename(src_anc) if rel == "." \
                    else os.path.join(os.path.basename(src_anc), rel)
                resources.append((kind, rp))
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext in PROCESSABLE:
                resources.append((".process", p))
            else:
                resources.append((".copy", p))
            if os.path.isdir(os.path.join(self.proj_dir, p)):
                symlinks.append((os.path.join(target_dir, p), p))
            else:
                self.mirror_file(p, target_dir, symlinks)
        if ib_excluded:
            # Exclude the same farm path SwiftPM's resource scan sees, so an
            # auto-included storyboard never reaches ibtool (Mastodon's
            # LaunchScreen/Main storyboards did exactly that through the
            # "Supporting Files" link). Under src_anc the visible spelling is
            # basename(src_anc)/...; elsewhere the file is only reachable at
            # its emitted path, if at all.
            for p in ib_excluded:
                if src_anc and (p == src_anc or p.startswith(src_anc + "/")):
                    rel = os.path.relpath(p, src_anc)
                    excludes.append(os.path.basename(src_anc) if rel == "."
                                    else os.path.join(os.path.basename(src_anc), rel))
                else:
                    excludes.append(p)
            self.warn(f"{len(ib_excluded)} Interface Builder resource(s) excluded "
                      "- Linux has no ibtool to compile them: "
                      + ", ".join(ib_excluded))
            missing_ui = self.excluded_storyboard_in_plist(ib_excluded, infoplist_rel)
            if missing_ui:
                self.warn(f"Info.plist references excluded storyboard {missing_ui!r}; "
                          "the launch/main UI will be missing from the bundle")
        intents = [p for _k, p in resources if p.endswith(".intentdefinition")]
        if intents:
            self.warn(f"{len(intents)} .intentdefinition file(s) copied uncompiled "
                      "(Xcode compiles them and generates intent classes; Linux has "
                      "no intent compiler), e.g. " + intents[0])
        return symlinks, sorted(set(excludes)), resources, swift_rels

    def excluded_storyboard_in_plist(self, ib_excluded, infoplist_rel):
        """Name an excluded storyboard the Info.plist references, if any."""
        if not infoplist_rel:
            return None
        path = os.path.join(self.proj_dir, infoplist_rel)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                pl = plistlib.load(f)
        except Exception:
            return None
        names = {os.path.splitext(pl[k])[0] for k in
                 ("UILaunchStoryboardName", "UIMainStoryboardFile",
                  "NSMainStoryboardFile") if pl.get(k)}
        for p in ib_excluded:
            if os.path.splitext(os.path.basename(p))[0] in names:
                return os.path.basename(p)
        return None

    def non_member_excludes(self, anc, members, keep=()):
        """Paths under ancestor `anc` that are neither on a member's path nor kept
        (resources stay out of exclude so SwiftPM does not see a conflict)."""
        keep = set(keep)
        path_parts = set()
        for m in list(members) + list(keep):
            rel = os.path.relpath(m, anc)
            parts = rel.split(os.sep)
            for i in range(len(parts)):
                path_parts.add(os.path.join(*parts[: i + 1]))
        out = []
        root = os.path.join(self.proj_dir, anc)

        def visit(dirpath, rel):
            for name in sorted(os.listdir(dirpath)):
                r = os.path.join(rel, name) if rel else name
                if r in path_parts:
                    p = os.path.join(dirpath, name)
                    if os.path.isdir(p) and r not in keep:
                        visit(p, r)
                else:
                    out.append(r)

        visit(root, "")
        return out

    def mirror_file(self, rel, target_dir, symlinks):
        """Symlink one file, creating real parent dirs (for root-level files)."""
        link = os.path.join(target_dir, rel)
        os.makedirs(os.path.dirname(os.path.join(self.out_dir, link)), exist_ok=True)
        symlinks.append((link, rel))

    # -- packages for the target --------------------------------------------

    def discover_local_packages(self):
        """Library product name -> package dir (project-relative), for all
        Package.swift manifests near the project (depth-capped)."""
        found = {}
        root_depth = self.proj_dir.rstrip(os.sep).count(os.sep)
        out_abs = os.path.abspath(self.out_dir)
        for base, dirs, files in os.walk(self.proj_dir):
            if base.count(os.sep) - root_depth >= 3:
                dirs[:] = []
                continue
            if os.path.abspath(base) == out_abs:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in (".git", ".build", "Pods",
                                                    "DerivedData", "xtool")
                       and not d.startswith(".")]
            if "Package.swift" in files:
                rel = os.path.relpath(base, self.proj_dir)
                text = open(os.path.join(base, "Package.swift"),
                            encoding="utf-8", errors="replace").read()
                for m in re.finditer(r'\.library\(\s*name:\s*"([^"]+)"', text):
                    found.setdefault(m.group(1), rel)
        return found

    def plan_packages(self, target, swift_rels):
        """Returns (packages, products) SwiftPM declarations for the target."""
        target_deps = [self.objs[i] for i in target.get("packageProductDependencies", [])
                       if isinstance(self.objs.get(i), dict)]
        refs = {oid: o for oid, o in self.objs.items()
                if o.get("isa") == "XCRemoteSwiftPackageReference"}
        local_refs = {oid: o for oid, o in self.objs.items()
                      if o.get("isa") == "XCLocalSwiftPackageReference"}
        revs = self.resolved_revisions()

        packages, products, seen_pkg, seen_prod = [], [], {}, set()
        decl_local, local_paths = {}, []

        # Pass 1: resolve every explicit product dependency (no emission yet;
        # the provided-module closure needs the local declarations first).
        explicit = []   # ("remote", name, url, req) | ("local", name, rp, None)
        for dep in target_deps:
            name = dep.get("productName")
            if not name or name in seen_prod:
                continue
            seen_prod.add(name)
            pkg_id = dep.get("package")
            if pkg_id in refs:
                req = self.requirement(refs[pkg_id], revs)
                if req:
                    explicit.append(("remote", name,
                                     refs[pkg_id]["repositoryURL"], req))
            else:
                rp = self.find_local_package(name)
                if rp is None:
                    if pkg_id in local_refs:
                        rp = local_refs[pkg_id].get("relativePath")
                    if rp is None:
                        self.warn(f"local package for product {name!r} not found; skipped")
                        continue
                explicit.append(("local", name, rp, None))
                if rp not in decl_local:
                    decl_local[rp] = name
                    local_paths.append(rp)

        # Pass 2: modules already carried by declared local products.
        provided = set()
        provider_of = {}
        for rp, prod_name in decl_local.items():
            closure = self.provided_module_closure(rp, prod_name)
            provided |= closure
            for mod in closure:
                provider_of.setdefault(mod, prod_name)

        # Pass 3: emit. A product the declared dynamic product already carries
        # is omitted: SwiftPM fails the whole build with "linked as a static
        # library by X and Y" when the same static product reaches both the
        # app executable and the dynamic library.
        for kind, name, x, req in explicit:
            if kind == "remote":
                if name in provided:
                    self.warn(f"product {name!r} is already carried by "
                              f"{provider_of.get(name)!r}; omitted from this "
                              "target's dependencies")
                    continue
                if x not in seen_pkg:
                    seen_pkg[x] = True
                    packages.append(f'.package(url: {sw_sy(x)}, {req})')
                products.append((name, package_label(x)))
            else:
                if name in provided and name != decl_local.get(x):
                    self.warn(f"product {name!r} is already carried by "
                              f"{provider_of.get(name)!r}; omitted from this "
                              "target's dependencies")
                    continue
                if x not in decl_local or decl_local[x] == name:
                    if not any(p.startswith(f'.package(name: {sw_sy(name)}, ')
                               for p in packages):
                        packages.append(f'.package(name: {sw_sy(name)}, '
                                        f'path: {sw_sy(self.path_from_out(x))})')
                products.append((name, name))

        # SwiftPM needs transitive products that target sources import directly
        # (Xcode resolves them through indirect dependencies; SwiftPM does not).
        imported = set()
        for rel in swift_rels:
            p = os.path.join(self.proj_dir, rel)
            if os.path.isfile(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        m = re.match(r"\s*import\s+([A-Za-z_]\w*)", line)
                        if m:
                            imported.add(m.group(1))
        disc = self.discover_local_packages()
        remote_map = self.remote_products_in_manifests(
            set(disc.values()) | set(local_paths))
        # Modules provided by already-declared local packages: every target in
        # the declared product's transitive closure (through same-package
        # target deps), every product name in the manifest, and every REMOTE
        # product those closure targets consume. Xcode lets a target import
        # such modules directly; re-declaring them as extra products duplicates
        # the package's static deps into every consumer (the app would link
        # the static product alongside the dynamic one).
        provided = set()
        for rp, prod_name in decl_local.items():
            provided |= self.provided_module_closure(rp, prod_name)
        extra_pkgs, extra_prods = [], []
        for mod in sorted(imported):
            if mod in seen_prod or mod == target["name"]:
                continue
            if mod in provided:
                continue
            if mod in disc:
                rp = disc[mod]
                if rp not in decl_local:
                    decl_local[rp] = mod
                    packages.append(f'.package(name: {sw_sy(mod)}, '
                                    f'path: {sw_sy(self.path_from_out(rp))})')
                extra_prods.append((mod, decl_local[rp]))
                seen_prod.add(mod)
                continue
            hit = remote_map.get(mod)
            if not hit:
                continue
            url, req = hit
            seen_prod.add(mod)
            if url not in seen_pkg:
                seen_pkg[url] = True
                extra_pkgs.append(f'.package(url: {sw_sy(url)}, {req})')
            extra_prods.append((mod, package_label(url)))
        if extra_prods:
            self.warn("declared additional packages for modules the target imports "
                      "through indirect dependencies (Xcode allows this, SwiftPM "
                      "does not): " + ", ".join(sorted({m for m, _ in extra_prods})))
        return packages + extra_pkgs, products + extra_prods

    # -- manifest assembly --------------------------------------------------

    def swift_settings(self, layers):
        out = []
        v = self.setting(layers, "SWIFT_VERSION") or ""
        mode = ".v6" if v.startswith("6") else (".v5" if v.startswith("5") else None)
        if mode is None:
            if v:
                self.warn(f"SWIFT_VERSION {v!r} not mapped; using language mode .v6")
            mode = ".v6"
        out.append(f".swiftLanguageMode({mode})")
        if self.setting(layers, "SWIFT_DEFAULT_ACTOR_ISOLATION") == "MainActor":
            out.append(".defaultIsolation(MainActor.self)")
        upcoming = []
        if self.setting(layers, "SWIFT_APPROACHABLE_CONCURRENCY") == "YES":
            # What Xcode's approachable concurrency expands to (matches the
            # OTHER_SWIFT_FLAGS projects add by hand). This toolchain's
            # PackageDescription has no enableApproachableConcurrency().
            upcoming += ["NonisolatedNonsendingByDefault", "InferIsolatedConformances"]
        for l in layers:
            for k, val in l.items():
                if k.startswith("SWIFT_UPCOMING_FEATURE_") and val == "YES" and \
                        "[sdk=" not in k:
                    feat = k[len("SWIFT_UPCOMING_FEATURE_"):]
                    if feat not in upcoming:
                        upcoming.append(feat)
        for feat in upcoming:
            out.append(f'.enableUpcomingFeature({sw_sy(feat)})')
        # Xcode resolves SWIFT_ENABLE_BARE_SLASH_REGEX to YES for iOS 16+
        # deployment targets when the setting is unset; below language mode 6 a
        # /regex/ literal is a parse error without the feature (Mastodon's
        # GenericMastodonPost+Subclasses.swift).
        bare = self.setting(layers, "SWIFT_ENABLE_BARE_SLASH_REGEX")
        if bare not in ("YES", "NO"):
            dt = self.setting(layers, "IPHONEOS_DEPLOYMENT_TARGET")
            m = re.match(r"(\d+)(?:\.(\d+))?", self.expand(dt, layers)) if dt else None
            bare = "YES" if m and (int(m.group(1)), int(m.group(2) or 0)) >= (16, 0) else "NO"
        if bare == "YES" and mode != ".v6" and "BareSlashRegexLiterals" not in upcoming:
            upcoming.insert(0, "BareSlashRegexLiterals")
            out.insert(1, '.enableUpcomingFeature("BareSlashRegexLiterals")')
        cond = self.setting(layers, "SWIFT_ACTIVE_COMPILATION_CONDITIONS")
        if cond:
            for d in re.sub(r"\$\([^)]*\)", "", cond).replace(",", " ").split():
                out.append(f".define({sw_sy(d)})")
        flags = self.setting(layers, "OTHER_SWIFT_FLAGS")
        if flags:
            toks = [t for t in re.sub(r"\$\([^)]*\)", "", flags).split() if t]
            if toks:
                self.warn("OTHER_SWIFT_FLAGS not mapped (SwiftPM forbids "
                          "unsafeFlags outside the root package, and xtool nests "
                          "this one): " + " ".join(toks))
        return out

    def bundle_id(self, layers):
        raw = self.setting(layers, "PRODUCT_BUNDLE_IDENTIFIER")
        if not raw:
            self.warn("no PRODUCT_BUNDLE_IDENTIFIER; using placeholder BUNDLE.ID.TO.BE.SET")
            return "BUNDLE.ID.TO.BE.SET"
        val = self.expand(raw, layers)
        if "$(" in val:
            self.warn(f"PRODUCT_BUNDLE_IDENTIFIER has unresolvable {raw!r}; "
                      f"set bundleID in xtool.yml by hand")
            return re.sub(r"\$\([^)]*\)", "SET-BY-HAND", val)
        return val

    def target_infoplan(self, layers, target_name, dev_region, extension):
        """Builds the adapter Info.plist for one target (app or extension):
        the project's INFOPLIST_FILE when present, plus INFOPLIST_KEY_* values
        when GENERATE_INFOPLIST_FILE = YES (file keys win, as in Xcode), with
        $(BUILD_SETTING) placeholders resolved; unresolved values and the
        executable/bundle-id keys xtool owns are dropped.

        Returns (plist, dropped_keys); the caller writes it."""
        ipf = self.setting(layers, "INFOPLIST_FILE")
        ipf_path = os.path.normpath(ipf) if ipf else None
        if ipf and not os.path.isfile(os.path.join(self.proj_dir, ipf_path)):
            self.warn(f"INFOPLIST_FILE {ipf!r} does not exist")
            ipf_path = None
        plist = {}
        if ipf_path:
            with open(os.path.join(self.proj_dir, ipf_path), "rb") as f:
                plist = plistlib.load(f)
        if self.setting(layers, "GENERATE_INFOPLIST_FILE") == "YES":
            generated = {}
            for l in layers:
                for k, v in l.items():
                    if not k.startswith("INFOPLIST_KEY_") or "[sdk=" in k:
                        continue
                    key = k[len("INFOPLIST_KEY_"):]
                    v = self.expand(v, layers)
                    if key.startswith("UISupportedInterfaceOrientations"):
                        name = "UISupportedInterfaceOrientations~ipad" if \
                            key.endswith("_iPad") else "UISupportedInterfaceOrientations"
                        generated[name] = v.split()
                    elif key == "UILaunchScreen_Generation" and v == "YES":
                        generated["UILaunchScreen"] = {}
                    else:
                        generated[key] = v
            merged = dict(generated)
            merged.update(plist)
            plist = merged
            if not ipf_path:
                self.warn("wrote a minimal Info.plist from INFOPLIST_KEY_* settings; "
                          "review it before shipping")
        if not ipf_path and self.setting(layers, "GENERATE_INFOPLIST_FILE") != "YES":
            if not extension:
                self.warn("no Info.plist file and GENERATE_INFOPLIST_FILE != YES; "
                          "xtool.yml gets no infoPath")
                return None, []

        flat = {}
        for l in layers:
            for k, v in l.items():
                flat.setdefault(k, v)
        flat.update({
            "TARGET_NAME": target_name,
            "PRODUCT_NAME": "$(TARGET_NAME)",
            "EXECUTABLE_NAME": "$(PRODUCT_NAME)",
            "DEVELOPMENT_LANGUAGE": dev_region or "en",
            "PRODUCT_BUNDLE_PACKAGE_TYPE": "XPC!" if extension else "APPL",
        })

        dropped = []
        for key in list(plist):
            v = plist[key]
            if not isinstance(v, str):
                continue
            nv = self.expand(v, [flat])
            if "$(" in nv:
                dropped.append(key)
                del plist[key]
            elif nv != v:
                plist[key] = nv
        xtool_owned = [k for k in ("CFBundleExecutable", "CFBundleIdentifier")
                       if k in plist]
        for k in xtool_owned:
            del plist[k]
        if xtool_owned or dropped:
            self.warn(f"{target_name} Info.plist dropped {sorted(xtool_owned + dropped)} "
                      "(the first two are set by xtool from the product name and "
                      "bundleID; the rest use build settings the generator cannot "
                      "resolve)")
        if extension and "NSExtension" not in plist:
            self.warn(f"{target_name} Info.plist has no NSExtension dictionary; "
                      "wrote an empty one - set NSExtensionPointIdentifier by hand")
            plist["NSExtension"] = {}
        return plist, dropped

    # -- top level ----------------------------------------------------------

    def extension_targets(self, app_target_id):
        """(id, obj) of the app-extension native targets the app embeds."""
        app = self.objs[app_target_id]
        out, seen = [], set()
        for dep_id in app.get("dependencies", []):
            dep = self.objs.get(dep_id, {})
            tid = dep.get("target")
            if not tid:
                proxy = self.objs.get(dep.get("targetProxy"), {})
                tid = proxy.get("remoteGlobalIDString")
            t = self.objs.get(tid, {})
            if t.get("isa") == "PBXNativeTarget" and \
                    t.get("productType", "").endswith("app-extension") and \
                    tid not in seen:
                seen.add(tid)
                out.append((tid, t))
        return out

    def run(self):
        target_id, self.target = self.pick_target()
        target = self.target
        name = target["name"]
        layers = self.target_merged(target)
        dev_region = self.project.get("developmentRegion")

        podfile = os.path.join(self.proj_dir, "Podfile")
        if os.path.isfile(podfile):
            self.warn("Podfile found; CocoaPods dependencies are not converted")

        others = [f"{o['name']} ({o.get('productType', '').rsplit('.', 1)[-1]})"
                  for _i, o in self.app_targets() if _i != target_id]
        if others:
            self.warn(f"skipping non-selected application targets: {', '.join(others)}")
        embedded = self.extension_targets(target_id)
        other_exts = [o["name"] for i, o in self.objs.items()
                      if o.get("isa") == "PBXNativeTarget"
                      and o.get("productType", "").endswith("app-extension")
                      and i not in {e for e, _ in embedded}]
        if other_exts:
            self.warn(f"app extensions not embedded in {name} are not converted: "
                      f"{', '.join(other_exts)}")

        if os.path.exists(os.path.join(self.out_dir, "Package.swift")) or \
                os.path.exists(os.path.join(self.out_dir, "xtool.yml")):
            raise SystemExit(f"error: {self.out_dir} already holds an adapter; "
                             "pass --out to write elsewhere")

        def write_plist(tname, plist, extension):
            if plist is None:
                return None
            fname = "Info.plist" if not extension else f"{tname}-Info.plist"
            with open(os.path.join(self.out_dir, fname), "wb") as f:
                plistlib.dump(plist, f)
            return fname

        def materialize(tname, symlinks):
            for link, dest in symlinks:
                lpath = os.path.join(self.out_dir, link)
                os.makedirs(os.path.dirname(lpath), exist_ok=True)
                if os.path.lexists(lpath):
                    continue
                os.symlink(os.path.relpath(os.path.join(self.proj_dir, dest),
                                           os.path.dirname(lpath)), lpath)

        symlink_count = 0
        symlinks, excludes, resources, swift_rels = self.plan_target_files(
            target_id, target)
        resources = self.dedupe_resources(resources)
        packages, products = self.plan_packages(target, swift_rels)
        app_products = list(products)
        app_swift = self.swift_settings(layers)
        os.makedirs(os.path.join(self.out_dir, "Sources", name), exist_ok=True)
        materialize(name, symlinks)
        symlink_count += len(symlinks)
        app_info, _ = self.target_infoplan(layers, name, dev_region, extension=False)
        app_info_path = write_plist(name, app_info, extension=False)
        ent = self.setting(layers, "CODE_SIGN_ENTITLEMENTS")
        if ent:
            self.warn(f"CODE_SIGN_ENTITLEMENTS {ent!r} not wired (xtool dev signs "
                      "without entitlements; ship.sh signs with its own)")

        extensions = []
        pkg_seen = set(packages)
        for ext_id, ext in embedded:
            ename = ext["name"]
            elayers = self.target_merged(ext)
            esym, eexc, eres, eswift = self.plan_target_files(ext_id, ext)
            if not eswift:
                self.warn(f"extension {ename} has no Swift sources; skipped")
                continue
            eres = self.dedupe_resources(eres)
            epkgs, eprods = self.plan_packages(ext, eswift)
            new_pkgs = [p for p in epkgs if p not in pkg_seen]
            pkg_seen.update(new_pkgs)
            packages += new_pkgs
            # Package declarations are shared across the manifest; product
            # dependencies are per target (the widget must name RSWeb itself
            # even when the app already depends on it).
            os.makedirs(os.path.join(self.out_dir, "Sources", ename), exist_ok=True)
            materialize(ename, esym)
            symlink_count += len(esym)
            eplist, _ = self.target_infoplan(elayers, ename, dev_region, extension=True)
            epath = write_plist(ename, eplist, extension=True)
            edt = self.setting(elayers, "IPHONEOS_DEPLOYMENT_TARGET")
            adt = self.setting(layers, "IPHONEOS_DEPLOYMENT_TARGET")
            if edt and adt and self.expand(edt, elayers) != self.expand(adt, layers):
                self.warn(f"extension {ename} deployment target {edt} differs from "
                          f"the app's {adt}; xtool applies one platform to the whole "
                          "package (the app's)")
            ent = self.setting(elayers, "CODE_SIGN_ENTITLEMENTS")
            if ent:
                self.warn(f"{ename}: CODE_SIGN_ENTITLEMENTS {ent!r} not wired "
                          "(xtool dev signs without entitlements; ship.sh signs "
                          "with its own)")
            extensions.append({
                "name": ename,
                "products": eprods,
                "excludes": eexc,
                "resources": eres,
                "swift": self.swift_settings(elayers),
                "bundleID": self.bundle_id(elayers),
                "infoPath": epath,
            })

        self.write_manifest(name, layers, packages, app_products,
                            excludes, resources, app_swift, extensions)
        bundle = self.bundle_id(layers)
        yml = "version: 1\n"
        yml += f"bundleID: {bundle}\n"
        yml += f"product: {name}\n"
        if app_info_path:
            yml += f"infoPath: {app_info_path}\n"
        if extensions:
            yml += "extensions:\n"
            for e in extensions:
                yml += f"  - product: {e['name']}\n"
                yml += f"    bundleID: {e['bundleID']}\n"
                yml += f"    infoPath: {e['infoPath']}\n"
        with open(os.path.join(self.out_dir, "xtool.yml"), "w") as f:
            f.write(yml)

        icon = self.setting(layers, "ASSETCATALOG_COMPILER_APPICON_NAME") or "AppIcon"
        # Icon Composer .icon: ASSETCATALOG_COMPILER_APPICON_NAME is the icon
        # *name* (no extension). The app target's primary asset is the
        # <name>.icon directory in either a classic Resources phase or a
        # synced group. Symlink it into the adapter root so ship.sh (and the
        # Linux actool) can render it; the project's own file is left alone.
        app_icon_linked = self.symlink_app_icon(target, layers)
        print(f"APP_ICON={icon}   # pass to ship.sh")
        for w in self.warnings:
            print(w, file=sys.stderr)
        print(f"wrote {self.out_dir} (Package.swift, xtool.yml, "
              f"{symlink_count} symlinks under Sources/, "
              f"{len(extensions)} extensions"
              f"{', app icon' if app_icon_linked else ''})")

    def primary_app_icon_name(self, layers):
        """Xcode convention: ASSETCATALOG_COMPILER_APPICON_NAME is the icon
        name without extension (e.g. 'AppIcon'). Used to recognise the
        app target's primary <name>.icon Icon Composer asset."""
        return self.setting(layers, "ASSETCATALOG_COMPILER_APPICON_NAME") or "AppIcon"

    def app_icon_relative_path(self, target, layers):
        """Project-relative path of the app target's primary Icon Composer
        asset, or None if not found. Searches the classic Resources phase and
        every synced group of the target."""
        name = f"{self.primary_app_icon_name(layers)}.icon"

        # Classic Resources phase.
        for _ref_id, p in self.phase_files(target, "PBXResourcesBuildPhase"):
            if os.path.basename(p) == name:
                return p
        # Synced groups.
        for gid in target.get("fileSystemSynchronizedGroups", []):
            g = self.objs.get(gid, {})
            base = self.synced_group_path(gid) or (g.get("path") or g.get("name"))
            if base:
                candidate = os.path.join(base, name)
                if os.path.exists(os.path.join(self.proj_dir, candidate)):
                    return candidate
        return None

    def symlink_app_icon(self, target, layers):
        name = f"{self.primary_app_icon_name(layers)}.icon"
        rel = self.app_icon_relative_path(target, layers)
        if not rel:
            return False
        src = os.path.join(self.proj_dir, rel)
        if not os.path.exists(src):
            return False
        link = os.path.join(self.out_dir, name)
        if not os.path.lexists(link):
            os.symlink(os.path.relpath(src, self.out_dir), link)
        return True

    def target_block(self, tname, deps, excludes, resources, swift):
        prod_lines = "\n".join(
            f"                .product(name: {sw_sy(n)}, package: {sw_sy(pk)}),"
            for n, pk in deps)
        txt = f"""        .target(
            name: {sw_sy(tname)},
            dependencies: [
{prod_lines}
            ],
"""
        if excludes:
            ex = ",\n".join(f"                {sw_sy(e)}" for e in excludes)
            txt += f"            exclude: [\n{ex},\n            ],\n"
        if resources:
            rs = "\n".join(f"                {k}({sw_sy(p)})," for k, p in resources)
            txt += f"            resources: [\n{rs}\n            ],\n"
        if swift:
            ss = ", ".join(swift)
            txt += f"            swiftSettings: [{ss}]\n"
        return txt + "        ),\n"

    def write_manifest(self, name, layers, packages, products,
                       excludes, resources, swift, extensions):
        plat = self.setting(layers, "IPHONEOS_DEPLOYMENT_TARGET") or "17.0"
        plat = re.sub(r"[^0-9.]", "", self.expand(plat, layers)) or "17.0"
        deps = (",\n".join(f"        {p}" for p in packages)) or "        // none"
        dev_region = self.project.get("developmentRegion")
        libs = [f"    .library(name: {sw_sy(name)}, targets: [{sw_sy(name)}])"]
        libs += [f"    .library(name: {sw_sy(e['name'])}, targets: [{sw_sy(e['name'])}])"
                 for e in extensions]
        libs_txt = ",\n".join(libs)
        blocks = self.target_block(name, products, excludes, resources, swift)
        for e in extensions:
            blocks += self.target_block(e["name"], e["products"], e["excludes"],
                                        e["resources"], e["swift"])
        txt = f"""// swift-tools-version: 6.2
// Generated by tools/xcodeproj2xtool.py from {os.path.basename(self.proj_path)}
// (target {name}). Regenerate after changing the Xcode project.
import PackageDescription

let package = Package(
    name: {sw_sy(name)},
"""
        if dev_region:
            txt += f"    defaultLocalization: {sw_sy(dev_region)},\n"
        txt += f"""    platforms: [.iOS({sw_sy(plat)})],
    products: [
{libs_txt},
    ],
    dependencies: [
{deps}
    ],
    targets: [
{blocks}    ]
)
"""
        with open(os.path.join(self.out_dir, "Package.swift"), "w") as f:
            f.write(txt)


# ---------------------------------------------------------------- self-test

SELF_TEST_PROJ = r"""// !$*UTF8*$!
{
	archiveVersion = 1;
	objectVersion = 54;
	objects = {

/* Begin PBXBuildFile section */
		EEEE0000000000000000000C /* App.swift in Sources */ = {isa = PBXBuildFile; fileRef = AAAA00000000000000000001 /* App.swift */; };
		EEEE0000000000000000000E /* Helper.swift in Sources */ = {isa = PBXBuildFile; fileRef = AAAA00000000000000000002 /* Helper.swift */; };
		EEEE0000000000000000000D /* Assets.xcassets in Resources */ = {isa = PBXBuildFile; fileRef = AAAA00000000000000000004 /* Assets.xcassets */; };
		EEEE0000000000000000000F /* Widget.swift in Sources */ = {isa = PBXBuildFile; fileRef = AAAA00000000000000000006 /* Widget.swift */; };
		EEEE00000000000000000010 /* DemoIcon.icon in Resources */ = {isa = PBXBuildFile; fileRef = AAAA00000000000000000008 /* DemoIcon.icon */; };
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		AAAA00000000000000000001 /* App.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = App.swift; sourceTree = "<group>"; };
		AAAA00000000000000000002 /* Helper.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = Helper.swift; sourceTree = "<group>"; };
		AAAA00000000000000000003 /* Unused.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = Unused.swift; sourceTree = "<group>"; };
		AAAA00000000000000000004 /* Assets.xcassets */ = {isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = Assets.xcassets; sourceTree = "<group>"; };
		AAAA00000000000000000005 /* appent.entitlements */ = {isa = PBXFileReference; lastKnownFileType = text.plist.entitlements; path = appent.entitlements; sourceTree = "<group>"; };
		AAAA00000000000000000006 /* Widget.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = Widget.swift; sourceTree = "<group>"; };
		AAAA00000000000000000007 /* Info.plist */ = {isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>"; };
		AAAA00000000000000000008 /* DemoIcon.icon */ = {isa = PBXFileReference; lastKnownFileType = folder.iconcomposer; path = DemoIcon.icon; sourceTree = "<group>"; };
		EEEE00000000000000000008 /* proj.xcconfig */ = {isa = PBXFileReference; lastKnownFileType = text.xcconfig; path = proj.xcconfig; sourceTree = "<group>"; };
/* End PBXFileReference section */

/* Begin PBXGroup section */
		BBBB00000000000000000001 /* main */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000001 /* src */,
				CCCC00000000000000000002 /* demo-widget */,
				CCCC00000000000000000003 /* shared */,
				AAAA00000000000000000008 /* DemoIcon.icon */,
				AAAA00000000000000000005 /* appent.entitlements */,
			);
			sourceTree = "<group>";
		};
		CCCC00000000000000000001 /* src */ = {
			isa = PBXGroup;
			children = (
				AAAA00000000000000000001 /* App.swift */,
				AAAA00000000000000000002 /* Helper.swift */,
				AAAA00000000000000000003 /* Unused.swift */,
				AAAA00000000000000000004 /* Assets.xcassets */,
			);
			path = src;
			sourceTree = "<group>";
		};
		CCCC00000000000000000002 /* demo-widget */ = {
			isa = PBXGroup;
			children = (
				AAAA00000000000000000006 /* Widget.swift */,
				AAAA00000000000000000007 /* Info.plist */,
			);
			path = demo-widget;
			sourceTree = "<group>";
		};
/* End PBXGroup section */

/* Begin PBXFileSystemSynchronizedRootGroup section */
		CCCC00000000000000000003 /* shared */ = {isa = PBXFileSystemSynchronizedRootGroup; exceptions = (CCCC00000000000000000004 /* PBXFileSystemSynchronizedBuildFileExceptionSet */, ); explicitFileTypes = {}; explicitFolders = (); path = shared; sourceTree = "<group>"; };
/* End PBXFileSystemSynchronizedRootGroup section */

/* Begin PBXFileSystemSynchronizedBuildFileExceptionSet section */
		CCCC00000000000000000004 /* PBXFileSystemSynchronizedBuildFileExceptionSet */ = {
			isa = PBXFileSystemSynchronizedBuildFileExceptionSet;
			membershipExceptions = (
				WidgetShared.swift,
			);
			target = DDDD0000000000000000000C /* DemoWidget */;
		};
/* End PBXFileSystemSynchronizedBuildFileExceptionSet section */

/* Begin PBXNativeTarget section */
		DDDD00000000000000000001 /* DemoApp */ = {
			isa = PBXNativeTarget;
			buildConfigurationList = EEEE00000000000000000001;
			buildPhases = (
				DDDD00000000000000000002 /* Sources */,
				DDDD00000000000000000003 /* Frameworks */,
				DDDD00000000000000000004 /* Resources */,
			);
			dependencies = (
				DDDD0000000000000000000B /* PBXTargetDependency */,
			);
			name = DemoApp;
			packageProductDependencies = (
				FFFF00000000000000000001 /* Logging */,
				FFFF00000000000000000002 /* Branchy */,
				FFFF00000000000000000003 /* DemoLib */,
			);
			productName = DemoApp;
			productType = "com.apple.product-type.application";
		};
		DDDD0000000000000000000C /* DemoWidget */ = {
			isa = PBXNativeTarget;
			buildConfigurationList = EEEE00000000000000000011;
			buildPhases = (
				DDDD0000000000000000000A /* Sources */,
			);
			dependencies = (
			);
			name = DemoWidget;
			productName = DemoWidget;
			productType = "com.apple.product-type.app-extension";
		};
		DDDD0000000000000000000B /* PBXTargetDependency */ = {
			isa = PBXTargetDependency;
			target = DDDD0000000000000000000C /* DemoWidget */;
		};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		EEEE00000000000000000009 /* Project object */ = {
			isa = PBXProject;
			attributes = {
			};
			buildConfigurationList = EEEE00000000000000000007;
			developmentRegion = en;
			mainGroup = BBBB00000000000000000001;
			packageReferences = (
				EEEE0000000000000000000A /* XCRemoteSwiftPackageReference "swift-log" */,
				EEEE0000000000000000000B /* XCRemoteSwiftPackageReference "Branchy" */,
				EEEE00000000000000000013 /* XCLocalSwiftPackageReference "DemoPkg" */,
			);
			targets = (
				DDDD00000000000000000001 /* DemoApp */,
				DDDD0000000000000000000C /* DemoWidget */,
			);
		};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		DDDD00000000000000000004 /* Resources */ = {
			isa = PBXResourcesBuildPhase;
			files = (
				EEEE0000000000000000000D /* Assets.xcassets in Resources */,
				EEEE00000000000000000010 /* DemoIcon.icon in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		DDDD0000000000000000000A /* Sources */ = {
			isa = PBXSourcesBuildPhase;
			files = (
				EEEE0000000000000000000F /* Widget.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
		DDDD00000000000000000002 /* Sources */ = {
			isa = PBXSourcesBuildPhase;
			files = (
				EEEE0000000000000000000C /* App.swift in Sources */,
				EEEE0000000000000000000E /* Helper.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		EEEE00000000000000000003 /* Release */ = {
			isa = XCBuildConfiguration;
			baseConfigurationReference = EEEE00000000000000000008 /* proj.xcconfig */;
			buildSettings = {
				SWIFT_VERSION = "";
			};
			name = Release;
		};
		EEEE00000000000000000005 /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				ASSETCATALOG_COMPILER_APPICON_NAME = DemoIcon;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_KEY_CFBundleDisplayName = "Demo App";
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				"INFOPLIST_KEY_UIApplicationSceneManifest_Generation[sdk=iphoneos*]" = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft";
				IPHONEOS_DEPLOYMENT_TARGET = 16.4;
				PRODUCT_BUNDLE_IDENTIFIER = "$(BUNDLE_PREFIX).demo";
				SWIFT_APPROACHABLE_CONCURRENCY = YES;
				SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor;
				SWIFT_UPCOMING_FEATURE_CONCISE_MAGIC_FILE = YES;
				SWIFT_VERSION = 5.0;
			};
			name = Release;
		};
		EEEE00000000000000000012 /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = demo-widget/Info.plist;
				IPHONEOS_DEPLOYMENT_TARGET = 16.4;
				MARKETING_VERSION = 2026.10;
				PRODUCT_BUNDLE_IDENTIFIER = "$(BUNDLE_PREFIX).demo.widget";
				SWIFT_VERSION = 5.0;
			};
			name = Release;
		};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		EEEE00000000000000000011 = {
			isa = XCConfigurationList;
			buildConfigurations = (
				EEEE00000000000000000012 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		EEEE00000000000000000001 = {
			isa = XCConfigurationList;
			buildConfigurations = (
				EEEE00000000000000000005 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		EEEE00000000000000000007 = {
			isa = XCConfigurationList;
			buildConfigurations = (
				EEEE00000000000000000003 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
/* End XCConfigurationList section */

/* Begin XCRemoteSwiftPackageReference section */
		EEEE0000000000000000000A /* XCRemoteSwiftPackageReference "swift-log" */ = {
			isa = XCRemoteSwiftPackageReference;
			repositoryURL = "https://github.com/apple/swift-log.git";
			requirement = {
				kind = upToNextMinorVersion;
				minimumVersion = 1.5.3;
			};
		};
		EEEE0000000000000000000B /* XCRemoteSwiftPackageReference "Branchy" */ = {
			isa = XCRemoteSwiftPackageReference;
			repositoryURL = "https://example.com/branchy.git";
			requirement = {
				branch = main;
				kind = branch;
			};
		};
/* End XCRemoteSwiftPackageReference section */

/* Begin XCLocalSwiftPackageReference section */
		EEEE00000000000000000013 /* XCLocalSwiftPackageReference "DemoPkg" */ = {
			isa = XCLocalSwiftPackageReference;
			relativePath = DemoPkg;
		};
/* End XCLocalSwiftPackageReference section */

/* Begin XCSwiftPackageProductDependency section */
		FFFF00000000000000000001 /* Logging */ = {
			isa = XCSwiftPackageProductDependency;
			package = EEEE0000000000000000000A /* XCRemoteSwiftPackageReference "swift-log" */;
			productName = Logging;
		};
		FFFF00000000000000000002 /* Branchy */ = {
			isa = XCSwiftPackageProductDependency;
			package = EEEE0000000000000000000B /* XCRemoteSwiftPackageReference "Branchy" */;
			productName = Branchy;
		};
		FFFF00000000000000000003 /* DemoLib */ = {
			isa = XCSwiftPackageProductDependency;
			package = EEEE00000000000000000013 /* XCLocalSwiftPackageReference "DemoPkg" */;
			productName = DemoLib;
		};
/* End XCSwiftPackageProductDependency section */
	};
	rootObject = EEEE00000000000000000009 /* Project object */;
}
"""


def self_test():
    import shutil
    import tempfile
    root = tempfile.mkdtemp(prefix="xcodeproj2xtool-test-")
    try:
        _self_test(root)
        _self_test_collision(root)
    except BaseException:
        # weakref.finalize would delete a TemporaryDirectory at exit even when
        # referenced, so keep the dir by simply not removing it
        print(f"self-test failed; scratch dir kept for inspection: {root}")
        raise
    shutil.rmtree(root)
    print("self-test passed")


def _self_test(root):
    proj = os.path.join(root, "DemoApp.xcodeproj")
    os.makedirs(os.path.join(proj, "project.xcworkspace", "xcshareddata",
                             "swiftpm"))
    os.makedirs(os.path.join(proj, "..", "src"))
    src = os.path.join(root, "src")
    open(os.path.join(src, "App.swift"), "w").write(
        "import Logging\nimport DemoLibInner\nimport Collections\nlet x = 1\n")
    open(os.path.join(src, "Helper.swift"), "w").write("let y = 2\n")
    open(os.path.join(src, "Unused.swift"), "w").write("let z = 3\n")
    os.makedirs(os.path.join(src, "Assets.xcassets"))
    open(os.path.join(root, "proj.xcconfig"), "w").write(
        "// comment\nBUNDLE_PREFIX = net.example\n")
    with open(os.path.join(proj, "project.xcworkspace", "xcshareddata",
                           "swiftpm", "Package.resolved"), "w") as f:
        json.dump({"version": 3, "pins": [{"identity": "branchy",
                   "state": {"revision": "abc123def456"}}]}, f)
    with open(os.path.join(proj, "project.pbxproj"), "w") as f:
        f.write(SELF_TEST_PROJ)

    out = os.path.join(root, "gen")
    # A local package the app explicitly depends on (product DemoLib) while
    # ALSO importing its inner target module (DemoLibInner) - the import
    # scan must not re-declare DemoLibInner as a product.
    pkgdir = os.path.join(root, "DemoPkg")
    os.makedirs(os.path.join(pkgdir, "Sources", "DemoLib"))
    os.makedirs(os.path.join(pkgdir, "Sources", "DemoLibInner"))
    with open(os.path.join(pkgdir, "Package.swift"), "w") as f:
        f.write(
            "// swift-tools-version: 5.9\n"
            "import PackageDescription\n"
            "let package = Package(\n"
            "    name: \"DemoPkg\",\n"
            "    products: [.library(name: \"DemoLib\", targets: [\"DemoLib\", \"DemoLibInner\"])],\n"
            "    dependencies: [.package(url: \"https://github.com/apple/swift-collections.git\", from: \"1.0.0\")],\n"
            "    targets: [\n"
            "        .target(name: \"DemoLib\"),\n"
            "        .target(name: \"DemoLibInner\", dependencies: [\"DemoLib\",\n"
            "            .product(name: \"Collections\", package: \"swift-collections\")]),\n"
            "    ]\n"
            ")\n")
    wdir = os.path.join(root, "demo-widget")
    os.makedirs(wdir)
    with open(os.path.join(wdir, "Widget.swift"), "w") as f:
        f.write("import WidgetKit\nimport SwiftUI\nimport DemoLib\n")
    # App's primary Icon Composer asset. ship.sh consumes the symlink.
    os.makedirs(os.path.join(root, "DemoIcon.icon"))
    # Synced folder owned by no target; an exception set adds one file of it
    # to DemoWidget (Xcode's non-owner membership semantics).
    os.makedirs(os.path.join(root, "shared"))
    for n in ("WidgetShared.swift", "NotShared.swift"):
        with open(os.path.join(root, "shared", n), "w") as f:
            f.write("let s = 1\n")
    with open(os.path.join(wdir, "Info.plist"), "wb") as f:
        plistlib.dump({
            "CFBundleExecutable": "$(EXECUTABLE_NAME)",
            "CFBundleShortVersionString": "$(MARKETING_VERSION)",
            "NSExtension": {"NSExtensionPointIdentifier":
                            "com.apple.widgetkit-extension"},
        }, f)
    gen = Generator(proj, out_dir=out)
    # capture warnings from the first run (we check the Icon Composer
    # handling against this buffer below)
    import io as _io
    err_buf = _io.StringIO()
    saved, sys.stderr = sys.stderr, err_buf
    try:
        gen.run()
    finally:
        sys.stderr = saved
    warnings_text = err_buf.getvalue()
    pkg = open(os.path.join(out, "Package.swift")).read()
    yml = open(os.path.join(out, "xtool.yml")).read()
    wpl = plistlib.load(open(os.path.join(out, "DemoWidget-Info.plist"), "rb"))
    checks = [
        ("tools-version", "// swift-tools-version: 6.2" in pkg),
        ("platform", '.iOS("16.4")' in pkg),
        ("upToNextMinor range", '"1.5.3"..<"1.6.0"' in pkg),
        ("branch requirement preserved",
         '.package(url: "https://example.com/branchy.git", branch: "main")' in pkg),
        ("branch requirement has no warning", "cannot build branch" not in warnings_text),
        ("library product", '.library(name: "DemoApp", targets: ["DemoApp"])' in pkg),
        ("product dep", '.product(name: "Logging", package: "swift-log")' in pkg),
        ("swift mode v5", ".swiftLanguageMode(.v5)" in pkg),
        ("defaultIsolation", ".defaultIsolation(MainActor.self)" in pkg),
        ("approachable concurrency as features", ".enableUpcomingFeature(\"NonisolatedNonsendingByDefault\")" in pkg),
        ("upcoming feature", '.enableUpcomingFeature("CONCISE_MAGIC_FILE")' in pkg),
        ("bare slash regex feature", '.enableUpcomingFeature("BareSlashRegexLiterals")' in pkg),
        ("source ancestor symlink", 'exclude' in pkg and '"src/Unused.swift"' in pkg),
        ("resource process", '.process("src/Assets.xcassets")' in pkg),
        ("bundleID expanded from xcconfig", "bundleID: net.example.demo" in yml),
        ("generated Info.plist", "infoPath: Info.plist" in yml),
        ("Info.plist content", plistlib.load(open(os.path.join(out, "Info.plist"),
                                                  "rb")).get("CFBundleDisplayName") == "Demo App"),
        ("UILaunchScreen", plistlib.load(open(os.path.join(out, "Info.plist"),
                                              "rb")).get("UILaunchScreen") == {}),
        ("orientations array", plistlib.load(open(os.path.join(out, "Info.plist"),
                                                  "rb")).get("UISupportedInterfaceOrientations") ==
         ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationLandscapeLeft"]),
        ("APP_ICON printed to stdout", True),  # covered by run() call below
        ("xtool product key", "product: DemoApp\n" in yml),
        ("extension yml entry", "  - product: DemoWidget\n" in yml),
        ("extension bundleID", "bundleID: net.example.demo.widget" in yml),
        ("extension infoPath", "infoPath: DemoWidget-Info.plist" in yml),
        ("extension library product",
         '.library(name: "DemoWidget", targets: ["DemoWidget"])' in pkg),
        ("extension target in manifest", 'name: "DemoWidget"' in pkg),
        ("extension plist placeholder substituted",
         wpl.get("CFBundleShortVersionString") == "2026.10"),
        ("extension NSExtension kept",
         wpl.get("NSExtension", {}).get("NSExtensionPointIdentifier") ==
         "com.apple.widgetkit-extension"),
        ("xtool-owned plist keys dropped",
         "CFBundleExecutable" not in wpl and "CFBundleIdentifier" not in wpl),
        ("app icon symlinked into adapter",
         os.path.islink(os.path.join(out, "DemoIcon.icon"))
         and os.path.realpath(os.path.join(out, "DemoIcon.icon"))
             == os.path.realpath(os.path.join(root, "DemoIcon.icon"))),
        ("app icon not in target resources",
         "DemoIcon.icon" not in pkg),
        ("app icon no Icon Composer warning",
         "Icon Composer asset 'DemoIcon.icon'" not in warnings_text),
        ("import scan keeps explicit local product",
         '.product(name: "DemoLib", package: "DemoLib")' in pkg),
        ("import scan skips inner target of declared product",
         '.product(name: "DemoLibInner"' not in pkg),
        ("import scan skips remote product of closure target",
         "Collections" not in pkg),
        ("extension keeps its own dep on a product the app also uses",
         '.product(name: "DemoLib", package: "DemoLib")'
         in pkg[pkg.find('name: "DemoWidget",', pkg.find("\n    targets: [\n")):]),
        ("non-owner exception set adds the file to the extension",
         os.path.islink(os.path.join(out, "Sources", "DemoWidget", "shared",
                                     "WidgetShared.swift"))),
        ("non-owner exception set adds only the listed file",
         not os.path.lexists(os.path.join(out, "Sources", "DemoWidget", "shared",
                                          "NotShared.swift"))
         and not os.path.lexists(os.path.join(out, "Sources", "DemoApp", "shared"))),
    ]
    # symlink sanity
    assert os.path.islink(os.path.join(out, "Sources", "DemoApp", "src"))
    # APP_ICON line goes to stdout; re-run capture
    import io
    import contextlib
    gen2 = Generator(proj, out_dir=os.path.join(root, "gen2"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        gen2.run()
    assert "APP_ICON=DemoIcon" in buf.getvalue(), buf.getvalue()
    # tools-version and platform parse as a manifest would
    assert "target(" in pkg
    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS " if ok else "FAIL ") + n)
    if failed:
        print(open(os.path.join(out, "Package.swift")).read())
        raise SystemExit(f"self-test FAILED: {', '.join(failed)}")
    print(f"self-test passed ({len(checks)} checks)")


COLLISION_PROJ = r"""// !$*UTF8*$!
{
	archiveVersion = 1;
	objectVersion = 54;
	objects = {

/* Begin PBXBuildFile section */
		CCCC00000000000000000A01 /* BundleObj.swift in Sources */ = {isa = PBXBuildFile; fileRef = CCCC00000000000000000B01 /* BundleObj.swift */; };
		CCCC00000000000000000A02 /* BUNDLE.bundle in Resources */ = {isa = PBXBuildFile; fileRef = CCCC00000000000000000B02 /* BUNDLE.bundle */; };
		CCCC00000000000000000A03 /* Main.storyboard in Resources */ = {isa = PBXBuildFile; fileRef = CCCC00000000000000000B03 /* Main.storyboard */; };
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		CCCC00000000000000000B01 /* BundleObj.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = BundleObj.swift; sourceTree = "<group>"; };
		CCCC00000000000000000B02 /* BUNDLE.bundle */ = {isa = PBXFileReference; lastKnownFileType = wrapper.cfbundle; path = BUNDLE.bundle; sourceTree = "<group>"; };
		CCCC00000000000000000B03 /* Main.storyboard */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = file.storyboard; path = Main.storyboard; sourceTree = "<group>"; };
		CCCC00000000000000000B04 /* App-Info.plist */ = {isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = App-Info.plist; sourceTree = "<group>"; };
/* End PBXFileReference section */

/* Begin PBXGroup section */
		CCCC00000000000000000C01 /* main */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000C02 /* support */,
			);
			sourceTree = "<group>";
		};
		CCCC00000000000000000C02 /* support */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000C03 /* Extra */,
			);
			path = support;
			sourceTree = "<group>";
		};
		CCCC00000000000000000C03 /* Extra */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000B01 /* BundleObj.swift */,
				CCCC00000000000000000B02 /* BUNDLE.bundle */,
				CCCC00000000000000000C04 /* Base.lproj */,
				CCCC00000000000000000B04 /* App-Info.plist */,
			);
			path = Extra;
			sourceTree = "<group>";
		};
		CCCC00000000000000000C04 /* Base.lproj */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000B03 /* Main.storyboard */,
			);
			path = Base.lproj;
			sourceTree = "<group>";
		};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		CCCC00000000000000000D01 /* CollApp */ = {
			isa = PBXNativeTarget;
			buildConfigurationList = CCCC00000000000000000E01;
			buildPhases = (
				CCCC00000000000000000D02 /* Sources */,
				CCCC00000000000000000D03 /* Frameworks */,
				CCCC00000000000000000D04 /* Resources */,
			);
			dependencies = ();
			name = CollApp;
			productName = CollApp;
			productType = "com.apple.product-type.application";
		};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		CCCC00000000000000000E02 /* Project object */ = {
			isa = PBXProject;
			attributes = {
			};
			buildConfigurationList = CCCC00000000000000000E03;
			developmentRegion = en;
			mainGroup = CCCC00000000000000000C01;
			targets = (
				CCCC00000000000000000D01 /* CollApp */,
			);
		};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		CCCC00000000000000000D04 /* Resources */ = {
			isa = PBXResourcesBuildPhase;
			files = (
				CCCC00000000000000000A02 /* BUNDLE.bundle in Resources */,
				CCCC00000000000000000A03 /* Main.storyboard in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		CCCC00000000000000000D02 /* Sources */ = {
			isa = PBXSourcesBuildPhase;
			files = (
				CCCC00000000000000000A01 /* BundleObj.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		CCCC00000000000000000E04 /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = "support/Extra/App-Info.plist";
				IPHONEOS_DEPLOYMENT_TARGET = 16.4;
				PRODUCT_BUNDLE_IDENTIFIER = net.example.collision;
				SWIFT_VERSION = 5.0;
			};
			name = Release;
		};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		CCCC00000000000000000E01 = {
			isa = XCConfigurationList;
			buildConfigurations = (
				CCCC00000000000000000E04 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		CCCC00000000000000000E03 = {
			isa = XCConfigurationList;
			buildConfigurations = (
				CCCC00000000000000000E04 /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
/* End XCConfigurationList section */
	};
	rootObject = CCCC00000000000000000E02 /* Project object */;
}
"""


def _self_test_collision(root):
    """Reproduce the Mastodon collision: a classic subtree whose group path
    spans several components ("support/Extra"), so basename(src_anc) ("Extra")
    is NOT the first component of the emitted project-relative resource path
    ("support/Extra/BUNDLE.bundle"). The src_anc symlink exposes the subtree at
    target-relative "Extra/..." — every emitted resource must resolve through
    it, directory resources included, and auto-scanned storyboards must be
    excluded with one naming warning."""
    proj = os.path.join(root, "CollApp.xcodeproj")
    os.makedirs(proj)
    extra = os.path.join(root, "support", "Extra")
    os.makedirs(os.path.join(extra, "BUNDLE.bundle"))
    os.makedirs(os.path.join(extra, "Base.lproj"))
    with open(os.path.join(extra, "BundleObj.swift"), "w") as f:
        f.write("let coll = 1\n")
    with open(os.path.join(extra, "BUNDLE.bundle", "Localizable.strings"), "w") as f:
        f.write('"k" = "v";\n')
    with open(os.path.join(extra, "Base.lproj", "Main.storyboard"), "w") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
    with open(os.path.join(extra, "App-Info.plist"), "wb") as f:
        plistlib.dump({"CFBundleDisplayName": "Coll",
                       "UILaunchStoryboardName": "Main"}, f)
    with open(os.path.join(proj, "project.pbxproj"), "w") as f:
        f.write(COLLISION_PROJ)

    out = os.path.join(root, "gen-coll")
    gen = Generator(proj, out_dir=out)
    import io as _io
    err_buf = _io.StringIO()
    saved, sys.stderr = sys.stderr, err_buf
    try:
        gen.run()
    finally:
        sys.stderr = saved
    warnings_text = err_buf.getvalue()
    pkg = open(os.path.join(out, "Package.swift")).read()

    # Every emitted resource path must exist under Sources/CollApp: this is
    # the assertion the pre-fix generator failed ("support/Extra/BUNDLE.bundle"
    # was emitted but never materialized, so packaging died at CpResource).
    app_id = next(k for k, v in gen.objs.items()
                  if isinstance(v, dict) and v.get("name") == "CollApp")
    sym, exc, res, swift = gen.plan_target_files(app_id, gen.objs[app_id])
    checks = [
        ("bundle resource emitted anc-relative",
         '.process("Extra/BUNDLE.bundle")' in pkg),
        ("old project-relative path gone",
         "support/Extra/BUNDLE.bundle" not in pkg),
        ("storyboard excluded farm-relative",
         '"Extra/Base.lproj/Main.storyboard"' in pkg),
        ("one IB warning naming the file",
         "1 Interface Builder resource(s) excluded" in warnings_text
         and "support/Extra/Base.lproj/Main.storyboard" in warnings_text),
        ("Info.plist launch storyboard warning",
         "Info.plist references excluded storyboard 'Main.storyboard'"
         in warnings_text),
    ] + [("resource resolves: " + rp, ok) for (kind, rp), ok in
         [(r, os.path.exists(os.path.join(out, "Sources", "CollApp", r[1])))
          for r in res]]
    failed = [n for n, ok in checks if not ok]
    if failed:
        print(pkg)
        raise SystemExit("collision self-test FAILED: " + "; ".join(failed))
    print("collision self-test passed "
          f"({len(checks)} checks, {len(res)} resources, {len(exc)} excludes)")


def main():
    ap = argparse.ArgumentParser(
        description="Generate an xtool adapter package from an Xcode project.")
    ap.add_argument("project", nargs="?", help="path/to/App.xcodeproj")
    ap.add_argument("--target", help="application target name when the project "
                                     "has several")
    ap.add_argument("--out", help="output directory "
                                  "(default: <project root>/omarchy-xtool)")
    ap.add_argument("--self-test", action="store_true",
                    help="run the built-in round-trip check on a synthetic "
                         "classic-groups project")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.project:
        ap.error("project path required (or --self-test)")
    if not args.project.endswith(".xcodeproj") or \
            not os.path.isfile(os.path.join(args.project, "project.pbxproj")):
        ap.error(f"{args.project} is not an .xcodeproj directory")
    Generator(args.project, args.target, args.out).run()


if __name__ == "__main__":
    main()
