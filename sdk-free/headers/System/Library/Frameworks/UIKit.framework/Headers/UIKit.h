#pragma once
// Omarchy SDK-free UIKit subset, written from public behaviour and names; grows as builds fail.
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>

#define UIKIT_EXTERN extern
#define UIKIT_STATIC_INLINE static inline
#define UI_APPEARANCE_SELECTOR
#define IBOutlet
#define IBAction void
#define IBInspectable
#define IB_DESIGNABLE

typedef NSString *UIApplicationLaunchOptionsKey __attribute__((swift_wrapper(struct)));
typedef NSString *UIApplicationOpenURLOptionsKey __attribute__((swift_wrapper(struct)));
typedef NSString *UIApplicationOpenExternalURLOptionsKey __attribute__((swift_wrapper(struct)));
typedef NSUInteger UIBackgroundTaskIdentifier;
typedef NS_ENUM(NSInteger, UIApplicationState) { UIApplicationStateActive, UIApplicationStateInactive, UIApplicationStateBackground };
typedef NS_ENUM(NSUInteger, UIBackgroundFetchResult) {
  UIBackgroundFetchResultNewData, UIBackgroundFetchResultNoData, UIBackgroundFetchResultFailed
};
typedef NS_OPTIONS(NSUInteger, UIInterfaceOrientationMask) {
  UIInterfaceOrientationMaskPortrait = (1 << 1), UIInterfaceOrientationMaskLandscapeLeft = (1 << 3),
  UIInterfaceOrientationMaskLandscapeRight = (1 << 2), UIInterfaceOrientationMaskPortraitUpsideDown = (1 << 4),
  UIInterfaceOrientationMaskLandscape = (UIInterfaceOrientationMaskLandscapeLeft | UIInterfaceOrientationMaskLandscapeRight),
  UIInterfaceOrientationMaskAll = 30, UIInterfaceOrientationMaskAllButUpsideDown = 26
};
typedef NS_ENUM(NSInteger, UIStatusBarStyle) { UIStatusBarStyleDefault, UIStatusBarStyleLightContent, UIStatusBarStyleDarkContent = 3 };
typedef NS_ENUM(NSInteger, UIUserInterfaceStyle) { UIUserInterfaceStyleUnspecified, UIUserInterfaceStyleLight, UIUserInterfaceStyleDark };
typedef NS_ENUM(NSInteger, UIGestureRecognizerState) {
  UIGestureRecognizerStatePossible, UIGestureRecognizerStateBegan, UIGestureRecognizerStateChanged,
  UIGestureRecognizerStateEnded, UIGestureRecognizerStateCancelled, UIGestureRecognizerStateFailed
};

NS_ASSUME_NONNULL_BEGIN

@protocol UIUserActivityRestoring;
@class UISceneConfiguration, UIApplication;
@class UIView, UIViewController, UIWindow, UIScreen, UIEvent, UITouch, UIPress, UIColor, UIImage, UIGestureRecognizer,
    UIScene, UISceneSession, UISceneConnectionOptions, UIOpenURLContext, UIWindowScene, UIApplicationShortcutItem,
    UIUserNotificationSettings, UILocalNotification, UINavigationController, UITraitCollection, UIPresentationController,
    UIStoryboard, UIStoryboardSegue, UIBarButtonItem, UIPasteboard, UIAccessibilityElement, UIOpenURLContext;

@interface UIResponder : NSObject
@property(nonatomic, readonly, nullable) UIResponder *nextResponder;
@property(nonatomic, readonly) BOOL canBecomeFirstResponder;
- (BOOL)becomeFirstResponder;
- (BOOL)resignFirstResponder;
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(nullable UIEvent *)event;
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(nullable UIEvent *)event;
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(nullable UIEvent *)event;
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(nullable UIEvent *)event;
- (void)pressesBegan:(NSSet<UIPress *> *)presses withEvent:(nullable UIEvent *)event;
- (void)pressesEnded:(NSSet<UIPress *> *)presses withEvent:(nullable UIEvent *)event;
- (void)pressesChanged:(NSSet<UIPress *> *)presses withEvent:(nullable UIEvent *)event;
- (void)pressesCancelled:(NSSet<UIPress *> *)presses withEvent:(nullable UIEvent *)event;
@end

@interface UIColor : NSObject <NSSecureCoding, NSCopying>
@property(class, nonatomic, readonly) UIColor *whiteColor;
@property(class, nonatomic, readonly) UIColor *blackColor;
@property(class, nonatomic, readonly) UIColor *clearColor;
@property(class, nonatomic, readonly) UIColor *systemBackgroundColor;
+ (UIColor *)colorWithRed:(CGFloat)red green:(CGFloat)green blue:(CGFloat)blue alpha:(CGFloat)alpha;
+ (UIColor *)colorWithWhite:(CGFloat)white alpha:(CGFloat)alpha;
@end

@interface UIImage : NSObject <NSSecureCoding>
@property(nonatomic, readonly) CGSize size;
+ (nullable UIImage *)imageNamed:(NSString *)name;
@end

@interface UIDevice : NSObject
@property(class, nonatomic, readonly) UIDevice *currentDevice;
@property(nonatomic, readonly, copy) NSString *systemVersion;
@property(nonatomic, readonly, copy) NSString *model;
@property(nonatomic, readonly, copy) NSString *name;
@end

@interface UIScreen : NSObject
@property(class, nonatomic, readonly) UIScreen *mainScreen;
@property(nonatomic, readonly) CGRect bounds;
@property(nonatomic, readonly) CGFloat scale;
@property(nonatomic, readonly) CGFloat nativeScale;
@end

@interface UITouch : NSObject
@property(nonatomic, readonly) NSTimeInterval timestamp;
@property(nonatomic, readonly, nullable) UIView *view;
- (CGPoint)locationInView:(nullable UIView *)view;
@end

@interface UIEvent : NSObject
@property(nonatomic, readonly) NSTimeInterval timestamp;
@end

@interface UIPress : NSObject
@end

@interface UITraitCollection : NSObject
@property(nonatomic, readonly) UIUserInterfaceStyle userInterfaceStyle;
@property(nonatomic, readonly) CGFloat displayScale;
@end

@interface UIGestureRecognizer : NSObject
@property(nonatomic, readonly) UIGestureRecognizerState state;
@property(nonatomic, getter=isEnabled) BOOL enabled;
@property(nonatomic, readonly, nullable) UIView *view;
@end
@protocol UIGestureRecognizerDelegate <NSObject>
@optional
- (BOOL)gestureRecognizer:(UIGestureRecognizer *)gestureRecognizer shouldReceiveTouch:(UITouch *)touch;
- (BOOL)gestureRecognizerShouldBegin:(UIGestureRecognizer *)gestureRecognizer;
- (BOOL)gestureRecognizer:(UIGestureRecognizer *)gestureRecognizer shouldRecognizeSimultaneouslyWithGestureRecognizer:(UIGestureRecognizer *)other;
@end

@interface UIView : UIResponder
@property(nonatomic) CGRect frame;
@property(nonatomic) CGRect bounds;
@property(nonatomic, readonly, nullable) UIView *superview;
@property(nonatomic, readonly, copy) NSArray<__kindof UIView *> *subviews;
@property(nonatomic, readonly, nullable) UIWindow *window;
@property(nonatomic, copy, nullable) UIColor *backgroundColor;
@property(nonatomic) CGFloat alpha;
@property(nonatomic, getter=isHidden) BOOL hidden;
@property(nonatomic, getter=isOpaque) BOOL opaque;
@property(nonatomic, getter=isUserInteractionEnabled) BOOL userInteractionEnabled;
@property(nonatomic, getter=isMultipleTouchEnabled) BOOL multipleTouchEnabled;
@property(nonatomic) NSInteger tag;
@property(nonatomic) BOOL clipsToBounds;
@property(nonatomic) BOOL translatesAutoresizingMaskIntoConstraints;
@property(nonatomic, copy, nullable) NSArray<UIGestureRecognizer *> *gestureRecognizers;
- (instancetype)initWithFrame:(CGRect)frame NS_DESIGNATED_INITIALIZER;
- (nullable instancetype)initWithCoder:(NSCoder *)coder NS_DESIGNATED_INITIALIZER;
- (void)addSubview:(UIView *)view;
- (void)removeFromSuperview;
- (void)insertSubview:(UIView *)view atIndex:(NSInteger)index;
- (void)setNeedsLayout;
- (void)layoutSubviews;
- (void)setNeedsDisplay;
- (void)addGestureRecognizer:(UIGestureRecognizer *)gestureRecognizer;
- (void)removeGestureRecognizer:(UIGestureRecognizer *)gestureRecognizer;
- (CGPoint)convertPoint:(CGPoint)point toView:(nullable UIView *)view;
@end

@interface UILabel : UIView
@property(nonatomic, copy, nullable) NSString *text;
@property(nonatomic, strong) UIColor *textColor;
@property(nonatomic) NSInteger numberOfLines;
@end

@interface UIWindow : UIView
@property(nonatomic, strong, nullable) UIViewController *rootViewController;
@property(nonatomic, readonly, nullable) UIWindowScene *windowScene;
- (void)makeKeyAndVisible;
- (void)makeKeyWindow;
@end

@interface UIViewController : UIResponder <NSCoding>
@property(null_resettable, nonatomic, strong) UIView *view;
@property(nonatomic, readonly, nullable) UIViewController *parentViewController;
@property(nonatomic, readonly, nullable) UIViewController *presentedViewController;
@property(nonatomic, readonly, copy) NSArray<__kindof UIViewController *> *childViewControllers;
@property(nonatomic, readonly, nullable) UINavigationController *navigationController;
@property(nonatomic, readonly) UITraitCollection *traitCollection;
@property(nonatomic, copy, nullable) NSString *title;
- (instancetype)initWithNibName:(nullable NSString *)nibNameOrNil bundle:(nullable NSBundle *)nibBundleOrNil NS_DESIGNATED_INITIALIZER;
- (nullable instancetype)initWithCoder:(NSCoder *)coder NS_DESIGNATED_INITIALIZER;
- (void)loadView;
- (void)viewDidLoad;
- (void)viewWillAppear:(BOOL)animated;
- (void)viewDidAppear:(BOOL)animated;
- (void)viewWillDisappear:(BOOL)animated;
- (void)viewDidDisappear:(BOOL)animated;
- (void)viewWillLayoutSubviews;
- (void)viewDidLayoutSubviews;
- (void)viewSafeAreaInsetsDidChange;
- (void)viewWillTransitionToSize:(CGSize)size withTransitionCoordinator:(id)coordinator;
- (void)traitCollectionDidChange:(nullable UITraitCollection *)previousTraitCollection;
- (void)didReceiveMemoryWarning;
- (void)presentViewController:(UIViewController *)viewControllerToPresent animated:(BOOL)flag completion:(void (^_Nullable)(void))completion;
- (void)dismissViewControllerAnimated:(BOOL)flag completion:(void (^_Nullable)(void))completion;
- (void)addChildViewController:(UIViewController *)childController;
- (void)didMoveToParentViewController:(nullable UIViewController *)parent;
- (void)willMoveToParentViewController:(nullable UIViewController *)parent;
- (void)removeFromParentViewController;
- (void)setNeedsStatusBarAppearanceUpdate;
- (void)setNeedsUpdateOfScreenEdgesDeferringSystemGestures;
@property(nonatomic, readonly) UIStatusBarStyle preferredStatusBarStyle;
@property(nonatomic, readonly) BOOL prefersStatusBarHidden;
@property(nonatomic, readonly) UIInterfaceOrientationMask supportedInterfaceOrientations;
@property(nonatomic, readonly) BOOL shouldAutorotate;
@end

@interface UIApplicationShortcutItem : NSObject <NSCopying, NSMutableCopying>
@property(nonatomic, copy, readonly) NSString *type;
@end

@interface UIUserNotificationSettings : NSObject
@end
@interface UILocalNotification : NSObject
@end

@interface UIOpenURLContext : NSObject
@property(nonatomic, copy, readonly) NSURL *URL;
@end

@interface UISceneSession : NSObject
@property(nonatomic, readonly, copy) NSString *persistentIdentifier;
@end
@interface UISceneConnectionOptions : NSObject
@property(nonatomic, copy, readonly) NSSet<UIOpenURLContext *> *URLContexts;
@property(nonatomic, copy, readonly) NSSet<NSUserActivity *> *userActivities;
@property(nonatomic, strong, readonly, nullable) UIApplicationShortcutItem *shortcutItem;
@end
@interface UIScene : UIResponder
@property(nonatomic, readonly) UISceneSession *session;
@end
@interface UIWindowScene : UIScene
@property(nonatomic, readonly) NSArray<UIWindow *> *windows;
@property(nonatomic, readonly, nullable) UIWindow *keyWindow;
@end
@protocol UISceneDelegate <NSObject>
@optional
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)connectionOptions;
- (void)sceneDidDisconnect:(UIScene *)scene;
- (void)sceneDidBecomeActive:(UIScene *)scene;
- (void)sceneWillResignActive:(UIScene *)scene;
- (void)sceneWillEnterForeground:(UIScene *)scene;
- (void)sceneDidEnterBackground:(UIScene *)scene;
- (void)scene:(UIScene *)scene openURLContexts:(NSSet<UIOpenURLContext *> *)URLContexts;
- (void)scene:(UIScene *)scene continueUserActivity:(NSUserActivity *)userActivity;
@end
@protocol UIWindowSceneDelegate <UISceneDelegate>
@optional
@property(nonatomic, strong, nullable) UIWindow *window;
- (void)windowScene:(UIWindowScene *)windowScene performActionForShortcutItem:(UIApplicationShortcutItem *)shortcutItem completionHandler:(void (^)(BOOL succeeded))completionHandler;
@end

@protocol UIApplicationDelegate <NSObject>
@optional
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(nullable NSDictionary<UIApplicationLaunchOptionsKey, id> *)launchOptions;
- (BOOL)application:(UIApplication *)application willFinishLaunchingWithOptions:(nullable NSDictionary<UIApplicationLaunchOptionsKey, id> *)launchOptions;
- (void)applicationDidBecomeActive:(UIApplication *)application;
- (void)applicationWillResignActive:(UIApplication *)application;
- (void)applicationDidEnterBackground:(UIApplication *)application;
- (void)applicationWillEnterForeground:(UIApplication *)application;
- (void)applicationWillTerminate:(UIApplication *)application;
- (void)applicationDidReceiveMemoryWarning:(UIApplication *)application;
- (BOOL)application:(UIApplication *)app openURL:(NSURL *)url options:(NSDictionary<UIApplicationOpenURLOptionsKey, id> *)options;
- (UISceneConfiguration *)application:(UIApplication *)application configurationForConnectingSceneSession:(UISceneSession *)connectingSceneSession options:(UISceneConnectionOptions *)options;
- (void)application:(UIApplication *)application didRegisterForRemoteNotificationsWithDeviceToken:(NSData *)deviceToken;
- (void)application:(UIApplication *)application didFailToRegisterForRemoteNotificationsWithError:(NSError *)error;
- (void)application:(UIApplication *)application didReceiveRemoteNotification:(NSDictionary *)userInfo fetchCompletionHandler:(void (^)(UIBackgroundFetchResult result))completionHandler;
- (void)application:(UIApplication *)application performActionForShortcutItem:(UIApplicationShortcutItem *)shortcutItem completionHandler:(void (^)(BOOL succeeded))completionHandler;
- (void)application:(UIApplication *)application performFetchWithCompletionHandler:(void (^)(UIBackgroundFetchResult result))completionHandler;
- (BOOL)application:(UIApplication *)application continueUserActivity:(NSUserActivity *)userActivity restorationHandler:(void (^)(NSArray<id<UIUserActivityRestoring>> *_Nullable))restorationHandler;
@property(nonatomic, strong, nullable) UIWindow *window;
@end

@interface UISceneConfiguration : NSObject
@property(nonatomic, readonly, nullable) NSString *name;
@property(nonatomic, strong, nullable) Class delegateClass;
+ (instancetype)configurationWithName:(nullable NSString *)name sessionRole:(NSString *)sessionRole;
@end

@interface UIApplication : UIResponder
@property(class, nonatomic, readonly) UIApplication *sharedApplication NS_EXTENSION_UNAVAILABLE_IOS("");
@property(nonatomic, assign, nullable) id<UIApplicationDelegate> delegate;
@property(nonatomic, readonly) UIApplicationState applicationState;
@property(nonatomic, readonly, nullable) UIWindow *keyWindow;
@property(nonatomic, readonly) NSArray<UIWindow *> *windows;
@property(nonatomic, getter=isIdleTimerDisabled) BOOL idleTimerDisabled;
- (BOOL)canOpenURL:(NSURL *)url;
- (void)openURL:(NSURL *)url options:(NSDictionary<UIApplicationOpenExternalURLOptionsKey, id> *)options completionHandler:(void (^_Nullable)(BOOL success))completion;
- (void)registerForRemoteNotifications;
- (UIBackgroundTaskIdentifier)beginBackgroundTaskWithExpirationHandler:(void (^_Nullable)(void))handler;
- (void)endBackgroundTask:(UIBackgroundTaskIdentifier)identifier;
@end

UIKIT_EXTERN int UIApplicationMain(int argc, char *_Nonnull *_Nonnull argv, NSString *_Nullable principalClassName, NSString *_Nullable delegateClassName);
UIKIT_EXTERN NSString *const UIApplicationLaunchOptionsURLKey;
UIKIT_EXTERN UIApplicationOpenURLOptionsKey const UIApplicationOpenURLOptionsSourceApplicationKey;

NS_ASSUME_NONNULL_END
