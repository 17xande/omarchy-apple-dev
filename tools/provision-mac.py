#!/usr/bin/env python3
"""Developer ID provisioning for ship-mac.sh: enable the capabilities a bundle
claims, create a MAC_APP_DIRECT profile per bundle id, write build/provision/.

Run inside the adapter package directory (xtool.yml + Info.plist present).

  provision-mac.py [APP_ENTITLEMENTS]

The app profile goes to build/provision/app.provisionprofile; each xtool.yml
extension gets build/provision/<product>.provisionprofile, the names ship-mac.sh
embeds. The certificate comes from DEVELOPER_ID_CERT_ID, else
$DEVELOPER_ID_DIR/certificate-id (the dir ship-mac.sh signs with). Capabilities
derive from the entitlements files, never a hardcoded list: ICLOUD for
icloud-services, PUSH for aps-environment, APP_GROUPS for application-groups.
Apple's public API cannot attach specific App Group or iCloud container ids, so
after creating a profile we compare its granted Entitlements with the claimed
ones and print exactly what lacks profile backing (ship without those keys).
"""
import base64
import json
import os
import plistlib
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import asc  # noqa: E402


def yml_entries():
    """(product, bundle_id, info_path) for the app then each extension."""
    rows, in_ext = [], False
    for line in Path("xtool.yml").read_text(encoding="utf-8").splitlines():
        if re.match(r"\s*extensions:", line):
            in_ext = True
            continue
        m = re.match(r"\s*-\s*product:\s*(.+?)\s*$", line)
        if m and in_ext:
            rows.append([m.group(1), "", ""])
            continue
        m = re.match(r"\s*(bundleID|infoPath|product):\s*(.+?)\s*$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if not in_ext:  # the app header: bundleID, product, infoPath in any order
            if key == "bundleID" and not rows:
                rows.append(["", val, ""])
            elif rows:
                rows[0][0 if key == "product" else 2] = val
        elif rows:
            rows[-1][1 if key == "bundleID" else 2] = val
    return [tuple(r) for r in rows if r[1]]


def plist_value(path, key):
    try:
        with open(path, "rb") as f:
            return plistlib.load(f).get(key)
    except Exception:
        return None


def expand(ent_path):
    """Entitlements text with $(VAR)s expanded from the adapter's Info.plist."""
    vals = {}
    for name, key in (("APP_GROUP_ID", "AppGroup"), ("ORGANIZATION_IDENTIFIER", "OrganizationIdentifier")):
        vals[name] = plist_value("Info.plist", key) or ""
    return re.sub(r"\$\((\w+)\)", lambda m: vals.get(m.group(1), ""),
                  Path(ent_path).read_text(encoding="utf-8"))


def cert_id():
    cid = os.environ.get("DEVELOPER_ID_CERT_ID")
    if cid:
        return cid
    d = Path(os.environ.get("DEVELOPER_ID_DIR", Path.home() / ".config/omarchy-apple-dev/developer-id"))
    return (d / "certificate-id").read_text().strip()


def bundle_id(identifier):
    found = [b for b in asc.call("GET", f"/v1/bundleIds?filter[identifier]={identifier}&limit=200")["data"]
             if b["attributes"]["identifier"] == identifier]
    if found:
        return found[0]["id"]
    print(f"registering bundle id {identifier} (MAC_OS)")
    return asc.call("POST", "/v1/bundleIds", {"data": {"type": "bundleIds", "attributes": {
        "identifier": identifier, "name": identifier.replace(".", " "), "platform": "MAC_OS"}}})["data"]["id"]


def enable_capability(bid, kind, ident):
    existing = asc.call("GET", f"/v1/bundleIds/{bid}/bundleIdCapabilities")["data"]
    if any(c.get("attributes", {}).get("capabilityType") == kind for c in existing):
        print(f"{kind} already enabled for {ident}")
        return
    bodies = [{"data": {
        "type": "bundleIdCapabilities",
        "attributes": {"capabilityType": kind},
        "relationships": {"bundleId": asc.rel("bundleIds", bid)},
    }}]
    if kind == "ICLOUD":  # bare create is refused: CloudkitVersion 'null'
        bodies.insert(0, {"data": {
            "type": "bundleIdCapabilities",
            "attributes": {"capabilityType": kind, "settings": [
                {"key": "ICLOUD_VERSION", "options": [{"key": "XCODE_6"}]},
            ]},
            "relationships": {"bundleId": asc.rel("bundleIds", bid)},
        }})
    for body in bodies:
        try:
            asc.call("POST", "/v1/bundleIdCapabilities", body)
            print(f"enabled {kind} for {ident}")
            return
        except SystemExit as e:
            err = str(e)[:200]
    print(f"CAPABILITY REFUSED: {kind} for {ident}: {err}")


def make_profile(ident, cid, force=False):
    name = f"DevID {ident} {cid[:8]}"
    found = asc.call("GET", f"/v1/profiles?filter[name]={urllib.request.quote(name)}"
                            "&filter[profileType]=MAC_APP_DIRECT")["data"]
    active = [p for p in found if p["attributes"]["profileState"] == "ACTIVE"]
    if active and not force:
        return base64.b64decode(active[0]["attributes"]["profileContent"])
    if found:
        asc.call("DELETE", f"/v1/profiles/{found[0]['id']}")
        print(f"recreating profile '{name}'")
    print(f"creating MAC_APP_DIRECT profile '{name}'")
    return base64.b64decode(asc.call("POST", "/v1/profiles", {"data": {
        "type": "profiles",
        "attributes": {"name": name, "profileType": "MAC_APP_DIRECT"},
        "relationships": {
            "bundleId": asc.rel("bundleIds", bundle_id(ident)),
            "certificates": {"data": [{"type": "certificates", "id": cid}]},
        },
    }})["data"]["attributes"]["profileContent"])


def granted(prov):
    """Entitlements dict a profile payload carries, or {}."""
    try:
        return plistlib.loads(prov[prov.index(b"<?xml"):prov.index(b"</plist>") + 8]).get("Entitlements", {})
    except Exception:
        return {}


RESTRICTED = ("com.apple.developer.aps-environment", "com.apple.developer.ubiquity-kvstore-identifier",
              "com.apple.security.application-groups")


def report(prov, claims_text, label):
    have = {k for k in granted(prov) if k.startswith("com.apple.")}
    want = plistlib.loads(claims_text.encode())
    claimed = [k for k in want if k.startswith("com.apple.")]
    missing = sorted(k for k in claimed
                     if (k.startswith("com.apple.developer.") or k in RESTRICTED) and k not in have)
    print(f"{label}: profile grants {sorted(have) or '(nothing)'}")
    if missing:
        print(f"{label}: NOT backed by the profile, ship without these keys: {missing}")
    else:
        print(f"{label}: profile backs every claimed com.apple.* entitlement")
    return missing


def main():
    out = Path("build/provision")
    out.mkdir(parents=True, exist_ok=True)
    cid = cert_id()
    entries = yml_entries()
    if not entries:
        sys.exit("provision-mac.py: no bundleID in xtool.yml")
    app_ent = next((a for a in sys.argv[1:] if not a.startswith("-")), "")
    force = "--force" in sys.argv

    pkg = json.loads(subprocess.run(["swift", "package", "describe", "--type", "json"],
                                    capture_output=True, text=True, check=True).stdout)
    target_path = {t["name"]: t.get("path", "Sources/" + t["name"]) for t in pkg["targets"]}

    for product, ident, info in entries:
        bid = bundle_id(ident)
        ent = app_ent if ident == entries[0][1] else ""
        if not ent and product:
            d = target_path.get(product, "")
            if d and Path(d).is_dir():
                ent = next((str(p) for p in sorted(Path(d).rglob("*.entitlements"))
                            if "-dev" not in p.name), "")
        if ent:
            text = expand(ent)
            wants = plistlib.loads(text.encode())
            if any(k.startswith("com.apple.developer.icloud-") for k in wants):
                enable_capability(bid, "ICLOUD", ident)
            if "com.apple.developer.aps-environment" in wants:
                enable_capability(bid, "PUSH_NOTIFICATIONS", ident)
        if plist_value(info, "AppGroup"):
            enable_capability(bid, "APP_GROUPS", ident)
        prov = make_profile(ident, cid, force)
        name = "app" if ident == entries[0][1] else product
        dest = out / f"{name}.provisionprofile"
        dest.write_bytes(prov)
        print(f"wrote {dest} for {ident}")
        if ent:
            report(dest.read_bytes(), expand(ent), f"{name}")

    if not app_ent:
        print("no app entitlements given: created the app profile from the bundle id alone")


if __name__ == "__main__":
    main()
