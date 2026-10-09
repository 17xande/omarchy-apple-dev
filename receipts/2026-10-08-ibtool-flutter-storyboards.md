# Receipt: Flutter's template storyboards through the Linux ibtool, 2026-10-08

Claim: `tools/ibtool` compiles the `Main.storyboard` and
`LaunchScreen.storyboard` that `flutter create` writes, unmodified, and the
output is byte-identical to Apple's ibtool 27.0.

Goldens: `tests/ibtool/compile-golden.sh` over the whole `src/` tree on a Mac
with Xcode 27.0 (27A266a), `--minimum-deployment-target 17.0`. Only the new
`golden/Runner` was copied in. Of the 65 files already committed, 61 came back
identical; four view nibs of NetNewsWire's `Main.storyboardc` differed on this
Mac and were left as committed (6Bn-mF-MPS, JEX-9P-axG, QJM-al-rDe,
vO9-a3-Dnu; not looked into).

1. Before: `LaunchScreen.storyboard` stops with `<view> is missing
   <key='frame'> subelement`, `Main.storyboard` with `unsupported color
   element {... 'customColorSpace': 'calibratedWhite'}`. With those two
   rewritten by hand the scene view nibs compile to 1010 and 1497 bytes;
   Apple's are 1863 and 2309.
2. After, `python3 tools/ibtool --module Runner --minimum-deployment-target
   17.0 --target-device iphone --target-device ipad ...`: all six files of the
   two `.storyboardc` are identical (`cmp`) to the goldens.
3. Deployment target. Apple's ibtool on the Mac, `LaunchScreen.storyboard`,
   scene view bounds:

   | `--minimum-deployment-target` | Scene view | Image view |
   |---|---|---|
   | 13.0, 15.0, 16.6 | 393 x 852 | 1000 x 1000 |
   | 17.0, 26.0 | 1000 x 1000 | 1000 x 1000 |

   The Linux ibtool's scene nib is identical to Apple's at each of the five.
4. `calibratedWhite` probes, `Main.storyboard` with the background swapped,
   compiled on the Mac and on Linux: white/alpha 0.5/0.25, 0/1,
   0.33333334326744080/1, 0.66666666666666663/0.5, 1/0,
   0.5/0.33333334326744080, 0.25/0.1 and
   0.80000001192092896/0.80000001192092896. Eight of eight identical. Three are
   kept in the corpus.
5. Against a real build: the `Base.lproj` of an app that Xcode 27.0 built on a
   macOS runner from these same two storyboards at a 16.6 deployment target.
   All six files identical to the Linux ibtool's output at 16.6.
6. `python3 tools/ibtool --self-test`: passed, 66 golden nibs round-trip (56
   before), with `Flutter Runner Main.storyboardc`, `Flutter Runner
   LaunchScreen.storyboardc`, the three white probes and `Flutter Runner
   LaunchScreen at iOS 16.6` among the byte-identical compiles.
   `python3 tools/nibarchive.py --self-test`: passed.
7. On a device: `flutter/build.sh` on the sample from
   `receipts/2026-10-08-flutter-ios.md` with the storyboards untouched, on
   Omarchy x86_64. The launch nib in the bundle is identical to Apple's at the
   app's 15.0 target. `xtool install`, launched on an iPad (9th generation,
   iPadOS 27.0): the app starts and all four plugin probes pass, build stamp
   `pr-ibtool-2004Z`.

Not done: a storyboard with only one of the two guides, guides referenced by a
document constraint, `multipleTouchEnabled` together with
`userInteractionEnabled` on an image view (ibtool stops rather than guess the
key order), and the launch screen's appearance was not inspected frame by
frame, only that the app starts.
