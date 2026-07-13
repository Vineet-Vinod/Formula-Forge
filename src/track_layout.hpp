#pragma once

#include <array>

struct TrackControlPoint {
    float x = 0.0f;
    float y = 0.0f;
};

inline constexpr float kBreakwaterCourseScale = 1.50f;

// Centerline traced from the supplied top-down outline, starting on the lower
// straight and running clockwise. Extra points retain the right-hand step,
// upper-right bulb, upper-left shelf, and rounded lower-left return.
inline constexpr std::array<TrackControlPoint, 57> kBreakwaterControlPoints = {{
    {-492.0f, -519.0f}, {-300.0f, -519.0f}, {-111.0f, -525.0f}, {24.0f, -537.0f},
    {180.0f, -534.0f},  {510.0f, -519.0f},  {669.0f, -486.0f},  {783.0f, -453.0f},
    {900.0f, -462.0f},  {960.0f, -447.0f},  {984.0f, -408.0f},  {987.0f, -306.0f},
    {1020.0f, -276.0f}, {1167.0f, -255.0f}, {1170.0f, 42.0f},   {1146.0f, 135.0f},
    {1119.0f, 261.0f},  {1089.0f, 342.0f},  {1050.0f, 372.0f},  {966.0f, 384.0f},
    {885.0f, 378.0f},   {840.0f, 345.0f},   {804.0f, 294.0f},   {789.0f, 210.0f},
    {750.0f, 162.0f},   {663.0f, 153.0f},   {390.0f, 150.0f},   {117.0f, 147.0f},
    {-6.0f, 171.0f},    {-189.0f, 216.0f},  {-243.0f, 216.0f},  {-273.0f, 243.0f},
    {-297.0f, 297.0f},  {-309.0f, 345.0f},  {-312.0f, 420.0f},  {-321.0f, 519.0f},
    {-360.0f, 543.0f},  {-483.0f, 534.0f},  {-609.0f, 531.0f},  {-720.0f, 520.0f},
    {-800.0f, 480.0f},  {-855.0f, 410.0f},  {-885.0f, 300.0f},  {-885.0f, 54.0f},
    {-930.0f, -66.0f},
    {-969.0f, -123.0f}, {-1011.0f, -150.0f}, {-1071.0f, -153.0f}, {-1116.0f, -186.0f},
    {-1149.0f, -240.0f}, {-1152.0f, -378.0f}, {-1116.0f, -450.0f}, {-1080.0f, -504.0f},
    {-984.0f, -534.0f}, {-852.0f, -546.0f}, {-693.0f, -543.0f}, {-591.0f, -531.0f},
}};
