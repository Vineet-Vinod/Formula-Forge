#pragma once

#include <array>

struct TrackControlPoint {
    float x = 0.0f;
    float y = 0.0f;
};

enum class TrackLayoutId {
    SunsetCove,
    SpaCoast,
};

struct TrackElevationPoint {
    float distanceMeters = 0.0f;
    float elevationMeters = 0.0f;
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

inline constexpr float kSpaTargetLength = 7004.0f;
inline constexpr float kSpaElevationRelief = 102.2f;
inline constexpr float kSpaStartPhase = 0.0f;

// Starts after the Bus Stop and follows the 19 turns in race order. These
// survey-space points retain the distinctive La Source hairpin, Eau Rouge S,
// long Kemmel run, technical middle sector, and fast Blanchimont return.
inline constexpr std::array<TrackControlPoint, 121> kSpaControlPoints = {{
    {-198.0f, -139.0f}, {-210.0f, -151.0f}, {-230.0f, -166.0f}, {-250.0f, -184.0f},
    {-275.0f, -204.0f}, {-294.0f, -216.0f}, {-305.0f, -217.0f}, {-309.0f, -211.0f},
    {-306.0f, -198.0f}, {-297.0f, -181.0f}, {-286.0f, -162.0f}, {-274.0f, -141.0f},
    {-261.0f, -118.0f}, {-248.0f, -94.0f},  {-235.0f, -71.0f},  {-220.0f, -48.0f},
    {-205.0f, -31.0f},  {-190.0f, -24.0f},  {-180.0f, -32.0f},  {-175.0f, -15.0f},
    {-185.0f, 5.0f},    {-192.0f, 14.0f},   {-187.0f, 22.0f},   {-170.0f, 25.0f},
    {-150.0f, 24.0f},   {-133.0f, 20.0f},   {-110.0f, 43.0f},   {-85.0f, 66.0f},
    {-57.0f, 89.0f},    {-28.0f, 109.0f},   {3.0f, 128.0f},     {36.0f, 145.0f},
    {69.0f, 161.0f},    {101.0f, 176.0f},   {130.0f, 185.0f},   {145.0f, 191.0f},
    {156.0f, 190.0f},   {166.0f, 181.0f},   {174.0f, 171.0f},   {184.0f, 170.0f},
    {194.0f, 177.0f},   {207.0f, 188.0f},   {218.0f, 193.0f},   {230.0f, 190.0f},
    {242.0f, 178.0f},   {252.0f, 165.0f},   {266.0f, 150.0f},   {279.0f, 133.0f},
    {289.0f, 117.0f},   {294.0f, 102.0f},   {293.0f, 91.0f},    {287.0f, 85.0f},
    {278.0f, 83.0f},    {269.0f, 88.0f},    {259.0f, 99.0f},    {249.0f, 110.0f},
    {236.0f, 119.0f},   {220.0f, 124.0f},   {203.0f, 122.0f},   {186.0f, 115.0f},
    {168.0f, 104.0f},   {149.0f, 91.0f},    {130.0f, 74.0f},    {115.0f, 56.0f},
    {102.0f, 37.0f},    {95.0f, 18.0f},     {96.0f, 1.0f},      {104.0f, -12.0f},
    {117.0f, -20.0f},   {133.0f, -25.0f},   {151.0f, -26.0f},   {170.0f, -29.0f},
    {190.0f, -34.0f},   {209.0f, -42.0f},   {220.0f, -53.0f},   {222.0f, -67.0f},
    {218.0f, -80.0f},   {221.0f, -92.0f},   {232.0f, -101.0f},  {249.0f, -106.0f},
    {270.0f, -109.0f},  {291.0f, -114.0f},  {311.0f, -123.0f},  {322.0f, -134.0f},
    {324.0f, -149.0f},  {319.0f, -165.0f},  {310.0f, -181.0f},  {299.0f, -198.0f},
    {286.0f, -210.0f},  {272.0f, -215.0f},  {258.0f, -214.0f},  {242.0f, -207.0f},
    {225.0f, -197.0f},  {207.0f, -184.0f},  {189.0f, -170.0f},  {169.0f, -154.0f},
    {150.0f, -139.0f},  {130.0f, -123.0f},  {111.0f, -108.0f},  {92.0f, -94.0f},
    {74.0f, -82.0f},    {55.0f, -74.0f},    {35.0f, -70.0f},    {15.0f, -74.0f},
    {-4.0f, -83.0f},    {-25.0f, -96.0f},   {-46.0f, -108.0f},  {-67.0f, -119.0f},
    {-89.0f, -127.0f},  {-110.0f, -130.0f}, {-129.0f, -126.0f}, {-144.0f, -117.0f},
    {-151.0f, -105.0f}, {-151.0f, -91.0f},  {-149.0f, -76.0f},  {-155.0f, -67.0f},
    {-168.0f, -65.0f},  {-185.0f, -72.0f},  {-194.0f, -88.0f},  {-196.0f, -109.0f},
    {-195.0f, -128.0f},
}};

// Scale is calibrated against the closed Catmull-Rom centerline above so one
// simulation unit represents one metre over Spa's 7,004 m lap.
inline constexpr float kSpaCourseScale = 2.9584332f;

// FIA distance/altitude stations, shifted to a zero datum and normalized from
// their 99 m sampled span to the published 102.2 m overall circuit relief.
inline constexpr std::array<TrackElevationPoint, 18> kSpaElevationProfile = {{
    {0.0f, 47.4869f},
    {220.0f, 55.7455f},
    {690.0f, 34.0667f},
    {890.0f, 20.6465f},
    {1130.0f, 45.4222f},
    {1490.0f, 61.9394f},
    {2200.0f, 96.0061f},
    {2470.0f, 102.2000f},
    {2870.0f, 88.7798f},
    {3110.0f, 70.1980f},
    {3600.0f, 30.9697f},
    {4280.0f, 7.2263f},
    {4740.0f, 3.0970f},
    {5100.0f, 0.0000f},
    {5700.0f, 14.4525f},
    {6000.0f, 24.7758f},
    {6540.0f, 39.2283f},
    {7004.0f, 47.4869f},
}};
