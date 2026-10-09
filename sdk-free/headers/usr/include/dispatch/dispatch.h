#pragma once
// Omarchy SDK-free dispatch subset (names only; links against libSystem).
#include <stdint.h>
#include <stddef.h>
#include <objc/NSObject.h>
#define OS_OBJECT_USE_OBJC 1
// Dispatch objects are Objective-C objects on Apple platforms: ARC retains and releases them.
@protocol OS_dispatch_object <NSObject>
@end
@protocol OS_dispatch_queue <OS_dispatch_object>
@end
@protocol OS_dispatch_group <OS_dispatch_object>
@end
@protocol OS_dispatch_semaphore <OS_dispatch_object>
@end
typedef NSObject<OS_dispatch_queue> *dispatch_queue_t;
typedef NSObject<OS_dispatch_queue> *dispatch_queue_main_t;
typedef NSObject<OS_dispatch_queue> *dispatch_queue_global_t;
typedef NSObject<OS_dispatch_object> *dispatch_object_t;
typedef NSObject<OS_dispatch_group> *dispatch_group_t;
typedef NSObject<OS_dispatch_semaphore> *dispatch_semaphore_t;
struct dispatch_queue_s;
struct dispatch_queue_attr_s;
typedef struct dispatch_queue_attr_s *dispatch_queue_attr_t;
typedef uint64_t dispatch_time_t;
typedef void (^dispatch_block_t)(void);
#define DISPATCH_TIME_NOW 0ull
#define DISPATCH_TIME_FOREVER (~0ull)
#define NSEC_PER_SEC 1000000000ull
#define NSEC_PER_MSEC 1000000ull
extern struct dispatch_queue_s _dispatch_main_q;
#define dispatch_get_main_queue() ((__bridge dispatch_queue_main_t)&_dispatch_main_q)
dispatch_queue_t dispatch_get_global_queue(intptr_t identifier, uintptr_t flags);
dispatch_queue_t dispatch_queue_create(const char *label, dispatch_queue_attr_t _Nullable attr);
void dispatch_async(dispatch_queue_t queue, dispatch_block_t block);
void dispatch_sync(dispatch_queue_t queue, dispatch_block_t block);
void dispatch_after(dispatch_time_t when, dispatch_queue_t queue, dispatch_block_t block);
dispatch_time_t dispatch_time(dispatch_time_t when, int64_t delta);
#define DISPATCH_QUEUE_PRIORITY_HIGH 2
#define DISPATCH_QUEUE_PRIORITY_DEFAULT 0
#define DISPATCH_QUEUE_PRIORITY_LOW (-2)
#define DISPATCH_QUEUE_PRIORITY_BACKGROUND (-32768)
#define DISPATCH_QUEUE_SERIAL ((dispatch_queue_attr_t)0)
#define DISPATCH_QUEUE_CONCURRENT ((dispatch_queue_attr_t)&_dispatch_queue_attr_concurrent)
extern const struct dispatch_queue_attr_s _dispatch_queue_attr_concurrent;
void dispatch_queue_set_specific(dispatch_queue_t queue, const void *key, void *context, void (*destructor)(void *));
void *dispatch_get_specific(const void *key);
void dispatch_async_f(dispatch_queue_t queue, void *context, void (*work)(void *));
dispatch_group_t dispatch_group_create(void);
void dispatch_group_enter(dispatch_group_t group);
void dispatch_group_leave(dispatch_group_t group);
long dispatch_group_wait(dispatch_group_t group, dispatch_time_t timeout);
void dispatch_group_notify(dispatch_group_t group, dispatch_queue_t queue, dispatch_block_t block);
dispatch_semaphore_t dispatch_semaphore_create(long value);
long dispatch_semaphore_wait(dispatch_semaphore_t dsema, dispatch_time_t timeout);
long dispatch_semaphore_signal(dispatch_semaphore_t dsema);
typedef long dispatch_once_t;
void dispatch_once(dispatch_once_t *predicate, dispatch_block_t block);
#define dispatch_release(x) ((void)0)
#define dispatch_retain(x) ((void)0)
