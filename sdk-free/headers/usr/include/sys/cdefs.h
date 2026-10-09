#pragma once
#ifdef __cplusplus
#define __BEGIN_DECLS extern "C" {
#define __END_DECLS }
#else
#define __BEGIN_DECLS
#define __END_DECLS
#endif
#define __unused __attribute__((unused))
#define __deprecated __attribute__((deprecated))
#define __deprecated_msg(_msg) __attribute__((deprecated(_msg)))
#define __unavailable __attribute__((unavailable))
#define __dead2 __attribute__((noreturn))
#define __printflike(fmtarg, firstvararg) __attribute__((format(printf, fmtarg, firstvararg)))
#define __pure2 __attribute__((const))
