#define UNAVAILABLE_ATTRIBUTE __attribute__((unavailable))
#define DEPRECATED_ATTRIBUTE __attribute__((deprecated))
#define DEPRECATED_MSG_ATTRIBUTE(s) __attribute__((deprecated(s)))
#define NS_UNAVAILABLE UNAVAILABLE_ATTRIBUTE
