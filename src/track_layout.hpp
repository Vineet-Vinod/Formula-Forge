#pragma once

#include <array>

struct TrackControlPoint {
    float x = 0.0f;
    float y = 0.0f;
};

inline constexpr float kSharkHarborCourseScale = 0.94f;

// A deliberately non-self-approaching coastal loop. The old three-lobed route
// put unrelated road branches in the driver's forward view; this perimeter
// layout keeps the next piece of road unambiguous while retaining varied bends.
inline constexpr std::array<TrackControlPoint, 26> kSharkHarborControlPoints = {{
    {-610.0f, -1160.0f}, {-210.0f, -1220.0f}, {250.0f, -1215.0f},  {690.0f, -1120.0f},
    {1040.0f, -930.0f},  {1310.0f, -680.0f},  {1490.0f, -380.0f},  {1540.0f, -25.0f},
    {1480.0f, 330.0f},   {1320.0f, 650.0f},   {1080.0f, 900.0f},   {770.0f, 1070.0f},
    {420.0f, 1160.0f},   {55.0f, 1140.0f},    {-280.0f, 1060.0f},  {-580.0f, 900.0f},
    {-800.0f, 710.0f},   {-990.0f, 525.0f},   {-1230.0f, 350.0f},  {-1450.0f, 80.0f},
    {-1510.0f, -220.0f}, {-1420.0f, -500.0f}, {-1210.0f, -700.0f}, {-950.0f, -790.0f},
    {-790.0f, -940.0f},  {-710.0f, -1080.0f},
}};
