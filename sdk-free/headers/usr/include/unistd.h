#pragma once
#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>
int close(int fd);
ssize_t read(int fd, void *buf, size_t n);
ssize_t write(int fd, const void *buf, size_t n);
int unlink(const char *path);
int access(const char *path, int mode);
pid_t getpid(void);
unsigned int sleep(unsigned int seconds);
int usleep(unsigned int useconds);
char *getcwd(char *buf, size_t size);
int chdir(const char *path);
#define F_OK 0
#define R_OK 4
#define W_OK 2
#define X_OK 1
