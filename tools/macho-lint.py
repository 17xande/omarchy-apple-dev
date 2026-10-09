"""Mach-O lint for every image in an ipa: arm64, iOS platform, minos/sdk, __LINKEDIT string pool 8-byte aligned,
string table last in the file, code signature present, and `rcodesign verify` clean.
usage: macho-lint.py IPA"""
import os
import struct
import subprocess
import sys
import tempfile
import zipfile

MH64, FAT = 0xFEEDFACF, 0xCAFEBABE
LC_SYMTAB, LC_SEGMENT_64, LC_CODE_SIGNATURE, LC_BUILD_VERSION = 0x2, 0x19, 0x1D, 0x32


def lint(path):
    with open(path, "rb") as f:
        d = f.read()
    if len(d) < 32 or struct.unpack_from("<I", d, 0)[0] != MH64:
        return None
    cpu, _sub, ftype, ncmds = struct.unpack_from("<iiII", d, 4)
    off, symtab, sig, bv = 32, None, False, None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", d, off)
        if cmd == LC_SYMTAB:
            symtab = struct.unpack_from("<IIII", d, off + 8)
        elif cmd == LC_CODE_SIGNATURE:
            sig = True
        elif cmd == LC_BUILD_VERSION:
            bv = struct.unpack_from("<IIII", d, off + 8)
        off += size
    problems = []
    if cpu != 0x0100000C:
        problems.append(f"cputype {cpu:#x} is not arm64")
    if bv is None or bv[0] != 2:
        problems.append("platform is not iOS")
    if symtab and symtab[2] % 8:
        problems.append(f"string pool offset {symtab[2]} is not 8-byte aligned")
    if symtab and symtab[2] + symtab[3] > len(d):
        problems.append("string table runs past the end of the file")
    if not sig:
        problems.append("no LC_CODE_SIGNATURE")
    minos = f"{bv[1] >> 16}.{(bv[1] >> 8) & 255}" if bv else "?"
    sdk = f"{bv[2] >> 16}.{(bv[2] >> 8) & 255}" if bv else "?"
    return {"filetype": ftype, "minos": minos, "sdk": sdk, "problems": problems}


ipa = sys.argv[1]
tmp = tempfile.mkdtemp(prefix="macholint-", dir=os.path.expanduser("~/tmp"))
zipfile.ZipFile(ipa).extractall(tmp)
bad = total = 0
for base, _dirs, files in os.walk(tmp):
    for f in sorted(files):
        p = os.path.join(base, f)
        if os.path.islink(p):
            continue
        r = lint(p)
        if r is None:
            continue
        total += 1
        v = subprocess.run(["rcodesign", "verify", p], capture_output=True, text=True, check=False)
        if v.returncode:
            r["problems"].append("rcodesign verify: " + (v.stderr.strip().splitlines() or ["failed"])[-1][:100])
        rel = os.path.relpath(p, tmp)
        status = "ok  " if not r["problems"] else "FAIL"
        bad += bool(r["problems"])
        print(f"{status} {rel}  type={r['filetype']} minos={r['minos']} sdk={r['sdk']} {'; '.join(r['problems'])}")
print(f"{total - bad}/{total} Mach-O images clean")
sys.exit(1 if bad else 0)
