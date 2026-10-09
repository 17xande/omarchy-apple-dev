#pragma once
#include <stdint.h>
#include <stdbool.h>
typedef double CGFloat;
#define CGFLOAT_MIN __DBL_MIN__
#define CGFLOAT_MAX __DBL_MAX__
typedef struct CGPoint { CGFloat x, y; } CGPoint;
typedef struct CGSize { CGFloat width, height; } CGSize;
typedef struct CGRect { CGPoint origin; CGSize size; } CGRect;
typedef struct CGVector { CGFloat dx, dy; } CGVector;
typedef struct CGAffineTransform { CGFloat a, b, c, d, tx, ty; } CGAffineTransform;
static const CGPoint CGPointZero = {0, 0};
static const CGSize CGSizeZero = {0, 0};
static const CGRect CGRectZero = {{0, 0}, {0, 0}};
static inline CGPoint CGPointMake(CGFloat x, CGFloat y) { CGPoint p = {x, y}; return p; }
static inline CGSize CGSizeMake(CGFloat w, CGFloat h) { CGSize s = {w, h}; return s; }
static inline CGRect CGRectMake(CGFloat x, CGFloat y, CGFloat w, CGFloat h) { CGRect r = {{x, y}, {w, h}}; return r; }
typedef struct CGColor *CGColorRef;
typedef struct CGImage *CGImageRef;
typedef struct CGContext *CGContextRef;
typedef struct CGColorSpace *CGColorSpaceRef;
