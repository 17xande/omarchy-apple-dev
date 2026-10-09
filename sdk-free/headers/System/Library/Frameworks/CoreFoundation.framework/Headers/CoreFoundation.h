#pragma once
// Omarchy SDK-free CoreFoundation subset (toll-free bridging names only).
#include <stdint.h>
#include <stdbool.h>
typedef const void *CFTypeRef;
typedef unsigned long CFTypeID;
typedef signed long CFIndex;
typedef unsigned long CFOptionFlags;
typedef const struct __CFAllocator *CFAllocatorRef;
typedef const struct __CFString *CFStringRef;
typedef const struct __CFNumber *CFNumberRef;
typedef const struct __CFBoolean *CFBooleanRef;
typedef const struct __CFData *CFDataRef;
typedef const struct __CFArray *CFArrayRef;
typedef const struct __CFDictionary *CFDictionaryRef;
typedef struct __CFRunLoop *CFRunLoopRef;
typedef signed char Boolean_cf_unused;
extern const CFBooleanRef kCFBooleanTrue;
extern const CFBooleanRef kCFBooleanFalse;
extern const CFAllocatorRef kCFAllocatorDefault;
CFTypeID CFGetTypeID(CFTypeRef cf);
CFTypeID CFBooleanGetTypeID(void);
CFTypeID CFStringGetTypeID(void);
CFTypeID CFNumberGetTypeID(void);
unsigned char CFNumberIsFloatType(CFNumberRef number);
CFTypeRef CFRetain(CFTypeRef cf);
void CFRelease(CFTypeRef cf);
CFIndex CFGetRetainCount(CFTypeRef cf);
