#pragma once

#include <array>
#include <cstdint>

struct TrackControlPoint {
    float x = 0.0f;
    float y = 0.0f;
};

enum class TrackLayoutId {
    SpaCoast,
    Suzuka,
    Silverstone,
    Monza,
    Interlagos,
};

struct TrackElevationPoint {
    float distanceMeters = 0.0f;
    float elevationMeters = 0.0f;
};

// Signed road crossfall. Positive angles raise the driver's left edge and
// therefore provide positive camber through a right-hand corner.
struct TrackBankPoint {
    float distanceMeters = 0.0f;
    float angleDegrees = 0.0f;
};

enum class TrackRunoffSurface : std::uint8_t {
    Asphalt,
    Gravel,
    Grass,
};

// Side uses the driver's frame: -1 right, 0 both, +1 left.
struct TrackRunoffZone {
    float startMeters = 0.0f;
    float endMeters = 0.0f;
    std::int8_t side = 0;
    TrackRunoffSurface surface = TrackRunoffSurface::Grass;
    float widthMeters = 0.0f;
};

inline constexpr float kSpaTargetLength = 7004.0f;
inline constexpr float kSpaSimulationUnitsPerMeter = 17.0f;
inline constexpr float kSpaElevationRelief = 102.2f;
inline constexpr float kSpaStartPhase = 0.0f;

// Starts after the Bus Stop and follows the 19 turns in race order. These
// survey-space points retain the distinctive La Source hairpin, Eau Rouge S,
// long Kemmel run, technical middle sector, and fast Blanchimont return.
inline constexpr std::array<TrackControlPoint, 121> kSpaControlPoints = {{
    {-316.592f, 138.919f}, {-340.151f, 155.331f}, {-363.901f, 171.464f},
    {-387.818f, 187.349f}, {-411.877f, 203.019f}, {-436.055f, 218.503f},
    {-460.330f, 233.836f}, {-484.547f, 249.209f}, {-500.000f, 237.629f},
    {-487.811f, 211.649f}, {-476.089f, 185.439f}, {-463.806f, 159.490f},
    {-450.105f, 134.263f}, {-434.294f, 110.322f}, {-414.958f, 89.130f},
    {-394.101f, 69.398f}, {-373.823f, 49.072f}, {-353.693f, 28.599f},
    {-333.284f, 8.409f}, {-314.788f, -13.424f}, {-300.224f, -38.097f},
    {-278.368f, -56.241f}, {-251.064f, -64.649f}, {-224.332f, -74.349f},
    {-200.921f, -90.959f}, {-178.338f, -108.689f}, {-155.460f, -126.037f},
    {-132.291f, -142.993f}, {-108.577f, -159.174f}, {-83.210f, -172.544f},
    {-56.386f, -182.762f}, {-29.112f, -191.732f}, {-2.048f, -201.311f},
    {24.847f, -211.363f}, {51.685f, -221.566f}, {78.484f, -231.869f},
    {105.256f, -242.245f}, {132.006f, -252.675f}, {158.741f, -263.144f},
    {185.467f, -273.637f}, {212.201f, -284.109f}, {238.878f, -294.720f},
    {266.035f, -303.952f}, {292.892f, -298.869f}, {313.371f, -279.296f},
    {340.851f, -283.964f}, {367.472f, -294.615f}, {394.936f, -291.452f},
    {414.637f, -270.592f}, {433.665f, -249.091f}, {452.449f, -227.377f},
    {471.179f, -205.616f}, {489.721f, -183.701f}, {500.000f, -157.755f},
    {481.025f, -138.285f}, {455.035f, -146.447f}, {436.925f, -168.718f},
    {419.546f, -191.572f}, {395.680f, -204.575f}, {369.066f, -194.527f},
    {342.453f, -183.758f}, {315.750f, -173.207f}, {288.582f, -163.942f},
    {260.950f, -156.147f}, {233.075f, -149.272f}, {205.158f, -142.564f},
    {177.435f, -135.102f}, {152.925f, -120.639f}, {142.197f, -94.675f},
    {141.821f, -65.989f}, {147.591f, -37.948f}, {163.025f, -14.216f},
    {187.160f, 1.240f}, {214.355f, 10.303f}, {242.277f, 16.986f},
    {269.878f, 24.891f}, {297.372f, 33.165f}, {324.745f, 41.829f},
    {351.886f, 51.094f}, {370.667f, 71.722f}, {367.358f, 99.722f},
    {359.424f, 127.083f}, {370.251f, 152.695f}, {394.627f, 167.815f},
    {420.642f, 179.945f}, {446.625f, 192.137f}, {469.624f, 209.071f},
    {473.693f, 235.937f}, {459.032f, 260.595f}, {442.409f, 283.995f},
    {420.481f, 301.876f}, {392.150f, 303.952f}, {364.176f, 297.639f},
    {337.106f, 288.102f}, {311.669f, 274.869f}, {288.361f, 258.125f},
    {266.288f, 239.769f}, {245.853f, 219.621f}, {227.818f, 197.295f},
    {211.179f, 173.897f}, {195.355f, 149.948f}, {179.338f, 126.134f},
    {161.012f, 104.057f}, {137.833f, 87.349f}, {112.048f, 74.721f},
    {85.478f, 63.887f}, {57.991f, 55.615f}, {29.934f, 49.561f},
    {1.437f, 48.552f}, {-25.361f, 58.651f}, {-50.413f, 72.675f},
    {-75.760f, 86.160f}, {-101.720f, 98.394f}, {-129.170f, 106.755f},
    {-157.150f, 113.190f}, {-185.146f, 119.561f}, {-213.165f, 125.827f},
    {-241.416f, 130.873f}, {-250.428f, 109.660f}, {-270.779f, 104.305f},
    {-293.568f, 121.770f},
}};

// The survey outline is normalized to the physical lap length during track
// construction; this value only preserves the authored coordinate scale.
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

// Modest crossfall follows the major corner complexes while retaining Spa's
// defining off-camber downhill Pouhon. Values are intentionally conservative:
// the large vertical character comes from the surveyed elevation profile.
inline constexpr std::array<TrackBankPoint, 25> kSpaBankProfile = {{
    {0.0f, 0.0f},     {120.0f, 0.0f},   {220.0f, 3.0f},   {360.0f, 0.0f},
    {650.0f, -1.5f},  {760.0f, 2.2f},   {930.0f, -1.2f},  {1130.0f, 0.0f},
    {2070.0f, 0.0f},  {2200.0f, 2.0f},  {2370.0f, -1.6f}, {2520.0f, 0.0f},
    {2870.0f, 3.2f},  {3110.0f, -1.4f}, {3440.0f, 0.0f},  {3600.0f, 1.8f},
    {3980.0f, 0.0f},  {4280.0f, 1.8f},  {4470.0f, -1.8f}, {4740.0f, 1.5f},
    {5100.0f, 0.8f},  {5700.0f, -1.8f}, {6250.0f, 0.0f},  {6540.0f, 2.0f},
    {7004.0f, 0.0f},
}};

inline constexpr std::array<TrackRunoffZone, 9> kSpaRunoffProfile = {{
    {120.0f, 360.0f, 1, TrackRunoffSurface::Gravel, 17.0f},
    {560.0f, 1180.0f, 0, TrackRunoffSurface::Asphalt, 9.0f},
    {2050.0f, 2450.0f, 0, TrackRunoffSurface::Gravel, 13.0f},
    {2700.0f, 3060.0f, 1, TrackRunoffSurface::Gravel, 18.0f},
    {3430.0f, 3880.0f, -1, TrackRunoffSurface::Gravel, 16.0f},
    {4100.0f, 4600.0f, 0, TrackRunoffSurface::Gravel, 12.0f},
    {4660.0f, 5260.0f, 1, TrackRunoffSurface::Grass, 10.0f},
    {5530.0f, 6200.0f, -1, TrackRunoffSurface::Gravel, 13.0f},
    {6370.0f, 6860.0f, 0, TrackRunoffSurface::Asphalt, 11.0f},
}};
