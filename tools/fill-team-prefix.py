#!/usr/bin/env python3
"""Fill Xcode's team-prefix placeholders in a built bundle's Info.plists.

Xcode expands $(AppIdentifierPrefix) and $(TeamIdentifierPrefix) (both
"<TeamID>.") from the signing team at build time. xcodeproj2xtool.py keeps
them as placeholders; the step that knows the team runs this before the
bundle is signed or installed:

  App Store:  ship.sh, right after tools/asc.py identity (--team is the
              profile's com.apple.developer.team-identifier)
  Device:     before `xtool install`, from the key xtool signs with
              (--from-xtool-auth) or a development profile (--profile)

usage:
  fill-team-prefix.py --team TEAMID BUNDLE [BUNDLE ...]
  fill-team-prefix.py --from-xtool-auth BUNDLE [BUNDLE ...]
  fill-team-prefix.py --profile FILE.mobileprovision BUNDLE [BUNDLE ...]

Each BUNDLE is an .app; its PlugIns/*.appex are filled too. An .appex path
is accepted on its own."""
import argparse
import plistlib
import re
import subprocess
import sys
from pathlib import Path

PREFIXES = ("$(AppIdentifierPrefix)", "$(TeamIdentifierPrefix)")


def team_from_xtool_auth():
    """The team of the key xtool signs device installs with."""
    raw = subprocess.run(["xtool", "auth"], capture_output=True, text=True,
                         check=True).stdout
    found = re.search(r"Team ID: (\w+)", raw)
    if not found:
        sys.exit("error: `xtool auth` shows no Team ID; log in once or pass --team")
    return found.group(1)


def team_from_profile(path):
    """ApplicationIdentifierPrefix of a .mobileprovision (CMS-signed payload
    with a plain XML plist inside, as in asc.py profile_payload)."""
    data = Path(path).read_bytes()
    payload = plistlib.loads(data[data.index(b"<?xml"):
                                 data.index(b"</plist>") + len(b"</plist>")])
    teams = payload.get("ApplicationIdentifierPrefix") or payload.get("TeamIdentifier") or []
    if not teams:
        sys.exit(f"error: {path} carries no team identifier")
    return teams[0]


def fill_plist(path, team):
    """Substitute the placeholders in one Info.plist; returns filled key paths."""
    with path.open("rb") as f:
        data = plistlib.load(f)
    filled = []

    def walk(node, where=""):
        if isinstance(node, str):
            out = node
            for prefix in PREFIXES:
                if prefix in out:
                    filled.append(where)
                    out = out.replace(prefix, team + ".")
            return out
        if isinstance(node, list):
            return [walk(item, f"{where}[{i}]") for i, item in enumerate(node)]
        if isinstance(node, dict):
            return {key: walk(item, f"{where}.{key}" if where else key)
                    for key, item in node.items()}
        return node

    out = walk(data)
    if filled:
        with path.open("wb") as f:
            plistlib.dump(out, f)
    return filled


def bundle_plists(bundle):
    """A built bundle's own Info.plist plus its embedded extensions', or an
    xtool adapter's infoPath plists, so a fill made before `xtool dev build`
    or `device-run.sh --lldb` (which rebuilds) reaches the installed app."""
    bundle = Path(bundle)
    if (bundle / "xtool.yml").exists():
        plists = list({bundle / "Info.plist"}
                      | {bundle / line.split(":", 1)[1].strip()
                         for line in (bundle / "xtool.yml").read_text().splitlines()
                         if line.strip().startswith("infoPath:")})
        return sorted(p for p in plists if p.exists())
    plists = [bundle / "Info.plist"]
    plists += sorted((bundle / "PlugIns").glob("*.appex/Info.plist"))
    return [p for p in plists if p.exists()]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundles", nargs="+", metavar="BUNDLE")
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--team", help="the team id, e.g. Z6P74P6T99")
    source.add_argument("--from-xtool-auth", action="store_true",
                        help="take the team from `xtool auth`")
    source.add_argument("--profile", metavar="FILE",
                        help="take the team from a .mobileprovision")
    args = ap.parse_args()
    team = (team_from_xtool_auth() if args.from_xtool_auth
            else team_from_profile(args.profile) if args.profile
            else args.team)
    for bundle in args.bundles:
        for path in bundle_plists(bundle):
            filled = fill_plist(path, team)
            if filled:
                print(f"{path}: filled {', '.join(sorted(set(filled)))}")
            else:
                print(f"{path}: nothing to fill")


if __name__ == "__main__":
    main()
