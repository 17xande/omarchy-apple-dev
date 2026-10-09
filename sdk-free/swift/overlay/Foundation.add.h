// Declarations added for the Swift Foundation overlay build (authored from public API behaviour; not Apple's file).
// Appended to the module-clean copy of Foundation.h by mk-sdkm2.sh.
/* NSInteger for size/count members: the 6.x importer maps NSUInteger to UInt while the
   5.3 overlay sources pass Int; same ABI. */
#pragma once
NS_ASSUME_NONNULL_BEGIN
@interface NSDictionary (W71OverlayAdditions)
- (void)getObjects:(id _Nonnull __unsafe_unretained * _Nullable)objects andKeys:(id _Nonnull __unsafe_unretained * _Nullable)keys count:(NSUInteger)count;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSBundle (W71OverlayAdditions)
- (NSString *)localizedStringForKey:(NSString *)key value:(nullable NSString *)value table:(nullable NSString *)tableName;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSUserDefaults (W71OverlayAdditions)
- (nullable instancetype)initWithSuiteName:(nullable NSString *)suitename;
+ (void)resetStandardUserDefaults;
- (void)removeObjectForKey:(NSString *)defaultName;
- (nullable NSString *)stringForKey:(NSString *)defaultName;
- (nullable NSArray *)arrayForKey:(NSString *)defaultName;
- (nullable NSDictionary<NSString *, id> *)dictionaryForKey:(NSString *)defaultName;
- (nullable NSArray<NSString *> *)stringArrayForKey:(NSString *)defaultName;
- (NSInteger)integerForKey:(NSString *)defaultName;
- (float)floatForKey:(NSString *)defaultName;
- (double)doubleForKey:(NSString *)defaultName;
- (void)setInteger:(NSInteger)value forKey:(NSString *)defaultName __attribute__((swift_name("set(_:forKey:)")));
- (void)setFloat:(float)value forKey:(NSString *)defaultName __attribute__((swift_name("set(_:forKey:)")));
- (void)setDouble:(double)value forKey:(NSString *)defaultName __attribute__((swift_name("set(_:forKey:)")));
- (void)registerDefaults:(NSDictionary<NSString *, id> *)registrationDictionary;
- (NSDictionary<NSString *, id> *)dictionaryRepresentation;
- (nullable NSDictionary<NSString *, id> *)persistentDomainForName:(NSString *)domainName;
- (void)setPersistentDomain:(NSDictionary<NSString *, id> *)domain forName:(NSString *)domainName;
- (void)removePersistentDomainForName:(NSString *)domainName;
- (BOOL)synchronize;
@end
@interface NSThread (W71OverlayAdditions)
@property(class, readonly, copy) NSArray<NSString *> *callStackSymbols;
@property(class, readonly, strong) NSThread *currentThread;
@property(class, readonly, strong) NSThread *mainThread;
+ (void)sleepForTimeInterval:(NSTimeInterval)ti;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
FOUNDATION_EXPORT NSInteger NSPageSize(void);
typedef NS_OPTIONS(NSUInteger, NSDataReadingOptions) {
  NSDataReadingMappedIfSafe = 1UL << 0, NSDataReadingUncached = 1UL << 1, NSDataReadingMappedAlways = 1UL << 3,
  NSDataReadingMapped = NSDataReadingMappedIfSafe
};
typedef NS_OPTIONS(NSUInteger, NSDataWritingOptions) {
  NSDataWritingAtomic = 1UL << 0, NSDataWritingWithoutOverwriting = 1UL << 1,
  NSDataWritingFileProtectionNone = 0x10000000, NSDataWritingFileProtectionComplete = 0x20000000,
  NSDataWritingFileProtectionCompleteUnlessOpen = 0x30000000, NSDataWritingFileProtectionCompleteUntilFirstUserAuthentication = 0x40000000,
  NSDataWritingFileProtectionMask = 0xf0000000
};
typedef NS_OPTIONS(NSUInteger, NSDataSearchOptions) { NSDataSearchBackwards = 1UL << 0, NSDataSearchAnchored = 1UL << 1 }
;
typedef NS_OPTIONS(NSUInteger, NSDataBase64EncodingOptions) {
  NSDataBase64Encoding64CharacterLineLength = 1UL << 0, NSDataBase64Encoding76CharacterLineLength = 1UL << 1,
  NSDataBase64EncodingEndLineWithCarriageReturn = 1UL << 4, NSDataBase64EncodingEndLineWithLineFeed = 1UL << 5
} __attribute__((swift_name("NSData.Base64EncodingOptions")));
typedef NS_OPTIONS(NSUInteger, NSDataBase64DecodingOptions) { NSDataBase64DecodingIgnoreUnknownCharacters = 1UL << 0 }
  __attribute__((swift_name("NSData.Base64DecodingOptions")));
@interface NSData (W71OverlayAdditions)
- (instancetype)initWithBytesNoCopy:(void *)bytes length:(NSInteger)length deallocator:(nullable void (^)(void *bytes, NSInteger length))deallocator;
- (instancetype)initWithBytesNoCopy:(void *)bytes length:(NSInteger)length freeWhenDone:(BOOL)b;
- (instancetype)initWithBytesNoCopy:(void *)bytes length:(NSInteger)length;
- (instancetype)initWithData:(NSData *)data;
- (nullable instancetype)initWithContentsOfFile:(NSString *)path options:(NSDataReadingOptions)readOptionsMask error:(NSError **)errorPtr;
- (nullable instancetype)initWithContentsOfURL:(NSURL *)url options:(NSDataReadingOptions)readOptionsMask error:(NSError **)errorPtr;
- (nullable instancetype)initWithBase64EncodedString:(NSString *)base64String options:(NSDataBase64DecodingOptions)options __attribute__((swift_name("init(base64Encoded:options:)")));
- (nullable instancetype)initWithBase64EncodedData:(NSData *)base64Data options:(NSDataBase64DecodingOptions)options __attribute__((swift_name("init(base64Encoded:options:)")));
- (NSString *)base64EncodedStringWithOptions:(NSDataBase64EncodingOptions)options;
- (NSData *)base64EncodedDataWithOptions:(NSDataBase64EncodingOptions)options;
- (void)getBytes:(void *)buffer;
- (NSRange)rangeOfData:(NSData *)dataToFind options:(NSDataSearchOptions)mask range:(NSRange)searchRange __attribute__((swift_name("range(of:options:in:)")));
- (void)enumerateByteRangesUsingBlock:(void (NS_NOESCAPE ^)(const void *bytes, NSRange byteRange, BOOL *stop))block __attribute__((swift_name("enumerateBytes(_:)")));
- (BOOL)writeToFile:(NSString *)path options:(NSDataWritingOptions)writeOptionsMask error:(NSError **)errorPtr;
- (BOOL)writeToURL:(NSURL *)url options:(NSDataWritingOptions)writeOptionsMask error:(NSError **)errorPtr;
- (BOOL)_isCompact;
@end
@interface NSMutableData (W71OverlayAdditions)
- (void)setLength:(NSInteger)length;
- (void)increaseLengthBy:(NSInteger)extraLength;
- (void)resetBytesInRange:(NSRange)range;
- (void)setData:(NSData *)data;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
FOUNDATION_EXPORT NSErrorUserInfoKey const NSFilePathErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSURLErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSStringEncodingErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSHelpAnchorErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSLocalizedRecoverySuggestionErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSLocalizedRecoveryOptionsErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSRecoveryAttempterErrorKey;
FOUNDATION_EXPORT NSErrorUserInfoKey const NSDebugDescriptionErrorKey;
FOUNDATION_EXPORT NSErrorDomain const NSPOSIXErrorDomain;
FOUNDATION_EXPORT NSErrorDomain const NSOSStatusErrorDomain;
FOUNDATION_EXPORT NSErrorDomain const NSMachErrorDomain;
FOUNDATION_EXPORT NSErrorDomain const NSURLErrorDomain;
typedef NS_OPTIONS(NSUInteger, NSStringEnumerationOptions) {
  NSStringEnumerationByLines = 0, NSStringEnumerationByParagraphs = 1, NSStringEnumerationByComposedCharacterSequences = 2,
  NSStringEnumerationByWords = 3, NSStringEnumerationBySentences = 4, NSStringEnumerationReverse = 1UL << 8,
  NSStringEnumerationSubstringNotRequired = 1UL << 9, NSStringEnumerationLocalized = 1UL << 10
};
typedef NS_OPTIONS(NSUInteger, NSStringEncodingConversionOptions) {
  NSStringEncodingConversionAllowLossy = 1, NSStringEncodingConversionExternalRepresentation = 2
};
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
typedef NS_OPTIONS(NSUInteger, NSURLBookmarkCreationOptions) {
  NSURLBookmarkCreationPreferFileIDResolution = 1UL << 8, NSURLBookmarkCreationMinimalBookmark = 1UL << 9,
  NSURLBookmarkCreationSuitableForBookmarkFile = 1UL << 10, NSURLBookmarkCreationWithSecurityScope = 1UL << 11,
  NSURLBookmarkCreationSecurityScopeAllowOnlyReadAccess = 1UL << 12, NSURLBookmarkCreationWithoutImplicitSecurityScope = 1UL << 29
};
typedef NS_OPTIONS(NSUInteger, NSURLBookmarkResolutionOptions) {
  NSURLBookmarkResolutionWithoutUI = 1UL << 8, NSURLBookmarkResolutionWithoutMounting = 1UL << 9,
  NSURLBookmarkResolutionWithSecurityScope = 1UL << 10, NSURLBookmarkResolutionWithoutImplicitStartAccessing = 1UL << 15
};
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
FOUNDATION_EXPORT NSInteger NSRoundUpToMultipleOfPageSize(NSInteger bytes);
FOUNDATION_EXPORT NSInteger NSRoundDownToMultipleOfPageSize(NSInteger bytes);
FOUNDATION_EXPORT void NSCopyMemoryPages(const void *source, void *dest, NSInteger bytes);
FOUNDATION_EXPORT void (^const NSDataDeallocatorVM)(void *bytes, NSUInteger length);
FOUNDATION_EXPORT void (^const NSDataDeallocatorUnmap)(void *bytes, NSUInteger length);
FOUNDATION_EXPORT void (^const NSDataDeallocatorFree)(void *bytes, NSUInteger length);
FOUNDATION_EXPORT void (^const NSDataDeallocatorNone)(void *bytes, NSUInteger length);
FOUNDATION_EXPORT double NSFoundationVersionNumber;
#define NSFoundationVersionNumber_iOS_9_x_Max 1299
NS_ASSUME_NONNULL_END

typedef struct _NSZone NSZone;
NS_ASSUME_NONNULL_BEGIN
@interface NSError (W71OverlayAdditions)
+ (void)setUserInfoValueProviderForDomain:(NSErrorDomain)errorDomain provider:(nullable id _Nullable (^)(NSError *err, NSErrorUserInfoKey userInfoKey))provider __attribute__((swift_name("setUserInfoValueProvider(forDomain:provider:)")));
+ (nullable id _Nullable (^)(NSError *err, NSErrorUserInfoKey userInfoKey))userInfoValueProviderForDomain:(NSErrorDomain)errorDomain __attribute__((swift_name("userInfoValueProvider(forDomain:)")));
@end
FOUNDATION_EXPORT NSString *const NSURLErrorFailingURLErrorKey;
FOUNDATION_EXPORT NSString *const NSURLErrorFailingURLStringErrorKey;
FOUNDATION_EXPORT NSString *const NSURLErrorBackgroundTaskCancelledReasonKey;
FOUNDATION_EXPORT NSString *const NSURLErrorNetworkUnavailableReasonKey;
FOUNDATION_EXPORT NSString *const NSURLSessionDownloadTaskResumeData;
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSNumber (W71OverlayInits)
- (instancetype)initWithChar:(char)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedChar:(unsigned char)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithShort:(short)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedShort:(unsigned short)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithInt:(int)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedInt:(unsigned int)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithLong:(long)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedLong:(unsigned long)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithLongLong:(long long)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedLongLong:(unsigned long long)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithFloat:(float)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithDouble:(double)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithBool:(BOOL)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithInteger:(NSInteger)value __attribute__((swift_name("init(value:)")));
- (instancetype)initWithUnsignedInteger:(NSUInteger)value __attribute__((swift_name("init(value:)")));
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSSet<__covariant ObjectType> (W71OverlayAdditions)
- (instancetype)initWithObjects:(const ObjectType _Nonnull [_Nullable])objects count:(NSInteger)cnt;
- (instancetype)initWithArray:(NSArray<ObjectType> *)array;
- (instancetype)initWithSet:(NSSet<ObjectType> *)set;
- (nullable ObjectType)member:(ObjectType)object;
- (BOOL)isEqualToSet:(NSSet<ObjectType> *)otherSet;
- (void)enumerateObjectsUsingBlock:(void (NS_NOESCAPE ^)(ObjectType obj, BOOL *stop))block __attribute__((swift_name("enumerateObjects(_:)")));
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSString (W71OverlayAdditions)
- (nullable instancetype)initWithBytes:(const void *)bytes length:(NSInteger)len encoding:(NSStringEncoding)encoding;
- (nullable instancetype)initWithBytesNoCopy:(void *)bytes length:(NSInteger)len encoding:(NSStringEncoding)encoding freeWhenDone:(BOOL)freeBuffer;
- (instancetype)initWithString:(NSString *)aString;
- (instancetype)initWithFormat:(NSString *)format arguments:(va_list)argList NS_FORMAT_FUNCTION(1, 0);
- (instancetype)initWithFormat:(NSString *)format locale:(nullable id)locale arguments:(va_list)argList NS_FORMAT_FUNCTION(1, 0);
- (NSString *)stringByAppendingString:(NSString *)aString;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
@interface NSURL (W71OverlayAdditions)
- (nullable instancetype)initWithString:(NSString *)URLString relativeToURL:(nullable NSURL *)baseURL;
- (instancetype)initFileURLWithPath:(NSString *)path isDirectory:(BOOL)isDir relativeToURL:(nullable NSURL *)baseURL;
- (instancetype)initFileURLWithPath:(NSString *)path relativeToURL:(nullable NSURL *)baseURL;
- (instancetype)initFileURLWithPath:(NSString *)path isDirectory:(BOOL)isDir;
- (instancetype)initFileURLWithPath:(NSString *)path;
- (instancetype)initAbsoluteURLWithDataRepresentation:(NSData *)data relativeToURL:(nullable NSURL *)baseURL;
- (instancetype)initWithDataRepresentation:(NSData *)data relativeToURL:(nullable NSURL *)baseURL;
+ (nullable instancetype)URLWithString:(NSString *)URLString relativeToURL:(nullable NSURL *)baseURL;
+ (instancetype)fileURLWithPath:(NSString *)path isDirectory:(BOOL)isDir relativeToURL:(nullable NSURL *)baseURL;
+ (instancetype)fileURLWithPath:(NSString *)path relativeToURL:(nullable NSURL *)baseURL;
+ (instancetype)fileURLWithPath:(NSString *)path isDirectory:(BOOL)isDir;
@property(readonly, copy) NSData *dataRepresentation;
@property(readonly, copy, nullable) NSURL *absoluteURL;
@property(readonly, copy, nullable) NSURL *baseURL;
@property(readonly, copy) NSString *relativeString;
@property(readonly, copy, nullable) NSString *relativePath;
@property(readonly, copy, nullable) NSNumber *port;
@property(readonly, copy, nullable) NSString *user;
@property(readonly, copy, nullable) NSString *password;
@property(readonly, copy, nullable) NSString *parameterString;
@property(readonly, copy, nullable) NSString *lastPathComponent;
@property(readonly, copy, nullable) NSString *pathExtension;
@property(readonly, copy, nullable) NSArray<NSString *> *pathComponents;
@property(readonly) BOOL hasDirectoryPath;
@property(readonly, copy, nullable) NSURL *standardizedURL;
@property(readonly, copy, nullable) NSURL *filePathURL;
@property(readonly, copy, nullable) NSURL *fileReferenceURL;
@property(readonly, copy, nullable) NSURL *URLByDeletingLastPathComponent;
@property(readonly, copy, nullable) NSURL *URLByDeletingPathExtension;
@property(readonly, copy, nullable) NSURL *URLByStandardizingPath;
@property(readonly, copy, nullable) NSURL *URLByResolvingSymlinksInPath;
- (BOOL)isFileReferenceURL;
- (nullable NSURL *)URLByAppendingPathComponent:(NSString *)pathComponent isDirectory:(BOOL)isDirectory;
- (nullable NSURL *)URLByAppendingPathExtension:(NSString *)pathExtension;
- (BOOL)checkResourceIsReachableAndReturnError:(NSError **)error __attribute__((swift_error(none)));
@property(readonly) const char *fileSystemRepresentation NS_RETURNS_INNER_POINTER;
- (instancetype)initFileURLWithFileSystemRepresentation:(const char *)path isDirectory:(BOOL)isDir relativeToURL:(nullable NSURL *)baseURL __attribute__((swift_name("init(fileURLWithFileSystemRepresentation:isDirectory:relativeTo:)")));
+ (instancetype)fileURLWithFileSystemRepresentation:(const char *)path isDirectory:(BOOL)isDir relativeToURL:(nullable NSURL *)baseURL;
@end
NS_ASSUME_NONNULL_END
NS_ASSUME_NONNULL_BEGIN
FOUNDATION_EXPORT void NSGetSizeAndAlignment(const char *typePtr, NSUInteger * _Nullable sizep, NSUInteger * _Nullable alignp);
@interface NSValue (W71OverlayAdditions)
- (void)getValue:(void *)value;
/* NSInteger so the Swift importer sees Int, which is what the overlay sources pass (Apple's SDK apinotes map
   the NSUInteger parameter to Int as well); the ABI is the same register width. */
- (void)getValue:(void *)value size:(NSInteger)size;
- (instancetype)initWithBytes:(const void *)value objCType:(const char *)type;
+ (NSValue *)valueWithBytes:(const void *)value objCType:(const char *)type;
- (BOOL)isEqualToValue:(NSValue *)value;
@property(readonly) NSRange rangeValue;
+ (NSValue *)valueWithRange:(NSRange)range;
@end
NS_ASSUME_NONNULL_END
