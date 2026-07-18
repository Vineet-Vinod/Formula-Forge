#include "track_catalog.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace {

// These controls deliberately describe the recognizable driving line rather
// than copying survey/GIS coordinates. Published venue dimensions define the
// physical scale after Track3D arc-length normalization.
constexpr TrackControlPoint kSuzukaCenterline[] = {
    {420.0f, -350.0f}, {335.0f, -356.0f}, {245.0f, -360.0f}, {155.0f, -365.0f},
    {75.0f, -370.0f},  {8.0f, -362.0f},   {-42.0f, -335.0f}, {-66.0f, -295.0f},
    {-62.0f, -255.0f}, {-35.0f, -225.0f}, {10.0f, -215.0f},  {60.0f, -220.0f},
    {108.0f, -229.0f}, {148.0f, -220.0f}, {178.0f, -194.0f}, {205.0f, -168.0f},
    {238.0f, -160.0f}, {270.0f, -178.0f}, {300.0f, -195.0f}, {332.0f, -188.0f},
    {354.0f, -160.0f}, {372.0f, -130.0f}, {402.0f, -120.0f}, {432.0f, -140.0f},
    {452.0f, -174.0f}, {460.0f, -205.0f}, {477.0f, -223.0f}, {505.0f, -218.0f},
    {525.0f, -194.0f}, {534.0f, -155.0f}, {535.0f, -100.0f}, {536.0f, -45.0f},
    {550.0f, 6.0f},    {582.0f, 48.0f},   {620.0f, 75.0f},   {652.0f, 68.0f},
    {668.0f, 42.0f},   {674.0f, 2.0f},    {674.0f, -42.0f},  {688.0f, -72.0f},
    {714.0f, -80.0f},  {735.0f, -60.0f},  {738.0f, -20.0f},  {733.0f, 30.0f},
    {747.0f, 76.0f},   {780.0f, 112.0f},  {827.0f, 136.0f},  {882.0f, 148.0f},
    {932.0f, 145.0f},  {966.0f, 126.0f},  {980.0f, 96.0f},   {974.0f, 65.0f},
    {950.0f, 42.0f},   {917.0f, 34.0f},   {884.0f, 45.0f},   {853.0f, 66.0f},
    {818.0f, 88.0f},   {775.0f, 95.0f},   {730.0f, 82.0f},   {684.0f, 60.0f},
    {638.0f, 36.0f},   {592.0f, 5.0f},    {548.0f, -32.0f},  {512.0f, -70.0f},
    {482.0f, -100.0f}, {456.0f, -116.0f}, {438.0f, -144.0f}, {438.0f, -188.0f},
    {449.0f, -232.0f}, {454.0f, -273.0f}, {447.0f, -310.0f},
};

constexpr TrackElevationPoint kSuzukaElevation[] = {
    {0.0f, 9.0f},    {650.0f, 1.0f},   {1180.0f, 18.0f}, {1650.0f, 39.5f},
    {2140.0f, 31.0f}, {2680.0f, 23.0f}, {3290.0f, 10.0f}, {3820.0f, 0.0f},
    {4360.0f, 7.0f},  {4930.0f, 20.0f}, {5410.0f, 16.0f}, {5807.0f, 9.0f},
};

constexpr TrackWidthPoint kSuzukaWidth[] = {
    {0.0f, 14.0f},    {590.0f, 16.0f},  {1080.0f, 11.0f}, {1780.0f, 10.0f},
    {2370.0f, 12.0f}, {3150.0f, 13.0f}, {4090.0f, 11.0f}, {4890.0f, 12.0f},
    {5300.0f, 15.0f}, {5807.0f, 14.0f},
};

// The Degner-side branch passes above the west-to-east back straight.
constexpr TrackGradeSeparation kSuzukaCrossings[] = {{1710.0f, 4320.0f, 8.0f}};

constexpr TrackControlPoint kSilverstoneCenterline[] = {
    {175.0f, -430.0f}, {120.0f, -380.0f}, {65.0f, -330.0f},  {42.0f, -285.0f},
    {48.0f, -245.0f},  {58.0f, -190.0f},  {56.0f, -135.0f},  {35.0f, -88.0f},
    {5.0f, -42.0f},    {-22.0f, 5.0f},    {-28.0f, 45.0f},   {-6.0f, 72.0f},
    {35.0f, 82.0f},    {78.0f, 85.0f},    {115.0f, 72.0f},   {139.0f, 46.0f},
    {137.0f, 19.0f},   {112.0f, 0.0f},    {75.0f, -5.0f},    {37.0f, -2.0f},
    {3.0f, -18.0f},    {-18.0f, -50.0f},  {-28.0f, -86.0f},  {-44.0f, -116.0f},
    {-82.0f, -128.0f}, {-122.0f, -115.0f}, {-151.0f, -82.0f}, {-158.0f, -39.0f},
    {-158.0f, 15.0f},  {-158.0f, 75.0f},  {-157.0f, 140.0f}, {-150.0f, 193.0f},
    {-124.0f, 226.0f}, {-78.0f, 241.0f},  {-22.0f, 249.0f},  {38.0f, 250.0f},
    {92.0f, 248.0f},   {131.0f, 260.0f},  {164.0f, 281.0f},  {198.0f, 286.0f},
    {228.0f, 270.0f},  {257.0f, 252.0f},  {291.0f, 253.0f},  {319.0f, 273.0f},
    {345.0f, 292.0f},  {374.0f, 290.0f},  {397.0f, 269.0f},  {410.0f, 235.0f},
    {435.0f, 206.0f},  {476.0f, 180.0f},  {523.0f, 151.0f},  {572.0f, 121.0f},
    {620.0f, 90.0f},   {659.0f, 57.0f},   {680.0f, 22.0f},   {678.0f, -17.0f},
    {653.0f, -48.0f},  {609.0f, -66.0f},  {567.0f, -84.0f},  {535.0f, -108.0f},
    {506.0f, -137.0f}, {476.0f, -164.0f}, {449.0f, -193.0f}, {428.0f, -226.0f},
    {414.0f, -265.0f}, {418.0f, -294.0f}, {440.0f, -321.0f}, {445.0f, -352.0f},
    {427.0f, -380.0f}, {393.0f, -400.0f}, {355.0f, -408.0f}, {321.0f, -402.0f},
    {296.0f, -382.0f}, {274.0f, -360.0f}, {245.0f, -359.0f}, {224.0f, -383.0f},
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

constexpr TrackControlPoint kMonzaCenterline[] = {
    {-20.0f, -500.0f}, {-16.0f, -410.0f}, {-12.0f, -315.0f}, {-8.0f, -215.0f},
    {-4.0f, -115.0f},  {0.0f, -20.0f},    {2.0f, 80.0f},     {3.0f, 180.0f},
    {4.0f, 278.0f},    {8.0f, 365.0f},    {24.0f, 417.0f},   {52.0f, 438.0f},
    {82.0f, 428.0f},   {95.0f, 397.0f},   {78.0f, 370.0f},   {57.0f, 351.0f},
    {66.0f, 327.0f},   {105.0f, 314.0f},  {152.0f, 324.0f},  {205.0f, 350.0f},
    {260.0f, 377.0f},  {316.0f, 382.0f},  {358.0f, 362.0f},  {380.0f, 323.0f},
    {382.0f, 278.0f},  {365.0f, 240.0f},  {331.0f, 219.0f},  {296.0f, 207.0f},
    {278.0f, 183.0f},  {290.0f, 159.0f},  {320.0f, 151.0f},  {345.0f, 132.0f},
    {351.0f, 101.0f},  {335.0f, 74.0f},   {306.0f, 54.0f},   {271.0f, 34.0f},
    {255.0f, 7.0f},    {266.0f, -21.0f},  {296.0f, -42.0f},  {327.0f, -62.0f},
    {332.0f, -92.0f},  {312.0f, -118.0f}, {276.0f, -139.0f}, {231.0f, -163.0f},
    {180.0f, -189.0f}, {124.0f, -216.0f}, {69.0f, -243.0f},  {23.0f, -265.0f},
    {-12.0f, -286.0f}, {-29.0f, -313.0f}, {-17.0f, -338.0f}, {11.0f, -355.0f},
    {21.0f, -378.0f},  {3.0f, -397.0f},   {-34.0f, -403.0f}, {-85.0f, -412.0f},
    {-143.0f, -429.0f}, {-203.0f, -449.0f}, {-264.0f, -462.0f}, {-317.0f, -456.0f},
    {-357.0f, -432.0f}, {-381.0f, -394.0f}, {-388.0f, -350.0f}, {-377.0f, -311.0f},
    {-348.0f, -282.0f}, {-307.0f, -272.0f}, {-260.0f, -283.0f}, {-211.0f, -306.0f},
    {-164.0f, -340.0f}, {-120.0f, -380.0f}, {-81.0f, -425.0f}, {-49.0f, -468.0f},
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

constexpr TrackControlPoint kInterlagosCenterline[] = {
    {15.0f, 65.0f},    {-25.0f, 15.0f},   {-69.0f, -40.0f},  {-108.0f, -94.0f},
    {-132.0f, -135.0f}, {-136.0f, -169.0f}, {-119.0f, -185.0f}, {-91.0f, -183.0f},
    {-68.0f, -194.0f}, {-63.0f, -225.0f}, {-49.0f, -260.0f}, {-23.0f, -289.0f},
    {10.0f, -310.0f},  {47.0f, -317.0f},  {84.0f, -307.0f},  {127.0f, -287.0f},
    {172.0f, -263.0f}, {219.0f, -238.0f}, {266.0f, -213.0f}, {311.0f, -188.0f},
    {344.0f, -164.0f}, {354.0f, -136.0f}, {345.0f, -111.0f}, {324.0f, -92.0f},
    {299.0f, -77.0f},  {294.0f, -55.0f},  {307.0f, -35.0f},  {326.0f, -18.0f},
    {329.0f, 5.0f},    {309.0f, 21.0f},   {270.0f, 26.0f},   {224.0f, 24.0f},
    {178.0f, 20.0f},   {135.0f, 18.0f},   {105.0f, 29.0f},   {92.0f, 51.0f},
    {94.0f, 75.0f},    {111.0f, 92.0f},   {134.0f, 96.0f},   {151.0f, 82.0f},
    {153.0f, 60.0f},   {145.0f, 38.0f},   {152.0f, 19.0f},   {174.0f, 12.0f},
    {194.0f, 22.0f},   {204.0f, 45.0f},   {202.0f, 72.0f},   {207.0f, 96.0f},
    {225.0f, 113.0f},  {247.0f, 112.0f},  {266.0f, 96.0f},   {273.0f, 70.0f},
    {272.0f, 44.0f},   {280.0f, 27.0f},   {302.0f, 26.0f},   {325.0f, 40.0f},
    {342.0f, 65.0f},   {344.0f, 91.0f},   {330.0f, 112.0f},  {301.0f, 125.0f},
    {267.0f, 130.0f},  {230.0f, 130.0f},  {195.0f, 123.0f},  {160.0f, 110.0f},
    {125.0f, 94.0f},   {91.0f, 78.0f},    {58.0f, 62.0f},    {30.0f, 54.0f},
};

constexpr TrackElevationPoint kInterlagosElevation[] = {
    {0.0f, 38.0f},   {430.0f, 34.0f},  {820.0f, 19.0f},  {1230.0f, 0.0f},
    {1740.0f, 4.0f}, {2230.0f, 12.0f}, {2720.0f, 7.0f},  {3160.0f, 18.0f},
    {3520.0f, 27.0f}, {3890.0f, 43.0f}, {4309.0f, 38.0f},
};

constexpr TrackWidthPoint kInterlagosWidth[] = {
    {0.0f, 13.0f},    {480.0f, 15.0f},  {950.0f, 12.0f},  {1540.0f, 11.0f},
    {2190.0f, 10.0f}, {2820.0f, 9.5f},  {3400.0f, 11.0f}, {3840.0f, 14.0f},
    {4309.0f, 13.0f},
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
     kSuzukaCrossings},
    {CatalogCircuitId::Silverstone,
     "Silverstone",
     "Silverstone Circuit",
     "United Kingdom",
     "Fast airfield sweepers with the Arena loop, Copse, Maggotts-Becketts, Hangar Straight and Club.",
     "coastal-airfield",
     5891.0f,
     18,
     0.0f,
     11.2f,
     true,
     kSilverstoneCenterline,
     kSilverstoneElevation,
     kSilverstoneWidth,
     {}},
    {CatalogCircuitId::Monza,
     "Monza",
     "Autodromo Nazionale Monza",
     "Italy",
     "Long parkland straights broken by Rettifilo, Roggia and Ascari before the broad final curve.",
     "coastal-parkland",
     5793.0f,
     11,
     0.0f,
     12.8f,
     true,
     kMonzaCenterline,
     kMonzaElevation,
     kMonzaWidth,
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
