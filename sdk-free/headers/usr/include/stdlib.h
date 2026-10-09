#pragma once
#include <stddef.h>
#include <stdint.h>
void exit(int) __attribute__((noreturn));
void abort(void) __attribute__((noreturn));
void *malloc(size_t);
void *calloc(size_t, size_t);
void *realloc(void *, size_t);
void free(void *);
int atoi(const char *);
long atol(const char *);
double atof(const char *);
long strtol(const char *, char **, int);
unsigned long strtoul(const char *, char **, int);
long long strtoll(const char *, char **, int);
unsigned long long strtoull(const char *, char **, int);
double strtod(const char *, char **);
float strtof(const char *, char **);
int abs(int);
long labs(long);
int rand(void);
void srand(unsigned);
uint32_t arc4random(void);
uint32_t arc4random_uniform(uint32_t);
void arc4random_buf(void *, size_t);
void qsort(void *, size_t, size_t, int (*)(const void *, const void *));
void *bsearch(const void *, const void *, size_t, size_t, int (*)(const void *, const void *));
char *getenv(const char *);
int setenv(const char *, const char *, int);
int atexit(void (*)(void));
#define EXIT_SUCCESS 0
#define EXIT_FAILURE 1
#define RAND_MAX 0x7fffffff
