// Authored from the public API description of SafariServices (SFSafariViewController). No SDK file read.
#import <UIKit/UIKit.h>
NS_ASSUME_NONNULL_BEGIN
@class SFSafariViewController;
typedef NS_ENUM(NSInteger, SFSafariViewControllerDismissButtonStyle) {
  SFSafariViewControllerDismissButtonStyleDone,
  SFSafariViewControllerDismissButtonStyleClose,
  SFSafariViewControllerDismissButtonStyleCancel,
};
@protocol SFSafariViewControllerDelegate <NSObject>
@optional
- (void)safariViewControllerDidFinish:(SFSafariViewController *)controller;
- (void)safariViewController:(SFSafariViewController *)controller didCompleteInitialLoad:(BOOL)didLoadSuccessfully;
- (void)safariViewController:(SFSafariViewController *)controller initialLoadDidRedirectToURL:(NSURL *)URL;
@end
@interface SFSafariViewControllerConfiguration : NSObject
@property (nonatomic) BOOL entersReaderIfAvailable;
@property (nonatomic) BOOL barCollapsingEnabled;
@end
@interface SFSafariViewController : UIViewController
- (instancetype)initWithURL:(NSURL *)URL configuration:(SFSafariViewControllerConfiguration *)configuration NS_DESIGNATED_INITIALIZER;
- (instancetype)initWithURL:(NSURL *)URL;
- (instancetype)initWithNibName:(nullable NSString *)nibNameOrNil bundle:(nullable NSBundle *)nibBundleOrNil NS_UNAVAILABLE;
- (nullable instancetype)initWithCoder:(NSCoder *)coder NS_UNAVAILABLE;
@property (nonatomic, weak, nullable) id<SFSafariViewControllerDelegate> delegate;
@property (nonatomic) SFSafariViewControllerDismissButtonStyle dismissButtonStyle;
@end
NS_ASSUME_NONNULL_END
