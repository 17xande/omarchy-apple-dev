# LLDB on an iPhone from Linux, 2026-10-06

Host jw16 (Arch Linux aarch64). iPhone 15 Pro Max (iPhone16,2), iOS 27.0.1,
over USB. Swift 6.4.0 swift.org toolchain (`lldb` 21.0.0, revision 903b9faa),
pymobiledevice3 11.22.0, xtool 3cbf66b (FINDINGS.md 56).

1. `xtool install --udid 00008130-000978E630E1401C UO.app`: "Successfully installed!", exit 0. The app is a
   debug build of `xtool new` with two locals in `ContentView.body`.
2. `pymobiledevice3 mounter mount-personalized` with Xcode 27's
   `iOS_DDI/Restore/022-21793-062.dmg`, its trustcache and `BuildManifest.plist`.
3. `sudo pymobiledevice3 lockdown start-tunnel`, then
   `pymobiledevice3 developer debugserver lldb XTL-69A6DE8B.com.example.UO --rsd HOST PORT`
   with `breakpoint set --file ContentView.swift --line 7`, a synchronous `continue` and
   `frame variable greeting launches`.

First session, 17:38Z:

```
* thread #1, queue = 'com.apple.main-thread', stop reason = breakpoint 1.3
      frame #0: 0x00000001007280a0 UO`ContentView.body.getter() at ContentView.swift:7:23
   5   	        let greeting = "Hello from Omarchy Linux"
   6   	        let launches = 42
(lldb) (String) greeting = 6164403120
(Int) launches = 42
```

Next session, 18:18Z, same commands, LLDB's Swift metadata cache from the first session present:

```
(lldb) (String) greeting = "Hello from Omarchy Linux"
(Int) launches = 42
```

Session at 18:25Z with an empty cache (`settings set symbols.swift-metadata-cache-path` to a new
directory):

```
(lldb) (String) greeting = 6092755888
(lldb) (Swift.String) greeting = {
  utf16Length = 6092755888 {
    _value = 6092755888
  }
  crumbs = {
    _buffer = {
      _storage = {
        Swift.ManagedBuffer<Swift.Double.SIMD64Storage, Swift.AnyObject> = {
```

`utf16Length` and `crumbs` are the stored properties of the standard library's
`_StringBreadcrumbs`, not of `String`. With the cache present, `frame variable -R greeting` shows
`String`'s real layout (`_guts._object._countAndFlagsBits`, `_guts._object._object`).
`expr greeting` fails in every session: LLDB cannot load the Swift modules for the app
("could not load Swift Standard Library").
