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
silent: app extensions/widgets, CocoaPods, ObjC sources, run-script phases,
Icon Composer .icon assets, unmapped build settings.
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
                        p = self.resolved_ref_path(c, parents)
                        if p:
                            out.append((c, p))
                    continue
                p = self.resolved_ref_path(ref, parents)
                if p:
                    out.append((ref, p))
        return out

    # -- synced groups -----------------------------------------------------

    def synced_group_plan(self, group_id, target_id, infoplist_rel):
        """Returns (swift_count, resources, excludes) for one synced root group."""
        g = self.objs[group_id]
        gpath = g.get("path") or g.get("name")
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
            rev = revs.get(ident)
            if rev:
                self.warn(f"branch requirement for {url} emitted as revision {rev[:12]} "
                          "(xtool 1.20.1 cannot build branch: requirements, FINDINGS 24.1)")
                return f"revision: {sw_sy(rev)}"
            self.warn(f"branch requirement for {url} kept as branch: {req.get('branch')!r}; "
                      "xtool dev build fails on branch requirements - pin a revision from "
                      f"{self.proj_path}/project.xcworkspace/xcshareddata/swiftpm/Package.resolved")
            return f"branch: {sw_sy(req.get('branch', ''))}"
        if kind == "revision":
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
        return None

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
            for m in re.finditer(r'branch:\s*"([^"]+)"', text):
                self.warn(f"local package {rp!r} pins a dependency on branch {m.group(1)!r}; "
                          "xtool 1.20.1 cannot build branch requirements - point it at a "
                          "local checkout (see compat/icecubes/setup.sh)")
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
        ipf = self.setting(layers, "INFOPLIST_FILE")
        if ipf:
            infoplist_rel = os.path.normpath(ipf)

        for gid in target.get("fileSystemSynchronizedGroups", []):
            g = self.objs.get(gid, {})
            gpath = g.get("path") or g.get("name")
            n_swift, res, exc = self.synced_group_plan(gid, target_id, infoplist_rel)
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

        src_files = self.phase_files(target, "PBXSourcesBuildPhase")
        res_files = self.phase_files(target, "PBXResourcesBuildPhase")
        src_anc = None
        if src_files:
            members = []
            for ref_id, p in src_files:
                ext = os.path.splitext(p)[1].lower()
                if ext == ".swift":
                    members.append(p)
                    swift_rels.append(p)
                elif ext in OBJC_EXTS:
                    objc.append(p)
                else:
                    self.warn(f"source file {p!r} is neither Swift nor ObjC; skipped")
            if members:
                anc = os.path.dirname(os.path.commonprefix(
                    [m + "/" for m in members])).rstrip("/")
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

        for ref_id, p in res_files:
            if os.path.splitext(p)[1].lower() in IB_EXTS:
                self.warn(f"{p!r} excluded - Linux has no ibtool to compile "
                          "Interface Builder sources")
                continue
            if p.endswith(".icon"):
                self.warn(f"Icon Composer asset {p!r} excluded (Linux actool cannot "
                          "compile it)")
                continue
            if src_anc and (p == src_anc or p.startswith(src_anc + "/")):
                pj = os.path.join(self.proj_dir, p)
                kind = ".process" if (
                    os.path.splitext(p)[1].lower() in PROCESSABLE
                    or (os.path.isdir(pj) and dir_resource_kind(pj) == ".process")
                ) else ".copy"
                resources.append((kind, p))
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
        return symlinks, sorted(set(excludes)), resources, swift_rels

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
        for base, dirs, files in os.walk(self.proj_dir):
            if base.count(os.sep) - root_depth >= 3:
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
        for dep in target_deps:
            name = dep.get("productName")
            if not name or name in seen_prod:
                continue
            seen_prod.add(name)
            pkg_id = dep.get("package")
            if pkg_id in refs:
                req = self.requirement(refs[pkg_id], revs)
                if req:
                    url = refs[pkg_id]["repositoryURL"]
                    if url not in seen_pkg:
                        seen_pkg[url] = True
                        packages.append(f'.package(url: {sw_sy(url)}, {req})')
                    products.append((name, package_label(url)))
            else:
                rp = self.find_local_package(name)
                if rp is None:
                    if pkg_id in local_refs:
                        rp = local_refs[pkg_id].get("relativePath")
                    if rp is None:
                        self.warn(f"local package for product {name!r} not found; skipped")
                        continue
                if rp not in decl_local:
                    decl_local[rp] = True
                    local_paths.append(rp)
                    packages.append(f'.package(name: {sw_sy(name)}, '
                                    f'path: {sw_sy(self.path_from_out(rp))})')
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
        extra_pkgs, extra_prods = [], []
        for mod in sorted(imported):
            if mod in seen_prod or mod == target["name"]:
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

    def infoplan(self, layers, out_dir):
        """Returns xtool.yml infoPath, possibly writing a generated Info.plist."""
        ipf = self.setting(layers, "INFOPLIST_FILE")
        if ipf and os.path.isfile(os.path.join(self.proj_dir, ipf)):
            return os.path.relpath(os.path.join(self.proj_dir, ipf), out_dir)
        if ipf:
            self.warn(f"INFOPLIST_FILE {ipf!r} does not exist")
        if self.setting(layers, "GENERATE_INFOPLIST_FILE") != "YES":
            self.warn("no Info.plist file and GENERATE_INFOPLIST_FILE != YES; "
                      "xtool.yml gets no infoPath")
            return None
        plist = {}
        for l in layers:
            for k, v in l.items():
                if not k.startswith("INFOPLIST_KEY_") or "[sdk=" in k:
                    continue
                key = k[len("INFOPLIST_KEY_"):]
                v = self.expand(v, layers)
                if key.startswith("UISupportedInterfaceOrientations"):
                    name = "UISupportedInterfaceOrientations~ipad" if \
                        key.endswith("_iPad") else "UISupportedInterfaceOrientations"
                    plist[name] = v.split()
                elif key == "UILaunchScreen_Generation" and v == "YES":
                    plist["UILaunchScreen"] = {}
                else:
                    plist[key] = v
        plist.setdefault("CFBundleDisplayName",
                         plist.get("CFBundleName", self.target["name"]))
        path = os.path.join(out_dir, "Info.plist")
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        self.warn("wrote a minimal Info.plist from INFOPLIST_KEY_* settings; "
                  "review it before shipping")
        return "Info.plist"

    # -- top level ----------------------------------------------------------

    def run(self):
        target_id, self.target = self.pick_target()
        target = self.target
        name = target["name"]
        layers = self.target_merged(target)

        podfile = os.path.join(self.proj_dir, "Podfile")
        if os.path.isfile(podfile):
            self.warn("Podfile found; CocoaPods dependencies are not converted")

        others = [f"{o['name']} ({o.get('productType', '').rsplit('.', 1)[-1]})"
                  for _i, o in self.app_targets() if _i != target_id]
        if others:
            self.warn(f"skipping non-selected application targets: {', '.join(others)}")
        exts = [o["name"] for _i, o in self.objs.items()
                if o.get("isa") == "PBXNativeTarget"
                and o.get("productType", "").endswith("app-extension")]
        if exts:
            self.warn(f"app extensions are not converted and stay unbuilt: "
                      f"{', '.join(exts)}")

        if os.path.exists(os.path.join(self.out_dir, "Package.swift")) or \
                os.path.exists(os.path.join(self.out_dir, "xtool.yml")):
            raise SystemExit(f"error: {self.out_dir} already holds an adapter; "
                             "pass --out to write elsewhere")

        symlinks, excludes, resources, swift_rels = self.plan_target_files(
            target_id, target)
        resources = self.dedupe_resources(resources)
        packages, products = self.plan_packages(target, swift_rels)

        os.makedirs(os.path.join(self.out_dir, "Sources", name), exist_ok=True)
        for link, dest in symlinks:
            lpath = os.path.join(self.out_dir, link)
            os.makedirs(os.path.dirname(lpath), exist_ok=True)
            if os.path.lexists(lpath):
                continue
            os.symlink(os.path.relpath(os.path.join(self.proj_dir, dest),
                                       os.path.dirname(lpath)), lpath)

        self.write_manifest(name, layers, packages, products,
                            excludes, resources)
        bundle = self.bundle_id(layers)
        info = self.infoplan(layers, self.out_dir)
        yml = "version: 1\n"
        yml += f"bundleID: {bundle}\n"
        if info:
            yml += f"infoPath: {info}\n"
        with open(os.path.join(self.out_dir, "xtool.yml"), "w") as f:
            f.write(yml)

        icon = self.setting(layers, "ASSETCATALOG_COMPILER_APPICON_NAME") or "AppIcon"
        print(f"APP_ICON={icon}   # pass to ship.sh")
        for w in self.warnings:
            print(w, file=sys.stderr)
        print(f"wrote {self.out_dir} (Package.swift, xtool.yml, "
              f"{len(symlinks)} symlinks under Sources/{name})")

    def write_manifest(self, name, layers, packages, products,
                       excludes, resources):
        plat = self.setting(layers, "IPHONEOS_DEPLOYMENT_TARGET") or "17.0"
        plat = re.sub(r"[^0-9.]", "", self.expand(plat, layers)) or "17.0"
        prod_lines = "\n".join(
            f"                .product(name: {sw_sy(n)}, package: {sw_sy(pk)}),"
            for n, pk in products)
        deps = (",\n".join(f"        {p}" for p in packages)) or "        // none"
        dev_region = self.project.get("developmentRegion")
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
    products: [.library(name: {sw_sy(name)}, targets: [{sw_sy(name)}])],
    dependencies: [
{deps}
    ],
    targets: [
        .target(
            name: {sw_sy(name)},
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
        sw = self.swift_settings(layers)
        if sw:
            ss = ", ".join(sw)
            txt += f"            swiftSettings: [{ss}]\n"
        txt += """        ),
    ]
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
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		AAAA00000000000000000001 /* App.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = App.swift; sourceTree = "<group>"; };
		AAAA00000000000000000002 /* Helper.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = Helper.swift; sourceTree = "<group>"; };
		AAAA00000000000000000003 /* Unused.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = Unused.swift; sourceTree = "<group>"; };
		AAAA00000000000000000004 /* Assets.xcassets */ = {isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = Assets.xcassets; sourceTree = "<group>"; };
		AAAA00000000000000000005 /* appent.entitlements */ = {isa = PBXFileReference; lastKnownFileType = text.plist.entitlements; path = appent.entitlements; sourceTree = "<group>"; };
		EEEE00000000000000000008 /* proj.xcconfig */ = {isa = PBXFileReference; lastKnownFileType = text.xcconfig; path = proj.xcconfig; sourceTree = "<group>"; };
/* End PBXFileReference section */

/* Begin PBXGroup section */
		BBBB00000000000000000001 /* main */ = {
			isa = PBXGroup;
			children = (
				CCCC00000000000000000001 /* src */,
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
/* End PBXGroup section */

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
			);
			name = DemoApp;
			packageProductDependencies = (
				FFFF00000000000000000001 /* Logging */,
				FFFF00000000000000000002 /* Branchy */,
			);
			productName = DemoApp;
			productType = "com.apple.product-type.application";
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
			);
			targets = (
				DDDD00000000000000000001 /* DemoApp */,
			);
		};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		DDDD00000000000000000004 /* Resources */ = {
			isa = PBXResourcesBuildPhase;
			files = (
				EEEE0000000000000000000D /* Assets.xcassets in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
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
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
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
/* End XCSwiftPackageProductDependency section */
	};
	rootObject = EEEE00000000000000000009 /* Project object */;
}
"""


def self_test():
    import tempfile
    root = tempfile.mkdtemp(prefix="xcodeproj2xtool-test-")
    proj = os.path.join(root, "DemoApp.xcodeproj")
    os.makedirs(os.path.join(proj, "project.xcworkspace", "xcshareddata",
                             "swiftpm"))
    os.makedirs(os.path.join(proj, "..", "src"))
    src = os.path.join(root, "src")
    open(os.path.join(src, "App.swift"), "w").write(
        "import Logging\nlet x = 1\n")
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
    gen = Generator(proj, out_dir=out)
    # silence stderr for the run
    saved, sys.stderr = sys.stderr, open(os.devnull, "w")
    try:
        gen.run()
    finally:
        sys.stderr = saved
    pkg = open(os.path.join(out, "Package.swift")).read()
    yml = open(os.path.join(out, "xtool.yml")).read()
    checks = [
        ("tools-version", "// swift-tools-version: 6.2" in pkg),
        ("platform", '.iOS("16.4")' in pkg),
        ("upToNextMinor range", '"1.5.3"..<"1.6.0"' in pkg),
        ("branch pinned to revision from Package.resolved",
         '.package(url: "https://example.com/branchy.git", revision: "abc123def456")' in pkg),
        ("library product", '.library(name: "DemoApp", targets: ["DemoApp"])' in pkg),
        ("product dep", '.product(name: "Logging", package: "swift-log")' in pkg),
        ("swift mode v5", ".swiftLanguageMode(.v5)" in pkg),
        ("defaultIsolation", ".defaultIsolation(MainActor.self)" in pkg),
        ("approachable concurrency as features", ".enableUpcomingFeature(\"NonisolatedNonsendingByDefault\")" in pkg),
        ("upcoming feature", '.enableUpcomingFeature("CONCISE_MAGIC_FILE")' in pkg),
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
    print("self-test passed "
          f"({len(checks)} checks, scratch dir {root})")


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
