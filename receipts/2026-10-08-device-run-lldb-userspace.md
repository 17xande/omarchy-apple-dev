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

## Full run, 2026-10-08 (after the usbmuxd restart)

From ~/dev/music-practice-app, no sudo:

```
$ LLDB_CMDS=$'breakpoint set -r "RootView\\.body\\.getter"\ncontinue\nbt 6\nbreakpoint delete -f\nprocess detach\nquit' \
    ~/dev/omarchy-apple-dev/device-run.sh --lldb
Build complete! (15.48 secs)
== 5. LLDB ==
[Installing] 100%
Attaching to pid 1442
(lldb) process attach --pid 1442
Process 1442 stopped
       frame #0: 0x00000001057e9a90 dyld`_dyld_start
(lldb) breakpoint set -r "RootView\.body\.getter"
Breakpoint 1: 33 locations.
(lldb) continue
* thread #1, stop reason = breakpoint 1.12
    frame #0: 0x0000000104f69ab0 MusicPractice`RootView.body.getter() at RootView.swift:29:29
-> 29  	        NavigationSplitView {
(lldb) bt 6
   * frame #0: 0x0000000104f69ab0 MusicPractice`RootView.body.getter() at RootView.swift:29:29
     frame #2: 0x00000001975d9ce4 SwiftUICore`
(lldb) process detach
Process 1442 detached
(lldb) quit
exit=0
```

The install went over the stopped app, the suspended launch stopped at `_dyld_start`, and the
breakpoint in app code hit with source. After the detach, the app (still pid 1442) answered
`/ping` with ok, no forwarder or lldb process was left, and usbmuxd stayed active. About 50 s from
step 5 to exit. The earlier attempt (21:20) failed because usbmuxd aborted during `xtool install`
(`free(): invalid pointer` after "Sending to client fd 13 failed: Broken pipe"), before any of this
code ran.

Not tested: a real Ctrl-C at the LLDB prompt (simulated only: SIGINT to the script's process
group leaves the setsid'd forwarder running).
