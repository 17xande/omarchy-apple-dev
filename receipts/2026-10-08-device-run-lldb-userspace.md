# device-run.sh --lldb without root, 2026-10-08

Host sdt-omrch-alex (Arch Linux x86_64), iPad (UDID 00008122-001259DE26E8401C)
iOS 27.0.1 (24A446), pymobiledevice3 11.26.0, Swift toolchain lldb 21.0.0, the
Music Practice app (dev.alexf.MusicPractice) running as pid 1318.

## Verified

The `lldb_session` userspace path, run on its own against the running app (DDI already mounted,
the sysroot already in `~/.cache/omarchy-apple-dev/DeviceSupport/27.0.1 (24A446)`),
`LLDB_CMDS` = `bt 15`, `process detach`, `quit`:

```
Attaching to pid 1318
(lldb) process connect connect://127.0.0.1:55141
(lldb) process attach --pid 1318
Process 1318 stopped
* thread #1, stop reason = signal SIGSTOP
(lldb) bt 15
     frame #7: 0x0000000193aa01cc UIKitCore`
     frame #8: 0x0000000199a8f404 SwiftUI`
     frame #11: 0x0000000104a440d8 MusicPractice`
(lldb) process detach
Process 1318 detached
```

About 30 s end to end, exit 0, forwarder gone, the app still answering its debug server
(`/ping` ok), usbmuxd healthy. MusicPractice frames have no names here because the local
`xtool/MusicPractice.app` was a newer build than the installed one (UUID mismatch).

Packet logs: attaching with a synchronous `process connect` never sends `vAttach`; with
`SetAsync(True)` it is answered with a `T11` stop in ~1 s.

## Not verified yet

The full `./device-run.sh --lldb` (build, stop app, install, suspended launch, attach, app
function names, Ctrl-C at the prompt). The attempt on 2026-10-08 21:20 built fine, then
usbmuxd aborted (`free(): invalid pointer` right after "Sending to client fd 13 failed: Broken
pipe") while `xtool install` was connecting, so the install failed with `noDevice`. The
app-stop-before-install step, the setsid/trap rework and the readiness checks were added after
the isolated run above and have only been syntax-checked.
