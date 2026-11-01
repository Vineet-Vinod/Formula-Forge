#include "track_catalog.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace {

#include "track_data/silverstone_survey.inc"
#include "track_data/monza_survey.inc"
#include "track_data/interlagos_survey.inc"

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

constexpr TrackRunoffZone kMonzaRunoff[] = {
    {530.0f, 730.0f, 0, TrackRunoffSurface::Asphalt, 24.0f},
    {850.0f, 1530.0f, 1, TrackRunoffSurface::Gravel, 18.0f},
    {1780.0f, 1940.0f, 0, TrackRunoffSurface::Gravel, 22.0f},
    {2180.0f, 2390.0f, 1, TrackRunoffSurface::Gravel, 29.0f},
    {2500.0f, 2680.0f, 1, TrackRunoffSurface::Gravel, 28.0f},
    {3610.0f, 3880.0f, 0, TrackRunoffSurface::Gravel, 22.0f},
    {4770.0f, 5180.0f, 1, TrackRunoffSurface::Gravel, 35.0f},
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
    {"Rettifilo entry", 0.10707f, TrackTurnDirection::Right},
    {"Rettifilo exit", 0.11367f, TrackTurnDirection::Left},
    {"Curva Grande", 0.17038f, TrackTurnDirection::Right},
    {"Roggia entry", 0.31810f, TrackTurnDirection::Left},
    {"Roggia exit", 0.32548f, TrackTurnDirection::Right},
    {"Lesmo 1", 0.38956f, TrackTurnDirection::Right},
    {"Lesmo 2", 0.44524f, TrackTurnDirection::Right},
    {"Ascari entry", 0.62985f, TrackTurnDirection::Left},
    {"Ascari middle", 0.65096f, TrackTurnDirection::Right},
    {"Ascari exit", 0.66209f, TrackTurnDirection::Left},
    {"Parabolica", 0.83959f, TrackTurnDirection::Right},
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

constexpr std::array<TrackCatalogEntry, 3> kCatalog = {{
    {TrackLayoutId::Silverstone,
     "Silverstone",
     "Silverstone Circuit",
     "United Kingdom",
     "Fast airfield sweepers with the Arena loop, Copse, Maggotts-Becketts, Hangar Straight and Club.",
     "historic-airfield",
     5891.0f,
     18,
     0.0f,
     11.336290f,
     true,
     1.0f,
     true,
     kSilverstoneSurveyCenterline,
     kSilverstoneSurveyElevation,
     kSilverstoneSurveyWidth,
     kSilverstoneSurveyBank,
     kSilverstoneRunoff,
     {}},    {TrackLayoutId::Monza,
     "Monza",
     "Autodromo Nazionale Monza",
     "Italy",
     "Long parkland straights broken by Rettifilo, Roggia and Ascari before the broad final curve.",
     "royal-parkland",
     5793.0f,
     11,
     0.0f,
     13.08f,
     true,
     1.0f,
     true,
     kMonzaCenterline,
     kMonzaElevation,
     kMonzaWidth,
     kMonzaBank,
     kMonzaRunoff,
     {}},    {TrackLayoutId::Interlagos,
     "Interlagos",
     "Autodromo Jose Carlos Pace",
     "Brazil",
     "A compact anti-clockwise lap descending through the Senna S, then climbing from Juncao to the line.",
     "coastal-hillside",
     4309.0f,
     15,
     60.0f / 4309.0f,
     43.473482f,
     false,
     1.0f,
     true,
     kInterlagosSurveyCenterline,
     kInterlagosSurveyElevation,
     kInterlagosSurveyWidth,
     kInterlagosSurveyBank,
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

const TrackCatalogEntry* findTrackCatalogEntry(TrackLayoutId id) noexcept {
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

std::span<const TrackTurnExpectation> trackTurnExpectations(TrackLayoutId id) noexcept {
    switch (id) {
        case TrackLayoutId::Silverstone:
            return kSilverstoneTurns;
        case TrackLayoutId::Monza:
            return kMonzaTurns;
        case TrackLayoutId::Interlagos:
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
        case TrackLayoutId::Silverstone:
            expectedAspect = 1.38f;
            break;
        case TrackLayoutId::Monza:
            expectedAspect = 0.581629f;
            break;
        case TrackLayoutId::Interlagos:
            expectedAspect = 0.635f;
            break;
    }
    result.aspectMatches = std::abs(result.aspectRatio - expectedAspect) <= expectedAspect * 0.12f;
    const float visibleOrientation = result.signedArea * (track.mirrorCenterlineY ? 1.0f : -1.0f);
    result.directionMatches = track.clockwise ? visibleOrientation < 0.0f : visibleOrientation > 0.0f;

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

    for (const TrackTurnExpectation& expected : trackTurnExpectations(track.id)) {
        // The surveyed chicanes reverse inside 40 m; Biassono needs a wider chord.
        const float kTurnWindow = track.id == TrackLayoutId::Monza
            ? (expected.landmark == "Curva Grande" ? 0.012f : 0.003f) : 0.018f;
        const TrackControlPoint before = pointAtFraction(expected.lapFraction - kTurnWindow);
        const TrackControlPoint center = pointAtFraction(expected.lapFraction);
        const TrackControlPoint after = pointAtFraction(expected.lapFraction + kTurnWindow);
        const float firstX = center.x - before.x;
        const float firstY = center.y - before.y;
        const float secondX = after.x - center.x;
        const float secondY = after.y - center.y;
        const float sourceTurn = std::atan2(cross(firstX, firstY, secondX, secondY),
                                            firstX * secondX + firstY * secondY);
        const float signedTurn = sourceTurn * (track.mirrorCenterlineY ? 1.0f : -1.0f);
        const float expectedSign = static_cast<float>(static_cast<int>(expected.direction));
        ++result.landmarkChecks;
        if (signedTurn * expectedSign < 0.08f) {
            ++result.landmarkFailures;
        }
    }
    return result;
}
