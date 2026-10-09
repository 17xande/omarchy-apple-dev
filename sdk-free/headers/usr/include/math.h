#pragma once
#define M_PI 3.14159265358979323846
#define M_E 2.7182818284590452354
#define HUGE_VAL __builtin_huge_val()
#define INFINITY __builtin_inff()
#define NAN __builtin_nanf("")
#define isnan(x) __builtin_isnan(x)
#define isinf(x) __builtin_isinf(x)
#define isfinite(x) __builtin_isfinite(x)
double fabs(double); float fabsf(float);
double floor(double); double ceil(double); double round(double); double trunc(double);
double fmod(double, double); double sqrt(double); float sqrtf(float);
double pow(double, double); double exp(double); double log(double); double log10(double); double log2(double);
double sin(double); double cos(double); double tan(double); double atan(double); double atan2(double, double);
double fmin(double, double); double fmax(double, double);
