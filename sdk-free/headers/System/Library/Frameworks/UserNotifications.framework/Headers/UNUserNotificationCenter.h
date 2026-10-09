#pragma once
#import <Foundation/Foundation.h>
NS_ASSUME_NONNULL_BEGIN
@class UNNotification, UNNotificationResponse, UNUserNotificationCenter;
typedef NS_OPTIONS(NSUInteger, UNNotificationPresentationOptions) {
  UNNotificationPresentationOptionBadge = (1 << 0), UNNotificationPresentationOptionSound = (1 << 1),
  UNNotificationPresentationOptionList = (1 << 3), UNNotificationPresentationOptionBanner = (1 << 4)
};
@protocol UNUserNotificationCenterDelegate <NSObject>
@optional
- (void)userNotificationCenter:(UNUserNotificationCenter *)center willPresentNotification:(UNNotification *)notification withCompletionHandler:(void (^)(UNNotificationPresentationOptions options))completionHandler;
- (void)userNotificationCenter:(UNUserNotificationCenter *)center didReceiveNotificationResponse:(UNNotificationResponse *)response withCompletionHandler:(void (^)(void))completionHandler;
@end
@interface UNUserNotificationCenter : NSObject
@property(nonatomic, weak, nullable) id<UNUserNotificationCenterDelegate> delegate;
+ (UNUserNotificationCenter *)currentNotificationCenter;
@end
NS_ASSUME_NONNULL_END
