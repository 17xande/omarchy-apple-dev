# Receipt: NetNewsWire iOS built on Linux shows its UI on an iPhone (2026-10-08)

Before: the app launched and stayed alive, and the main screen stayed black. The device syslog (`pymobiledevice3
syslog live -m NetNewsWire` while the app started) held three UIKit errors:

    Info.plist configuration "Default Configuration" for UIWindowSceneSessionRoleApplication contained
    UISceneDelegateClassName key, but could not load class with name "NetNewsWire.SceneDelegate".
    There is no scene delegate set. A scene delegate class must be specified to use a main storyboard file.

Cause: Xcode names the Swift module of a target from `PRODUCT_MODULE_NAME` (`NetNewsWire`). SwiftPM names it
after the target (`NetNewsWire_iOS`). The binary holds `_TtC15NetNewsWire_iOS13SceneDelegate`, so a class named
`NetNewsWire.SceneDelegate` does not exist at run time.

Fix: `tools/xcodeproj2xtool.py` rewrites the module prefix of `UISceneDelegateClassName`, `NSPrincipalClass`
and `NSExtensionPrincipalClass` to the SwiftPM module when the two names differ.

After: same device, same install path (`ship.sh --device`, `tools/sign-dev.sh`, `pymobiledevice3 apps install`).
The app shows the Feeds screen: "Smart Feeds" and "On My iPhone" with 378 articles from the default feeds
(`2026-10-08-nnw-ios-on-iphone.png`; the "PhoneInference" label in the status bar belongs to another app).
