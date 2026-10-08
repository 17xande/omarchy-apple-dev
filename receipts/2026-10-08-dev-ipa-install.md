# Receipt: sign on the build host, install with pymobiledevice3 (2026-10-08)

The phone host had no xtool. The build host signed the apps and the phone host installed them.

1. `CONFIGURATION=debug ship.sh --device 9LX44YXXVX` and `ship.sh --device 9LX44YXXVX` built NetNewsWire iOS
   with `--bundle-id` set to a development id. App and both extensions carried `AppGroup` and the group
   from the profile (`xcodeproj2xtool.py` rebases the group with `--bundle-id`, commit 5b2f571).
2. `tools/sign-dev.sh App.app out.ipa` signed the dylibs, the two extensions (each with its own profile
   entitlements) and the app with the development identity. Output: a 29.2 MB release ipa and a 31.6 MB
   debug ipa; each of the three bundles has an `embedded.mobileprovision`.
3. `pymobiledevice3 apps install out.ipa` on the phone host: "Installation succeed" for NetNewsWire iOS
   (release and debug) and for IceCubes (54.6 MB ipa, five profiles from `tools/provision-dev.py`).
4. `developer dvt launch` started both apps. They stayed in the process list and no new crash report
   appeared for NetNewsWire after the launch. The earlier `ExtensionContainersFile.filePath` trap (nil App
   Group container) did not recur.

Not covered: NetNewsWire iOS shows a black main screen after launch (open bug). LLDB was not run in this
window.
