#include "track_catalog.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace {

// Centerlines are sampled from the current circuit diagrams, then centered and
// converted from SVG screen coordinates to the simulation's Cartesian plane.
// Track3D arc-length normalization applies each venue's published lap length.
constexpr TrackControlPoint kSuzukaCenterline[] = {
    {260.755f, 252.239f}, {301.514f, 252.310f}, {342.273f, 252.381f},
    {383.032f, 252.453f}, {423.791f, 252.524f}, {464.135f, 247.983f},
    {493.781f, 221.517f}, {500.000f, 183.228f}, {465.475f, 167.940f},
    {425.029f, 172.971f}, {384.521f, 177.331f}, {351.244f, 156.892f},
    {315.904f, 140.996f}, {278.373f, 156.524f}, {239.152f, 157.410f},
    {210.683f, 128.680f}, {173.402f, 116.275f}, {142.854f, 140.397f},
    {120.880f, 174.544f}, {82.793f, 182.098f}, {46.598f, 163.424f},
    {16.798f, 136.056f}, {1.031f, 98.783f}, {-0.295f, 58.230f},
    {7.131f, 18.156f}, {14.434f, -21.928f}, {-6.264f, -56.451f},
    {-31.367f, -87.974f}, {-68.538f, -74.272f}, {-104.382f, -54.869f},
    {-140.120f, -35.272f}, {-174.264f, -13.734f}, {-195.590f, 20.956f},
    {-221.583f, 36.301f}, {-211.746f, -2.856f}, {-200.482f, -41.988f},
    {-199.552f, -82.429f}, {-216.696f, -119.058f}, {-245.161f, -148.073f},
    {-279.145f, -170.550f}, {-316.298f, -186.896f}, {-356.721f, -190.088f},
    {-396.542f, -181.661f}, {-435.652f, -170.187f}, {-475.138f, -169.136f},
    {-499.986f, -200.496f}, {-500.000f, -238.936f}, {-463.024f, -252.524f},
    {-422.832f, -245.994f}, {-383.335f, -235.951f}, {-344.599f, -223.323f},
    {-307.444f, -206.636f}, {-271.872f, -186.742f}, {-236.607f, -166.305f},
    {-201.468f, -145.652f}, {-166.406f, -124.869f}, {-131.399f, -103.992f},
    {-102.796f, -81.591f}, {-78.265f, -52.298f}, {-58.434f, -18.128f},
    {-43.933f, 18.906f}, {-35.391f, 56.789f}, {-33.436f, 93.509f},
    {-35.242f, 134.228f}, {-9.876f, 158.014f}, {-1.648f, 196.537f},
    {20.834f, 229.583f}, {57.365f, 247.168f}, {97.720f, 251.954f},
    {138.479f, 252.025f}, {179.238f, 252.096f}, {219.997f, 252.168f},
};

constexpr TrackElevationPoint kSuzukaElevation[] = {
    {0.0f, 14.0f},   {650.0f, 5.0f},   {1180.0f, 20.0f}, {1650.0f, 39.5f},
    {2140.0f, 20.0f}, {2272.0f, 14.0f}, {2680.0f, 18.0f}, {3290.0f, 8.0f},
    {3820.0f, 0.0f},  {4360.0f, 20.0f}, {4645.0f, 30.0f}, {4930.0f, 28.0f},
    {5410.0f, 20.0f}, {5807.0f, 14.0f},
};

constexpr TrackWidthPoint kSuzukaWidth[] = {
    {0.0f, 14.0f},    {590.0f, 16.0f},  {1080.0f, 11.0f}, {1780.0f, 10.0f},
    {2370.0f, 12.0f}, {3150.0f, 13.0f}, {4090.0f, 11.0f}, {4890.0f, 12.0f},
    {5300.0f, 15.0f}, {5807.0f, 14.0f},
};

// Positive angles raise the driver's left edge. The alternating signs mirror
// Suzuka's opening esses; Turn 7 deliberately reverses the expected camber.
constexpr TrackBankPoint kSuzukaBank[] = {
    {0.0f, 0.0f},     {420.0f, 0.0f},   {565.0f, 2.8f},   {730.0f, 2.2f},
    {820.0f, -2.4f},  {930.0f, 2.2f},   {1040.0f, -2.0f}, {1180.0f, 1.7f},
    {1320.0f, 2.0f},  {1510.0f, 0.0f},  {1700.0f, 2.5f},  {1940.0f, 2.0f},
    {2250.0f, 0.0f},  {2660.0f, -3.6f}, {2920.0f, 0.0f},  {3470.0f, -3.0f},
    {3820.0f, -3.4f}, {4170.0f, 0.0f},  {4760.0f, -3.5f}, {5010.0f, 0.0f},
    {5140.0f, 2.1f},  {5270.0f, -1.8f}, {5440.0f, 0.0f},  {5807.0f, 0.0f},
};

constexpr TrackRunoffZone kSuzukaRunoff[] = {
    {420.0f, 790.0f, 1, TrackRunoffSurface::Gravel, 18.0f},
    {760.0f, 1450.0f, 0, TrackRunoffSurface::Grass, 9.0f},
    {1570.0f, 2070.0f, 1, TrackRunoffSurface::Gravel, 14.0f},
    {2480.0f, 2850.0f, -1, TrackRunoffSurface::Gravel, 18.0f},
    {3260.0f, 4010.0f, -1, TrackRunoffSurface::Gravel, 19.0f},
    {4560.0f, 4940.0f, -1, TrackRunoffSurface::Gravel, 17.0f},
    {5000.0f, 5360.0f, 0, TrackRunoffSurface::Asphalt, 12.0f},
    {5370.0f, 5710.0f, -1, TrackRunoffSurface::Gravel, 11.0f},
};

// The Spoon-to-130R back straight is the bridge; the Degner-to-hairpin branch
// passes beneath it. These stations match the sole plan-view intersection.
constexpr TrackGradeSeparation kSuzukaCrossings[] = {{2315.7f, 4660.5f, 10.0f}};

constexpr TrackControlPoint kSilverstoneCenterline[] = {
    {69.383f, -231.257f}, {36.068f, -193.943f}, {2.221f, -157.113f},
    {-31.985f, -120.623f}, {-27.338f, -73.692f}, {-2.542f, -30.313f},
    {15.126f, 16.343f}, {5.213f, 64.687f}, {-20.059f, 107.749f},
    {-51.210f, 146.877f}, {-27.604f, 174.107f}, {21.737f, 180.218f},
    {12.329f, 219.488f}, {-29.693f, 246.500f}, {-77.965f, 251.382f},
    {-120.283f, 224.996f}, {-161.225f, 196.256f}, {-202.275f, 167.671f},
    {-243.297f, 139.046f}, {-283.869f, 109.789f}, {-323.281f, 78.992f},
    {-361.299f, 46.488f}, {-398.383f, 12.918f}, {-394.731f, -26.491f},
    {-348.237f, -44.663f}, {-341.694f, -90.265f}, {-386.074f, -96.504f},
    {-425.461f, -65.726f}, {-461.804f, -31.423f}, {-490.944f, 9.121f},
    {-500.000f, 57.212f}, {-495.054f, 106.984f}, {-488.398f, 156.560f},
    {-481.412f, 206.092f}, {-473.509f, 255.481f}, {-463.985f, 304.588f},
    {-439.124f, 346.000f}, {-391.999f, 361.470f}, {-342.084f, 364.083f},
    {-292.115f, 361.982f}, {-242.569f, 355.250f}, {-193.862f, 343.924f},
    {-145.002f, 333.435f}, {-95.688f, 338.896f}, {-48.772f, 335.832f},
    {-7.091f, 308.264f}, {40.907f, 301.647f}, {88.430f, 314.353f},
    {126.910f, 286.184f}, {141.594f, 238.423f}, {171.764f, 198.932f},
    {209.070f, 165.609f}, {246.434f, 132.351f}, {283.766f, 99.055f},
    {320.987f, 65.637f}, {358.022f, 32.012f}, {394.779f, -1.915f},
    {430.785f, -36.636f}, {465.549f, -72.600f}, {497.683f, -110.809f},
    {500.000f, -158.685f}, {463.483f, -190.580f}, {414.292f, -199.308f},
    {369.072f, -220.217f}, {324.573f, -243.063f}, {279.695f, -265.157f},
    {265.997f, -301.100f}, {257.515f, -346.531f}, {212.174f, -364.083f},
    {167.229f, -344.996f}, {134.503f, -307.202f}, {102.177f, -269.029f},
};

constexpr TrackElevationPoint kSilverstoneElevation[] = {
    {0.0f, 4.2f},    {620.0f, 6.0f},   {1180.0f, 1.8f}, {1810.0f, 0.0f},
    {2510.0f, 3.1f}, {3250.0f, 8.4f},  {3990.0f, 11.2f}, {4750.0f, 7.1f},
    {5360.0f, 3.5f}, {5891.0f, 4.2f},
};

constexpr TrackWidthPoint kSilverstoneWidth[] = {
    {0.0f, 15.0f},    {620.0f, 13.0f},  {1280.0f, 12.0f}, {1870.0f, 15.0f},
    {2640.0f, 12.0f}, {3500.0f, 14.0f}, {4370.0f, 13.0f}, {5050.0f, 16.0f},
    {5540.0f, 14.0f}, {5891.0f, 15.0f},
};

// Positive angles raise the driver's left edge. Silverstone is an airfield
// circuit, so this intentionally stays subtle: the profile follows the real
// corner sequence without turning its fast sweepers into artificial bowls.
constexpr TrackBankPoint kSilverstoneBank[] = {
    {0.0f, 0.0f},     {150.0f, 0.0f},   {247.0f, 1.8f},   {390.0f, 0.0f},
    {620.0f, 0.0f},   {736.0f, 2.0f},   {820.0f, 0.0f},   {901.0f, -2.0f},
    {1040.0f, 0.0f},  {1710.0f, 0.0f},  {1856.0f, -1.7f}, {1945.0f, 0.0f},
    {2044.0f, 2.1f},  {2200.0f, 0.0f},  {2780.0f, 0.0f},  {2946.0f, 2.4f},
    {3130.0f, 0.0f},  {3350.0f, 0.0f},  {3434.0f, -2.0f}, {3515.0f, 0.0f},
    {3599.0f, 2.1f},  {3680.0f, 0.0f},  {3765.0f, -1.8f}, {3900.0f, 0.0f},
    {4750.0f, 0.0f},  {4907.0f, 2.2f},  {5070.0f, 0.0f},  {5319.0f, -2.0f},
    {5420.0f, 0.0f},  {5567.0f, 2.2f},  {5760.0f, 0.0f},  {5891.0f, 0.0f},
};

constexpr TrackRunoffZone kSilverstoneRunoff[] = {
    {175.0f, 365.0f, 1, TrackRunoffSurface::Asphalt, 20.0f},
    {625.0f, 825.0f, 1, TrackRunoffSurface::Asphalt, 24.0f},
    {815.0f, 1020.0f, -1, TrackRunoffSurface::Asphalt, 20.0f},
    {1740.0f, 1950.0f, -1, TrackRunoffSurface::Gravel, 18.0f},
    {1950.0f, 2210.0f, 1, TrackRunoffSurface::Gravel, 16.0f},
    {2830.0f, 3090.0f, 1, TrackRunoffSurface::Gravel, 24.0f},
    {3340.0f, 3495.0f, -1, TrackRunoffSurface::Grass, 15.0f},
    {3480.0f, 3650.0f, 1, TrackRunoffSurface::Gravel, 17.0f},
    {3625.0f, 3810.0f, -1, TrackRunoffSurface::Grass, 14.0f},
    {4800.0f, 5050.0f, 1, TrackRunoffSurface::Gravel, 25.0f},
    {5240.0f, 5410.0f, -1, TrackRunoffSurface::Gravel, 18.0f},
    {5450.0f, 5780.0f, 1, TrackRunoffSurface::Gravel, 20.0f},
};

constexpr TrackControlPoint kMonzaCenterline[] = {
    {54.576f, -241.388f}, {18.926f, -241.927f}, {-16.724f, -242.397f},
    {-52.375f, -242.832f}, {-88.026f, -243.263f}, {-118.985f, -235.531f},
    {-144.059f, -231.461f}, {-178.048f, -242.149f}, {-213.345f, -246.611f},
    {-248.997f, -246.551f}, {-284.560f, -244.278f}, {-318.060f, -232.819f},
    {-347.495f, -212.782f}, {-370.869f, -186.048f}, {-386.469f, -154.074f},
    {-396.503f, -119.878f}, {-404.124f, -85.051f}, {-410.460f, -49.967f},
    {-416.598f, -14.845f}, {-422.690f, 20.284f}, {-432.101f, 53.588f},
    {-454.158f, 77.481f}, {-468.287f, 110.210f}, {-484.024f, 142.200f},
    {-498.968f, 174.536f}, {-500.000f, 209.204f}, {-471.114f, 228.073f},
    {-436.142f, 235.008f}, {-401.141f, 241.796f}, {-366.042f, 246.611f},
    {-342.737f, 220.196f}, {-322.395f, 190.914f}, {-301.970f, 161.692f},
    {-281.071f, 132.807f}, {-259.043f, 104.780f}, {-234.758f, 78.686f},
    {-208.996f, 54.043f}, {-182.567f, 30.113f}, {-156.178f, 6.138f},
    {-130.026f, -18.094f}, {-103.846f, -42.298f}, {-77.501f, -66.321f},
    {-50.839f, -89.991f}, {-17.679f, -94.023f}, {16.457f, -100.130f},
    {46.332f, -117.308f}, {81.953f, -118.213f}, {117.606f, -118.038f},
    {153.260f, -117.903f}, {188.913f, -117.811f}, {224.567f, -117.762f},
    {260.220f, -117.756f}, {295.874f, -117.794f}, {331.527f, -117.874f},
    {367.181f, -117.996f}, {402.834f, -118.156f}, {438.487f, -118.353f},
    {474.072f, -119.614f}, {500.000f, -141.327f}, {499.333f, -176.274f},
    {476.384f, -203.134f}, {445.430f, -220.384f}, {410.663f, -228.024f},
    {375.217f, -231.853f}, {339.711f, -235.054f}, {304.103f, -236.825f},
    {268.460f, -237.673f}, {232.809f, -238.043f}, {197.157f, -238.356f},
    {161.510f, -239.043f}, {125.869f, -239.978f}, {90.224f, -240.750f},
};

constexpr TrackElevationPoint kMonzaElevation[] = {
    {0.0f, 10.8f},   {930.0f, 10.1f},  {1540.0f, 8.4f}, {2350.0f, 12.8f},
    {3100.0f, 7.0f}, {3570.0f, 0.0f},  {4340.0f, 2.2f}, {5050.0f, 6.8f},
    {5793.0f, 10.8f},
};

constexpr TrackWidthPoint kMonzaWidth[] = {
    {0.0f, 12.0f},    {1020.0f, 11.0f}, {1610.0f, 12.0f}, {2460.0f, 10.0f},
    {3290.0f, 10.5f}, {4230.0f, 11.0f}, {4950.0f, 10.0f}, {5430.0f, 12.0f},
    {5793.0f, 12.0f},
};

// The current road course uses restrained crossfall; this does not reproduce
// the disused 1955 high-speed oval's extreme banking. Signs follow the real
// right-left chicanes and the long clockwise Biassono/Alboreto curves.
constexpr TrackBankPoint kMonzaBank[] = {
    {0.0f, 0.0f},     {220.0f, 0.0f},   {324.0f, 2.2f},   {405.0f, 0.0f},
    {481.0f, -2.1f},  {610.0f, 0.0f},   {760.0f, 0.0f},   {886.0f, 2.5f},
    {1120.0f, 0.0f},  {1500.0f, 0.0f},  {1610.0f, -2.2f}, {1650.0f, 0.0f},
    {1692.0f, 2.1f},  {1810.0f, 0.0f},  {2010.0f, 2.3f},  {2190.0f, 0.0f},
    {2390.0f, 0.0f},  {2491.0f, 2.4f},  {2700.0f, 0.0f},  {3260.0f, 0.0f},
    {3377.0f, -2.2f}, {3460.0f, 0.0f},  {3540.0f, 2.1f},  {3580.0f, 0.0f},
    {3621.0f, -2.2f}, {3770.0f, 0.0f},  {4430.0f, 0.0f},  {4669.0f, 2.8f},
    {5050.0f, 1.4f},  {5260.0f, 0.0f},  {5793.0f, 0.0f},
};

constexpr TrackRunoffZone kMonzaRunoff[] = {
    {220.0f, 530.0f, 0, TrackRunoffSurface::Asphalt, 24.0f},
    {720.0f, 1060.0f, 1, TrackRunoffSurface::Grass, 18.0f},
    {1460.0f, 1750.0f, 0, TrackRunoffSurface::Gravel, 22.0f},
    {1900.0f, 2160.0f, 1, TrackRunoffSurface::Gravel, 20.0f},
    {2370.0f, 2660.0f, 1, TrackRunoffSurface::Gravel, 20.0f},
    {3210.0f, 3740.0f, 0, TrackRunoffSurface::Gravel, 22.0f},
    {4480.0f, 5080.0f, 1, TrackRunoffSurface::Gravel, 24.0f},
};

constexpr TrackControlPoint kInterlagosCenterline[] = {
    {-286.034f, -112.307f}, {-272.632f, -168.521f}, {-259.229f, -224.736f},
    {-245.827f, -280.950f}, {-232.425f, -337.165f}, {-219.022f, -393.379f},
    {-205.122f, -449.465f}, {-178.180f, -499.977f}, {-126.283f, -500.000f},
    {-82.880f, -463.055f}, {-29.926f, -482.708f}, {24.867f, -498.440f},
    {81.675f, -489.384f}, {130.366f, -459.245f}, {161.524f, -410.881f},
    {180.960f, -356.552f}, {196.030f, -300.762f}, {211.100f, -244.971f},
    {226.170f, -189.181f}, {241.240f, -133.390f}, {256.309f, -77.599f},
    {271.379f, -21.809f}, {286.449f, 33.982f}, {301.519f, 89.772f},
    {316.589f, 145.563f}, {320.372f, 202.073f}, {277.144f, 235.262f},
    {220.387f, 246.135f}, {163.260f, 245.619f}, {113.581f, 217.190f},
    {78.003f, 171.762f}, {43.658f, 125.285f}, {9.350f, 78.780f},
    {-24.911f, 32.241f}, {-59.108f, -14.345f}, {-95.323f, -59.228f},
    {-148.787f, -77.227f}, {-204.670f, -64.982f}, {-241.733f, -22.350f},
    {-256.113f, 33.542f}, {-262.031f, 90.863f}, {-228.617f, 127.688f},
    {-179.893f, 97.646f}, {-129.734f, 116.955f}, {-137.515f, 170.413f},
    {-178.000f, 211.642f}, {-207.562f, 260.932f}, {-219.413f, 317.392f},
    {-188.627f, 350.085f}, {-149.442f, 307.965f}, {-110.758f, 265.131f},
    {-57.546f, 245.698f}, {-2.326f, 260.095f}, {37.755f, 300.799f},
    {68.313f, 349.849f}, {98.871f, 398.899f}, {118.946f, 450.851f},
    {71.388f, 481.000f}, {16.850f, 500.000f}, {-40.526f, 497.760f},
    {-96.854f, 485.106f}, {-150.292f, 463.153f}, {-200.259f, 434.309f},
    {-239.761f, 392.553f}, {-262.577f, 339.774f}, {-276.421f, 283.667f},
    {-290.092f, 227.517f}, {-303.425f, 171.287f}, {-315.534f, 114.785f},
    {-320.372f, 57.305f}, {-312.839f, 0.122f}, {-299.436f, -56.092f},
};

constexpr TrackElevationPoint kInterlagosElevation[] = {
    // Interlagos sits in a natural bowl.  The line is already high, the
    // circuit crests on the approach to the Senna S, then falls continuously
    // through Curva do Sol to the Turn 4/5 Descida do Lago low point.  The
    // infield undulates before the sustained climb from Juncao through the
    // banked final corner and back to the line.  The 43 m relief matches the
    // published circuit figure while the additional stations keep the road
    // grade continuous through each named section.
    {0.0f, 41.0f},    {160.0f, 43.0f},  {430.0f, 35.0f},  {820.0f, 18.0f},
    {1180.0f, 5.0f},  {1480.0f, 0.0f},  {1740.0f, 3.0f},  {1980.0f, 8.0f},
    {2230.0f, 12.0f}, {2500.0f, 10.0f}, {2720.0f, 7.0f},  {2960.0f, 11.0f},
    {3160.0f, 17.0f}, {3520.0f, 27.0f}, {3760.0f, 35.0f}, {3970.0f, 39.0f},
    {4309.0f, 41.0f},
};

constexpr TrackWidthPoint kInterlagosWidth[] = {
    {0.0f, 13.0f},    {480.0f, 15.0f},  {950.0f, 12.0f},  {1540.0f, 11.0f},
    {2190.0f, 10.0f}, {2820.0f, 10.0f}, {3400.0f, 11.0f}, {3840.0f, 14.0f},
    {4309.0f, 13.0f},
};

// Interlagos combines visibly banked historic-oval sections with rapid
// crossfall changes through the infield.  Negative values support its long
// left-hand climb and the left-hand Senna-S entry; positive values support
// the right-hand exits and hairpins.  The adverse-camber Descida do Lago
// station deliberately raises the inside (driver-left) edge of its left turn.
constexpr TrackBankPoint kInterlagosBank[] = {
    {0.0f, -3.5f},    {180.0f, -4.0f},  {360.0f, -3.0f}, {540.0f, 2.0f},
    {720.0f, -2.0f},  {1120.0f, 0.0f},  {1450.0f, 1.2f}, {1700.0f, 2.0f},
    {2150.0f, 2.4f},  {2500.0f, -2.0f}, {2870.0f, 2.2f}, {3250.0f, -2.4f},
    {3600.0f, -4.0f}, {4050.0f, -3.5f}, {4309.0f, -3.5f},
};

constexpr TrackRunoffZone kInterlagosRunoff[] = {
    {250.0f, 700.0f, -1, TrackRunoffSurface::Asphalt, 18.0f},
    {1120.0f, 1710.0f, 1, TrackRunoffSurface::Gravel, 14.0f},
    {1710.0f, 2440.0f, 0, TrackRunoffSurface::Grass, 12.0f},
    {2440.0f, 3150.0f, 0, TrackRunoffSurface::Grass, 10.0f},
    {3150.0f, 3540.0f, -1, TrackRunoffSurface::Gravel, 13.0f},
    {3540.0f, 4309.0f, 1, TrackRunoffSurface::Grass, 12.0f},
};

// Named race-order landmarks make a mirrored outline fail independently of
// its bounding box or lap length. Fractions refer to the start/finish-aligned
// reference centerlines above.
constexpr TrackTurnExpectation kSuzukaTurns[] = {
    {"Turn 1", 0.097f, TrackTurnDirection::Right},
    {"S Curve 3", 0.139f, TrackTurnDirection::Left},
    {"S Curve 4", 0.167f, TrackTurnDirection::Right},
    {"Hairpin", 0.458f, TrackTurnDirection::Left},
    {"130R", 0.819f, TrackTurnDirection::Left},
    {"Final chicane entry", 0.875f, TrackTurnDirection::Right},
};

constexpr TrackTurnExpectation kSilverstoneTurns[] = {
    {"Abbey", 0.042f, TrackTurnDirection::Right},
    {"Village", 0.125f, TrackTurnDirection::Right},
    {"The Loop", 0.153f, TrackTurnDirection::Left},
    {"Luffield", 0.347f, TrackTurnDirection::Right},
    {"Copse", 0.500f, TrackTurnDirection::Right},
    {"Maggotts", 0.583f, TrackTurnDirection::Left},
    {"Becketts", 0.611f, TrackTurnDirection::Right},
    {"Stowe", 0.833f, TrackTurnDirection::Right},
    {"Vale", 0.903f, TrackTurnDirection::Left},
};

constexpr TrackTurnExpectation kMonzaTurns[] = {
    {"Rettifilo entry", 0.056f, TrackTurnDirection::Right},
    {"Rettifilo exit", 0.083f, TrackTurnDirection::Left},
    {"Curva Grande", 0.153f, TrackTurnDirection::Right},
    {"Roggia entry", 0.278f, TrackTurnDirection::Left},
    {"Roggia exit", 0.292f, TrackTurnDirection::Right},
    {"Lesmo 1", 0.347f, TrackTurnDirection::Right},
    {"Ascari entry", 0.583f, TrackTurnDirection::Left},
    {"Ascari middle", 0.611f, TrackTurnDirection::Right},
    {"Ascari exit", 0.625f, TrackTurnDirection::Left},
    {"Parabolica", 0.806f, TrackTurnDirection::Right},
};

constexpr TrackTurnExpectation kInterlagosTurns[] = {
    {"Senna S entry", 0.097f, TrackTurnDirection::Left},
    {"Senna S exit", 0.125f, TrackTurnDirection::Right},
    {"Curva do Sol", 0.167f, TrackTurnDirection::Left},
    {"Descida do Lago", 0.347f, TrackTurnDirection::Left},
    {"Ferradura", 0.500f, TrackTurnDirection::Right},
    {"Pinheirinho", 0.583f, TrackTurnDirection::Left},
    {"Bico de Pato", 0.667f, TrackTurnDirection::Right},
    {"Juncao", 0.778f, TrackTurnDirection::Left},
};

constexpr std::array<TrackCatalogEntry, 4> kCatalog = {{
    {CatalogCircuitId::Suzuka,
     "Suzuka",
     "Suzuka International Racing Course",
     "Japan",
     "A flowing figure-eight: opening esses, Degner bends, the hairpin, Spoon, 130R and a final chicane.",
     "coastal-japan",
     5807.0f,
     18,
     0.0f,
     39.5f,
     true,
     kSuzukaCenterline,
     kSuzukaElevation,
     kSuzukaWidth,
     kSuzukaBank,
     kSuzukaRunoff,
     kSuzukaCrossings},
    {CatalogCircuitId::Silverstone,
     "Silverstone",
     "Silverstone Circuit",
     "United Kingdom",
     "Fast airfield sweepers with the Arena loop, Copse, Maggotts-Becketts, Hangar Straight and Club.",
     "historic-airfield",
     5891.0f,
     18,
     0.0f,
     11.2f,
     true,
     kSilverstoneCenterline,
     kSilverstoneElevation,
     kSilverstoneWidth,
     kSilverstoneBank,
     kSilverstoneRunoff,
     {}},
    {CatalogCircuitId::Monza,
     "Monza",
     "Autodromo Nazionale Monza",
     "Italy",
     "Long parkland straights broken by Rettifilo, Roggia and Ascari before the broad final curve.",
     "royal-parkland",
     5793.0f,
     11,
     0.0f,
     12.8f,
     true,
     kMonzaCenterline,
     kMonzaElevation,
     kMonzaWidth,
     kMonzaBank,
     kMonzaRunoff,
     {}},
    {CatalogCircuitId::Interlagos,
     "Interlagos",
     "Autodromo Jose Carlos Pace",
     "Brazil",
     "A compact anti-clockwise lap descending through the Senna S, then climbing from Juncao to the line.",
     "coastal-hillside",
     4309.0f,
     15,
     0.0f,
     43.0f,
     false,
     kInterlagosCenterline,
     kInterlagosElevation,
     kInterlagosWidth,
     kInterlagosBank,
     kInterlagosRunoff,
     {}},
}};

float wrapDistance(float distance, float totalLength) noexcept {
    if (!(totalLength > 0.0f) || !std::isfinite(distance)) {
        return 0.0f;
    }
    distance = std::fmod(distance, totalLength);
    return distance < 0.0f ? distance + totalLength : distance;
}

template <typename Station, typename Value>
float sampleStations(std::span<const Station> stations, float distanceMeters, float totalLength,
                     Value value) noexcept {
    if (stations.empty()) {
        return 0.0f;
    }
    const float distance = wrapDistance(distanceMeters, totalLength);
    const auto next = std::upper_bound(stations.begin(), stations.end(), distance,
                                       [](float d, const Station& station) { return d < station.distanceMeters; });
    if (next == stations.begin()) {
        return value(stations.front());
    }
    if (next == stations.end()) {
        return value(stations.back());
    }
    const Station& a = *(next - 1);
    const Station& b = *next;
    const float span = std::max(0.001f, b.distanceMeters - a.distanceMeters);
    const float t = (distance - a.distanceMeters) / span;
    return value(a) + (value(b) - value(a)) * t;
}

}  // namespace

std::span<const TrackCatalogEntry> trackCatalog() noexcept { return kCatalog; }

const TrackCatalogEntry* findTrackCatalogEntry(CatalogCircuitId id) noexcept {
    const auto found = std::find_if(kCatalog.begin(), kCatalog.end(),
                                    [id](const TrackCatalogEntry& entry) { return entry.id == id; });
    return found == kCatalog.end() ? nullptr : &*found;
}

float sampleTrackElevationMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept {
    return sampleStations(track.elevationProfile, distanceMeters, track.targetLengthMeters,
                          [](const TrackElevationPoint& point) { return point.elevationMeters; });
}

float sampleTrackWidthMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept {
    return sampleStations(track.widthProfile, distanceMeters, track.targetLengthMeters,
                          [](const TrackWidthPoint& point) { return point.roadWidthMeters; });
}

float sampleTrackBankDegrees(const TrackCatalogEntry& track, float distanceMeters) noexcept {
    return sampleStations(track.bankProfile, distanceMeters, track.targetLengthMeters,
                          [](const TrackBankPoint& point) { return point.angleDegrees; });
}

std::span<const TrackTurnExpectation> trackTurnExpectations(CatalogCircuitId id) noexcept {
    switch (id) {
        case CatalogCircuitId::Suzuka:
            return kSuzukaTurns;
        case CatalogCircuitId::Silverstone:
            return kSilverstoneTurns;
        case CatalogCircuitId::Monza:
            return kMonzaTurns;
        case CatalogCircuitId::Interlagos:
            return kInterlagosTurns;
    }
    return {};
}

TrackShapeAuditResult auditTrackCatalogShape(const TrackCatalogEntry& track) noexcept {
    TrackShapeAuditResult result;
    if (track.centerline.size() < 4) {
        return result;
    }

    float minX = std::numeric_limits<float>::max();
    float maxX = std::numeric_limits<float>::lowest();
    float minY = std::numeric_limits<float>::max();
    float maxY = std::numeric_limits<float>::lowest();
    std::vector<float> cumulative(track.centerline.size() + 1, 0.0f);
    for (std::size_t i = 0; i < track.centerline.size(); ++i) {
        const TrackControlPoint& a = track.centerline[i];
        const TrackControlPoint& b = track.centerline[(i + 1) % track.centerline.size()];
        minX = std::min(minX, a.x);
        maxX = std::max(maxX, a.x);
        minY = std::min(minY, a.y);
        maxY = std::max(maxY, a.y);
        result.signedArea += 0.5f * (a.x * b.y - b.x * a.y);
        cumulative[i + 1] = cumulative[i] + std::hypot(b.x - a.x, b.y - a.y);
    }
    result.aspectRatio = (maxX - minX) / std::max(0.001f, maxY - minY);

    float expectedAspect = 1.0f;
    int expectedIntersections = 0;
    switch (track.id) {
        case CatalogCircuitId::Suzuka:
            expectedAspect = 2.0f;
            expectedIntersections = 1;
            break;
        case CatalogCircuitId::Silverstone:
            expectedAspect = 1.38f;
            break;
        case CatalogCircuitId::Monza:
            expectedAspect = 2.05f;
            break;
        case CatalogCircuitId::Interlagos:
            expectedAspect = 0.635f;
            break;
    }
    result.aspectMatches = std::abs(result.aspectRatio - expectedAspect) <= expectedAspect * 0.12f;
    result.directionMatches = track.clockwise ? result.signedArea < 0.0f : result.signedArea > 0.0f;

    const auto cross = [](float ax, float ay, float bx, float by) { return ax * by - ay * bx; };
    const std::size_t count = track.centerline.size();
    for (std::size_t i = 0; i < count; ++i) {
        const TrackControlPoint& a = track.centerline[i];
        const TrackControlPoint& b = track.centerline[(i + 1) % count];
        const float rx = b.x - a.x;
        const float ry = b.y - a.y;
        for (std::size_t j = i + 1; j < count; ++j) {
            const std::size_t separation = j - i;
            if (separation <= 2 || separation >= count - 2) {
                continue;
            }
            const TrackControlPoint& c = track.centerline[j];
            const TrackControlPoint& d = track.centerline[(j + 1) % count];
            const float sx = d.x - c.x;
            const float sy = d.y - c.y;
            const float denominator = cross(rx, ry, sx, sy);
            if (std::abs(denominator) < 0.00001f) {
                continue;
            }
            const float qx = c.x - a.x;
            const float qy = c.y - a.y;
            const float t = cross(qx, qy, sx, sy) / denominator;
            const float u = cross(qx, qy, rx, ry) / denominator;
            if (t > 0.0001f && t < 0.9999f && u > 0.0001f && u < 0.9999f) {
                ++result.selfIntersections;
            }
        }
    }
    result.intersectionsMatch = result.selfIntersections == expectedIntersections;

    const auto pointAtFraction = [&](float fraction) {
        fraction -= std::floor(fraction);
        const float target = cumulative.back() * fraction;
        const auto upper = std::upper_bound(cumulative.begin(), cumulative.end(), target);
        const std::size_t index = std::min<std::size_t>(count - 1,
            static_cast<std::size_t>(std::max<std::ptrdiff_t>(0, upper - cumulative.begin() - 1)));
        const float segmentLength = std::max(0.0001f, cumulative[index + 1] - cumulative[index]);
        const float t = (target - cumulative[index]) / segmentLength;
        const TrackControlPoint& a = track.centerline[index];
        const TrackControlPoint& b = track.centerline[(index + 1) % count];
        return TrackControlPoint{a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t};
    };

    constexpr float kTurnWindow = 0.018f;
    for (const TrackTurnExpectation& expected : trackTurnExpectations(track.id)) {
        const TrackControlPoint before = pointAtFraction(expected.lapFraction - kTurnWindow);
        const TrackControlPoint center = pointAtFraction(expected.lapFraction);
        const TrackControlPoint after = pointAtFraction(expected.lapFraction + kTurnWindow);
        const float firstX = center.x - before.x;
        const float firstY = center.y - before.y;
        const float secondX = after.x - center.x;
        const float secondY = after.y - center.y;
        const float signedTurn = std::atan2(cross(firstX, firstY, secondX, secondY),
                                            firstX * secondX + firstY * secondY);
        const float expectedSign = static_cast<float>(static_cast<int>(expected.direction));
        ++result.landmarkChecks;
        if (signedTurn * expectedSign < 0.08f) {
            ++result.landmarkFailures;
        }
    }
    return result;
}
