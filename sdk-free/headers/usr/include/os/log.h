#pragma once
typedef struct os_log_s *os_log_t;
typedef unsigned char os_log_type_t;
#define OS_LOG_DEFAULT ((os_log_t)0)
#define OS_LOG_TYPE_DEFAULT 0
#define OS_LOG_TYPE_INFO 1
#define OS_LOG_TYPE_DEBUG 2
#define OS_LOG_TYPE_ERROR 0x10
#define os_log(log, fmt, ...) ((void)0)
#define os_log_info(log, fmt, ...) ((void)0)
#define os_log_debug(log, fmt, ...) ((void)0)
#define os_log_error(log, fmt, ...) ((void)0)
#define os_log_with_type(log, type, fmt, ...) ((void)0)
