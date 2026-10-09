#!/usr/bin/env python3
"""install_name_tool subset for the SDK-free mode: -id NAME, -change OLD NEW, -rpath OLD NEW, -add_rpath X on one thin
arm64 Mach-O, in place. The load commands are rewritten inside the header padding; no LINKEDIT data moves.
Exits 1 when the new commands do not fit."""
import struct
import sys

LC_LOAD_DYLIB, LC_ID_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_RPATH = 0xC, 0xD, 0x80000018, 0x8000001F, 0x8000001C
DYLIB_CMDS = (LC_LOAD_DYLIB, LC_ID_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB)


def pad8(b):
    return b + b"\0" * (-len(b) % 8)


def rebuild(cmd, blob, name):
    """A dylib or rpath load command with a new name; version fields of dylib commands are kept."""
    if cmd in DYLIB_CMDS:
        data = pad8(struct.pack("<I", 24) + blob[12:24] + name.encode() + b"\0")
    else:
        data = pad8(struct.pack("<I", 12) + name.encode() + b"\0")
    return struct.pack("<II", cmd, 8 + len(data)) + data


def main(argv):
    path = argv[-1]
    ops = argv[:-1]
    with open(path, "rb") as f:
        d = bytearray(f.read())
    if struct.unpack_from("<I", d, 0)[0] != 0xFEEDFACF:
        sys.exit("install_name_tool shim: only thin 64-bit Mach-O files")
    ncmds, sizeofcmds = struct.unpack_from("<II", d, 16)
    cmds = []
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", d, off)
        cmds.append((cmd, bytes(d[off:off + size])))
        off += size
    first_section = min(
        (struct.unpack_from("<I", blob, 48)[0] for cmd, blob in cmds if cmd == 0x19 and struct.unpack_from("<I", blob, 48)[0]),
        default=len(d))
    i = 0
    while i < len(ops):
        op = ops[i]
        if op == "-id":
            cmds = [(c, rebuild(c, b, ops[i + 1]) if c == LC_ID_DYLIB else b) for c, b in cmds]
            i += 2
        elif op == "-change":
            old, new = ops[i + 1], ops[i + 2]
            out = []
            for c, b in cmds:
                if c in DYLIB_CMDS and c != LC_ID_DYLIB and b[struct.unpack_from("<I", b, 8)[0]:].split(b"\0", 1)[0].decode() == old:
                    b = rebuild(c, b, new)
                out.append((c, b))
            cmds = out
            i += 3
        elif op == "-rpath":
            old, new = ops[i + 1], ops[i + 2]
            out = []
            for c, b in cmds:
                if c == LC_RPATH and b[struct.unpack_from("<I", b, 8)[0]:].split(b"\0", 1)[0].decode() == old:
                    b = rebuild(c, b, new)
                out.append((c, b))
            cmds = out
            i += 3
        elif op == "-add_rpath":
            cmds.append((LC_RPATH, rebuild(LC_RPATH, b"", ops[i + 1])))
            i += 2
        else:
            sys.exit(f"install_name_tool shim: unsupported option {op}")
    total = sum(len(b) for _c, b in cmds)
    if 32 + total > first_section:
        sys.exit("install_name_tool shim: no room in the header padding")
    new = b"".join(b for _c, b in cmds)
    d[32:32 + len(new)] = new
    if total < sizeofcmds:
        d[32 + total:32 + sizeofcmds] = b"\0" * (sizeofcmds - total)
    struct.pack_into("<II", d, 16, len(cmds), total)
    with open(path, "wb") as f:
        f.write(d)


main(sys.argv[1:])
